import time
import random
import numpy as np

# Importaciones relativas para consistencia de paquete
from .problema import ProblemaGAPropio
from .utils import init_population
from .loader import procesar_datos_instancia 
from .operadores import SELECTION_OPS, CROSSOVER_OPS, MUTATION_OPS 

def ejecutar_algoritmo_genetico(config, datos_problema_raw, estrategias, job_id=None, reporte_progreso=None):
    """
    Punto de entrada principal para la ejecución del GA.
    Orquesta la preparación, el bucle evolutivo y la generación de resultados.
    """
    # 1. Preparación del Entorno
    SEED = config.get('seed', 1234)
    random.seed(SEED)
    np.random.seed(SEED)

    # 2. Inicialización de Componentes
    datos_procesados = procesar_datos_instancia(datos_problema_raw)
    problema = ProblemaGAPropio(**datos_procesados)

    # Resolución de estrategias de operadores
    estrategias = estrategias or {}
    seleccion_func = SELECTION_OPS[estrategias.get('sel', 'torneo_deterministico')]
    cruce_func = CROSSOVER_OPS[estrategias.get('cross', 'bloques_verticales')]
    mutacion_func = MUTATION_OPS[estrategias.get('mut', 'hibrida_adaptativa')]

    # Parámetros de evolución
    pop_size = config.get('pop_size', 100)
    generaciones = config.get('generaciones', 200)
    pc = config.get('pc', 0.85)
    pm = config.get('pm', 0.20)
    elitismo = config.get('elitismo', True)

    # 3. Población Inicial
    start_time = time.time()
    pop = init_population(pop_size, problema.num_profesionales, problema.num_dias, problema.max_turno_val, seed=SEED)
    fitnesses = [problema.fitness(ind) for ind in pop]

    # Seguimiento del mejor global
    best_idx = np.argmin(fitnesses)
    best_global = pop[best_idx].copy()
    best_global_f = fitnesses[best_idx]

    # 4. Bucle Evolutivo Principal
    for gen in range(1, generaciones + 1):
        # Reporte de progreso asincrónico
        _reportar_avance(reporte_progreso, job_id, gen, generaciones, best_global_f)

        new_pop = []
        if elitismo:
            new_pop.append(best_global.copy())

        while len(new_pop) < pop_size:
            # Selección de padres
            p1 = seleccion_func(pop, fitnesses, k=3)
            p2 = seleccion_func(pop, fitnesses, k=3)

            # Cruce
            if random.random() < pc:
                child = cruce_func(p1, p2, problema.num_profesionales, problema.num_dias)
            else:
                child = p1.copy()

            # Mutación
            if random.random() < pm:
                child = mutacion_func(child, problema)

            # Reparación: Garantiza que el hijo sea una solución válida antes de evaluarlo
            child_matriz = child.reshape(problema.num_profesionales, problema.num_dias)
            child_reparado = problema._reparar_cromosoma(child_matriz).reshape(-1)
            new_pop.append(child_reparado)

        # Reemplazo de población
        pop = new_pop[:pop_size]
        fitnesses = [problema.fitness(ind) for ind in pop]

        # Actualización del mejor global
        current_best_idx = np.argmin(fitnesses)
        if fitnesses[current_best_idx] < best_global_f:
            best_global_f = fitnesses[current_best_idx]
            best_global = pop[current_best_idx].copy()

    # 5. Finalización y Reporte Detallado
    elapsed = time.time() - start_time
    
    # Generamos la matriz final y el reporte de explicabilidad para el usuario
    reporte_explicabilidad = problema.evaluar_detallado(best_global)
    
    return {
        "fitness": float(best_global_f),
        "tiempo_ejecucion": elapsed,
        "solucion": reporte_explicabilidad["datos_equidad"]["horas_por_profesional"], # Ejemplo de datos procesados
        "matriz_solucion": best_global.reshape(problema.num_profesionales, problema.num_dias).tolist(),
        "generaciones_completadas": generaciones,
        "config_utilizada": config,
        "explicabilidad": reporte_explicabilidad 
    }

def _reportar_avance(reporte_progreso, job_id, gen, total, fitness):
    """Actualiza el diccionario compartido de progreso."""
    if reporte_progreso is not None and job_id:
        reporte_progreso[job_id] = {
            "gen_actual": gen,
            "gen_total": total,
            "porcentaje": int((gen / total) * 100),
            "mejor_fitness_actual": float(fitness)
        }