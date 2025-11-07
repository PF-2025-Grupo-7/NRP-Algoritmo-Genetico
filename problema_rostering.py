# proyecto_rostering/problema_rostering.py
import numpy as np
from mealpy import Problem
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
        
        # --- Configuración para mealpy (sin cambios) ---
        n_genes = self.num_profesionales * self.num_dias
        lb = [0] * n_genes 
        ub = [self.max_turno_val] * n_genes
        minmax = "min"
        
        super().__init__(lb=lb, ub=ub, minmax=minmax, **kwargs)

    
    def obj_func(self, solution):
        # ... 
        # (Esta función no cambia en absoluto. Sigue funcionando.)
        # ...
        # --- 1. Decodificar el Cromosoma ---
        matriz_asignacion = solution.reshape(self.num_profesionales, self.num_dias)
        
        # --- 2. Cálculo de Penalizaciones DURAS ---
        penalizacion_duras = 0.0
        penalizacion_duras += self._calcular_pen_cobertura(matriz_asignacion)
        penalizacion_duras += self._calcular_pen_descansos(matriz_asignacion)
        penalizacion_duras += self._calcular_pen_disponibilidad(matriz_asignacion)
        penalizacion_duras += self._calcular_pen_limites_turnos(matriz_asignacion)

        # --- 3. Cálculo de Penalizaciones BLANDAS ---
        pen_eq = self._calcular_pen_equidad_general(matriz_asignacion)
        pen_dif = self._calcular_pen_equidad_dificiles(matriz_asignacion)
        pen_pdl = self._calcular_pen_pdl(matriz_asignacion)
        pen_pte = self._calcular_pen_pte(matriz_asignacion)
        
        # --- 4. Función de Fitness Total ---
        penalizacion_total = (penalizacion_duras) + \
                             (self.pesos_fitness['eq'] * pen_eq) + \
                             (self.pesos_fitness['dif'] * pen_dif) + \
                             (self.pesos_fitness['pdl'] * pen_pdl) + \
                             (self.pesos_fitness['pte'] * pen_pte)
        
        return penalizacion_total