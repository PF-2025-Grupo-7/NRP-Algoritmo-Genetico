# Algoritmo Genético para NPR

Prototipo de optimización para la asignación de guardias médicas en hospitales japoneses, utilizando Algoritmos Genéticos. Este proyecto busca resolver el Nurse Rostering Problem considerando restricciones legales y preferencias del personal.

## Estructura del Proyecto
* `src/`: Código fuente del algoritmo genético y lógica de negocio.
  * `data/`: Instancias de prueba y configuración.
  * `penalizaciones/`: Restricciones duras y blandas.
* `logs/`: Resultados de las ejecuciones.

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
## Ejecución 
Desde la raíz del proyecto:
```bash
python src/main.py
```
O para especificar una instancia diferente:
```bash
python src/main.py --instancia src/data/instancia_02_grande.json
```

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
