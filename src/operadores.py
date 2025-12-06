import random
import numpy as np

# Estrategia de selección: torneo determinístico
def torneo_seleccion(population, fitnesses, k=3):
    idx = random.sample(range(len(population)), k)  # tomar k individuos al azar
    best = min(idx, key=lambda i: fitnesses[i])     # seleccionar al mejor
    return population[best].copy()                  # retornar copia del individuo

# Operador de cruce: crossover vertical por días
def crossover_block_aware(parent1, parent2, num_profesionales, num_dias):
    p1 = parent1.reshape(num_profesionales, num_dias)
    p2 = parent2.reshape(num_profesionales, num_dias)
    child = np.zeros_like(p1)

    # El operador trata a cada día como un bloque
    for d in range(num_dias):
        if random.random() < 0.5:
            child[:, d] = p1[:, d] # hereda columna de progenitor 1
        else:
            child[:, d] = p2[:, d] # hereda columna de progenitor 2
    
    return child.reshape(-1) # retornar hijo como vector


#-----------------------------------------------
#              MUTACIÓN HÍBRIDA 
#     Se elige al azar entre tres operadores.
# -----------------------------------------------

# Tipo 1: mutación de reasignación de turno
def mutate_reassign_shift(sol, problema, max_attempts=20):
    """
    Mueve un turno a otro profesional el mismo día.
    Propósito: balanceo de carga sin alterar cobertura total. [cite: 484]
    """
    matriz = sol.reshape(problema.num_profesionales, problema.num_dias).copy()
    
    # Filtramos días que tengan alguna asignación
    dias_con_asig = [d for d in range(problema.num_dias) if (matriz[:, d] > 0).any()]
    if not dias_con_asig: return sol
    
    d = random.choice(dias_con_asig)

    # Identificamos profesionales con turno ese día
    profesionales_con_turno = [p for p in range(problema.num_profesionales) if matriz[p, d] > 0]
    if not profesionales_con_turno: return sol

    # Tomamos turno al azar
    p_origen = random.choice(profesionales_con_turno)
    t = int(matriz[p_origen, d])

    # Buscamos candidatos para recibir el turno
    candidatos = []
    attempts = 0
    for p in range(problema.num_profesionales):
        if p == p_origen: continue

        # Chequeamos factibilidad parcial
        if problema.info_profesionales[p]['skill'] != problema.info_profesionales[p_origen]['skill']: continue
        if not bool(problema.matriz_disponibilidad[p, d]): continue
        
        prev = int(matriz[p, d-1]) if d > 0 else 0
        nxt = int(matriz[p, d+1]) if d < problema.num_dias - 1 else 0
        if (prev, t) in problema.secuencias_prohibidas: continue
        if (t, nxt) in problema.secuencias_prohibidas: continue
        if int((matriz[p] > 0).sum()) >= int(problema.info_profesionales[p]['t_max']): continue
        
        candidatos.append(p)
        attempts += 1
        if attempts >= max_attempts: break

    if not candidatos: return sol

    # Ejecutar movimiento
    p_destino = random.choice(candidatos)
    matriz[p_origen, d] = 0
    matriz[p_destino, d] = t

    return matriz.reshape(-1)

# Tipo 2: mutación de intercambio
def mutate_swap_same_day(sol, problema):
    """
    Intercambia asignaciones entre dos profesionales el mismo día.
    Propósito: mejorar preferencias y habilidades (ej. Senior x Junior). [cite: 487]
    """
    matriz = sol.reshape(problema.num_profesionales, problema.num_dias).copy()
    d = random.randint(0, problema.num_dias - 1)
    
    # Seleccionar dos profesionales de un mismo día
    p1, p2 = random.sample(range(problema.num_profesionales), 2)
    t1 = int(matriz[p1, d])
    t2 = int(matriz[p2, d])

    # Validaciones de seguridad
    if not bool(problema.matriz_disponibilidad[p1, d]) or not bool(problema.matriz_disponibilidad[p2, d]):
        return sol
    def viola_seq(p, dia, nuevo_turno):
        prev = int(matriz[p, dia-1]) if dia > 0 else 0
        nxt = int(matriz[p, dia+1]) if dia < problema.num_dias - 1 else 0
        if (prev, nuevo_turno) in problema.secuencias_prohibidas:
            return True
        if (nuevo_turno, nxt) in problema.secuencias_prohibidas:
            return True
        return False
    
    if viola_seq(p1, d, t2) or viola_seq(p2, d, t1): return sol
    
    # Validaciones de t_max tras el swap
    def count_after_swap(p, dia, turno_new):
        cnt = int((matriz[p] > 0).sum())
        if matriz[p, dia] > 0 and turno_new == 0: cnt -= 1
        if matriz[p, dia] == 0 and turno_new > 0: cnt += 1
        return cnt
    if count_after_swap(p1, d, t2) > int(problema.info_profesionales[p1]['t_max']): return sol
    if count_after_swap(p2, d, t1) > int(problema.info_profesionales[p2]['t_max']): return sol
    
    # Realiza el intercambio
    matriz[p1, d], matriz[p2, d] = t2, t1
    return matriz.reshape(-1)

# Tipo 3: mutación simple 
def mutate_flip(sol, problema):
    """
    Cambia el valor de una celda al azar.
    Propósito: inyectar o retirar horas para escapar de estancamiento. [cite: 490]
    """
    matriz = sol.reshape(problema.num_profesionales, problema.num_dias).copy()
    p = random.randint(0, problema.num_profesionales - 1)
    d = random.randint(0, problema.num_dias - 1)
    
    if not bool(problema.matriz_disponibilidad[p, d]): return sol
    
    # Selecciona el nuevo valor aleaorio
    posibles = [0] + problema.turnos_a_cubrir[:]
    random.shuffle(posibles)

    for turno in posibles:
        # Verifica secuencias antes de aplicar el cambio
        prev = int(matriz[p, d-1]) if d > 0 else 0
        nxt = int(matriz[p, d+1]) if d < problema.num_dias - 1 else 0
        if (prev, turno) in problema.secuencias_prohibidas: continue
        if (turno, nxt) in problema.secuencias_prohibidas: continue
        
        # Aplica el cambio
        matriz[p, d] = turno
        break
    return matriz.reshape(-1)

# Elegir aleatoriamente entre los tres operadores
def aplicar_mutaciones(sol, problema):
    ops = [mutate_reassign_shift, mutate_swap_same_day, mutate_flip]
    op = random.choice(ops)
    return op(sol, problema)


# --- CATÁLOGO DE OPERADORES ---
# Esto permite seleccionarlos por nombre desde la línea de comandos

SELECTION_OPS = {
    "torneo_deterministico": torneo_seleccion
}

CROSSOVER_OPS = {
    "bloques_verticales": crossover_block_aware
}

MUTATION_OPS = {
    # La estrategia por defecto (mezcla las 3)
    "hibrida_adaptativa": aplicar_mutaciones,

    # Estrategias individuales expuestas para testing
    "reasignar_turno": mutate_reassign_shift,  # Mueve turno a otro prof. (Balanceo)
    "intercambio_dia": mutate_swap_same_day,   # Intercambia entre 2 profs. (Preferencias)
    "flip_simple": mutate_flip                 # Cambia un valor al azar (Diversidad)
}