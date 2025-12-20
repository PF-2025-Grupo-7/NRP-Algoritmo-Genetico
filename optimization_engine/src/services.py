"""Módulo de Servicios y Gestión de Procesos Asincrónicos.

Este módulo actúa como la capa de servicios que orquesta la ejecución del 
Algoritmo Genético en procesos separados, permitiendo que la API de FastAPI 
permanezca receptiva mientras se realizan cálculos intensivos de CPU.
"""

import uuid
import asyncio
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Manager
from .motor_ga import ejecutar_algoritmo_genetico

# --- GESTIÓN DE ESTADO COMPARTIDO ---

# Manager permite crear estructuras de datos compartidas entre diferentes procesos
manager = Manager()

# PROGRESO_TRABAJOS (DictProxy): Diccionario compartido para almacenar el 
# porcentaje de avance y métricas en vivo accesibles por los procesos de la API.
PROGRESO_TRABAJOS = manager.dict()

# TRABAJOS (dict): Diccionario local al proceso principal para almacenar 
# metadatos persistentes, estados finales y resultados de los cálculos.
TRABAJOS = {}

# Executor que gestiona el Pool de Procesos para el paralelismo real.
executor = ProcessPoolExecutor(max_workers=2)

def correr_trabajo_pesado(job_id, config, datos, estrategias, shared_dict):
    """Ejecuta el motor del GA en un proceso worker independiente.

    Esta función es bloqueante y está diseñada para ejecutarse dentro de un 
    ProcessPoolExecutor para no interferir con el bucle de eventos asincrónico.

    Args:
        job_id (str): Identificador único de la tarea.
        config (dict): Parámetros de configuración para el GA.
        datos (dict): Instancia del problema procesada.
        estrategias (dict): Operadores genéticos seleccionados.
        shared_dict (DictProxy): Referencia al diccionario de progreso compartido.

    Returns:
        tuple: Un par (estado, resultado) donde estado es "completed" o "failed".
    """
    try:
        resultado = ejecutar_algoritmo_genetico(config, datos, estrategias, job_id, shared_dict)
        return ("completed", resultado)
    except Exception as e:
        return ("failed", str(e))

async def wrapper_trabajo(job_id, config, datos, estrategias):
    """Orquestador asincrónico que gestiona el ciclo de vida de un trabajo.

    Inicia el trabajo en el pool de procesos, espera su finalización de forma 
    no bloqueante y actualiza los diccionarios de estado locales y compartidos.

    Args:
        job_id (str): Identificador único generado por la API.
        config (dict): Configuración del algoritmo.
        datos (dict): Datos de entrada del problema.
        estrategias (dict): Estrategias de evolución seleccionadas.
    """
    loop = asyncio.get_running_loop()
    
    # Inicialización del estado de progreso
    PROGRESO_TRABAJOS[job_id] = {"porcentaje": 0, "gen_actual": 0, "estado": "iniciando"}

    # Ejecución en el pool de procesos sin bloquear el loop de FastAPI
    estado, data = await loop.run_in_executor(
        executor, 
        correr_trabajo_pesado, 
        job_id, config, datos, estrategias, PROGRESO_TRABAJOS
    )
    
    # Actualización del estado final en la memoria del proceso principal
    TRABAJOS[job_id]["status"] = estado
    
    if estado == "completed":
        TRABAJOS[job_id]["result"] = data
        # Limpieza de memoria compartida una vez finalizado el reporte de progreso
        if job_id in PROGRESO_TRABAJOS:
            del PROGRESO_TRABAJOS[job_id]
    else:
        TRABAJOS[job_id]["error"] = data