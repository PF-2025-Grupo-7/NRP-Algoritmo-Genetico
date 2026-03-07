# Sistema de Planificación de Guardias Hospitalarias (NRP)

Repositorio oficial del Proyecto Final de Carrera de ISI en la UTN FRCU (Grupo 7 - 2026).

Este sistema resuelve el problema de asignación de turnos (Nurse Rostering Problem) utilizando un Algoritmo Genético optimizado y una interfaz web para la gestión hospitalaria.

## Arquitectura del Sistema

El proyecto utiliza una arquitectura de microservicios contenerizada:

1.  **Web App (`web_app`):** Aplicación MVC en **Django** (Interfaz de usuario, lógica de negocio y gestión).
2.  **Motor de Optimización (`optimization_engine`):** API REST en **FastAPI** (Cálculo matemático intensivo y Algoritmo Genético).
3.  **Base de Datos (`db`):** Contenedor **PostgreSQL** persistente.

## Despliegue Rápido (Recomendado)

El sistema está diseñado para funcionar "out-of-the-box" utilizando **Docker**. No es necesario instalar Python, PostgreSQL ni librerías en tu máquina local.

**Requisitos:** Docker Desktop (o Docker Engine + Compose).

1.  **Clonar el repositorio:**
    ```bash
    git clone <URL_DEL_REPO>
    cd <NOMBRE_CARPETA>
    ```

2.  **Iniciar los servicios:**
    ```bash
    docker-compose up --build
    ```
    *Nota: La primera vez puede tardar unos minutos en descargar las imágenes y construir el entorno.*

3.  **Inicialización Automática:**
    Al detectar una instalación limpia, el sistema realizará automáticamente:
    * Las migraciones de Base de Datos.
    * La carga de especialidades base.
    * La creación del superusuario por defecto.

**¡Listo!** Cuando la terminal deje de mostrar logs de instalación, el sistema estará operativo.

## 🔗 Accesos y Credenciales

| Servicio | URL | Descripción |
| :--- | :--- | :--- |
| **Web App (Sistema)** | [http://localhost:8080](http://localhost:8080) | Interfaz principal de Usuario |
| **Panel Admin** | [http://localhost:8080/admin](http://localhost:8080/admin) | Back-office de Django |
| **Documentación API** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger/Redoc del Motor de IA |

### Credenciales por defecto
El sistema se inicializa con una cuenta de administrador lista para usar:

* **Usuario:** `admin`
* **Contraseña:** `admin`

### Acceso a Base de Datos (PgAdmin / DBeaver)
Para conexiones externas a Docker (SQL Client):
* **Host:** `localhost`
* **Puerto:** `5432`
* **Base de Datos:** `bd_hospital`
* **Usuario:** `admin`
* **Contraseña:** `admin`

## Guía de Inicio Rápido (Workflow)

Para generar tu primera planificación, sigue este orden lógico de configuración en el sistema:

1.  **Gestión > Esquemas de Turno:** configurá los turnos (ej: 12hs Día/Noche) para las especialidades.
2.  **Gestión > Plantillas de Demanda:** creá una plantilla y define cuántos médicos necesitas por día.
3.  **Gestión > Empleados:** cargá el personal y asígnales la especialidad correspondiente.
4.  **Inicio > Generar Planificación:** seleccioná las fechas, la plantilla e iniciá la planificación.

## Comandos Útiles

* **Detener todo:** `Ctrl + C` en la terminal o:
    ```bash
    docker-compose down
    ```

* **Reiniciar de fábrica (Borrar BD):**
    ```bash
    docker-compose down -v
    docker-compose up --build
    ```

* **Entrar a la consola del contenedor Django:**
    ```bash
    docker-compose exec web bash
    ```

* **Ver logs en tiempo real:**
    ```bash
    docker-compose logs -f
    ```

---
**Desarrollado por:** Grupo 7 - Ingeniería en Sistemas de Información (UTN FRCU).