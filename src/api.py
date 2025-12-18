from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import uuid
import numpy as np

# Importaciones locales
from .loader import procesar_datos_instancia
from .problema import ProblemaGAPropio
from . import services  # <--- Importamos nuestro nuevo servicio

app = FastAPI(title="API Planificación Guardias - Grupo 7")

# --- MODELOS DE DATOS (Contratos) ---
class SolicitudEvaluacion(BaseModel):
    vector: List[int]
    datos_problema: Dict[str, Any]

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

# --- ENDPOINTS ---

@app.post("/soluciones/evaluar", tags=["Auditoría"])
async def evaluar_solucion_especifica(solicitud: SolicitudEvaluacion):
    try:
        datos_procesados = procesar_datos_instancia(solicitud.datos_problema)
        problema = ProblemaGAPropio(**datos_procesados)
        vector_np = np.array(solicitud.vector)
        return problema.evaluar_detallado(vector_np)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en evaluación: {str(e)}")

@app.post("/planificar", response_model=RespuestaCreacion)
async def iniciar_planificacion(solicitud: SolicitudPlanificacion, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    # Registramos el inicio en el servicio
    services.TRABAJOS[job_id] = {
        "status": "processing",
        "submitted_at": str(uuid.uuid1().time)
    }
    
    background_tasks.add_task(
        services.wrapper_trabajo, 
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
    if job_id not in services.TRABAJOS:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    job_local = services.TRABAJOS[job_id]
    status_general = job_local["status"]

    respuesta = {"job_id": job_id, "status": status_general}

    if status_general == "processing":
        info_vivo = services.PROGRESO_TRABAJOS.get(job_id)
        if info_vivo:
            respuesta["progreso"] = {
                "porcentaje": f"{info_vivo.get('porcentaje')}%",
                "generacion": f"{info_vivo.get('gen_actual')}/{info_vivo.get('gen_total', '?')}",
                "fitness_actual": info_vivo.get('mejor_fitness_actual')
            }
        else:
            respuesta["progreso"] = "Iniciando..."

    return respuesta

@app.get("/result/{job_id}")
async def obtener_resultado(job_id: str):
    if job_id not in services.TRABAJOS:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    job = services.TRABAJOS[job_id]
    
    if job["status"] == "processing":
        return {"mensaje": "Trabajo en proceso", "status_url": f"/status/{job_id}"}
    
    if job["status"] == "failed":
        return {"status": "failed", "error": job.get("error")}
        
    return job["result"]