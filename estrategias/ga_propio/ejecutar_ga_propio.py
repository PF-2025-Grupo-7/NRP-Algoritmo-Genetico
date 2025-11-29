import random
import numpy as np
import time
import os
import sys

# ensure local imports work when running this script directly
sys.path.insert(0, os.path.dirname(__file__))

from problema_ga_propio import ProblemaGAPropio
from operadores_ga_propio import torneo_seleccion, crossover_block_aware, aplicar_mutaciones
from utils_ga import init_population, diversity, population_stats
from penalizaciones.duras import PenalizacionesDurasMixin

# Copy cargar_datos_de_prueba from the original implementation (adapted to local imports)

def cargar_datos_de_prueba():
    print("Cargando datos de prueba COMPLEJOS (Escenario de Estrés)...")
    P = 20
    D = 30
    max_turno = 3
    turnos_a_cubrir = [1,2,3]
    skills_a_cubrir = ['junior','senior']
    info_prof = []
    for i in range(P):
        skill = 'senior' if i < 10 else 'junior'
        info_prof.append({'skill': skill, 't_min': 12, 't_max': 16})
    dias_no_habiles = set(d for d in range(D) if d%7 in (5,6))
    reqs = {}
    total_demand = 0
    for d in range(D):
        reqs[d] = {}
        dia_semana = d%7
        es_pico = (dia_semana==0 or dia_semana==4)
        es_valle = (dia_semana==2)
        es_finde = (d in dias_no_habiles)
        for s in turnos_a_cubrir:
            reqs[d][s] = {}
            j=0; sr=0
            if s==1:
                if es_pico: j,sr = 3,2
                elif es_valle: j,sr = 2,1
                elif es_finde: j,sr = 2,1
                else: j,sr = 2,2
            elif s==2:
                if es_pico: j,sr = 2,2
                elif es_finde: j,sr = 1,1
                else: j,sr = 2,1
            elif s==3:
                j,sr = 1,1
            reqs[d][s]['junior'] = j
            reqs[d][s]['senior'] = sr
            total_demand += (j+sr)
    print(f"Demanda Total de Turnos: {total_demand}")
    dispon = np.full((P,D), True)
    dispon[0,0:10] = False
    dispon[1,5:15] = False
    dispon[15,20:30] = False
    for d in range(D):
        if d%7==3:
            dispon[19%P,d] = False
    prefs = np.zeros((P,D))
    prefs[2,15] = -1
    prefs[3,15] = -1
    prefs[4,15] = -1
    prefs[5,15] = -1
    for d in range(5):
        prefs[10%P,d] = 1
    for d in range(10,20):
        prefs[8%P,d] = 2
    sec_prohibidas = {(3,1),(3,2),(2,1)}
    pesos = { 'eq': 1.0, 'dif': 1.5, 'pdl': 2.5, 'pte': 0.5, 'alpha_pte': 0.5 }
    return {
        'num_profesionales': P,
        'num_dias': D,
        'max_turno_val': max_turno,
        'info_profesionales': info_prof,
        'matriz_preferencias': prefs,
        'matriz_disponibilidad': dispon,
        'requerimientos_cobertura': reqs,
        'pesos_fitness': pesos,
        'secuencias_prohibidas': sec_prohibidas,
        'turnos_a_cubrir': turnos_a_cubrir,
        'skills_a_cubrir': skills_a_cubrir,
        'duracion_turnos': {1:8,2:8,3:8},
        'tolerancia_equidad_general': 8,
        'tolerancia_equidad_dificil': 4,
        'dias_no_habiles': dias_no_habiles,
        'turnos_noche': {3}
    }

if __name__ == '__main__':
    SEED = 1234
    random.seed(SEED)
    np.random.seed(SEED)

    datos = cargar_datos_de_prueba()
    problema = ProblemaGAPropio(
        num_profesionales=datos['num_profesionales'],
        num_dias=datos['num_dias'],
        max_turno_val=datos['max_turno_val'],
        info_profesionales=datos['info_profesionales'],
        matriz_preferencias=datos['matriz_preferencias'],
        matriz_disponibilidad=datos['matriz_disponibilidad'],
        requerimientos_cobertura=datos['requerimientos_cobertura'],
        pesos_fitness=datos['pesos_fitness'],
        secuencias_prohibidas=datos['secuencias_prohibidas'],
        turnos_a_cubrir=datos['turnos_a_cubrir'],
        skills_a_cubrir=datos['skills_a_cubrir'],
        duracion_turnos=datos['duracion_turnos'],
        tolerancia_equidad_general=datos['tolerancia_equidad_general'],
        tolerancia_equidad_dificil=datos['tolerancia_equidad_dificil'],
        dias_no_habiles=datos['dias_no_habiles'],
        turnos_noche=datos['turnos_noche']
    )

    pop_size = 120
    generaciones = 250
    pc = 0.85
    pm = 0.20
    elitismo = True

    pop = init_population(pop_size, problema.num_profesionales, problema.num_dias, problema.max_turno_val, seed=SEED)

    # evaluate
    fitnesses = [problema.fitness(ind) for ind in pop]
    best_idx = int(min(range(len(fitnesses)), key=lambda i: fitnesses[i]))
    best_global = pop[best_idx].copy()
    best_global_f = fitnesses[best_idx]

    start = time.time()
    for gen in range(1, generaciones+1):
        new_pop = []
        # elitismo
        if elitismo:
            new_pop.append(best_global.copy())
        while len(new_pop) < pop_size:
            parent1 = torneo_seleccion(pop, fitnesses, k=3)
            parent2 = torneo_seleccion(pop, fitnesses, k=3)
            child = crossover_block_aware(parent1, parent2, problema.num_profesionales, problema.num_dias)
            if random.random() < pm:
                child = aplicar_mutaciones(child, problema)
            # repair
            matriz_child = child.reshape(problema.num_profesionales, problema.num_dias)
            matriz_child = problema._reparar_cromosoma(matriz_child)
            child = matriz_child.reshape(-1)
            new_pop.append(child)
        pop = new_pop[:pop_size]
        fitnesses = [problema.fitness(ind) for ind in pop]
        # update best
        best_idx = int(min(range(len(fitnesses)), key=lambda i: fitnesses[i]))
        if fitnesses[best_idx] < best_global_f:
            best_global_f = fitnesses[best_idx]
            best_global = pop[best_idx].copy()
        if gen % 5 == 0 or gen == 1:
            best, mean, std = population_stats(fitnesses)
            divers = diversity(pop)
            print(f"Gen {gen}: best={best:.4f}, mean={mean:.4f}, std={std:.4f}, diversity={divers}")

    end = time.time()
    print(f"GA propio finalizado in {end-start:.2f}s")
    print(f"Mejor fitness: {best_global_f}")
    matriz_final = best_global.reshape(problema.num_profesionales, problema.num_dias)
    matriz_final = problema._reparar_cromosoma(matriz_final)
    print("Matriz final reparada:")
    print(matriz_final.astype(int))