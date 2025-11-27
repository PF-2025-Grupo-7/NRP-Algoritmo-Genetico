# proyecto_rostering/ejecutar.py
import numpy as np
from mealpy import GA
from problema_rostering import ProblemaRostering

def cargar_datos_de_prueba():
    """
    Función de prueba para cargar datos de ejemplo.
    (Versión actualizada con los datos para las penalizaciones duras)
    """
    print("Cargando datos de prueba...")
    
    # 6 enfermeras, 7 días
    P = 6
    D = 7
    # 0=libre, 1=mañana, 2=tarde, 3=noche
    max_turno = 3
    turnos_a_cubrir = [1, 2, 3]
    skills_a_cubrir = ['junior', 'senior']
    
    # --- Info de Profesionales ---
    info_prof = [
        {'skill': 'senior', 't_min': 3, 't_max': 6}, # P0
        {'skill': 'junior', 't_min': 3, 't_max': 6}, # P1
        {'skill': 'junior', 't_min': 3, 't_max': 6}, # P2
        {'skill': 'senior', 't_min': 4, 't_max': 6}, # P3
        {'skill': 'junior', 't_min': 3, 't_max': 6}, # P4
        {'skill': 'senior', 't_min': 3, 't_max': 6}  # P5
        ]
    
    # --- Preferencias y Disponibilidad ---
    prefs = np.zeros((P, D))
    dispon = np.full((P, D), True) # Todos disponibles siempre
    
    # Ejemplo: P0 no disponible el día 2
    dispon[0, 2] = False
    
    # --- Requerimientos de Cobertura ---
    # (d, s, k) -> Requerido
    reqs = {}
    for d in range(D):
        reqs[d] = {}
        for s in turnos_a_cubrir:
            reqs[d][s] = {}
            if s == 1: # Mañana
                reqs[d][s]['junior'] = 1
                reqs[d][s]['senior'] = 1
            elif s == 2: # Tarde
                reqs[d][s]['junior'] = 1
                reqs[d][s]['senior'] = 0
            elif s == 3: # Noche
                reqs[d][s]['junior'] = 0
                reqs[d][s]['senior'] = 1
                
    # --- Secuencias Prohibidas (Enfermería) [cite: 96] ---
    sec_prohibidas = {(3, 1), (3, 2), (2, 1)}

    # --- Pesos del Fitness ---
    pesos = { 'eq': 1.0, 'dif': 1.5, 'pdl': 2.0, 'pte': 0.5 }
    
    return {
        "num_profesionales": P,
        "num_dias": D,
        "max_turno_val": max_turno,
        "info_profesionales": info_prof,
        "matriz_preferencias": prefs,
        "matriz_disponibilidad": dispon,
        "requerimientos_cobertura": reqs,
        "pesos_fitness": pesos,
        # --- Nuevos datos ---
        "secuencias_prohibidas": sec_prohibidas,
        "turnos_a_cubrir": turnos_a_cubrir,
        "skills_a_cubrir": skills_a_cubrir,
        # --- Datos Blandos requeridos por ProblemaRostering ---
        "duracion_turnos": {1: 8, 2: 8, 3: 8},
        "tolerancia_equidad_general": 8,
        "tolerancia_equidad_dificil": 4,
        "dias_no_habiles": set(),
        "turnos_noche": {3}
    }


# --- SCRIPT PRINCIPAL ---
if __name__ == "__main__":
    
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
        # --- Pasamos los nuevos datos ---
        secuencias_prohibidas=datos_problema["secuencias_prohibidas"],
        turnos_a_cubrir=datos_problema["turnos_a_cubrir"],
        skills_a_cubrir=datos_problema["skills_a_cubrir"],
        # --- Pasamos datos blandos obligatorios ---
        duracion_turnos=datos_problema["duracion_turnos"],
        tolerancia_equidad_general=datos_problema["tolerancia_equidad_general"],
        tolerancia_equidad_dificil=datos_problema["tolerancia_equidad_dificil"],
        dias_no_habiles=datos_problema["dias_no_habiles"],
        turnos_noche=datos_problema["turnos_noche"],
        log_to="console"
    )
    
    # ... (El resto del script para correr el GA es igual) ...
    epoch = 300
    pop_size = 200
    pc = 0.9
    pm = 0.3
    
    modelo_ga = GA.OriginalGA(epoch=epoch, pop_size=pop_size, pc=pc, pm=pm)
    
    print(f"Ejecutando GA con {epoch} generaciones y {pop_size} individuos...")
    g_best_agent = modelo_ga.solve(problema)

    print(f"Optimización finalizada.")
    print(f"Mejor penalización (fitness) encontrada: {g_best_agent.target.fitness}")

    # Recuperamos la solución cruda
    matriz_cruda = g_best_agent.solution.reshape(datos_problema["num_profesionales"], datos_problema["num_dias"])
    # La reparamos para mostrar el cronograma final válido
    matriz_solucion = problema._reparar_cromosoma(matriz_cruda)

    print("Mejor cronograma encontrado:")
    print(matriz_solucion.astype(int)) # Usamos astype(int) para que se vea mejor