"""Motor del Algoritmo Genético para la Planificación de Guardias (NRP).

Este módulo contiene la lógica principal del bucle evolutivo, encargándose de la 
inicialización de la población, la aplicación de operadores genéticos y el 
reporte de progreso asincrónico para la API.
"""

import time
import random
import numpy as np

# Importaciones relativas para consistencia de paquete
from .utils import init_population
from .loader import procesar_datos_instancia 
from .problema import ProblemaGAPropio  # <--- AGREGADO: Faltaba esta importación
from .operadores import SELECTION_OPS, CROSSOVER_OPS, MUTATION_OPS 

def ejecutar_algoritmo_genetico(config, datos_problema_raw, estrategias, job_id=None, reporte_progreso=None):
    """Orquesta la ejecución completa del Algoritmo Genético.

    Realiza la preparación del entorno, la configuración de la instancia del 
    problema y ejecuta el bucle evolutivo hasta completar las generaciones 
    estipuladas.

    Args:
        config (dict): Parámetros de configuración del GA (pop_size, generaciones, 
            pc, pm, elitismo, seed).
        datos_problema_raw (dict): Diccionario con los datos crudos de la 
            instancia del problema (proveniente del JSON de la API).
        estrategias (dict): Mapeo de nombres de estrategias a utilizar para 
            los operadores (sel, cross, mut).
        job_id (str, optional): Identificador único del trabajo para el 
            reporte de progreso.
        reporte_progreso (dict, optional): Diccionario compartido (multiprocessing) 
            donde se registran los avances de cada generación.

    Returns:
        dict: Resultados finales del algoritmo, incluyendo:
            - fitness (float): Valor de aptitud de la mejor solución encontrada.
            - tiempo_ejecucion (float): Tiempo total en segundos.
            - solucion (list): Vector de horas trabajadas por profesional.
            - matriz_solucion (list): Representación PxD de la planificación final.
            - generaciones_completadas (int): Cantidad de iteraciones realizadas.
            - config_utilizada (dict): Configuración final aplicada.
            - explicabilidad (dict): Reporte detallado de penalizaciones y equidad.
    """
    # 1. Preparación del Entorno
    # Si la seed es None, usamos una fija por defecto o el reloj del sistema si preferimos aleatoriedad pura
    SEED = config.get('seed', 1234) 
    
    if SEED is not None:
        random.seed(SEED)
        np.random.seed(SEED)

    # 2. Inicialización de Componentes
    datos_procesados = procesar_datos_instancia(datos_problema_raw)
    problema = ProblemaGAPropio(**datos_procesados)

    # Resolución de funciones de operadores basadas en las estrategias elegidas
    # Usamos .get() con defaults seguros, aunque la API ya debería haber validado esto.
    estrategias = estrategias or {}
    seleccion_func = SELECTION_OPS.get(estrategias.get('sel'), SELECTION_OPS['torneo_deterministico'])
    cruce_func = CROSSOVER_OPS.get(estrategias.get('cross'), CROSSOVER_OPS['bloques_verticales'])
    mutacion_func = MUTATION_OPS.get(estrategias.get('mut'), MUTATION_OPS['hibrida_adaptativa'])

    # Parámetros de evolución
    pop_size = config.get('pop_size', 100)
    generaciones = config.get('generaciones', 200)
    pc = config.get('pc', 0.85)
    pm = config.get('pm', 0.20)
    elitismo = config.get('elitismo', True)

    # 3. Creación de Población Inicial
    start_time = time.time()
    # Pasamos la seed también a init_population para garantizar reproducibilidad en la generación inicial
    pop = init_population(pop_size, problema.num_profesionales, problema.num_dias, problema.max_turno_val, seed=SEED)
    fitnesses = [problema.fitness(ind) for ind in pop]

    # Seguimiento del mejor individuo histórico
    best_idx = np.argmin(fitnesses)
    best_global = pop[best_idx].copy()
    best_global_f = fitnesses[best_idx]

    # 4. Bucle Evolutivo Principal
    for gen in range(1, generaciones + 1):
        # Reporte de progreso asincrónico para la interfaz de usuario
        _reportar_avance(reporte_progreso, job_id, gen, generaciones, best_global_f)

        new_pop = []
        if elitismo:
            new_pop.append(best_global.copy())

        while len(new_pop) < pop_size:
            # Selección de padres mediante torneo (o la estrategia seleccionada)
            # Nota: Si seleccion_ranking no usa k, el argumento extra se ignora o se maneja dentro
            p1 = seleccion_func(pop, fitnesses, k=3)
            p2 = seleccion_func(pop, fitnesses, k=3)

            # Cruce (Crossover)
            if random.random() < pc:
                child = cruce_func(p1, p2, problema.num_profesionales, problema.num_dias)
            else:
                child = p1.copy()

            # Mutación
            if random.random() < pm:
                child = mutacion_func(child, problema)

            # Reparación: Se asegura la validez de la solución antes de su evaluación
            child_matriz = child.reshape(problema.num_profesionales, problema.num_dias)
            child_reparado = problema._reparar_cromosoma(child_matriz).reshape(-1)
            new_pop.append(child_reparado)

        # Transición generacional
        pop = new_pop[:pop_size]
        fitnesses = [problema.fitness(ind) for ind in pop]

        # Actualización del mejor global si se encontró una mejora
        current_best_idx = np.argmin(fitnesses)
        if fitnesses[current_best_idx] < best_global_f:
            best_global_f = fitnesses[current_best_idx]
            best_global = pop[current_best_idx].copy()

    # 5. Consolidación de Resultados Finales
    elapsed = time.time() - start_time
    
    # Generación de la auditoría final y explicabilidad
    reporte_explicabilidad = problema.evaluar_detallado(best_global)
    
    return {
        "fitness": float(best_global_f),
        "tiempo_ejecucion": elapsed,
        # Asumimos que 'horas_por_profesional' está disponible en el reporte de equidad
        "solucion": reporte_explicabilidad["datos_equidad"].get("horas_por_profesional", []),
        "matriz_solucion": best_global.reshape(problema.num_profesionales, problema.num_dias).tolist(),
        "generaciones_completadas": generaciones,
        "config_utilizada": config,
        "explicabilidad": reporte_explicabilidad 
    }

def _reportar_avance(reporte_progreso, job_id, gen, total, fitness):
    """Actualiza el estado de progreso en la memoria compartida.

    Args:
        reporte_progreso (dict): Diccionario del Manager para comunicación entre procesos.
        job_id (str): ID único de la tarea actual.
        gen (int): Generación actual alcanzada.
        total (int): Cantidad total de generaciones programadas.
        fitness (float): Mejor valor de fitness alcanzado hasta el momento.
    """
    if reporte_progreso is not None and job_id:
        reporte_progreso[job_id] = {
            "gen_actual": gen,
            "gen_total": total,
            "porcentaje": int((gen / total) * 100),
            "mejor_fitness_actual": float(fitness)
        }