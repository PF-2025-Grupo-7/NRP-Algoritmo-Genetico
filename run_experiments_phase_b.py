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
CARPETA_DESTINO = "FASE_B" 

# Instancia
INSTANCIA_PATH = os.path.join("src", "data", "instancia_03_muy_ajustada.json")

# Semillas
SEEDS = list(range(1, 31))

# Configuración
CONFIG_GANADORA = {
    "sel": "torneo_deterministico",
    "cross": "bloques_horizontales", 
    "mut": "hibrida_adaptativa",
    "generaciones": 150 
}

EXPERIMENTOS_FASE_B = {
    "B1_Pop_50":  {"pop_size": 50},
    "B1_Pop_100": {"pop_size": 100},
    "B1_Pop_200": {"pop_size": 200}
}

# ================= FUNCIONES =================

def crear_config_temporal(exp_name, seed, overrides):
    with open(BASE_CONFIG_PATH, 'r') as f:
        data = json.load(f)
    data['seed'] = seed
    for k, v in overrides.items():
        data[k] = v
    temp_filename = f"temp_{exp_name}_{seed}.json"
    temp_path = os.path.join("src", "data", temp_filename)
    with open(temp_path, 'w') as f:
        json.dump(data, f)
    return temp_path

def buscar_y_mover_resultado(slug):
    """
    Busca recursivamente en tests_logs cualquier carpeta que empiece con el slug
    y la mueve a tests_logs/FASE_B.
    """
    ruta_destino_final = os.path.join(LOGS_DIR, CARPETA_DESTINO)
    if not os.path.exists(ruta_destino_final):
        os.makedirs(ruta_destino_final)

    # Esperar un momento para asegurar que el SO actualizó el sistema de archivos
    time.sleep(1)

    candidatos = []

    # BARRIDO COMPLETO: Miramos en las carpetas donde `main.py` puede haber creado logs.
    # Originalmente buscamos en `tests_logs`, pero `src/main.py` crea en `logs/`.
    search_roots = [LOGS_DIR, "logs"]
    # Construir prefijos alternativos para el slug (ej: B1_Pop_50_SEED_01 -> P50_SEED_01)
    alt_prefixes = [slug]
    m = re.search(r"Pop_(\d+)", slug)
    if m:
        pop_n = m.group(1)
        # patrón en logs: P{pop}_SEED_01_2025...
        seed_part = None
        mseed = re.search(r"SEED_(\d{2})", slug)
        if mseed:
            seed_part = mseed.group(1)
        if seed_part:
            alt_prefixes.append(f"P{pop_n}_SEED_{seed_part}")

    for search_root in search_roots:
        if not os.path.exists(search_root):
            continue
        for root, dirs, files in os.walk(search_root):
            for directory in dirs:
                # aceptar cualquiera de los prefijos (slug original o alternativos)
                if any(directory.startswith(p) for p in alt_prefixes):
                    full_path = os.path.join(root, directory)

                    # Si ya está en la carpeta destino, lo ignoramos (ya está hecho)
                    if os.path.abspath(root) == os.path.abspath(ruta_destino_final):
                        return True

                    # Guardamos fecha de modificación para coger el más reciente
                    candidatos.append((full_path, os.path.getmtime(full_path)))

    if not candidatos:
        return False

    # Tomar el más reciente (por si hubo ejecuciones fallidas antes)
    carpeta_a_mover = max(candidatos, key=lambda x: x[1])[0]
    nombre_carpeta = os.path.basename(carpeta_a_mover)
    destino_carpeta = os.path.join(ruta_destino_final, nombre_carpeta)

    try:
        # Si existe una carpeta igual en destino (de una prueba fallida), borrarla
        if os.path.exists(destino_carpeta):
            shutil.rmtree(destino_carpeta)
        
        # Copiamos la carpeta completa para conservar el original en `logs`.
        # Esto preserva el nombre y todo su contenido (metadatos, reporte, csvs, etc.).
        shutil.copytree(carpeta_a_mover, destino_carpeta, dirs_exist_ok=True)
        return True
    except Exception as e:
        print(f"❌ Error crítico moviendo archivos: {e}")
        return False

def ya_existe_en_destino(slug):
    """Verifica si ya tenemos resultados válidos en FASE_B para no repetir."""
    ruta_fase_b = os.path.join(LOGS_DIR, CARPETA_DESTINO)
    if not os.path.exists(ruta_fase_b): return False
    
    for item in os.listdir(ruta_fase_b):
        if item.startswith(slug):
            if os.path.exists(os.path.join(ruta_fase_b, item, "metadatos.json")):
                return True
    return False

def extraer_datos_txt(ruta_txt):
    """Parsea el reporte de texto."""
    datos = {"Cob": None, "Pref": None, "Eq": None, "Gen_Hallazgo": None}
    if not os.path.exists(ruta_txt): return datos
    try:
        with open(ruta_txt, 'r', encoding='utf-8') as f:
            texto = f.read()
            m_cob = re.search(r'(?:Cobertura|Coverage).*?:\s*([\d\.]+)', texto, re.IGNORECASE)
            if m_cob: datos["Cob"] = float(m_cob.group(1))
            m_pref = re.search(r'(?:Preferencias|Preferences).*?:\s*([\d\.]+)', texto, re.IGNORECASE)
            if m_pref: datos["Pref"] = float(m_pref.group(1))
            m_eq = re.search(r'(?:Equidad|Equity).*?:\s*([\d\.]+)', texto, re.IGNORECASE)
            if m_eq: datos["Eq"] = float(m_eq.group(1))
            m_gen = re.search(r'(?:generación|generation).*?encontrada.*?:\s*(\d+)', texto, re.IGNORECASE)
            if m_gen: datos["Gen_Hallazgo"] = int(m_gen.group(1))
    except: pass
    return datos

def run_fase_b():
    print(f"=== INICIANDO FASE B ===")
    print(f"Los resultados se moverán a: {os.path.join(LOGS_DIR, CARPETA_DESTINO)}\n")
    
    total = len(EXPERIMENTOS_FASE_B) * len(SEEDS)
    i = 0

    for exp_name, params in EXPERIMENTOS_FASE_B.items():
        print(f">>> GRUPO: {exp_name} (Poblacion: {params['pop_size']})")
        
        for seed in SEEDS:
            i += 1
            slug = f"{exp_name}_SEED_{seed:02d}"
            
            # 1. Chequear si ya está hecho
            if ya_existe_en_destino(slug):
                print(f"[{i}/{total}] SKIP: {slug} (Ya existe en {CARPETA_DESTINO})")
                continue

            # 2. Configurar
            overrides = {
                "generaciones": CONFIG_GANADORA["generaciones"],
                "pop_size": params["pop_size"],
                "selection_strategy": CONFIG_GANADORA["sel"],
                "crossover_operator": CONFIG_GANADORA["cross"],
                "mutation_operator": CONFIG_GANADORA["mut"]
            }
            cfg_path = crear_config_temporal(exp_name, seed, overrides)

            # 3. Ejecutar
            # Usamos solo el slug como tag. Main.py creará la carpeta donde quiera.
            cmd = [PYTHON_EXE, SCRIPT_PATH, "--instancia", INSTANCIA_PATH, "--config", cfg_path, "--tag", slug]
            
            print(f"[{i}/{total}] Ejecutando {slug}...", end=" ", flush=True)
            
            try:
                # Antes de ejecutar, decidimos el nombre de carpeta deseado en tests_logs/FASE_B
                destino_fase_b = os.path.join(LOGS_DIR, CARPETA_DESTINO)
                os.makedirs(destino_fase_b, exist_ok=True)

                # Prefijo que usamos para comparar (poblacion en formato P{n}_SEED_{xx})
                pref_alt = f"P{params['pop_size']}_SEED_{seed:02d}"

                # Si ya existe alguna carpeta en tests_logs/FASE_B que empiece con pref_alt, saltamos
                existe = False
                for it in os.listdir(destino_fase_b):
                    if it.startswith(pref_alt):
                        existe = True
                        break

                if existe:
                    print("SKIP (ya existe en tests_logs/FASE_B)")
                else:
                    # Creamos nombre con timestamp similar al formato que usas
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    forced_name = f"{pref_alt}_{ts}"

                    # Preparamos variables de entorno para forzar creación en tests_logs/FASE_B
                    env = os.environ.copy()
                    env['LOGS_TARGET_DIR'] = os.path.abspath(destino_fase_b)
                    env['LOGS_FORCE_EXACT_NAME'] = '1'
                    env['LOGS_FORCE_NAME'] = forced_name

                    # Ejecutamos el script hijo con las vars de entorno (creará la carpeta en tests_logs/FASE_B)
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
                    print(f"✅ OK -> {forced_name}")

            except subprocess.CalledProcessError as e:
                print(f"\n❌ FALLO EL SCRIPT: {e}")
                # Si quieres ver el error real descomenta esto:
                # print(e.stderr.decode())
            finally:
                if os.path.exists(cfg_path): os.remove(cfg_path)

    generar_csv_final()

def generar_csv_final():
    print("\nGenerando CSV Final...")
    ruta_datos = os.path.join(LOGS_DIR, CARPETA_DESTINO)
    filas = []
    
    if not os.path.exists(ruta_datos):
        print("No hay datos para procesar.")
        return

    for item in os.listdir(ruta_datos):
        full_p = os.path.join(ruta_datos, item)
        if os.path.isdir(full_p):
            meta = os.path.join(full_p, "metadatos.json")
            rep = os.path.join(full_p, "reporte_solucion.txt")
            
            if os.path.exists(meta):
                try:
                    with open(meta, 'r') as f: d = json.load(f)
                    txt = extraer_datos_txt(rep)
                    
                    nombre_exp = item.split('_SEED_')[0]
                    stats = d.get('estadisticas_ejecucion', {})
                    
                    filas.append({
                        "Experimento": nombre_exp,
                        "Seed": d['parametros']['seed'],
                        "Poblacion": d['parametros']['poblacion'],
                        "Fitness": stats.get('mejor_fitness'),
                        "Tiempo": stats.get('tiempo_total'),
                        "Gen_Hallazgo": txt["Gen_Hallazgo"] if txt["Gen_Hallazgo"] else stats.get('generaciones'),
                        "Cob": txt["Cob"], "Pref": txt["Pref"], "Eq": txt["Eq"]
                    })
                except: pass

    if filas:
        df = pd.DataFrame(filas)
        df.sort_values(by=["Poblacion", "Seed"], inplace=True)
        df.to_csv("resumen_fase_b.csv", index=False)
        print(f"CSV guardado: resumen_fase_b.csv ({len(df)} registros)")

if __name__ == "__main__":
    run_fase_b()