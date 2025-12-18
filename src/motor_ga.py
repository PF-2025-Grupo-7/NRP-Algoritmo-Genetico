import time
import random
import numpy as np
from .problema import ProblemaGAPropio
from .utils import init_population
from .loader import procesar_datos_instancia 
from .operadores import SELECTION_OPS, CROSSOVER_OPS, MUTATION_OPS 

def ejecutar_algoritmo_genetico(config, datos_problema_raw, estrategias, job_id=None, reporte_progreso=None):
    """
    Ejecuta el GA y reporta el progreso en tiempo real.
    Ahora incluye el reporte detallado de explicabilidad al finalizar.
    """
    
    # 1. Configurar Semilla
    SEED = config.get('seed', 1234)
    random.seed(SEED)
    np.random.seed(SEED)

    # 2. Procesar datos
    datos_procesados = procesar_datos_instancia(datos_problema_raw)

    # 3. Inicializar Problema
    problema = ProblemaGAPropio(**datos_procesados)

    # 4. Resolver Funciones de Operadores
    estrategias = estrategias or {}
    seleccion_func = SELECTION_OPS[estrategias.get('sel', 'torneo_deterministico')]
    cruce_func = CROSSOVER_OPS[estrategias.get('cross', 'bloques_verticales')]
    mutacion_func = MUTATION_OPS[estrategias.get('mut', 'hibrida_adaptativa')]

    # 5. Parámetros GA
    pop_size = config.get('pop_size', 100)
    generaciones = config.get('generaciones', 200)
    pc = config.get('pc', 0.85)
    pm = config.get('pm', 0.20)
    elitismo = config.get('elitismo', True)

    # --- BUCLE EVOLUTIVO ---
    start_time = time.time()
    pop = init_population(pop_size, problema.num_profesionales, problema.num_dias, problema.max_turno_val, seed=SEED)
    fitnesses = [problema.fitness(ind) for ind in pop]

    best_idx = np.argmin(fitnesses)
    best_global = pop[best_idx].copy()
    best_global_f = fitnesses[best_idx]

    for gen in range(1, generaciones + 1):
        # --- LÓGICA DE REPORTE DE PROGRESO ---
        if reporte_progreso is not None and job_id:
            porcentaje = int((gen / generaciones) * 100)
            reporte_progreso[job_id] = {
                "gen_actual": gen,
                "gen_total": generaciones,
                "porcentaje": porcentaje,
                "mejor_fitness_actual": float(best_global_f)
            }

        new_pop = []
        if elitismo:
            new_pop.append(best_global.copy())

        while len(new_pop) < pop_size:
            p1 = seleccion_func(pop, fitnesses, k=3)
            p2 = seleccion_func(pop, fitnesses, k=3)

            if random.random() < pc:
                child = cruce_func(p1, p2, problema.num_profesionales, problema.num_dias)
            else:
                child = p1.copy()

            if random.random() < pm:
                child = mutacion_func(child, problema)

            # Reparación y aplanado
            child = problema._reparar_cromosoma(child.reshape(problema.num_profesionales, problema.num_dias)).reshape(-1)
            new_pop.append(child)

        pop = new_pop[:pop_size]
        fitnesses = [problema.fitness(ind) for ind in pop]

        current_best_idx = np.argmin(fitnesses)
        if fitnesses[current_best_idx] < best_global_f:
            best_global_f = fitnesses[current_best_idx]
            best_global = pop[current_best_idx].copy()

    end_time = time.time()
    elapsed = end_time - start_time
    
    # 6. Generar Solución Final y Explicabilidad
    matriz_final = problema._reparar_cromosoma(best_global.reshape(problema.num_profesionales, problema.num_dias))
    
    # Llamamos al nuevo método para obtener el desglose de incidentes
    reporte_explicabilidad = problema.evaluar_detallado(best_global)
    
    return {
        "fitness": float(best_global_f),
        "tiempo_ejecucion": elapsed,
        "solucion": matriz_final.tolist(), 
        "generaciones_completadas": generaciones,
        "config_utilizada": config,
        "explicabilidad": reporte_explicabilidad  # <--- Nuevo campo para la App
    }