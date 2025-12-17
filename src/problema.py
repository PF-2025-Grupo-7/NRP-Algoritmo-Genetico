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
