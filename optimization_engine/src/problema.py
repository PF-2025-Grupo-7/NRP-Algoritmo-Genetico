import numpy as np
from .penalizaciones.duras import PenalizacionesDurasMixin
from .penalizaciones.blandas import PenalizacionesBlandasMixin
from .repair import reparar_cromosoma

class ProblemaGAPropio(PenalizacionesDurasMixin, PenalizacionesBlandasMixin):
    """Representa la instancia del problema de planificación de guardias (NRP).

    Esta clase centraliza la lógica de evaluación del Algoritmo Genético, 
    heredando mixins de penalizaciones duras (restricciones obligatorias) 
    y blandas (objetivos de optimización).

    Attributes:
        PENALIZACION_DURA (int): Valor constante para penalizar violaciones 
            inaceptables de restricciones del hospital.
        num_profesionales (int): Cantidad total de personal médico.
        num_dias (int): Horizonte de planificación (ej: 30 días).
        max_turno_val (int): Valor entero máximo para un turno (ej: 3 para Noche).
        info_profesionales (list): Metadatos de cada profesional (skills, t_min, t_max).
        matriz_preferencias (np.ndarray): Matriz PxD con preferencias de descanso/turno.
        matriz_disponibilidad (np.ndarray): Matriz booleana PxD de licencias/ausencias.
        requerimientos_cobertura (dict): Demanda de personal por día, turno y skill.
        pesos_fitness (dict): Coeficientes de ponderación para penalizaciones blandas.
        secuencias_prohibidas (set): Tuplas de transiciones de turnos no permitidas.
        turnos_a_cubrir (list): Lista de identificadores de turnos activos.
        skills_a_cubrir (list): Tipos de habilidades requeridas (senior, junior).
        duracion_turnos (dict): Mapeo de ID de turno a carga horaria (en horas).
        tolerancia_equidad_general (int): Margen de desvío permitido en horas totales.
        tolerancia_equidad_dificil (int): Margen de desvío en turnos críticos.
        dias_no_habiles (set): Índices de días de fin de semana o feriados.
        turnos_noche (set): Identificadores de turnos nocturnos.
    """

    PENALIZACION_DURA = 1_000_000

    def __init__(self,
                 num_profesionales,
                 num_dias,
                 max_turno_val,
                 info_profesionales,
                 matriz_preferencias,
                 matriz_disponibilidad,
                 requerimientos_cobertura,
                 pesos_fitness,
                 secuencias_prohibidas,
                 turnos_a_cubrir,
                 skills_a_cubrir,
                 duracion_turnos,
                 tolerancia_equidad_general,
                 tolerancia_equidad_dificil,
                 dias_no_habiles,
                 turnos_noche,
                 ):
        """Inicializa la instancia del problema con todos los parámetros de negocio."""
        self.num_profesionales = num_profesionales
        self.num_dias = num_dias
        self.max_turno_val = max_turno_val
        self.info_profesionales = info_profesionales
        self.matriz_preferencias = matriz_preferencias
        self.matriz_disponibilidad = matriz_disponibilidad
        self.requerimientos_cobertura = requerimientos_cobertura
        self.pesos_fitness = pesos_fitness
        self.secuencias_prohibidas = secuencias_prohibidas
        self.turnos_a_cubrir = turnos_a_cubrir
        self.skills_a_cubrir = skills_a_cubrir
        self.duracion_turnos = duracion_turnos
        self.tolerancia_equidad_general = tolerancia_equidad_general
        self.tolerancia_equidad_dificil = tolerancia_equidad_dificil
        self.dias_no_habiles = dias_no_habiles
        self.turnos_noche = turnos_noche

        # --- CORRECCIÓN CRÍTICA: NORMALIZACIÓN DE CLAVES (STRING -> INT) ---
        # El JSON manda claves de turno como strings ("6"), pero el algoritmo usa enteros (6).
        # Esto convierte todo a entero para que el diccionario se lea bien.
        
        self.requerimientos_cobertura = []
        for d in range(num_dias):
            dia_data_sucio = requerimientos_cobertura[d] # El dict que viene de afuera
            dia_data_limpio = {}
            
            # Si es una lista (raro pero posible), asumimos indices directos
            if isinstance(dia_data_sucio, list):
                 self.requerimientos_cobertura.append(dia_data_sucio)
                 continue

            # Si es diccionario, convertimos las claves
            for t_key, skills_dict in dia_data_sucio.items():
                try:
                    # Forzamos que la clave del turno sea un ENTERO
                    t_id_int = int(t_key)
                    
                    # Normalizamos también los skills a minúscula por si acaso (Junior vs junior)
                    skills_limpio = {k.lower(): v for k, v in skills_dict.items()}
                    
                    dia_data_limpio[t_id_int] = skills_limpio
                except ValueError:
                    continue # Si la clave no es un número, la ignoramos
            
            self.requerimientos_cobertura.append(dia_data_limpio)
        
        # Validación de Seguridad para que duermas tranquilo
        self._validar_estructura_datos()

    def _validar_estructura_datos(self):
        """Imprime un debug rápido para confirmar que el AG ve la demanda."""
        try:
            # Chequeamos el primer día, primer turno a cubrir
            primer_turno = self.turnos_a_cubrir[0]
            req_test = self.requerimientos_cobertura[0].get(primer_turno, {})
            print(f"DEBUG AG DATOS: Día 0, Turno {primer_turno} (int) -> Demanda: {req_test}")
            
            if not req_test:
                print("⚠️ ALERTA: El AG sigue viendo demanda VACÍA. Revisar IDs de turnos.")
            else:
                print("✅ ÉXITO: El AG está leyendo la demanda correctamente.")
        except Exception as e:
            print(f"Error validando datos: {e}")

    def fitness(self, solution_vector):
        """Calcula el valor de aptitud (fitness) de un individuo.

        El fitness es la suma de todas las penalizaciones. Un valor más bajo 
        indica una mejor solución. El proceso incluye la reparación del 
        cromosoma antes de la evaluación.

        Args:
            solution_vector (np.ndarray): Vector plano que representa la matriz de guardias.

        Returns:
            float: Valor total de penalización acumulado.
        """
        matriz = solution_vector.reshape(self.num_profesionales, self.num_dias)
        matriz_reparada = self._reparar_cromosoma(matriz)
        
        penalizacion = 0.0
        # Penalizaciones Duras (Obligatorias)
        penalizacion += self._calcular_pen_disponibilidad(matriz_reparada)
        penalizacion += self._calcular_pen_descansos(matriz_reparada)
        penalizacion += self._calcular_pen_limites_turnos(matriz_reparada)
        penalizacion += self._calcular_pen_cobertura(matriz_reparada)
        
        # Penalizaciones Blandas (Deseables, ponderadas por pesos_fitness)
        pen_eq = self._calcular_pen_equidad_general(matriz_reparada)
        pen_dif = self._calcular_pen_equidad_dificiles(matriz_reparada)
        pen_pdl = self._calcular_pen_pdl(matriz_reparada)
        pen_pte = self._calcular_pen_pte(matriz_reparada)
        
        total = (penalizacion + 
                 (self.pesos_fitness['eq'] * pen_eq) + 
                 (self.pesos_fitness['dif'] * pen_dif) + 
                 (self.pesos_fitness['pdl'] * pen_pdl) + 
                 (self.pesos_fitness['pte'] * pen_pte))
        return float(total)

    def _reparar_cromosoma(self, matriz):
        """Aplica el operador de reparación para corregir inconsistencias inmediatas.

        Args:
            matriz (np.ndarray): Matriz de guardias PxD antes de reparar.

        Returns:
            np.ndarray: Matriz corregida según las reglas de reparación definidas.
        """
        return reparar_cromosoma(matriz, self)
    
    def evaluar_detallado(self, solution_vector):
        """Genera un reporte exhaustivo de calidad sobre una solución específica.

        Este método se utiliza para la auditoría de soluciones, devolviendo un 
        desglose de quiénes tienen sobrecarga y qué reglas se incumplieron.

        Args:
            solution_vector (np.ndarray): Vector plano de la solución a evaluar.

        Returns:
            dict: Diccionario estructurado con métricas de éxito, violaciones 
                de reglas y estadísticas de equidad horaria.
        """
        matriz = solution_vector.reshape(self.num_profesionales, self.num_dias)
        matriz_reparada = self._reparar_cromosoma(matriz)
        
        pen_cob, inc_cob = self._calcular_pen_cobertura(matriz_reparada, detallar=True)
        pen_pdl, inc_pdl = self._calcular_pen_pdl(matriz_reparada, detallar=True)
        pen_pte, inc_pte = self._calcular_pen_pte(matriz_reparada, detallar=True)
        
        # Análisis de Equidad (Explicabilidad)
        horas_gen = self._obtener_horas_por_profesional(matriz_reparada, tipo="general")
        _, scores, h_avg, h_min, h_max = self._calcular_score_equidad(
            horas_gen, self.tolerancia_equidad_general, detallar=True
        )
        
        outliers = []
        for p, s in enumerate(scores):
            if s < 1.0: # Identifica desbalances frente al promedio objetivo
                outliers.append({
                    "profesional_id": p,
                    "horas": float(horas_gen[p]),
                    "estado": "sobrecarga" if horas_gen[p] > h_avg else "subcarga",
                    "puntos_fuera_del_ideal": round(abs(horas_gen[p] - h_avg), 2)
                })

        return {
            "status": "success",
            "metricas": {
                "fitness_total": self.fitness(solution_vector),
                "cobertura_cumplida": pen_cob == 0
            },
            "violaciones_duras": { "deficit_cobertura": inc_cob },
            "violaciones_blandas": {
                "preferencia_libre_incumplida": inc_pdl,
                "preferencia_turno_incumplida": inc_pte,
                "desbalance_equidad": outliers
            },
            "datos_equidad": {
                "promedio_objetivo": float(h_avg),
                "rango_ideal": [float(h_min), float(h_max)],
                "horas_por_profesional": horas_gen.tolist()
            }
        }

    def _obtener_horas_por_profesional(self, matriz, tipo="general"):
        """Calcula la carga horaria acumulada para cada profesional.

        Args:
            matriz (np.ndarray): Matriz de planificación actual.
            tipo (str): "general" para total de horas, "dificil" para 
                horas en días no hábiles o turnos nocturnos.

        Returns:
            np.ndarray: Vector con las horas totales trabajadas por profesional.
        """
        horas = np.zeros(self.num_profesionales)
        for p in range(self.num_profesionales):
            for d in range(self.num_dias):
                turno = int(matriz[p, d])
                if turno > 0:
                    duracion = self.duracion_turnos.get(turno, 0)
                    if tipo == "dificil":
                        es_finde_o_feriado = (d in self.dias_no_habiles)
                        es_turno_noche = (turno in self.turnos_noche)
                        if es_finde_o_feriado or es_turno_noche:
                            horas[p] += duracion
                    else: 
                        horas[p] += duracion
        return horas