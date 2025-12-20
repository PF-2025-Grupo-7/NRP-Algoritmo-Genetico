# Motor de Optimización para Planificación de Guardias (NRP) - Grupo 7

Este repositorio contiene el núcleo algorítmico y la API de servicios para el proyecto **"Aplicación para la Planificación de Guardias en Hospitales Japoneses"**, desarrollado para la asignatura Proyecto Final de la carrera Ingeniería en Sistemas de Información (UTN FRCU).

El sistema resuelve el *Nurse Rostering Problem* (NRP) mediante **Algoritmos Genéticos** (AG), permitiendo automatizar la asignación de turnos médicos cumpliendo con restricciones legales, operativas y de equidad horaria.

## Arquitectura del Sistema

El proyecto implementa una arquitectura por capas para garantizar la separación de intereses y facilitar el mantenimiento:

* **Capa de API (FastAPI):** Define los contratos de datos mediante modelos estrictos de Pydantic V2 y gestiona los puntos de entrada del sistema.
* **Capa de Servicios (`services.py`):** Gestiona la asincronía y el paralelismo. Utiliza un `ProcessPoolExecutor` para ejecutar el algoritmo genético sin bloquear el servidor web.
* **Motor GA (`motor_ga.py`):** Contiene la lógica del ciclo evolutivo (Selección, Cruce, Mutación y Reparación).
* **Modelo del Problema (`problema.py`):** Define la función de *Fitness* y las métricas de auditoría/explicabilidad.
* **Loader (`loader.py`):** Modulo encargado de transformar datos de negocio en estructuras de datos optimizadas (Sets y matrices NumPy).

## Tecnologías Utilizadas

* **Python 3.12+**: Lenguaje base del proyecto.
* **FastAPI**: Framework para la construcción de la API asincrónica.
* **Pydantic V2**: Validación de datos y modelos de configuración.
* **NumPy**: Procesamiento eficiente de matrices de guardias.
* **Pytest & HTTPX**: Infraestructura para pruebas automatizadas de integración y unidad.

## Estructura del Proyecto

```text
├── src/
│   ├── api.py              # Endpoints y validación de modelos
│   ├── services.py         # Orquestación de procesos y estado compartido
│   ├── motor_ga.py         # Lógica del Algoritmo Genético
│   ├── problema.py         # Modelado de restricciones y fitness
│   ├── loader.py           # Transformación y carga de datos
│   ├── operadores.py       # Operadores genéticos (cruce, mutación, selección)
│   ├── repair.py           # Operador de reparación de soluciones
│   └── penalizaciones/     # Mixins de reglas de negocio (Duras y Blandas)
├── tests/                  # Suite de tests (Workflow completo, API, Loader)
├── examples/               # Archivos JSON de ejemplo para pruebas
├── requirements.txt        # Dependencias del sistema
└── README.md
```

## Despliegue y Desarrollo con Docker (Recomendado)

El proyecto cuenta con una arquitectura dockerizada que facilita el despliegue y asegura la consistencia del entorno de ejecución.

**Requisitos:** 1. Tener instalado [Docker Desktop](https://www.docker.com/products/docker-desktop/) (o Docker Engine + Compose).
2. **Importante:** Asegurarse de que Docker Desktop esté **abierto y corriendo** (icono de la ballena visible) antes de ejecutar los comandos.

### Iniciar la aplicación
Para levantar el entorno completo (API + Dependencias) con un solo comando:

```bash
docker-compose up --build
```
* **API URL:** `http://localhost:8000`
* **Documentación Interactiva (Swagger):** `http://localhost:8000/docs`

### Características del entorno Docker
* **Hot-Reload Activo:** El contenedor está configurado para detectar cambios en el código fuente (`src/`) y reiniciar el servidor automáticamente. Puedes desarrollar localmente mientras la app corre en Docker.
* **Volúmenes:** La carpeta de trabajo se sincroniza en tiempo real, por lo que no es necesario reconstruir la imagen ante cambios de código (solo ante cambios en `requirements.txt`).

Para detener la aplicación y limpiar los recursos:
```bash
docker-compose down
```

## Instalación y Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone <url-del-repositorio>
    cd nrp-algoritmo-genetico
    ```

2.  **Configurar el entorno virtual:**
    ```bash
    python -m venv .venv
    # Activar en Windows:
    .venv\Scripts\activate
    # Activar en Linux/Mac:
    source .venv/bin/activate
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    # Para desarrollo y tests:
    pip install pytest httpx requests
    ```

## Ejecución y Testing

### Iniciar la API
Para ejecutar el servidor de desarrollo:
```bash
uvicorn src.api:app --reload
```

La documentación interactiva (Swagger) se genera automáticamente en: `http://127.0.0.1:8000/docs`

### Ejecutar Pruebas Automatizadas
Para correr la suite de tests completa y asegurar la integridad del sistema tras cualquier refactorización:
```bash
python -m pytest
```

## Endpoints de Interés

* **`POST /planificar`**: Inicia la búsqueda de la planificación óptima de forma asincrónica utilizando el `ProcessPoolExecutor` para evitar bloqueos.
* **`GET /status/{job_id}`**: Permite monitorear el progreso (generación actual, porcentaje y mejor fitness) en tiempo real consultando la memoria compartida del sistema.
* **`GET /result/{job_id}`**: Recupera la matriz final de guardias y el reporte detallado de explicabilidad una vez que el estado es `completed`.
* **`POST /soluciones/evaluar`**: Endpoint dedicado a la auditoría técnica que permite validar vectores de solución externos y obtener un desglose de penalizaciones.

## Equipo de Desarrollo - Grupo 7

* **Integrantes**:
    * Fernandez, María Emilia
    * Orcellet, Nicolás Agustín
    * Tiguá, Salvador
* **Tutor**: Casanova Pietroboni, Carlos Antonio
* **Institución**: Universidad Tecnológica Nacional - Facultad Regional Concepción del Uruguay (UTN FRCU)