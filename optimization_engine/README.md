# Motor de Optimización (Algoritmo Genético)

> ⚠️ **Nota de Arquitectura:** Este componente funciona como un microservicio independiente (API REST). Para levantar el sistema completo (Frontend + Backend), consulta el [README principal](../README.md) en la raíz del repositorio.

Este directorio contiene la lógica matemática, los operadores genéticos y la API FastAPI encargada de la planificación automática de guardias.

## 🧠 Descripción Técnica

El núcleo es un **Algoritmo Genético (AG)** diseñado para resolver el problema *Nurse Rostering Problem* (NRP). A diferencia de soluciones genéricas, este motor implementa operadores híbridos y restricciones específicas para contratos y normativas de hospitales.

### Stack Tecnológico
* **Lenguaje:** Python 3.11+
* **Core Matemático:** `numpy` (operaciones vectoriales de alto rendimiento).
* **API Framework:** `FastAPI` (validación con Pydantic V2).
* **Servidor:** `Uvicorn` (ASGI).

## 🚀 Flujo de la API

La API funciona de manera **asíncrona** para no bloquear el servidor durante cálculos pesados:

1.  **POST `/planificar`**: Recibe la configuración y datos (incluyendo la nómina real de profesionales). Retorna un `job_id` inmediatamente.
2.  **GET `/status/{job_id}`**: Permite consultar el progreso (porcentaje, generación actual, mejor fitness) en tiempo real (Polling).
3.  **GET `/result/{job_id}`**: Devuelve el JSON final con la matriz de guardias y el reporte de auditoría una vez que el estado es "completed".
4.  **GET `/info/opciones`**: Endpoint de metadatos que devuelve dinámicamente las estrategias disponibles (Selection, Crossover, Mutation) para poblar los selectores del Frontend.

## 🧪 Ejecución Local (Sin Docker)

Para desarrollo rápido, debugging o correr los scripts de la carpeta `examples/` sin levantar todo el entorno de contenedores:

### 1. Preparar el Entorno
Desde esta carpeta (`optimization_engine`):

```bash
# 1. Crear entorno virtual
python -m venv .venv

# 2. Activar entorno
# En Windows (PowerShell):
.\.venv\Scripts\Activate
# En Mac/Linux:
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

### 2. Levantar la API
```bash
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en: http://localhost:8000/docs

## 📂 Estructura del Módulo
* `src/`: Código fuente del AG (población, fitness, operadores).
* * `api.py`: Definición de endpoints y modelos.
* * `motor_ga.py`: Bucle principal evolutivo.
* * `operadores.py`: Catálogo de funciones de cruce, mutación y selección.
* * `problema.py`: Clase que calcula el fitness y maneja las restricciones.
* * `loader.py`: Transformación del JSON a matrices Numpy.

* `examples/`: Scripts de experimentación y JSONs de prueba.
* `tests/`: Tests unitarios.