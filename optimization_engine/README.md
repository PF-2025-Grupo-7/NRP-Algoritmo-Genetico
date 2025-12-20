# Motor de Optimización (Algoritmo Genético)

> ⚠️ **Nota de Arquitectura:** Este componente funciona como un microservicio dentro del sistema general. Para levantar el proyecto completo, consulta el [README principal](../README.md) en la raíz del repositorio.

Este directorio contiene la lógica matemática y la API del motor de asignación de guardias.

## 🧠 Descripción Técnica
El núcleo de este módulo es un Algoritmo Genético (AG) diseñado para resolver el problema *Nurse Rostering Problem* (NRP) con restricciones específicas de hospitales japoneses/argentinos.

### Stack Tecnológico
* **Lenguaje:** Python 3.11
* **Librerías Core:** `numpy`, `pandas`
* **API Framework:** FastAPI / Uvicorn

## 🧪 Ejecución Independiente (Solo Desarrollo/Tests)

Si necesitas ejecutar scripts de prueba o experimentar con el algoritmo **sin levantar todo el entorno Docker** (por ejemplo, para correr los scripts de la carpeta `examples/`):

1.  Crear entorno virtual dentro de esta carpeta:
    ```bash
    cd optimization_engine
    python -m venv .venv
    source .venv/bin/activate  # O .venv\Scripts\activate en Windows
    ```

2.  Instalar dependencias:
    ```bash
    pip install -r requirements.txt
    ```

3.  Ejecutar un script de prueba:
    ```bash
    # Ejemplo: Levantar la API localmente (sin Docker)
    uvicorn src.api:app --reload
    ```

## 📂 Estructura del Módulo
* `src/`: Código fuente del AG (población, fitness, operadores).
* `api.py`: Punto de entrada de la API REST.
* `examples/`: Scripts de experimentación y JSONs de prueba.
* `tests/`: Tests unitarios.