import uuid
import asyncio
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Manager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional

from motor_ga import ejecutar_algoritmo_genetico

app = FastAPI(title="API Planificación Guardias - Grupo 7")

# --- NUEVO MODELO PARA EVALUACIÓN ---
from typing import List

class SolicitudEvaluacion(BaseModel):
    vector: List[int]
    datos_problema: Dict[str, Any]

# --- NUEVO ENDPOINT ---
@app.post("/soluciones/evaluar", tags=["Auditoría"])
async def evaluar_solucion_especifica(solicitud: SolicitudEvaluacion):
    try:
        from problema import ProblemaGAPropio
        from loader import procesar_datos_instancia # <--- IMPORTANTE
        import numpy as np
        
        # 1. Transformamos los datos crudos del JSON al formato que entiende la lógica
        datos_procesados = procesar_datos_instancia(solicitud.datos_problema)
        
        # 2. Ahora sí inicializamos con los datos correctos
        problema = ProblemaGAPropio(**datos_procesados)
        vector_np = np.array(solicitud.vector)
        
        reporte = problema.evaluar_detallado(vector_np)
        return reporte
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en evaluación: {str(e)}")


# --- GESTIÓN DE ESTADO COMPARTIDO ---
# Necesitamos un Manager para compartir memoria entre procesos de forma segura
manager = Manager()
# Este diccionario guardará el progreso en vivo: { "job_id": { "porcentaje": 10... } }
PROGRESO_TRABAJOS = manager.dict()

# Base de datos simple para resultados finales y metadatos
TRABAJOS = {}

executor = ProcessPoolExecutor(max_workers=2)

# --- MODELOS ---
class SolicitudPlanificacion(BaseModel):
    config: Dict[str, Any]
    datos_problema: Dict[str, Any]
    estrategias: Optional[Dict[str, str]] = {
        "sel": "torneo_deterministico", 
        "cross": "bloques_verticales", 
        "mut": "hibrida_adaptativa"
    }

class RespuestaCreacion(BaseModel):
    job_id: str
    mensaje: str
    status_url: str

# --- WORKER Y WRAPPER ---
def correr_trabajo_pesado(job_id, config, datos, estrategias, shared_dict):
    """
    Función que corre en otro proceso. Recibe el shared_dict para reportar.
    """
    try:
        # Llamamos al motor pasando el diccionario compartido
        resultado = ejecutar_algoritmo_genetico(config, datos, estrategias, job_id, shared_dict)
        return ("completed", resultado)
    except Exception as e:
        return ("failed", str(e))

async def wrapper_trabajo(job_id, config, datos, estrategias):
    loop = asyncio.get_running_loop()
    
    # Iniciamos entrada en el dict de progreso
    PROGRESO_TRABAJOS[job_id] = {"porcentaje": 0, "gen_actual": 0, "estado": "iniciando"}

    estado, data = await loop.run_in_executor(
        executor, 
        correr_trabajo_pesado, 
        job_id, config, datos, estrategias, PROGRESO_TRABAJOS
    )
    
    # Actualizamos el estado final en la memoria local
    TRABAJOS[job_id]["status"] = estado
    if estado == "completed":
        TRABAJOS[job_id]["result"] = data
        # Limpiamos el progreso para no ocupar memoria del Manager innecesariamente
        if job_id in PROGRESO_TRABAJOS:
            del PROGRESO_TRABAJOS[job_id]
    else:
        TRABAJOS[job_id]["error"] = data

# --- ENDPOINTS ---

@app.post("/planificar", response_model=RespuestaCreacion)
async def iniciar_planificacion(solicitud: SolicitudPlanificacion, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    TRABAJOS[job_id] = {
        "status": "processing",
        "submitted_at": str(uuid.uuid1().time)
    }
    
    background_tasks.add_task(
        wrapper_trabajo, 
        job_id, 
        solicitud.config, 
        solicitud.datos_problema, 
        solicitud.estrategias
    )
    
    return {
        "job_id": job_id,
        "mensaje": "Planificación iniciada.",
        "status_url": f"/status/{job_id}"
    }

@app.get("/status/{job_id}")
async def consultar_estado(job_id: str):
    if job_id not in TRABAJOS:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    job_local = TRABAJOS[job_id]
    status_general = job_local["status"]

    respuesta = {
        "job_id": job_id,
        "status": status_general
    }

    # Si está procesando, buscamos el detalle en tiempo real en el Manager
    if status_general == "processing":
        # Usamos .get() porque en condiciones de carrera podría borrarse justo antes de leer
        info_vivo = PROGRESO_TRABAJOS.get(job_id)
        if info_vivo:
            respuesta["progreso"] = {
                "porcentaje": f"{info_vivo.get('porcentaje')}%",
                "generacion": f"{info_vivo.get('gen_actual')}/{info_vivo.get('gen_total')}",
                "fitness_actual": info_vivo.get('mejor_fitness_actual')
            }
        else:
            respuesta["progreso"] = "Iniciando..."

    return respuesta

@app.get("/result/{job_id}")
async def obtener_resultado(job_id: str):
    if job_id not in TRABAJOS:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    job = TRABAJOS[job_id]
    
    if job["status"] == "processing":
        return {"mensaje": "Trabajo en proceso", "status_url": f"/status/{job_id}"}
    
    if job["status"] == "failed":
        return {"status": "failed", "error": job.get("error")}
        
    return job["result"]