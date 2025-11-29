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
        1) Limpia asignaciones inválidas.
        2) Si sobran enfermeros es un turno, los libera.
        3) Recorte de t_max.
        4) Relleno inteligente de déficits (Priorizando preferencias y equidad).

        """
        matriz_reparada = matriz.copy()

        # --- Paso de Limpieza ---
        # Forzar a 0 asignaciones que no aportan a la cobertura para la habilidad
        for p in range(self.num_profesionales):
            skill = self.info_profesionales[p]['skill']
            for d in range(self.num_dias):
                turno = int(matriz_reparada[p, d])
                if turno == 0: continue

                # Si el profesional no está disponible ese día lo limpiamos
                if not bool(self.matriz_disponibilidad[p, d]):
                    matriz_reparada[p, d] = 0
                    continue

                # Si el turno no requiere la habilidad del profesional, lo limpiamos
                try:
                    requerido = self.requerimientos_cobertura[d][turno].get(skill, 0)
                except Exception:
                    requerido = 0

                if requerido == 0:
                    matriz_reparada[p, d] = 0

        # --- Secuencias prohibidas ---
        for p in range(self.num_profesionales):
            for d in range(self.num_dias - 1):
                sec = (int(matriz_reparada[p, d]), int(matriz_reparada[p, d+1]))
                if sec in self.secuencias_prohibidas:
                    matriz_reparada[p, d+1] = 0

        # --- Podado de Sobre-Asignación ---
        # Elimina profesionales de turnos que ya tienen exceso de gente
        for d in range(self.num_dias):
            for turno in self.turnos_a_cubrir:
                for skill in self.skills_a_cubrir:
                    try:
                        requerido = self.requerimientos_cobertura[d][turno].get(skill, 0)
                    except: requerido = 0
                    
                    # Identificar quiénes están asignados actualmente
                    asignados = []
                    for p in range(self.num_profesionales):
                        if int(matriz_reparada[p, d]) == turno and self.info_profesionales[p]['skill'] == skill:
                            asignados.append(p)
                    
                    # Si sobran, eliminar al azar hasta cumplir el requisito
                    sobrantes = len(asignados) - requerido
                    if sobrantes > 0:
                        random.shuffle(asignados)
                        for _ in range(sobrantes):
                            p_elim = asignados.pop()
                            matriz_reparada[p_elim, d] = 0

        # --- Inicializar Contadores y Estructuras Auxiliares ---
        assigned_counts = {}
        prof_counts = [0] * self.num_profesionales
        dificiles_counts = [0] * self.num_profesionales 

        for d in range(self.num_dias):
            assigned_counts[d] = {}
            for turno in self.turnos_a_cubrir:
                assigned_counts[d][turno] = {}
                for k in self.skills_a_cubrir:
                    assigned = 0
                    for p in range(self.num_profesionales):
                        if int(matriz_reparada[p, d]) == turno and self.info_profesionales[p]['skill'] == k:
                            assigned += 1
                    assigned_counts[d][turno][k] = assigned

        # Calcular conteos iniciales
        for p in range(self.num_profesionales):
            for d in range(self.num_dias):
                turno = int(matriz_reparada[p, d])
                if turno > 0:
                    prof_counts[p] += 1
                    # Chequear si es difícil (Finde o Noche)
                    es_finde = d in self.dias_no_habiles
                    es_noche = turno in self.turnos_noche
                    if es_finde or es_noche:
                        dificiles_counts[p] += 1

        # --- Si hay profesionales por encima de t_max, recortarlos ---
        for p in range(self.num_profesionales):
            t_max = self.info_profesionales[p]['t_max']
            skill = self.info_profesionales[p]['skill']
            if prof_counts[p] <= t_max: continue

            # Priorizar eliminación de días con mayor exceso de cobertura
            trabajados = [d for d in range(self.num_dias) if int(matriz_reparada[p, d]) != 0]
            random.shuffle(trabajados)
            
            eliminar = prof_counts[p] - t_max
            for d_elim in trabajados:
                if eliminar <= 0: break
                
                turno_elim = int(matriz_reparada[p, d_elim])
                es_finde = d_elim in self.dias_no_habiles
                es_noche = turno_elim in self.turnos_noche
                if es_finde or es_noche:
                    dificiles_counts[p] -= 1
                
                matriz_reparada[p, d_elim] = 0
                try:
                    assigned_counts[d_elim][turno_elim][skill] = max(0, assigned_counts[d_elim][turno_elim][skill] - 1)
                except: pass
                prof_counts[p] -= 1
                eliminar -= 1

        # --- Cubrir déficit de cobertura ---
        for d in range(self.num_dias):
            for turno in self.turnos_a_cubrir:
                
                # Identificar si el turno actual es "Difícil"
                es_finde = d in self.dias_no_habiles
                es_noche = turno in self.turnos_noche
                turno_es_dificil = es_finde or es_noche

                for skill in self.skills_a_cubrir:
                    try:
                        requerido = self.requerimientos_cobertura[d][turno].get(skill, 0)
                    except: requerido = 0
                    
                    asignado = assigned_counts[d][turno].get(skill, 0)
                    deficit = requerido - asignado
                    
                    while deficit > 0:
                        # Buscar candidatos válidos
                        candidatos = []
                        for p in range(self.num_profesionales):
                            if self.info_profesionales[p]['skill'] != skill: continue
                            if int(matriz_reparada[p, d]) != 0: continue
                            if not bool(self.matriz_disponibilidad[p, d]): continue
                            if prof_counts[p] >= self.info_profesionales[p]['t_max']: continue

                            prev_turno = int(matriz_reparada[p, d-1]) if d-1 >= 0 else 0
                            next_turno = int(matriz_reparada[p, d+1]) if d+1 < self.num_dias else 0
                            if (prev_turno, turno) in self.secuencias_prohibidas: continue
                            if (turno, next_turno) in self.secuencias_prohibidas: continue

                            candidatos.append(p)

                        if not candidatos: break

                        # --- ESTRATEGIA DE SELECCIÓN ---
                        # Definimos una función para ordenar
                        def puntaje_candidato(p_idx):
                            # 1. Penalizar si viola PDL (Preferencia Día Libre) - Prioridad Máxima
                            viola_pdl = 1 if self.matriz_preferencias[p_idx, d] == -1 else 0
                            
                            # 2. Penalizar si viola PTE (Preferencia Turno Específico)
                            pref = self.matriz_preferencias[p_idx, d]
                            viola_pte = 1 if (pref > 0 and pref != turno) else 0
                            
                            # 3. Criterios de Equidad
                            if turno_es_dificil:
                                return (viola_pdl, viola_pte, dificiles_counts[p_idx], prof_counts[p_idx], random.random())
                            else:
                                return (viola_pdl, viola_pte, prof_counts[p_idx], dificiles_counts[p_idx], random.random())

                        # Ordenamos usando la nueva lógica
                        candidatos.sort(key=puntaje_candidato)

                        elegido_p = candidatos[0]

                        matriz_reparada[elegido_p, d] = turno
                        prof_counts[elegido_p] += 1
                        if turno_es_dificil:
                            dificiles_counts[elegido_p] += 1
                            
                        assigned_counts[d][turno][skill] = assigned_counts[d][turno].get(skill, 0) + 1
                        deficit -= 1

        # --- Rellenar hasta t_min ---
        for p in range(self.num_profesionales):
            if prof_counts[p] >= self.info_profesionales[p]['t_min']: continue
            
            dias_libres = [d for d in range(self.num_dias) if matriz_reparada[p, d] == 0 and bool(self.matriz_disponibilidad[p, d])]
            random.shuffle(dias_libres)
            
            skill = self.info_profesionales[p]['skill']
            t_max = self.info_profesionales[p]['t_max'] # Usamos t_max local para seguridad

            for d_cand in dias_libres:
                if prof_counts[p] >= self.info_profesionales[p]['t_min']: break
                
                # Intentar turnos útiles primero
                posibles = self.turnos_a_cubrir[:]
                random.shuffle(posibles)
                
                for turno in posibles:
                    prev_turno = int(matriz_reparada[p, d_cand-1]) if d_cand-1 >= 0 else 0
                    next_turno = int(matriz_reparada[p, d_cand+1]) if d_cand+1 < self.num_dias else 0
                    if (prev_turno, turno) in self.secuencias_prohibidas: continue
                    if (turno, next_turno) in self.secuencias_prohibidas: continue
                    
                    matriz_reparada[p, d_cand] = turno
                    prof_counts[p] += 1
                    break

        return matriz_reparada
