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
    # Create a per-instance folder: tests_logs/<inst_name>/<exp>_SEED_##
    slug = f"{exp_name}_SEED_{seed:02d}"
    tag_path = os.path.join(inst_name, slug)

    # Lógica incremental: buscar recursivamente metadatos.json en tests_logs
    if os.path.exists(LOGS_DIR):
        for root, dirs, files in os.walk(LOGS_DIR):
            if 'metadatos.json' in files:
                meta_path = os.path.join(root, 'metadatos.json')
                try:
                    with open(meta_path, 'r') as mf:
                        meta = json.load(mf)
                    m_seed = meta.get('parametros', {}).get('seed')
                    ops = meta.get('operadores_utilizados', {})
                    m_sel = ops.get('seleccion')
                    m_cross = ops.get('cruce')
                    m_mut = ops.get('mutacion')

                    if m_seed == seed and m_sel == params.get('sel') and m_cross == params.get('cross') and m_mut == params.get('mut'):
                        # Asegurarnos de que la metadata encontrada pertenezca a la misma instancia
                        try:
                            rel = os.path.relpath(root, LOGS_DIR)
                            top = rel.split(os.sep)[0]
                        except Exception:
                            top = None

                        if top == inst_name:
                            print(f"[SKIP] {inst_name}_{slug} (found existing run in {root})")
                            return
                except Exception:
                    continue

    # Preparar Config Temporal para Seed
    config_base = BASE_CONFIG_PATH
    if params['pop_size'] != 100 or params['generaciones'] != 150:
        config_base = ensure_config_file(params['pop_size'], params['generaciones'])

    with open(config_base, 'r') as f:
        cfg_data = json.load(f)
    cfg_data['seed'] = seed
    
    # Use slug (no path separators) for temp filenames
    run_config_path = f"src/data/temp_config_{slug}.json"
    with open(run_config_path, 'w') as f:
        json.dump(cfg_data, f)

    cmd = [
        PYTHON_EXE, SCRIPT_PATH,
        "--instancia", inst_path,
        "--config", run_config_path,
        "--sel", params['sel'],
        "--cross", params['cross'],
        "--mut", params['mut'],
        # Pass tag including instance as a path so the runner creates tests_logs/<inst>/<run>
        "--tag", tag_path
    ]

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Corriendo {inst_name}_{slug}...")
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
    # Recorremos recursivamente y recopilamos todos los metadatos
    for root, dirs, files in os.walk(LOGS_DIR):
        if 'metadatos.json' in files:
            ruta_meta = os.path.join(root, 'metadatos.json')
            try:
                with open(ruta_meta, 'r') as f:
                    data = json.load(f)

                # Determinar instancia a partir de la ruta relativa: tests_logs/<INSTANCIA>/...
                try:
                    rel = os.path.relpath(root, LOGS_DIR)
                    parts = rel.split(os.sep)
                    instancia_detectada = parts[0] if parts and parts[0] else 'Unknown'
                except Exception:
                    instancia_detectada = 'Unknown'

                # El nombre de la carpeta del run suele ser el último segmento
                run_folder = os.path.basename(root)
                prefix = run_folder.split('_SEED_')[0]
                experimento_detectado = prefix
                # Si el prefijo incluye el nombre de la instancia, lo limpiamos
                if experimento_detectado.startswith(instancia_detectada + '_'):
                    experimento_detectado = experimento_detectado.replace(instancia_detectada + '_', '', 1)

                stats = data.get('estadisticas_ejecucion', {})
                ops = data.get('operadores_utilizados', {})

                registros.append({
                    "Instancia": instancia_detectada,
                    "Experimento": experimento_detectado,
                    "Seed": data.get('parametros', {}).get('seed'),
                    "Fitness": stats.get('mejor_fitness'),
                    "Tiempo(s)": stats.get('tiempo_total'),
                    "Generaciones": stats.get('generaciones'),
                    "Seleccion": ops.get('seleccion'),
                    "Cruce": ops.get('cruce'),
                    "Mutacion": ops.get('mutacion')
                })
            except Exception:
                continue

    if registros:
        df = pd.DataFrame(registros)
        df.sort_values(by=["Instancia", "Experimento", "Seed"], inplace=True)
        # Guardar CSV completo y uno filtrado para BASE
        df.to_csv("resumen_resultados_v2.csv", index=False)
        # Filtrar y guardar CSV para BASE
        df_base = df[df['Instancia'] == 'BASE']
        if not df_base.empty:
            df_base.to_csv('resumen_resultados_base.csv', index=False)
            print('CSV Generado: resumen_resultados_base.csv')
        # Filtrar y guardar CSV para AJUSTADA
        df_ajustada = df[df['Instancia'] == 'AJUSTADA']
        if not df_ajustada.empty:
            df_ajustada.to_csv('resumen_resultados_ajustada.csv', index=False)
            print('CSV Generado: resumen_resultados_ajustada.csv')
        print('CSV Generado: resumen_resultados_v2.csv')

if __name__ == "__main__":
    main()