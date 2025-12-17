import os
import sys
import argparse
import time
import random
import numpy as np

# Rutas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from problema import ProblemaGAPropio
from ga_engine.utils import init_population, diversity, population_stats
from loader import cargar_configuracion_ga, cargar_instancia_problema
# Importamos los catálogos en lugar de las funciones sueltas
from operadores import SELECTION_OPS, CROSSOVER_OPS, MUTATION_OPS 

try:
    from logger import crear_estructura_logs, guardar_resultados
except ImportError:
    crear_estructura_logs = None

def main():
    parser = argparse.ArgumentParser(description="GA para Nurse Rostering")
    
    # Rutas de datos
    default_data = os.path.join(os.path.dirname(__file__), 'data')
    parser.add_argument('--instancia', default=os.path.join(default_data, 'instancia_01_base.json'))
    parser.add_argument('--config', default=os.path.join(default_data, 'config_ga_fast.json'))
    
    # --- NUEVOS ARGUMENTOS PARA OPERADORES ---
    # Usamos las claves de los diccionarios como opciones válidas
    parser.add_argument('--sel', type=str, default='torneo_deterministico', 
                        choices=SELECTION_OPS.keys(), help='Estrategia de Selección')
    parser.add_argument('--cross', type=str, default='bloques_verticales', 
                        choices=CROSSOVER_OPS.keys(), help='Operador de Cruce')
    parser.add_argument('--mut', type=str, default='hibrida_adaptativa', 
                        choices=MUTATION_OPS.keys(), help='Operador de Mutación')
    
    # Argumento para etiquetar logs (útil para experimentación masiva)
    parser.add_argument('--tag', type=str, default='run', help='Prefijo para la carpeta de logs')

    parser.add_argument('-v', '--verbose', action='store_true', 
                        help='Muestra estadísticas detalladas en consola generación a generación')
    
    args = parser.parse_args()

    # 1. Resolver Funciones de Operadores
    seleccion_func = SELECTION_OPS[args.sel]
    cruce_func = CROSSOVER_OPS[args.cross]
    mutacion_func = MUTATION_OPS[args.mut]

    # Diccionario para logs
    ops_names = {
        "seleccion": args.sel,
        "cruce": args.cross,
        "mutacion": args.mut
    }

    # 2. Setup Logs
    ruta_logs = None
    if crear_estructura_logs:
        ruta_logs = crear_estructura_logs(prefix=args.tag)
        print(f"Logs en: {ruta_logs}")

    # 3. Carga de Configuración
    config = cargar_configuracion_ga(args.config)
    datos_problema = cargar_instancia_problema(args.instancia)
    
    # Seed
    SEED = config.get('seed', 1234)
    random.seed(SEED)
    np.random.seed(SEED)

    # Inicializar Problema
    problema = ProblemaGAPropio(**datos_problema)

    # Parámetros GA
    pop_size = config.get('pop_size', 100)
    generaciones = config.get('generaciones', 200)
    pc = config.get('pc', 0.85)
    pm = config.get('pm', 0.20)
    elitismo = config.get('elitismo', True)

    print(f"Estrategia: {args.sel} | {args.cross} | {args.mut}")
    print(f"Modo Verbose: {'ACTIVADO' if args.verbose else 'DESACTIVADO'}")

    # --- BUCLE EVOLUTIVO ---
    start_time = time.time()
    pop = init_population(pop_size, problema.num_profesionales, problema.num_dias, problema.max_turno_val, seed=SEED)
    fitnesses = [problema.fitness(ind) for ind in pop]

    best_idx = np.argmin(fitnesses)
    best_global = pop[best_idx].copy()
    best_global_f = fitnesses[best_idx]

    for gen in range(1, generaciones + 1):
        new_pop = []
        if elitismo:
            new_pop.append(best_global.copy())

        while len(new_pop) < pop_size:
            # Uso dinámico del operador de selección
            p1 = seleccion_func(pop, fitnesses, k=3)
            p2 = seleccion_func(pop, fitnesses, k=3)

            # Uso dinámico del operador de cruce
            if random.random() < pc:
                child = cruce_func(p1, p2, problema.num_profesionales, problema.num_dias)
            else:
                child = p1.copy()

            # Uso dinámico del operador de mutación
            if random.random() < pm:
                child = mutacion_func(child, problema)

            # Reparación (siempre necesaria en este diseño)
            child = problema._reparar_cromosoma(child.reshape(problema.num_profesionales, problema.num_dias)).reshape(-1)
            new_pop.append(child)

        pop = new_pop[:pop_size]
        fitnesses = [problema.fitness(ind) for ind in pop]

        # Estadísticas para el mejor global (esto siempre se calcula)
        current_best_idx = np.argmin(fitnesses)
        if fitnesses[current_best_idx] < best_global_f:
            best_global_f = fitnesses[current_best_idx]
            best_global = pop[current_best_idx].copy()
            # Si es verbose, avisamos de la mejora inmediatamente
            if args.verbose:
                 print(f"   >>> ¡Mejora! Nuevo récord: {best_global_f:.4f}")
        
        # --- REPORTE CONDICIONAL EN CONSOLA ---
        # Solo imprimimos si el usuario usó --verbose
        if args.verbose and (gen % 10 == 0 or gen == 1):
            # Calculamos estadísticas extra solo si vamos a imprimir (ahorra tiempo)
            best_val, mean_val, std_val = population_stats(fitnesses)
            div_val = diversity(pop)
            print(f"Gen {gen:03d}: Best={best_val:.4f} | Mean={mean_val:.1f} | Div={div_val}")

    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"Fin. Fitness: {best_global_f:.4f}. Tiempo: {elapsed:.2f}s")
    
    # Guardado de Logs
    if ruta_logs and guardar_resultados:
        matriz_final = problema._reparar_cromosoma(best_global.reshape(problema.num_profesionales, problema.num_dias))
        stats = {
            "tiempo_total": elapsed,
            "mejor_fitness": best_global_f,
            "generaciones": generaciones,
            "solucion_valida": bool(best_global_f < 1000)
        }
        # Pasamos el nuevo diccionario 'ops_names'
        guardar_resultados(ruta_logs, config, ops_names, stats, matriz_final, problema)

if __name__ == '__main__':
    main()