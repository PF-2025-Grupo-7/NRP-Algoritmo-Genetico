import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# ================= CONFIGURACIÓN =================
LOGS_DIR = "tests_logs"
OUTPUT_FILE = "tabla_consolidada_resultados.csv"
# Colores para los gráficos (Estilo Tesis)
PALETA = "Set2" 

def cargar_datos(directorio):
    registros = []
    print(f"Leyendo logs desde {directorio}...")
    
    if not os.path.exists(directorio):
        print(f"Error: No existe el directorio {directorio}")
        return pd.DataFrame()

    for root, dirs, files in os.walk(directorio):
        for file in files:
            if file == "metadatos.json":
                ruta_completa = os.path.join(root, file)
                try:
                    with open(ruta_completa, 'r') as f:
                        data = json.load(f)
                    
                    # Extraer info del nombre de la carpeta
                    nombre_carpeta = os.path.basename(root)
                    
                    # Separamos por _SEED_ para aislar el nombre del experimento
                    if "_SEED_" in nombre_carpeta:
                        partes = nombre_carpeta.split("_SEED_")
                        nombre_exp_sucio = partes[0]
                    else:
                        # Fallback por si la carpeta tiene mal formato
                        nombre_exp_sucio = nombre_carpeta

                    # --- LÓGICA DE CORRECCIÓN DE NOMBRES ---
                    if nombre_exp_sucio.startswith("BASE_"):
                        instancia = "BASE"
                        experimento = nombre_exp_sucio.replace("BASE_", "", 1) # Reemplaza solo la primera ocurrencia
                    
                    elif nombre_exp_sucio.startswith("AJUSTADA_"):
                        instancia = "AJUSTADA"
                        experimento = nombre_exp_sucio.replace("AJUSTADA_", "", 1)
                        
                    else:
                        # CASO SIN PREFIJO:
                        # Como sabemos que los BASE tienen prefijo obligatoriamente (por la migración),
                        # cualquier carpeta huérfana debe ser de la AJUSTADA.
                        instancia = "AJUSTADA"
                        experimento = nombre_exp_sucio
                    # ---------------------------------------

                    # Extraer métricas del JSON
                    stats = data['estadisticas_ejecucion']
                    params = data['parametros']
                    
                    registros.append({
                        "Instancia": instancia,
                        "Experimento": experimento,
                        "Seed": int(params.get('seed', 0)),
                        "Fitness": float(stats['mejor_fitness']),
                        "Tiempo_seg": float(stats['tiempo_total']),
                        "Generaciones": int(stats['generaciones']),
                        "Solucion_Valida": stats.get('solucion_valida', False)
                    })
                except Exception as e:
                    print(f"Error leyendo {ruta_completa}: {e}")
    
    return pd.DataFrame(registros)

def generar_resumen_estadistico(df):
    if df.empty: return
    
    print("\n--- RESUMEN ESTADÍSTICO (Promedio ± Desviación Estándar) ---")
    resumen = df.groupby(['Instancia', 'Experimento'])[['Fitness', 'Tiempo_seg']].agg(['mean', 'std'])
    print(resumen)
    
    # Guardar en CSV para el anexo de la tesis
    resumen.to_csv("resumen_estadistico_tesis.csv")
    print("-> Guardado 'resumen_estadistico_tesis.csv'")

def graficar_boxplots(df):
    if df.empty: return
    
    # Configuración de estilo
    sns.set_style("whitegrid")
    instancias = df['Instancia'].unique()
    
    for inst in instancias:
        df_inst = df[df['Instancia'] == inst]
        
        # 1. Gráfico de FITNESS
        plt.figure(figsize=(12, 6))
        sns.boxplot(data=df_inst, x='Experimento', y='Fitness', palette=PALETA, showfliers=True)
        plt.title(f"Distribución de Fitness - Instancia {inst}")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(f"boxplot_fitness_{inst}.png", dpi=300)
        plt.close()
        
        # 2. Gráfico de TIEMPO
        plt.figure(figsize=(12, 6))
        sns.boxplot(data=df_inst, x='Experimento', y='Tiempo_seg', palette=PALETA)
        plt.title(f"Distribución de Tiempo de Cómputo - Instancia {inst}")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(f"boxplot_tiempo_{inst}.png", dpi=300)
        plt.close()
        
    print(f"-> Gráficos generados: boxplot_fitness_*.png y boxplot_tiempo_*.png")

def test_significancia(df):
    """
    Realiza un test t de Student o Wilcoxon comparando cada variante contra el BASELINE.
    Útil para validar la hipótesis científica.
    """
    if df.empty: return
    
    print("\n--- ANÁLISIS DE SIGNIFICANCIA ESTADÍSTICA (vs BASELINE) ---")
    instancias = df['Instancia'].unique()
    
    for inst in instancias:
        print(f"\n>>> Instancia: {inst}")
        df_inst = df[df['Instancia'] == inst]
        
        baseline_data = df_inst[df_inst['Experimento'] == 'BASELINE']['Fitness']
        if baseline_data.empty:
            print("No se encontró data de BASELINE para comparar.")
            continue
            
        variantes = df_inst['Experimento'].unique()
        for var in variantes:
            if var == 'BASELINE': continue
            
            var_data = df_inst[df_inst['Experimento'] == var]['Fitness']
            
            # Test de Wilcoxon (no paramétrico, ideal para GA)
            # H0: Las distribuciones son iguales
            # p-value < 0.05 => Rechazo H0 (Hay diferencia significativa)
            if len(var_data) == len(baseline_data):
                stat, p_val = stats.wilcoxon(baseline_data, var_data)
                es_significativo = "SÍ" if p_val < 0.05 else "NO"
                mejor = "MEJOR" if var_data.mean() < baseline_data.mean() else "PEOR"
                
                print(f"  {var:20} | p-value: {p_val:.4f} | Sig: {es_significativo} ({mejor})")

if __name__ == "__main__":
    # 1. Cargar
    df = cargar_datos(LOGS_DIR)
    
    if not df.empty:
        # 2. Guardar Raw Data
        df.sort_values(by=['Instancia', 'Experimento', 'Seed']).to_csv(OUTPUT_FILE, index=False)
        print(f"-> Datos crudos guardados en '{OUTPUT_FILE}'")
        
        # 3. Analizar
        generar_resumen_estadistico(df)
        graficar_boxplots(df)
        test_significancia(df)
    else:
        print("No se encontraron datos para analizar.")