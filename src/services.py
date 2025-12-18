import uuid
import asyncio
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Manager
from .motor_ga import ejecutar_algoritmo_genetico

# --- GESTIÓN DE ESTADO COMPARTIDO ---
manager = Manager()
# Diccionario para progreso en vivo (compartido entre procesos)
PROGRESO_TRABAJOS = manager.dict()
# Diccionario local para metadatos y resultados finales
TRABAJOS = {}

# Executor para no bloquear el loop de FastAPI
executor = ProcessPoolExecutor(max_workers=2)

def correr_trabajo_pesado(job_id, config, datos, estrategias, shared_dict):
    """Ejecución real del motor GA en un proceso separado."""
    try:
        resultado = ejecutar_algoritmo_genetico(config, datos, estrategias, job_id, shared_dict)
        return ("completed", resultado)
    except Exception as e:
        return ("failed", str(e))

async def wrapper_trabajo(job_id, config, datos, estrategias):
    """Orquestador asincrónico que actualiza el estado del trabajo."""
    loop = asyncio.get_running_loop()
    
    PROGRESO_TRABAJOS[job_id] = {"porcentaje": 0, "gen_actual": 0, "estado": "iniciando"}

    estado, data = await loop.run_in_executor(
        executor, 
        correr_trabajo_pesado, 
        job_id, config, datos, estrategias, PROGRESO_TRABAJOS
    )
    
    TRABAJOS[job_id]["status"] = estado
    if estado == "completed":
        TRABAJOS[job_id]["result"] = data
        if job_id in PROGRESO_TRABAJOS:
            del PROGRESO_TRABAJOS[job_id]
    else:
        TRABAJOS[job_id]["error"] = data