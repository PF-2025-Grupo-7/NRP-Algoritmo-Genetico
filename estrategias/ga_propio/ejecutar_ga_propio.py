import random
import numpy as np
import time
import os
import sys
import argparse

# Configuración de Rutas
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

LOCAL_DIR = os.path.dirname(__file__)
if LOCAL_DIR not in sys.path:
    sys.path.insert(0, LOCAL_DIR)

# Imports del Proyecto
from problema_ga_propio import ProblemaGAPropio
from operadores_ga_propio import torneo_seleccion, crossover_block_aware, aplicar_mutaciones
from utils_ga import init_population, diversity, population_stats
from loader import cargar_configuracion_ga, cargar_instancia_problema

# Import del Logger (NUEVO)
try:
    from logger import crear_estructura_logs, guardar_resultados
except ImportError:
    # Fallback silencioso si no existe el archivo logger.py
    crear_estructura_logs = None
    guardar_resultados = None

def main():
    # Configuración de Argumentos de Consola
    parser = argparse.ArgumentParser(description="Ejecutar GA Propio para Nurse Rostering")
    
    # Argumentos para indicar qué archivos usar. Por defecto busca en la carpeta data/ los archivos base.
    parser.add_argument('--instancia', type=str, default=os.path.join(LOCAL_DIR, 'data', 'instancia_01_base.json'),
                        help='Ruta al archivo JSON con los datos del hospital/problema')
    parser.add_argument('--config', type=str, default=os.path.join(LOCAL_DIR, 'data', 'config_ga_default.json'),
                        help='Ruta al archivo JSON con los parámetros del Algoritmo Genético')
    
    args = parser.parse_args()

    # Setup de Logs (NUEVO)
    ruta_logs = None
    if crear_estructura_logs:
        try:
            ruta_logs = crear_estructura_logs(tipo="propio")
        except Exception as e:
            print(f"Advertencia: No se pudieron crear los logs. {e}")

    print("\n" + "="*50)
    print(" Ejecutando AG Propio")
    # Mostrar ruta de logs si se creó (NUEVO)
    if ruta_logs:
        print(f" Logs en: {ruta_logs}")
    print("="*50)
    print(f"Instancia: {os.path.basename(args.instancia)}")
    print(f"Config:    {os.path.basename(args.config)}")

    # Carga de Datos desde JSON 
    try:
        config = cargar_configuracion_ga(args.config)
        datos_problema = cargar_instancia_problema(args.instancia)
        
    except FileNotFoundError as e:
        print(f"\nError: No se encontró uno de los archivos de configuración.\nDetalle: {e}")
        return
    except Exception as e:
        print(f"\nError al procesar los archivos JSON.\nDetalle: {e}")
        return

    # Configuración de Semilla (Reproducibilidad)
    SEED = config.get('seed', 1234)
    random.seed(SEED)
    np.random.seed(SEED)
    print(f"Seed:      {SEED}")

    # Inicialización del Problema
    try:
        problema = ProblemaGAPropio(**datos_problema)
    except TypeError as e:
        print(f"\nError al inicializar el problema. Probablemente faltan claves en el JSON de instancia.")
        print(f"Detalle técnico: {e}")
        return

    # Parámetros del GA 
    pop_size = config.get('pop_size', 100)
    generaciones = config.get('generaciones', 200)
    pc = config.get('pc', 0.85)  # Probabilidad de Cruce
    pm = config.get('pm', 0.20)  # Probabilidad de Mutación
    elitismo = config.get('elitismo', True)

    print(f"Población: {pop_size} | Gens: {generaciones} | PC: {pc} | PM: {pm}")
    print("-" * 50)

    # Bucle Evolutivo (GA)
    start_time = time.time()

    # Inicializar población
    pop = init_population(pop_size, problema.num_profesionales, problema.num_dias, problema.max_turno_val, seed=SEED)

    # Evaluar población inicial
    fitnesses = [problema.fitness(ind) for ind in pop]
    
    # Encontrar mejor inicial
    best_idx = int(min(range(len(fitnesses)), key=lambda i: fitnesses[i]))
    best_global = pop[best_idx].copy()
    best_global_f = fitnesses[best_idx]

    print(f"Estado Inicial -> Best Fitness: {best_global_f:.4f}")

    for gen in range(1, generaciones + 1):
        new_pop = []
        
        # Elitismo: Conservar al mejor de la generación anterior
        if elitismo:
            new_pop.append(best_global.copy())
        
        # Generar nueva población
        while len(new_pop) < pop_size:
            # Selección
            parent1 = torneo_seleccion(pop, fitnesses, k=3)
            parent2 = torneo_seleccion(pop, fitnesses, k=3)
            
            # Cruce (Crossover)
            if random.random() < pc:
                child = crossover_block_aware(parent1, parent2, problema.num_profesionales, problema.num_dias)
            else:
                child = parent1.copy() # Si no hay cruce, pasa el padre 1
            
            # Mutación
            if random.random() < pm:
                child = aplicar_mutaciones(child, problema)
            
            # Reparamos el hijo y lo devolvemos a la población ya corregido
            matriz_child = child.reshape(problema.num_profesionales, problema.num_dias)
            matriz_child = problema._reparar_cromosoma(matriz_child)
            child = matriz_child.reshape(-1)
            
            new_pop.append(child)
        
        # Reemplazo generacional
        pop = new_pop[:pop_size]
        fitnesses = [problema.fitness(ind) for ind in pop]
        
        # Actualizar mejor global
        current_best_idx = int(min(range(len(fitnesses)), key=lambda i: fitnesses[i]))
        current_best_f = fitnesses[current_best_idx]
        
        if current_best_f < best_global_f:
            best_global_f = current_best_f
            best_global = pop[current_best_idx].copy()
            print(f"   >>> ¡Mejora en Gen {gen}! Nuevo récord: {best_global_f:.4f}")

        # Logs periódicos
        if gen % 10 == 0 or gen == 1:
            best, mean, std = population_stats(fitnesses)
            div = diversity(pop)
            print(f"Gen {gen:03d}: Best={best:.4f} | Mean={mean:.1f} | Div={div}")

    # Resultados Finales
    end_time = time.time()
    elapsed = end_time - start_time
    
    print("="*50)
    print(f"Ejecución Finalizada en {elapsed:.2f} segundos")
    print(f"Mejor Fitness Final: {best_global_f:.4f}")
    
    if best_global_f < 1000:
        print("Solución Factible ENCONTRADA")
    else:
        print("Solución Inválida")

    # Mostrar Matriz
    matriz_final = best_global.reshape(problema.num_profesionales, problema.num_dias)
    # Una última reparación por seguridad (aunque ya debería venir reparado del bucle)
    matriz_final = problema._reparar_cromosoma(matriz_final)
    
    print("\nCronograma Resultante (Filas=Profesionales, Cols=Días):")
    print(matriz_final.astype(int))

    # Guardar logs al finalizar
    if ruta_logs and guardar_resultados:
        print(f"Guardando logs en: {ruta_logs}")
        stats = {
            "tiempo_total": elapsed,
            "mejor_fitness": best_global_f,
            "generaciones": generaciones,
            "pop_size": pop_size,
            "solucion_valida": bool(best_global_f < 1000)
        }
        guardar_resultados(ruta_logs, config, stats, matriz_final, problema)
        print("Logs guardados correctamente.")

    # Opcional: Aquí podrías llamar a una función para exportar a Excel
    # exportar_solucion(matriz_final, datos_problema)

if __name__ == '__main__':
    main()