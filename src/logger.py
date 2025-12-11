import os
import datetime
import json
import numpy as np

def crear_estructura_logs(prefix="run"):
    """
    Crea la carpeta de logs.
    Ahora usamos un prefijo genérico por defecto ('run') o 'test' para batchs.
    """
    # Permitir anular la carpeta base y el nombre desde variables de entorno
    # LOGS_TARGET_DIR: ruta absoluta donde crear la carpeta (si no, por defecto '../logs')
    # LOGS_FORCE_EXACT_NAME: '1' para usar LOGS_FORCE_NAME sin añadir timestamp
    # LOGS_FORCE_NAME: nombre exacto de carpeta a crear cuando LOGS_FORCE_EXACT_NAME=='1'
    env_target = os.environ.get('LOGS_TARGET_DIR')
    if env_target:
        base_dir = os.path.abspath(env_target)
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))

    force_exact = os.environ.get('LOGS_FORCE_EXACT_NAME') == '1'
    force_name = os.environ.get('LOGS_FORCE_NAME')

    if force_exact and force_name:
        nombre_carpeta = force_name
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_carpeta = f"{prefix}_{timestamp}"

    ruta_log = os.path.join(base_dir, nombre_carpeta)

    os.makedirs(ruta_log, exist_ok=True)
    return ruta_log

def guardar_resultados(ruta_log, config, operadores, estadisticas, matriz_final, problema):
    """
    Guarda metadatos completos incluyendo qué operadores se usaron.
    Args:
        operadores (dict): {'seleccion': 'torneo', 'cruce': '...', 'mutacion': '...'}
    """
    
    # Prepara la configuración para serializar (sets a listas)
    config_serializable = {}
    for k, v in config.items():
        if isinstance(v, set):
            config_serializable[k] = list(v)
        else:
            config_serializable[k] = v

    metadatos = {
        "fecha": datetime.datetime.now().isoformat(),
        "contexto": {
            "algoritmo": "GA_Genetico_NRP",
            "version": "2.0 (Systematic Testing Ready)"
        },
        "operadores_utilizados": operadores,  # <--- NUEVO: Trazabilidad total
        "parametros": config_serializable,
        "estadisticas_ejecucion": estadisticas
    }

    # Guardar JSON
    with open(os.path.join(ruta_log, "metadatos.json"), "w", encoding='utf-8') as f:
        json.dump(metadatos, f, indent=4, ensure_ascii=False)

    # GUARDAR REPORTE DE SOLUCIÓN
    with open(os.path.join(ruta_log, "reporte_solucion.txt"), "w", encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write(f" REPORTE DE EJECUCIÓN - {datetime.datetime.now()}\n")
        f.write("="*60 + "\n\n")
        
        f.write(f"Fitness Final: {estadisticas['mejor_fitness']:.4f}\n")
        f.write(f"Tiempo Total:  {estadisticas['tiempo_total']:.2f} segundos\n")
        f.write(f"Generaciones:  {estadisticas['generaciones']}\n")
        f.write(f"Operadores: {operadores['cruce']} + {operadores['mutacion']}\n")
        f.write("-" * 60 + "\n\n")

        f.write("--- ANÁLISIS DE PENALIZACIONES ---\n")
        # Calculamos el desglose usando los métodos del problema
        # Nota: Asumimos que la matriz ya viene reparada
        pen_eq = problema._calcular_pen_equidad_general(matriz_final)
        pen_dif = problema._calcular_pen_equidad_dificiles(matriz_final)
        pen_pdl = problema._calcular_pen_pdl(matriz_final)
        pen_pte = problema._calcular_pen_pte(matriz_final)
        
        f.write(f"Equidad General (0-1):  {pen_eq:.4f}\n")
        f.write(f"Equidad Difíciles (0-1):{pen_dif:.4f}\n")
        f.write(f"Violaciones Pref. Libres: {pen_pdl}\n")
        f.write(f"Violaciones Pref. Turno:  {pen_pte}\n")
        f.write("\n")

        f.write("--- CRONOGRAMA FINAL ---\n")
        f.write("Ref: 0=Libre, 1=Mañana, 2=Tarde, 3=Noche\n\n")
        
        # Cabecera de días
        f.write("PROF   |")
        for d in range(problema.num_dias):
            f.write(f"{d+1:02d} ")
        f.write("|\n")
        f.write("-" * (7 + problema.num_dias * 3) + "\n")

        # Filas de profesionales
        for p in range(problema.num_profesionales):
            skill = problema.info_profesionales[p]['skill'][0].upper() # S o J
            f.write(f"P{p:02d} ({skill})|")
            for d in range(problema.num_dias):
                turno = int(matriz_final[p, d])
                if turno == 0:
                    char = "."
                else:
                    char = str(turno)
                f.write(f" {char} ")
            f.write("|\n")