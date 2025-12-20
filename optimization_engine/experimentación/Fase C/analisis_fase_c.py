import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy import stats

# ================= CONFIGURACIÓN =================
INPUT_FILE = "resumen_fase_c.csv"
PALETA = "viridis"  # Paleta de colores profesional
ESTILO = "whitegrid"

def cargar_y_limpiar(ruta_csv):
    try:
        # Intentamos leer. Si usaste Excel en español, puede que el separador sea ';' o ','
        # El script que pasaste usa to_csv por defecto (coma), así que probamos eso primero.
        df = pd.read_csv(ruta_csv)
        
        # Mapeo de nombres para que el gráfico se vea ordenado (Eje X)
        # Asumiendo que tus escenarios se llaman "C1_Escala_50", etc.
        mapa_nombres = {
            "C1_Escala_50": 50,
            "C2_Escala_75": 75,
            "C3_Escala_100": 100
        }
        
        # Crear columna numérica de 'Tamaño' para poder graficar la tendencia lineal
        df['Tamano_Problema'] = df['Escenario'].map(mapa_nombres)
        
        return df.sort_values('Tamano_Problema')
    except Exception as e:
        print(f"Error cargando CSV: {e}")
        return pd.DataFrame()

def analizar_escalabilidad_tiempo(df):
    """Genera gráfico de Tiempo vs Tamaño del Problema"""
    plt.figure(figsize=(10, 6))
    sns.set_style(ESTILO)
    
    # 1. Gráfico de Puntos y Línea de Tendencia
    sns.lineplot(data=df, x='Tamano_Problema', y='Tiempo_s', marker='o', label='Promedio', color='blue')
    
    # Agregamos dispersión para ver la varianza
    sns.scatterplot(data=df, x='Tamano_Problema', y='Tiempo_s', alpha=0.3, color='blue')
    
    plt.title("Análisis de Escalabilidad Temporal", fontsize=14, fontweight='bold')
    plt.xlabel("Tamaño del Problema (Nº Enfermeros)", fontsize=12)
    plt.ylabel("Tiempo de Ejecución (segundos)", fontsize=12)
    plt.xticks([50, 75, 100]) # Forzar que solo muestre estos valores
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig("fase_c_escalabilidad_tiempo.png", dpi=300)
    plt.close()
    print("-> Gráfico generado: fase_c_escalabilidad_tiempo.png")
    
    # Calcular factor de crecimiento (Pendiente)
    # T = a * N^b (Complejidad empírica)
    # O más simple: ¿Cuánto aumenta el tiempo al duplicar el tamaño?
    promedios = df.groupby('Tamano_Problema')['Tiempo_s'].mean()
    print("\n--- Crecimiento del Tiempo ---")
    print(promedios)
    
    if 50 in promedios and 100 in promedios:
        aumento = promedios[100] / promedios[50]
        print(f"Al duplicar el problema (50->100), el tiempo aumentó {aumento:.2f} veces.")
        if aumento < 4:
            print("CONCLUSIÓN: La complejidad parece ser sub-cuadrática (¡Muy bueno!).")
        else:
            print("CONCLUSIÓN: La complejidad parece ser cuadrática o superior.")

def analizar_calidad_y_factibilidad(df):
    """Analiza si el algoritmo mantiene la calidad al escalar"""
    
    # 1. Gráfico de Factibilidad (% de soluciones válidas)
    factibilidad = df.groupby('Tamano_Problema')['Es_Valido'].mean() * 100
    
    plt.figure(figsize=(8, 5))
    barplot = sns.barplot(x=factibilidad.index, y=factibilidad.values, palette=PALETA)
    plt.title("Robustez: % de Soluciones Válidas según Escala", fontsize=14)
    plt.ylabel("% Factibilidad", fontsize=12)
    plt.xlabel("Tamaño del Problema", fontsize=12)
    plt.ylim(0, 110) # Para dar aire arriba
    
    # Poner etiquetas de valor
    for i, v in enumerate(factibilidad.values):
        barplot.text(i, v + 2, f"{v:.1f}%", ha='center', fontweight='bold')
        
    plt.savefig("fase_c_factibilidad.png", dpi=300)
    plt.close()
    print("-> Gráfico generado: fase_c_factibilidad.png")

    # 2. Boxplot de Fitness (Cuidado: el fitness absoluto sube al haber más gente, 
    # hay que tener cuidado al comparar, pero sirve para ver la dispersión).
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='Tamano_Problema', y='Fitness', palette=PALETA)
    plt.title("Dispersión del Fitness según Tamaño", fontsize=14)
    plt.savefig("fase_c_fitness_box.png", dpi=300)
    plt.close()
    print("-> Gráfico generado: fase_c_fitness_box.png")

if __name__ == "__main__":
    print("Procesando resultados de Fase C...")
    df = cargar_y_limpiar(INPUT_FILE)
    
    if not df.empty:
        analizar_escalabilidad_tiempo(df)
        analizar_calidad_y_factibilidad(df)
        print("\n¡Proceso terminado!")
    else:
        print("No se pudieron cargar los datos.")