import numpy as np
# Al estar ambos en src/, esto debería funcionar directo:
from penalizaciones.duras import PenalizacionesDurasMixin
from penalizaciones.blandas import PenalizacionesBlandasMixin
from repair import reparar_cromosoma

class ProblemaGAPropio(PenalizacionesDurasMixin, PenalizacionesBlandasMixin):
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

    def fitness(self, solution_vector):
        matriz = solution_vector.reshape(self.num_profesionales, self.num_dias)
        matriz_reparada = self._reparar_cromosoma(matriz)
        penalizacion = 0.0
        penalizacion += self._calcular_pen_disponibilidad(matriz_reparada)
        penalizacion += self._calcular_pen_descansos(matriz_reparada)
        penalizacion += self._calcular_pen_limites_turnos(matriz_reparada)
        penalizacion += self._calcular_pen_cobertura(matriz_reparada)
        pen_eq = self._calcular_pen_equidad_general(matriz_reparada)
        pen_dif = self._calcular_pen_equidad_dificiles(matriz_reparada)
        pen_pdl = self._calcular_pen_pdl(matriz_reparada)
        pen_pte = self._calcular_pen_pte(matriz_reparada)
        
        total = penalizacion + (self.pesos_fitness['eq'] * pen_eq) + (self.pesos_fitness['dif'] * pen_dif) + (self.pesos_fitness['pdl'] * pen_pdl) + (self.pesos_fitness['pte'] * pen_pte)
        return float(total)

    def _reparar_cromosoma(self, matriz):
        return reparar_cromosoma(matriz, self)
    
    def evaluar_detallado(self, solution_vector):
        matriz = solution_vector.reshape(self.num_profesionales, self.num_dias)
        matriz_reparada = self._reparar_cromosoma(matriz)
        
        # ... (mantener cálculos de cobertura, PDL y PTE igual que antes)
        pen_cob, inc_cob = self._calcular_pen_cobertura(matriz_reparada, detallar=True)
        pen_pdl, inc_pdl = self._calcular_pen_pdl(matriz_reparada, detallar=True)
        pen_pte, inc_pte = self._calcular_pen_pte(matriz_reparada, detallar=True)
        
        # --- EXPLICABILIDAD DE EQUIDAD ---
        horas_gen = self._obtener_horas_por_profesional(matriz_reparada, tipo="general")
        _, scores, h_avg, h_min, h_max = self._calcular_score_equidad(
            horas_gen, self.tolerancia_equidad_general, detallar=True
        )
        
        outliers = []
        for p, s in enumerate(scores):
            if s < 1.0: # No está en el punto ideal (h_avg)
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
                "desbalance_equidad": outliers  # <--- NUEVO: Detalle de quiénes están desbalanceados
            },
            "datos_equidad": {
                "promedio_objetivo": float(h_avg),
                "rango_ideal": [float(h_min), float(h_max)],
                "horas_por_profesional": horas_gen.tolist()
            }
        }

    # MÉTODO CORREGIDO (Indentado y con argumento 'tipo')
    def _obtener_horas_por_profesional(self, matriz, tipo="general"):
        """Extrae el vector de horas trabajadas (útil para el reporte)."""
        horas = np.zeros(self.num_profesionales)
        for p in range(self.num_profesionales):
            for d in range(self.num_dias):
                turno = int(matriz[p, d])
                if turno > 0:
                    # Lógica similar a _calcular_pen_equidad_general/dificiles en blandas.py
                    if tipo == "dificil":
                        es_finde_o_feriado = (d in self.dias_no_habiles)
                        es_turno_noche = (turno in self.turnos_noche)
                        if es_finde_o_feriado or es_turno_noche:
                            horas[p] += self.duracion_turnos.get(turno, 0)
                    else: # general
                        horas[p] += self.duracion_turnos.get(turno, 0)
        return horas