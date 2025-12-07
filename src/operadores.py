import random
import numpy as np

# ==============================================
#           ESTRATEGIAS DE SELECCIÓN
# ==============================================

def torneo_seleccion(population, fitnesses, k=3):
    """Selecciona el mejor individuo de un subgrupo aleatorio de tamaño k."""
    idx = random.sample(range(len(population)), k)
    best_idx = min(idx, key=lambda i: fitnesses[i])
    return population[best_idx].copy()

def seleccion_ranking(population, fitnesses, k=None):
    """
    Asigna probabilidad de selección basada en el ranking (orden) del fitness,
    evitando la dominancia excesiva de valores atípicos.
    """
    pop_size = len(population)
    
    # Ordenar índices por fitness (menor es mejor)
    ranked_indices = np.argsort(fitnesses)
    
    # Asignación de pesos lineal: el mejor tiene peso 'N', el peor '1'
    ranks = np.arange(pop_size, 0, -1)
    probs = ranks / np.sum(ranks)
    
    selected_idx = np.random.choice(ranked_indices, p=probs)
    return population[selected_idx].copy()

# =============================================
#       OPERADORES DE CRUCE (CROSSOVER)
# =============================================

def crossover_block_aware(parent1, parent2, num_profesionales, num_dias):
    """Cruce Vertical: Mantiene la estructura diaria intacta."""
    p1 = parent1.reshape(num_profesionales, num_dias)
    p2 = parent2.reshape(num_profesionales, num_dias)
    child = np.zeros_like(p1)

    for d in range(num_dias):
        # Hereda la columna completa (día) de uno de los padres
        if random.random() < 0.5:
            child[:, d] = p1[:, d]
        else:
            child[:, d] = p2[:, d]
    
    return child.reshape(-1)

def crossover_horizontal(parent1, parent2, num_profesionales, num_dias):
    """Cruce Horizontal: Mantiene la historia completa del profesional."""
    p1 = parent1.reshape(num_profesionales, num_dias)
    p2 = parent2.reshape(num_profesionales, num_dias)
    child = np.zeros_like(p1)

    for p in range(num_profesionales):
        # Hereda la fila completa (historial del médico) de uno de los padres
        if random.random() < 0.5:
            child[p, :] = p1[p, :]
        else:
            child[p, :] = p2[p, :]
            
    return child.reshape(-1)

def crossover_two_point(parent1, parent2, num_profesionales, num_dias):
    """Cruce Estándar de 2 Puntos: Corte genérico en el vector."""
    size = len(parent1)
    cx1 = random.randint(0, size - 2)
    cx2 = random.randint(cx1 + 1, size - 1)
    
    child = parent1.copy()
    child[cx1:cx2] = parent2[cx1:cx2]
    
    return child

# =====================================
#       OPERADORES DE MUTACIÓN
# =====================================

def mutate_reassign_shift(sol, problema, max_attempts=20):
    """Intenta mover un turno de un profesional a otro en el mismo día."""
    matriz = sol.reshape(problema.num_profesionales, problema.num_dias).copy()
    
    # Solo días con asignaciones
    dias_activos = [d for d in range(problema.num_dias) if (matriz[:, d] > 0).any()]
    if not dias_activos: return sol
    
    d = random.choice(dias_activos)
    profs_en_turno = [p for p in range(problema.num_profesionales) if matriz[p, d] > 0]
    if not profs_en_turno: return sol

    p_origen = random.choice(profs_en_turno)
    turno = int(matriz[p_origen, d])

    # Buscar receptor válido
    candidatos = []
    for p in range(problema.num_profesionales):
        if p == p_origen: continue
        # Validaciones rápidas: Skill, Disponibilidad, Max Horas
        if problema.info_profesionales[p]['skill'] != problema.info_profesionales[p_origen]['skill']: continue
        if not bool(problema.matriz_disponibilidad[p, d]): continue
        if int((matriz[p] > 0).sum()) >= int(problema.info_profesionales[p]['t_max']): continue
        
        # Validación de Secuencias
        prev = int(matriz[p, d-1]) if d > 0 else 0
        nxt = int(matriz[p, d+1]) if d < problema.num_dias - 1 else 0
        if (prev, turno) in problema.secuencias_prohibidas: continue
        if (turno, nxt) in problema.secuencias_prohibidas: continue
        
        candidatos.append(p)
        if len(candidatos) >= max_attempts: break

    if candidatos:
        p_destino = random.choice(candidatos)
        matriz[p_origen, d] = 0
        matriz[p_destino, d] = turno

    return matriz.reshape(-1)

def mutate_swap_same_day(sol, problema):
    """Intercambia los turnos de dos profesionales en el mismo día."""
    matriz = sol.reshape(problema.num_profesionales, problema.num_dias).copy()
    d = random.randint(0, problema.num_dias - 1)
    
    p1, p2 = random.sample(range(problema.num_profesionales), 2)
    t1, t2 = int(matriz[p1, d]), int(matriz[p2, d])

    if not (bool(problema.matriz_disponibilidad[p1, d]) and bool(problema.matriz_disponibilidad[p2, d])):
        return sol

    # Función auxiliar para chequear secuencias
    def check_seq(p, dia, t_new):
        prev = int(matriz[p, dia-1]) if dia > 0 else 0
        nxt = int(matriz[p, dia+1]) if dia < problema.num_dias - 1 else 0
        return ((prev, t_new) not in problema.secuencias_prohibidas and 
                (t_new, nxt) not in problema.secuencias_prohibidas)

    # Validar secuencias y límites de horas
    if check_seq(p1, d, t2) and check_seq(p2, d, t1):
        # Chequeo simple de T_max (solo si cambia estado libre/ocupado)
        def count(p, t_old, t_new):
            c = int((matriz[p] > 0).sum())
            return c - (1 if t_old > 0 else 0) + (1 if t_new > 0 else 0)
            
        if (count(p1, t1, t2) <= problema.info_profesionales[p1]['t_max'] and 
            count(p2, t2, t1) <= problema.info_profesionales[p2]['t_max']):
            
            matriz[p1, d], matriz[p2, d] = t2, t1

    return matriz.reshape(-1)

def mutate_flip(sol, problema):
    """Cambia el valor de una celda aleatoria por otro turno válido o libre."""
    matriz = sol.reshape(problema.num_profesionales, problema.num_dias).copy()
    p = random.randint(0, problema.num_profesionales - 1)
    d = random.randint(0, problema.num_dias - 1)
    
    if not bool(problema.matriz_disponibilidad[p, d]): return sol
    
    posibles = [0] + problema.turnos_a_cubrir[:]
    random.shuffle(posibles)

    for turno in posibles:
        prev = int(matriz[p, d-1]) if d > 0 else 0
        nxt = int(matriz[p, d+1]) if d < problema.num_dias - 1 else 0
        
        if (prev, turno) not in problema.secuencias_prohibidas and \
           (turno, nxt) not in problema.secuencias_prohibidas:
            matriz[p, d] = turno
            break
            
    return matriz.reshape(-1)

def aplicar_mutaciones(sol, problema):
    """Selecciona aleatoriamente una de las estrategias de mutación disponibles."""
    ops = [mutate_reassign_shift, mutate_swap_same_day, mutate_flip]
    return random.choice(ops)(sol, problema)


# =====================================
#        CATÁLOGO DE OPERADORES 
# =====================================

SELECTION_OPS = {
    "torneo_deterministico": torneo_seleccion,
    "ranking_lineal": seleccion_ranking
}

CROSSOVER_OPS = {
    "bloques_verticales": crossover_block_aware,
    "bloques_horizontales": crossover_horizontal,
    "dos_puntos": crossover_two_point
}

MUTATION_OPS = {
    "hibrida_adaptativa": aplicar_mutaciones,
    "reasignar_turno": mutate_reassign_shift,
    "intercambio_dia": mutate_swap_same_day,
    "flip_simple": mutate_flip
}