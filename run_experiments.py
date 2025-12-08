import os
import subprocess
import sys
import json
import pandas as pd
from datetime import datetime

# ================= CONFIGURACIÓN =================
PYTHON_EXE = sys.executable
SCRIPT_PATH = os.path.join("src", "main.py")
BASE_CONFIG_PATH = os.path.join("src", "data", "config_ga_default.json")
LOGS_DIR = "tests_logs"

# Semillas (1 al 30)
SEEDS = list(range(1, 31))

# --- AQUÍ DEFINIMOS QUÉ INSTANCIAS USAR PARA EL TESTING ---
# Recomendación: Usar Base y Ajustada para filtrar operadores.
INSTANCIAS_TEST = {
    "BASE": os.path.join("src", "data", "instancia_01_base.json"),
    "AJUSTADA": os.path.join("src", "data", "instancia_03_muy_ajustada.json")
}

# Configuración Baseline (Tu nueva default)
BASELINE = {
    "sel": "torneo_deterministico",
    "cross": "bloques_verticales",
    "mut": "hibrida_adaptativa",
    "pop_size": 100,
    "generaciones": 150 # Reducido por eficiencia
}

# Experimentos Fase A (Operadores)
EXPERIMENTOS = {
    # Variantes de Cruce
    "A1_Cross_Horizontal": {"cross": "bloques_horizontales"},
    "A1_Cross_TwoPoint":   {"cross": "dos_puntos"},

    # Variantes de Mutación
    "A2_Mut_Reasignar":    {"mut": "reasignar_turno"},
    "A2_Mut_Intercambio":  {"mut": "intercambio_dia"},
    "A2_Mut_Flip":         {"mut": "flip_simple"},

    # Variantes de Selección
    "A3_Sel_Ranking":      {"sel": "ranking_lineal"},
}

# ================= FUNCIONES =================

def ensure_config_file(pop_size, generaciones):
    """Crea config temporal si los params difieren del default."""
    with open(BASE_CONFIG_PATH, 'r') as f:
        data = json.load(f)
    
    data['pop_size'] = pop_size
    data['generaciones'] = generaciones
    
    temp_name = f"config_temp_p{pop_size}_g{generaciones}.json"
    temp_path = os.path.join("src", "data", temp_name)
    
    with open(temp_path, 'w') as f:
        json.dump(data, f)
        
    return temp_path

def run_simulation(inst_name, inst_path, exp_name, seed, params):
    # Tag incluye el nombre de la instancia ahora: BASE_A1_Cross_Horizontal_SEED_01
    tag = f"{inst_name}_{exp_name}_SEED_{seed:02d}"
    
    # Lógica incremental (Skip si existe)
    if os.path.exists(LOGS_DIR):
        existing = [d for d in os.listdir(LOGS_DIR) if d.startswith(tag)]
        if existing:
            print(f"[SKIP] {tag}")
            return

    # Preparar Config Temporal para Seed
    config_base = BASE_CONFIG_PATH
    if params['pop_size'] != 100 or params['generaciones'] != 150:
        config_base = ensure_config_file(params['pop_size'], params['generaciones'])

    with open(config_base, 'r') as f:
        cfg_data = json.load(f)
    cfg_data['seed'] = seed
    
    run_config_path = f"src/data/temp_config_{tag}.json"
    with open(run_config_path, 'w') as f:
        json.dump(cfg_data, f)

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--instancia", inst_path,
        "--config", run_config_path,
        "--sel", params['sel'],
        "--cross", params['cross'],
        "--mut", params['mut'],
        "--tag", tag
    ]

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Corriendo {tag}...")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error en {tag}: {e}")
    finally:
        if os.path.exists(run_config_path):
            os.remove(run_config_path)

def main():
    print(f"=== TESTING MULTI-INSTANCIA ({len(INSTANCIAS_TEST)} Instancias) ===")
    
    # Bucle Principal: Iteramos sobre Instancias
    for inst_name, inst_path in INSTANCIAS_TEST.items():
        print(f"\n >>> PROCESANDO INSTANCIA: {inst_name}")
        
        # 1. Baseline
        for seed in SEEDS:
            run_simulation(inst_name, inst_path, "BASELINE", seed, BASELINE)
            
        # 2. Experimentos
        for exp_name, changes in EXPERIMENTOS.items():
            params = BASELINE.copy()
            params.update(changes)
            for seed in SEEDS:
                run_simulation(inst_name, inst_path, exp_name, seed, params)

    print("\n=== FIN ===")
    generar_resumen_csv()

def generar_resumen_csv():
    registros = []
    if not os.path.exists(LOGS_DIR): return

    for carpeta in os.listdir(LOGS_DIR):
        if not os.path.isdir(os.path.join(LOGS_DIR, carpeta)): continue
        
        ruta_meta = os.path.join(LOGS_DIR, carpeta, "metadatos.json")
        if os.path.exists(ruta_meta):
            try:
                with open(ruta_meta, 'r') as f:
                    data = json.load(f)
                
                # Parsear el nombre de la carpeta para sacar Instancia y Experimento
                # Formato esperado: INSTANCIA_EXPERIMENTO_SEED_XX_TIMESTAMP
                parts = carpeta.split("_SEED_")
                prefix = parts[0] # Ej: BASE_A1_Cross_Horizontal
                
                # Intentamos separar la Instancia del Experimento
                instancia_detectada = "Unknown"
                experimento_detectado = prefix
                
                for k in INSTANCIAS_TEST.keys():
                    if prefix.startswith(k + "_"):
                        instancia_detectada = k
                        experimento_detectado = prefix.replace(k + "_", "")
                        break
                
                stats = data['estadisticas_ejecucion']
                ops = data['operadores_utilizados']
                
                registros.append({
                    "Instancia": instancia_detectada,
                    "Experimento": experimento_detectado,
                    "Seed": data['parametros'].get('seed'),
                    "Fitness": stats['mejor_fitness'],
                    "Tiempo(s)": stats['tiempo_total'],
                    "Generaciones": stats['generaciones'],
                    "Seleccion": ops['seleccion'],
                    "Cruce": ops['cruce'],
                    "Mutacion": ops['mutacion']
                })
            except: pass

    if registros:
        df = pd.DataFrame(registros)
        df.sort_values(by=["Instancia", "Experimento", "Seed"], inplace=True)
        df.to_csv("resumen_resultados_v2.csv", index=False)
        print("CSV Generado: resumen_resultados_v2.csv")

if __name__ == "__main__":
    main()