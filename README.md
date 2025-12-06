# Algoritmo Genético para NPR

Prototipo de optimización para la asignación de guardias médicas en hospitales japoneses, utilizando Algoritmos Genéticos. Este proyecto busca resolver el Nurse Rostering Problem considerando restricciones legales y preferencias del personal.

## 📋 Requisitos Previos
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
## Ejecución (simple)
Desde la raíz del proyecto:
```bash
python src/main.py
```
O para especificar una instancia diferente:
```bash
python src/main.py --instancia src/data/instancia_02_grande.json
```

## Estructura del Proyecto
* `src/`: Código fuente principal.
  * `data/`: Instancias de prueba y configuración.
  * `penalizaciones/`: Restricciones duras y blandas.
  * `operadores.py`: Catálogoo de estrategias de selección, cruce y mutación.
  * `main.py`: Punto de entrada único para ejecutar el algoritmo.
* `logs/`: Resultados de las ejecuciones.

## Personalización y Configuración

El algoritmo permite ajustar sus hiperparámetros mediante archivos JSON ubicados en `src/data/`. Esto permite cambiar el comportamiento de la búsqueda sin modificar el código.

### Parámetros Configurables

| Parámetro      | Descripción                                                |
| :---           | :---                                                       |
| `pop_size`     | Tamaño de la población (cantidad de soluciones simultáneas). |
| `generaciones` | Número de iteraciones del ciclo evolutivo.                 |
| `pc`           | Probabilidad de Cruce (Crossover).                         |
| `pm`           | Probabilidad de Mutación.                                  |
| `elitismo`     | `true` para conservar siempre al mejor individuo.          |

### ¿Cómo elegir una configuración?

Utiliza el argumento `--config` al ejecutar el script principal.

**Ejecución Estándar (usa default implícitamente):**
```bash
python src/main.py
```

**Ejecución Rápida (para pruebas):**
```bash
python src/main.py --config src/data/config_ga_fast.json
```
**Combinando Instancia y Configuración**
Podemos mezclar una instancia difícil con una configuración rápida para ver si el código corre sin errores:
```bash
python src/main.py --instancia src/data/instancia_02_grande.json --config src/data/config_ga_fast.json
```

## Experimentación con Operadores 

| Argumento      | Descripción                                                | Opciones Disponibles  |
| :---           | :---                                                       | :---    |
| `--mut`     | Estrategia de Mutación | `hibrida_adaptativa` (Default), `reasignar_turno`, `intercambio_dia`, `flip_simple` |
| `--cross` | Estrategia de Cruce                 | `bloques_verticales` (Default) |
| `--sel`           | Estrategia de Selección                         | `torneo_deterministico` (Default) |

**Ejemplo**
```bash
python src/main.py --mut intercambio_dia --tag experimento_swap
```

## Visualización y Logs

**Modo Verbose (`-v`)**
Muestra el progreso generación a generación en la consola. Útil para ver la convergencia en tiempo real.
```bash
python src/main.py -v
```

Define un prefijo para la carpeta de resultados en logs/, facilitando la identificación de experimentos.
```bash
python src/main.py --tag prueba_final_viernes
```
