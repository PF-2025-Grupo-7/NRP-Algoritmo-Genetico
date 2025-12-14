import os
import subprocess
import sys
import json
import pandas as pd
import re
import shutil
import time
from datetime import datetime

# ================= CONFIGURACIÓN =================
PYTHON_EXE = sys.executable
SCRIPT_PATH = os.path.join("src", "main.py")
BASE_CONFIG_PATH = os.path.join("src", "data", "config_ga_default.json")
LOGS_DIR = "tests_logs"
CARPETA_DESTINO = "FASE_C"

# Instancias de Escalabilidad
INSTANCIAS_FASE_C = {
    "C1_Escala_50": "src/data/instancia_04_escalabilidad_50.json",
    "C2_Escala_75": "src/data/instancia_05_escalabilidad_75.json",
    "C3_Escala_100": "src/data/instancia_06_escalabilidad_100.json"
}

# Configuración Ganadora (Fase B)
CONFIG_GANADORA = {
    "pop_size": 100,
    "generaciones": 150,
    "selection_strategy": "torneo_deterministico",
    "crossover_operator": "bloques_horizontales",
    "mutation_operator": "hibrida_adaptativa"
}

SEEDS = list(range(1, 31))

# ================= FUNCIONES =================

def crear_config_temporal(exp_name, seed):
    with open(BASE_CONFIG_PATH, 'r') as f:
        data = json.load(f)
    
    data.update(CONFIG_GANADORA)
    data['seed'] = seed
    
    temp_filename = f"temp_cfg_{exp_name}_{seed}.json"
    temp_path = os.path.join("src", "data", temp_filename)
    with open(temp_path, 'w') as f:
        json.dump(data, f)
    return temp_path

def analizar_validez(ruta_reporte):
    es_valido = False
    violaciones_duras = -1
    if os.path.exists(ruta_reporte):
        try:
            with open(ruta_reporte, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r"Violaciones Pref\. Libres:\s*([\d\.]+)", content)
                if match:
                    violaciones_duras = float(match.group(1))
                    if violaciones_duras == 0.0:
                        es_valido = True
        except: pass
    return es_valido, violaciones_duras

def run_fase_c():
    print(f"=== INICIANDO FASE C: ESCALABILIDAD ===")
    print(f"Salida: {os.path.join(LOGS_DIR, CARPETA_DESTINO)}\n")
    
    os.makedirs(os.path.join(LOGS_DIR, CARPETA_DESTINO), exist_ok=True)
    
    # --- CORRECCIÓN AQUÍ ---
    total = len(INSTANCIAS_FASE_C) * len(SEEDS) 
    
    contador = 0
    resultados = []

    for nombre_instancia, ruta_instancia in INSTANCIAS_FASE_C.items():
        if not os.path.exists(ruta_instancia):
            print(f"❌ ALERTA: No se encuentra {ruta_instancia}")
            continue

        print(f">>> GRUPO: {nombre_instancia}")
        
        for seed in SEEDS:
            contador += 1
            slug = f"{nombre_instancia}_SEED_{seed:02d}"
            
            ruta_final = os.path.join(LOGS_DIR, CARPETA_DESTINO, slug)
            if os.path.exists(ruta_final):
                print(f"[{contador}/{total}] SKIP: {slug}")
                try:
                    meta = os.path.join(ruta_final, "metadatos.json")
                    rep = os.path.join(ruta_final, "reporte_solucion.txt")
                    with open(meta, 'r') as f: d = json.load(f)
                    valido, v_duras = analizar_validez(rep)
                    resultados.append({
                        "Escenario": nombre_instancia,
                        "Seed": seed,
                        "Fitness": d['estadisticas_ejecucion']['mejor_fitness'],
                        "Tiempo_s": d['estadisticas_ejecucion']['tiempo_total'],
                        "Es_Valido": valido
                    })
                except: pass
                continue

            cfg_path = crear_config_temporal(nombre_instancia, seed)
            print(f"[{contador}/{total}] Ejecutando {slug}...", end=" ", flush=True)
            start_t = time.time()
            
            cmd = [PYTHON_EXE, SCRIPT_PATH, "--instancia", ruta_instancia, "--config", cfg_path, "--tag", slug]
            
            env = os.environ.copy()
            env['LOGS_TARGET_DIR'] = os.path.abspath(os.path.join(LOGS_DIR, CARPETA_DESTINO))
            env['LOGS_FORCE_EXACT_NAME'] = '1'
            env['LOGS_FORCE_NAME'] = slug

            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
                print(f"✅ ({time.time() - start_t:.1f}s)")
                
                # Recolectar datos
                if os.path.exists(os.path.join(ruta_final, "metadatos.json")):
                    with open(os.path.join(ruta_final, "metadatos.json"), 'r') as f: d = json.load(f)
                    valido, _ = analizar_validez(os.path.join(ruta_final, "reporte_solucion.txt"))
                    resultados.append({
                        "Escenario": nombre_instancia,
                        "Seed": seed,
                        "Fitness": d['estadisticas_ejecucion']['mejor_fitness'],
                        "Tiempo_s": d['estadisticas_ejecucion']['tiempo_total'],
                        "Es_Valido": valido
                    })

            except Exception as e:
                print(f"❌ ERROR: {e}")
            finally:
                if os.path.exists(cfg_path): os.remove(cfg_path)

    if resultados:
        df = pd.DataFrame(resultados)
        df.to_csv("resumen_fase_c.csv", index=False)
        print("\n=== RESUMEN DE FACTIBILIDAD ===")
        print(df.groupby("Escenario")["Es_Valido"].mean() * 100)

if __name__ == "__main__":
    run_fase_c()