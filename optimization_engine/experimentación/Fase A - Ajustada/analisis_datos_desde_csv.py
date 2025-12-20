import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# ================= CONFIGURACIÓN =================
INPUT_CSV = "tabla_corregida.csv"  # Nombre de tu archivo corregido
# Colores para los gráficos (Estilo Tesis)
PALETA = "Set2" 

def cargar_datos_desde_csv(ruta_csv):
    print(f"Leyendo datos desde '{ruta_csv}'...")
    
    if not os.path.exists(ruta_csv):
        print(f"Error: No existe el archivo {ruta_csv}")
        return pd.DataFrame()

    try:
        # Leemos el CSV indicando que el separador decimal es la coma ','
        # y el separador de columnas es coma ',' (formato estándar CSV)
        df = pd.read_csv(ruta_csv, decimal=',')
        
        # Renombrar columnas para que coincidan con las que espera el resto del script
        # "Tiempo (s)" -> "Tiempo_seg"
        df.rename(columns={'Tiempo (s)': 'Tiempo_seg'}, inplace=True)
        
        # Convertir Solucion_Valida a booleano real si viene como texto
        if df['Solucion_Valida'].dtype == 'object':
             df['Solucion_Valida'] = df['Solucion_Valida'].astype(str).str.upper() == 'TRUE'
             
        print(f"-> Cargados {len(df)} registros correctamente.")
        return df
        
    except Exception as e:
        print(f"Error procesando el CSV: {e}")
        return pd.DataFrame()

def generar_resumen_estadistico(df):
    if df.empty: return
    
    print("\n--- RESUMEN ESTADÍSTICO (Promedio ± Desviación Estándar) ---")
    # Agrupamos y calculamos media y desviación estándar
    resumen = df.groupby(['Instancia', 'Experimento'])[['Fitness', 'Tiempo_seg']].agg(['mean', 'std'])
    print(resumen)
    
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
    Realiza un test de Wilcoxon comparando cada variante contra el BASELINE.
    Requiere que existan las mismas semillas para ambos grupos.
    """
    if df.empty: return
    
    print("\n--- ANÁLISIS DE SIGNIFICANCIA ESTADÍSTICA (vs BASELINE) ---")
    instancias = df['Instancia'].unique()
    
    for inst in instancias:
        print(f"\n>>> Instancia: {inst}")
        df_inst = df[df['Instancia'] == inst]
        
        # Extraer datos del Baseline ordenados por semilla para alinear pares
        baseline_df = df_inst[df_inst['Experimento'] == 'BASELINE'].sort_values('Seed')
        baseline_data = baseline_df['Fitness'].values
        
        if len(baseline_data) == 0:
            print("No se encontró data de BASELINE para comparar.")
            continue
            
        variantes = df_inst['Experimento'].unique()
        for var in variantes:
            if var == 'BASELINE': continue
            
            var_df = df_inst[df_inst['Experimento'] == var].sort_values('Seed')
            var_data = var_df['Fitness'].values
            
            # Verificación de integridad: deben tener el mismo número de muestras
            if len(var_data) == len(baseline_data):
                try:
                    stat, p_val = stats.wilcoxon(baseline_data, var_data)
                    es_significativo = "SÍ" if p_val < 0.05 else "NO"
                    # Comparamos medias para saber quién ganó
                    mejor = "MEJOR" if var_data.mean() < baseline_data.mean() else "PEOR"
                    
                    print(f"  {var:20} | p-value: {p_val:.4f} | Sig: {es_significativo} ({mejor})")
                except Exception as e:
                    print(f"  {var:20} | No se pudo calcular (datos idénticos o error): {e}")
            else:
                print(f"  {var:20} | Error: Cantidad de semillas no coincide ({len(var_data)} vs {len(baseline_data)})")

if __name__ == "__main__":
    # 1. Cargar desde CSV
    df = cargar_datos_desde_csv(INPUT_CSV)
    
    # 2. Analizar
    if not df.empty:
        generar_resumen_estadistico(df)
        graficar_boxplots(df)
        test_significancia(df)
    else:
        print("No se pudo realizar el análisis.")