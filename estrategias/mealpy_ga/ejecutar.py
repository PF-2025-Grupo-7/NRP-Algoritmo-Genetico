import os
import sys
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import random
import numpy as np
from mealpy import GA
from problema_rostering import ProblemaRostering

def cargar_datos_de_prueba():
    """
    Función de prueba para cargar datos de ejemplo.

    """
    print("Cargando datos de prueba...")
    
    # --- 1. Configuración General ---
    P = 18  # 18 profesionales
    D = 30  # 30 días
    max_turno = 3
    turnos_a_cubrir = [1, 2, 3] # Mañana, Tarde, Noche
    skills_a_cubrir = ['junior', 'senior']
    
    # --- 2. Info de Profesionales ---
    # 10 Seniors y 8 Juniors.
    # Establecemos t_min=12 y t_max=16.
    
    info_prof = []
    for i in range(P):
        skill = 'senior' if i < 10 else 'junior' 
        info_prof.append({
            'skill': skill,
            't_min': 12, 
            't_max': 16 
        })

    # --- 3. Días Difíciles (Fines de Semana) ---
    dias_no_habiles = set()
    for d in range(D):
        if d % 7 == 5 or d % 7 == 6: # Sábado o Domingo
            dias_no_habiles.add(d)

    # --- 4. Requerimientos de Cobertura ---
    # Lunes y Viernes: ALTA demanda 
    # Resto semana: MEDIA demanda.
    # Fin de semana: BAJA demanda (pero difícil de cubrir por penalización).
    
    reqs = {}
    total_demand = 0
    
    for d in range(D):
        reqs[d] = {}
        dia_semana = d % 7
        
        # Determinar perfil del día
        es_pico = (dia_semana == 0 or dia_semana == 4) # Lunes(0) o Viernes(4)
        es_finde = (d in dias_no_habiles)
        
        for s in turnos_a_cubrir:
            reqs[d][s] = {}
            # Lógica de cobertura por turno
            if s == 1: # Mañana
                if es_pico:
                    j, sr = 2, 2 
                elif es_finde:
                    j, sr = 1, 1 
                else:
                    j, sr = 2, 1 
            elif s == 2: # Tarde
                if es_pico:
                    j, sr = 2, 1 
                elif es_finde:
                    j, sr = 1, 1 
                else:
                    j, sr = 1, 1 
            elif s == 3: # Noche 
                j, sr = 1, 1 
            
            reqs[d][s]['junior'] = j
            reqs[d][s]['senior'] = sr
            total_demand += (j + sr)

    print(f"Demanda Total de Turnos calculada: {total_demand}")
    print(f"Capacidad Máxima del equipo: {18 * 16} (t_max=16 * 18 pers)")

    # --- 5. Disponibilidad ---
    dispon = np.full((P, D), True)
    
    # P0: Vacaciones primera semana
    dispon[0, 0:7] = False
    # P6: Vacaciones superpuestas (días 5-10)
    dispon[6, 5:11] = False
    # P11: Baja médica fin de mes
    dispon[11, 25:30] = False
    # P3: No puede trabajar ningún fin de semana (Curso de posgrado)
    for d in dias_no_habiles:
        dispon[3, d] = False

    # --- 6. Preferencias ---
    prefs = np.zeros((P, D))
    
    # Día 15, 3 Seniors piden el día libre.
    prefs[0, 15] = -1
    prefs[1, 15] = -1
    prefs[2, 15] = -1
    
    # P8 y P9 (Juniors) quieren el Turno Mañana el Día 20.
    prefs[8, 20] = 1
    prefs[9, 20] = 1
    
    # P5 pide NOCHE el día 5, 6 y 7 (quiere acumular plus nocturno).
    prefs[5, 5] = 3
    prefs[5, 6] = 3
    prefs[5, 7] = 3

    # --- 7. Secuencias Prohibidas ---
    sec_prohibidas = {(3, 1), (3, 2), (2, 1)}

    # --- 8. Pesos ---
    pesos = { 'eq': 1.0, 'dif': 1.5, 'pdl': 2.0, 'pte': 0.5, 'alpha_pte': 0.5 }
    
    return {
        "num_profesionales": P,
        "num_dias": D,
        "max_turno_val": max_turno,
        "info_profesionales": info_prof,
        "matriz_preferencias": prefs,
        "matriz_disponibilidad": dispon,
        "requerimientos_cobertura": reqs,
        "pesos_fitness": pesos,
        "secuencias_prohibidas": sec_prohibidas,
        "turnos_a_cubrir": turnos_a_cubrir,
        "skills_a_cubrir": skills_a_cubrir,
        "duracion_turnos": {1: 8, 2: 8, 3: 8},
        "tolerancia_equidad_general": 8,
        "tolerancia_equidad_dificil": 4,
        "dias_no_habiles": dias_no_habiles,
        "turnos_noche": {3}
    }


# --- SCRIPT PRINCIPAL ---
if __name__ == "__main__":

    SEED = 1234
    np.random.seed(SEED)
    random.seed(SEED)
    
    print(f"Iniciando ejecución con semilla fija: {SEED}")
    
    datos_problema = cargar_datos_de_prueba()
    
    problema = ProblemaRostering(
        num_profesionales=datos_problema["num_profesionales"],
        num_dias=datos_problema["num_dias"],
        max_turno_val=datos_problema["max_turno_val"],
        info_profesionales=datos_problema["info_profesionales"],
        matriz_preferencias=datos_problema["matriz_preferencias"],
        matriz_disponibilidad=datos_problema["matriz_disponibilidad"],
        requerimientos_cobertura=datos_problema["requerimientos_cobertura"],
        pesos_fitness=datos_problema["pesos_fitness"],
        secuencias_prohibidas=datos_problema["secuencias_prohibidas"],
        turnos_a_cubrir=datos_problema["turnos_a_cubrir"],
        skills_a_cubrir=datos_problema["skills_a_cubrir"],
        duracion_turnos=datos_problema["duracion_turnos"],
        tolerancia_equidad_general=datos_problema["tolerancia_equidad_general"],
        tolerancia_equidad_dificil=datos_problema["tolerancia_equidad_dificil"],
        dias_no_habiles=datos_problema["dias_no_habiles"],
        turnos_noche=datos_problema["turnos_noche"], 
        log_to="console"
    )

    epoch = 150
    pop_size = 400 
    pc = 0.9
    pm = 0.3
    
    modelo_ga = GA.OriginalGA(epoch=epoch, pop_size=pop_size, pc=pc, pm=pm)
    
    print(f"Ejecutando GA para instancia compleja ({datos_problema['num_profesionales']} enfermeros)...")
    
    g_best_agent = modelo_ga.solve(problema, seed=SEED, mode="single")

    print(f"Optimización finalizada.")
    print(f"Mejor penalización (fitness) encontrada: {g_best_agent.target.fitness}")

    # Recuperamos la solución cruda
    matriz_cruda = g_best_agent.solution.reshape(datos_problema["num_profesionales"], datos_problema["num_dias"])
    # La reparamos para mostrar el cronograma final válido
    matriz_solucion = problema._reparar_cromosoma(matriz_cruda)

    print("Mejor cronograma encontrado:")
    print(matriz_solucion.astype(int))