from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal
import uuid
import numpy as np

# Importaciones locales
from .loader import procesar_datos_instancia
from .problema import ProblemaGAPropio
from . import services 

app = FastAPI(
    title="API Planificación Guardias - Grupo 7",
    description="Motor de Algoritmo Genético optimizado para hospitales."
)

# --- MODELOS DE SOPORTE (Pydantic V2 Ready) ---

class ConfigGA(BaseModel):
    pop_size: int = Field(100, gt=0)
    generaciones: int = Field(200, gt=0)
    pc: float = Field(0.85, ge=0, le=1)
    pm: float = Field(0.15, ge=0, le=1)
    elitismo: bool = True
    seed: Optional[int] = None

class DatosProfesional(BaseModel):
    id_db: int = Field(..., description="ID del profesional en la base de datos.")
    nombre: str = Field(..., description="Nombre del profesional.")
    skill: str = Field(..., description="'senior', 'junior', etc.")
    t_min: int = Field(..., description="Mínimo de horas/guardias por contrato.")
    t_max: int = Field(..., description="Máximo de horas/guardias por contrato.")

class DatosProblema(BaseModel):
    # num_profesionales: Eliminado (se calcula según el largo de la lista)
    
    num_dias: int = Field(..., gt=0)
    max_turno_val: int = Field(..., description="Valor máximo del turno (ej: 3)") 
    skills_a_cubrir: List[str] = Field(..., description="Lista de skills (senior, junior, etc)") 
    turnos_a_cubrir: List[int] = Field(default=[1, 2, 3])
    turnos_noche: List[int] = Field(default=[3])
    
    duracion_turnos: Dict[str, int] = Field(
        ..., 
        json_schema_extra={"example": {"1": 8, "2": 8, "3": 8}}
    )
    
    pesos_fitness: Dict[str, float] = Field(
        default={"eq": 1.0, "dif": 1.5, "pdl": 2.0, "pte": 0.5, "alpha_pte": 0.5}
    )
    
    # info_profesionales_base: Eliminado
    
    # NUEVO CAMPO: Lista detallada
    lista_profesionales: List[DatosProfesional] = Field(
        ..., 
        description="Lista detallada de la nómina de profesionales."
    )

    reglas_cobertura: Dict[str, Any]
    secuencias_prohibidas: List[List[int]] = []
    excepciones_disponibilidad: List[Dict[str, Any]] = []
    excepciones_preferencias: List[Dict[str, Any]] = []
    tolerancia_equidad_general: int = 8
    tolerancia_equidad_dificil: int = 4

# --- NUEVO MODELO DE ESTRATEGIAS (Validación Estricta) ---
class EstrategiasConfig(BaseModel):
    sel: Literal["torneo_deterministico", "ranking_lineal"] = Field(
        default="torneo_deterministico",
        description="Operador de Selección"
    )
    cross: Literal["bloques_verticales", "bloques_horizontales", "dos_puntos"] = Field(
        default="bloques_verticales",
        description="Operador de Cruzamiento"
    )
    mut: Literal["hibrida_adaptativa", "reasignar_turno", "intercambio_dia", "flip_simple"] = Field(
        default="hibrida_adaptativa",
        description="Operador de Mutación"
    )

# --- MODELOS DE ENTRADA ---

class SolicitudPlanificacion(BaseModel):
    config: ConfigGA
    datos_problema: DatosProblema
    estrategias: EstrategiasConfig = Field(default_factory=EstrategiasConfig)

class SolicitudEvaluacion(BaseModel):
    vector: List[int]
    datos_problema: DatosProblema

class RespuestaCreacion(BaseModel):
    job_id: str
    mensaje: str
    status_url: str

# --- ENDPOINTS ---

@app.post("/soluciones/evaluar", tags=["Auditoría"])
async def evaluar_solucion_especifica(solicitud: SolicitudEvaluacion):
    try:
        # Pydantic V2: model_dump() reemplaza a dict()
        datos_dict = solicitud.datos_problema.model_dump()
        datos_procesados = procesar_datos_instancia(datos_dict)
        
        problema = ProblemaGAPropio(**datos_procesados)
        vector_np = np.array(solicitud.vector)
        
        return problema.evaluar_detallado(vector_np)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en evaluación: {str(e)}")

@app.post("/planificar", response_model=RespuestaCreacion, tags=["Planificación"])
async def iniciar_planificacion(solicitud: SolicitudPlanificacion, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    services.TRABAJOS[job_id] = {
        "status": "processing",
        "submitted_at": str(uuid.uuid1().time)
    }
    
    background_tasks.add_task(
        services.wrapper_trabajo, 
        job_id, 
        solicitud.config.model_dump(), 
        solicitud.datos_problema.model_dump(), 
        solicitud.estrategias.model_dump() 
    )
    
    return {
        "job_id": job_id,
        "mensaje": "Planificación iniciada.",
        "status_url": f"/status/{job_id}"
    }

@app.get("/status/{job_id}", tags=["Estado"])
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
                "mejor_fitness": info_vivo.get('mejor_fitness_actual')
            }
        else:
            respuesta["progreso"] = "Iniciando..."
    
    elif status_general == "failed":
        respuesta["error"] = job_local.get("error")

    return respuesta

@app.get("/result/{job_id}", tags=["Estado"])
async def obtener_resultado(job_id: str):
    if job_id not in services.TRABAJOS:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    job = services.TRABAJOS[job_id]
    
    if job["status"] == "processing":
        return {"mensaje": "Calculando...", "status_url": f"/status/{job_id}"}
    
    if job["status"] == "failed":
        return {"status": "failed", "error": job.get("error")}
        
    return job["result"]