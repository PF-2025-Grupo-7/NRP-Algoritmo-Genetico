import uuid
import asyncio
from concurrent.futures import ProcessPoolExecutor
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Importamos nuestro motor y cargador
from motor_ga import ejecutar_algoritmo_genetico
from loader import cargar_instancia_problema # Podríamos necesitar adaptar esto para recibir JSON directo

app = FastAPI(title="API Planificación Guardias - Grupo 7")

# --- SIMULACIÓN DE BASE DE DATOS ---
# Estructura: { "job_id": { "status": "processing"|"completed"|"failed", "result": ... } }
TRABAJOS = {}

# Ejecutor para tareas pesadas (CPU bound)
executor = ProcessPoolExecutor(max_workers=2) # Máximo 2 planificaciones simultáneas para no saturar

# --- MODELOS DE DATOS (Pydantic) ---
class SolicitudPlanificacion(BaseModel):
    config: Dict[str, Any]       # Configuración del GA (generaciones, prob, etc.)
    datos_problema: Dict[str, Any] # La estructura del JSON de instancia completa
    estrategias: Optional[Dict[str, str]] = { # Opcional
        "sel": "torneo_deterministico", 
        "cross": "bloques_verticales", 
        "mut": "hibrida_adaptativa"
    }

class RespuestaCreacion(BaseModel):
    job_id: str
    mensaje: str
    status_url: str

# --- FUNCIÓN WORKER (Se ejecuta en otro proceso) ---
def correr_trabajo_pesado(job_id: str, config, datos, estrategias):
    try:
        # Aquí llamamos a la lógica pura que extrajimos
        resultado = ejecutar_algoritmo_genetico(config, datos, estrategias)
        return ("completed", resultado)
    except Exception as e:
        return ("failed", str(e))

async def wrapper_trabajo(job_id: str, config, datos, estrategias):
    """
    Wrapper asíncrono que espera al ejecutor y actualiza la 'Base de Datos'
    """
    loop = asyncio.get_running_loop()
    # Ejecutamos el bloqueo en un proceso separado para no congelar la API
    estado, data = await loop.run_in_executor(
        executor, 
        correr_trabajo_pesado, 
        job_id, config, datos, estrategias
    )
    
    # Actualizamos el estado
    TRABAJOS[job_id]["status"] = estado
    if estado == "completed":
        TRABAJOS[job_id]["result"] = data
    else:
        TRABAJOS[job_id]["error"] = data

# --- ENDPOINTS ---

@app.post("/planificar", response_model=RespuestaCreacion)
async def iniciar_planificacion(solicitud: SolicitudPlanificacion, background_tasks: BackgroundTasks):
    """
    Recibe los datos y lanza el proceso en segundo plano.
    Retorna inmediatamente un ID de trabajo.
    """
    job_id = str(uuid.uuid4())
    
    # Inicializamos estado
    TRABAJOS[job_id] = {
        "status": "processing",
        "submitted_at": str(uuid.uuid1().time) # Timestamp simple
    }
    
    # Agregamos la tarea al fondo (BackgroundTasks de FastAPI maneja el 'disparo y olvido')
    # Pero usamos nuestro wrapper para manejar el ProcessPool
    background_tasks.add_task(
        wrapper_trabajo, 
        job_id, 
        solicitud.config, 
        solicitud.datos_problema, 
        solicitud.estrategias
    )
    
    return {
        "job_id": job_id,
        "mensaje": "Planificación iniciada exitosamente.",
        "status_url": f"/status/{job_id}"
    }

@app.get("/status/{job_id}")
async def consultar_estado(job_id: str):
    if job_id not in TRABAJOS:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    job = TRABAJOS[job_id]
    return {
        "job_id": job_id,
        "status": job["status"]
    }

@app.get("/result/{job_id}")
async def obtener_resultado(job_id: str):
    if job_id not in TRABAJOS:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    job = TRABAJOS[job_id]
    
    if job["status"] == "processing":
        return {"mensaje": "El trabajo sigue en proceso. Intente más tarde."}
    
    if job["status"] == "failed":
        return {"status": "failed", "error": job.get("error")}
        
    return job["result"]