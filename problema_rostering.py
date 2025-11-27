# proyecto_rostering/problema_rostering.py
import numpy as np
import random
from mealpy import Problem
from mealpy.utils.space import IntegerVar
from penalizaciones.duras import PenalizacionesDurasMixin
from penalizaciones.blandas import PenalizacionesBlandasMixin

class ProblemaRostering(Problem, PenalizacionesDurasMixin, PenalizacionesBlandasMixin):
    
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
                 # --- NUEVOS PARÁMETROS (para Blandas) ---
                 duracion_turnos,         # Ej: {1: 8, 2: 8, 3: 8}
                 tolerancia_equidad_general, # Ej: 8 (horas)
                 tolerancia_equidad_dificil, # Ej: 4 (horas)
                 dias_no_habiles,         # Ej: {5, 6, 13, 14, ...} (índices de días)
                 turnos_noche,            # Ej: {3} (índices de turnos)
                 # --- FIN NUEVOS ---
                 **kwargs):
        
        self.num_profesionales = num_profesionales
        self.num_dias = num_dias
        self.max_turno_val = max_turno_val
        
        # Datos Duros
        self.info_profesionales = info_profesionales
        self.matriz_preferencias = matriz_preferencias
        self.matriz_disponibilidad = matriz_disponibilidad
        self.requerimientos_cobertura = requerimientos_cobertura
        self.secuencias_prohibidas = secuencias_prohibidas
        self.turnos_a_cubrir = turnos_a_cubrir
        self.skills_a_cubrir = skills_a_cubrir
        
        # Datos Blandos
        self.pesos_fitness = pesos_fitness
        self.duracion_turnos = duracion_turnos
        self.tolerancia_equidad_general = tolerancia_equidad_general
        self.tolerancia_equidad_dificil = tolerancia_equidad_dificil
        self.dias_no_habiles = dias_no_habiles
        self.turnos_noche = turnos_noche
        
        # --- Configuración para mealpy ---
        # Creamos una única IntegerVar que contiene todos los genes (n_genes)
        n_genes = self.num_profesionales * self.num_dias
        lb = [0] * n_genes
        ub = [self.max_turno_val] * n_genes
        minmax = "min"

        # mealpy espera instancias de BaseVar (IntegerVar, FloatVar, ...)
        bounds_var = IntegerVar(lb=lb, ub=ub, name="turnos_integer")

        super().__init__(bounds=bounds_var, minmax=minmax, **kwargs)


    
    def obj_func(self, solution):
        # --- 1. Decodificar el Cromosoma ---
        matriz_asignacion = solution.reshape(self.num_profesionales, self.num_dias)

        # --- 2. Reparación en cascada de restricciones duras ---
        matriz_reparada = self._reparar_cromosoma(matriz_asignacion)

        # --- 3. Cálculo de Penalizaciones DURAS (solo COBERTURA permanece) ---
        penalizacion_duras = 0.0
        penalizacion_duras += self._calcular_pen_cobertura(matriz_reparada)

        # --- 4. Cálculo de Penalizaciones BLANDAS con la matriz reparada ---
        pen_eq = self._calcular_pen_equidad_general(matriz_reparada)
        pen_dif = self._calcular_pen_equidad_dificiles(matriz_reparada)
        pen_pdl = self._calcular_pen_pdl(matriz_reparada)
        pen_pte = self._calcular_pen_pte(matriz_reparada)

        # --- 5. Función de Fitness Total ---
        penalizacion_total = (penalizacion_duras) + \
                             (self.pesos_fitness['eq'] * pen_eq) + \
                             (self.pesos_fitness['dif'] * pen_dif) + \
                             (self.pesos_fitness['pdl'] * pen_pdl) + \
                             (self.pesos_fitness['pte'] * pen_pte)

        return penalizacion_total

    def _reparar_cromosoma(self, matriz):
        """
        Aplica una reparación en cascada sobre la matriz de asignación:
        1) Disponibilidad: fuerza a 0 donde no está disponible.
        2) Secuencias prohibidas: si (d, d+1) es prohibida, fuerza d+1 a 0.
        3) Límites T_min / T_max: recorta al azar si excede, y intenta
           asignar turnos en días libres hasta alcanzar T_min respetando
           disponibilidad y secuencias prohibidas.

        Devuelve una copia reparada de la matriz original.
        """
        matriz_reparada = matriz.copy()

        # Paso 1: Disponibilidad
        mask_indisponible = (self.matriz_disponibilidad == False) & (matriz_reparada != 0)
        matriz_reparada[mask_indisponible] = 0

        # Paso 2: Secuencias prohibidas (forzamos d+1 = 0 si la pareja está prohibida)
        for p in range(self.num_profesionales):
            for d in range(self.num_dias - 1):
                sec = (int(matriz_reparada[p, d]), int(matriz_reparada[p, d+1]))
                if sec in self.secuencias_prohibidas:
                    matriz_reparada[p, d+1] = 0

        # Paso 3: Límites T_min / T_max
        for p in range(self.num_profesionales):
            t_min = self.info_profesionales[p]['t_min']
            t_max = self.info_profesionales[p]['t_max']

            # Recontar después de reparaciones previas
            dias_trabajados = list(np.where(matriz_reparada[p, :] != 0)[0])
            count = len(dias_trabajados)

            # Si excede t_max: eliminar aleatoriamente días trabajados
            if count > t_max:
                dias = dias_trabajados[:]
                random.shuffle(dias)
                eliminar = count - t_max
                for i in range(eliminar):
                    d_elim = dias[i]
                    matriz_reparada[p, d_elim] = 0

            # Si está por debajo de t_min: intentar asignar turnos en días libres
            elif count < t_min:
                dias_libres = list(np.where(matriz_reparada[p, :] == 0)[0])
                random.shuffle(dias_libres)
                # intentamos asignar hasta completar t_min
                for d_cand in dias_libres:
                    if count >= t_min:
                        break

                    # Debe estar disponible ese día
                    if not bool(self.matriz_disponibilidad[p, d_cand]):
                        continue

                    # Intentar turnos posibles en orden aleatorio
                    posibles_turnos = list(self.turnos_a_cubrir)
                    random.shuffle(posibles_turnos)
                    asignado = False
                    for turno in posibles_turnos:
                        # Verificar que asignar 'turno' no cree secuencia prohibida
                        prev_turno = int(matriz_reparada[p, d_cand-1]) if d_cand-1 >= 0 else 0
                        next_turno = int(matriz_reparada[p, d_cand+1]) if d_cand+1 < self.num_dias else 0

                        if (prev_turno, turno) in self.secuencias_prohibidas:
                            continue
                        if (turno, next_turno) in self.secuencias_prohibidas:
                            continue

                        # Si pasa las comprobaciones, asignamos
                        matriz_reparada[p, d_cand] = turno
                        count += 1
                        asignado = True
                        break

                    # Si no se pudo asignar en ese día, seguimos con otro día

        return matriz_reparada