# Algoritmo Genético para NPR

Prototipo de optimización para la asignación de guardias médicas en hospitales japoneses, utilizando Algoritmos Genéticos. Este proyecto busca resolver el Nurse Rostering Problem considerando restricciones legales y preferencias del personal.

## Requisitos Previos
- Python 3.10 o superior

## Instalación y Configuración
1. Crear entorno virtual
```bash
python -m venv .venv
```
2. Activar entorno
```bash
.\.venv\Scripts\Activate
```
3. Instalar dependencias
```bash
pip install -r requirements.txt
```
## Ejecución de Estrategias
Actualmente existen dos implementaciones del motor genético. Se recomienda ejecutar desde la raíz del repositorio.
### 1 - GA Propio
Implementación a medida con operadores de cruce y mutación diseñados para mantener la estructura de bloques de los turnos. Incluye reparación inteligente de individuos.
```bash
python estrategias/ga_propio/ejecutar_ga_propio.py
```
### 2 - Mealpy GA
Implementación basada en la librería estándar mealpy. Útil para comparar el rendimiento base frente a la solución propia.
```bash
python estrategias/mealpy_ga/ejecutar.py
```

## Estructura del Código
* estrategias/: contiene los runners y la lógica de cada enfoque.
* penalizaciones/: lógica compartida de negocio:
  * duras.py: restricciones inviolables.
  * blandas.py: función de fitness

## Notas para el Equipo
* Datos de Prueba: Actualmente los parámetros (enfermeros, días, demanda) están definidos dentro de los scripts ejecutar_*.py.

* Logs: La salida por consola muestra el progreso generacional y la matriz resultante formateada al final.  