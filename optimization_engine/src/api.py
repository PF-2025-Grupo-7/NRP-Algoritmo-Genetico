from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal
import uuid
import numpy as np

# Importaciones locales
from .loader import procesar_datos_instancia
from .problema import ProblemaGAPropio
from . import services 
from .operadores import SELECTION_OPS, CROSSOVER_OPS, MUTATION_OPS 

app = FastAPI(
    title="API Planificación Guardias - Grupo 7",
    description="Motor de Algoritmo Genético optimizado para hospitales."
)

# --- CONFIGURACIÓN CORS ---
origins = [
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
    "*", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE SOPORTE ---

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

class EstrategiasConfig(BaseModel):
    sel: Literal["torneo_deterministico", "ranking_lineal"] = Field(
        default="torneo_deterministico"
    )
    cross: Literal["bloques_verticales", "bloques_horizontales", "dos_puntos"] = Field(
        default="bloques_verticales"
    )
    mut: Literal["hibrida_adaptativa", "reasignar_turno", "intercambio_dia", "flip_simple"] = Field(
        default="hibrida_adaptativa"
    )

# --- MODELOS DE ENTRADA ---

# En src/api.py

class SolicitudPlanificacion(BaseModel):
    config: ConfigGA
    datos_problema: DatosProblema
    estrategias: EstrategiasConfig = Field(default_factory=EstrategiasConfig)

    # --- AGREGAR ESTO AL FINAL DE LA CLASE ---
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "config": {
                        "pop_size": 100,
                        "generaciones": 15,
                        "pc": 0.85,
                        "pm": 0.20,
                        "elitismo": True,
                        "seed": 1111
                    },
                    "datos_problema": {
                        "num_dias": 30,
                        "max_turno_val": 3,
                        "turnos_a_cubrir": [1, 2, 3],
                        "skills_a_cubrir": ["junior", "senior"],
                        "turnos_noche": [3],
                        "duracion_turnos": {"1": 8, "2": 8, "3": 8},
                        "pesos_fitness": {
                            "eq": 1.0, "dif": 1.5, "pdl": 2.0, "pte": 0.5, "alpha_pte": 0.5
                        },
                        "tolerancia_equidad_general": 8,
                        "tolerancia_equidad_dificil": 4,
                        "lista_profesionales": [
                            {"id_db": 101, "nombre": "Dr. Senior 1", "skill": "senior", "t_min": 12, "t_max": 16},
                            {"id_db": 102, "nombre": "Dr. Senior 2", "skill": "senior", "t_min": 12, "t_max": 16},
                            # ... (puedes poner solo 2 o 3 para que no sea tan largo en la doc) ...
                            {"id_db": 201, "nombre": "Dr. Junior 1", "skill": "junior", "t_min": 12, "t_max": 16}
                        ],
                        "reglas_cobertura": {
                            "dias_pico": [0, 4],
                            "demanda_pico": {"1": {"junior": 2, "senior": 2}, "2": {"junior": 2, "senior": 1}, "3": {"junior": 1, "senior": 1}},
                            "demanda_finde": {"1": {"junior": 1, "senior": 1}, "2": {"junior": 1, "senior": 1}, "3": {"junior": 1, "senior": 1}},
                            "demanda_normal": {"1": {"junior": 2, "senior": 1}, "2": {"junior": 1, "senior": 1}, "3": {"junior": 1, "senior": 1}}
                        },
                        "secuencias_prohibidas": [[3, 1], [3, 2], [2, 1]],
                        "excepciones_disponibilidad": [
                            {"prof_index": 0, "dias_range": [0, 7], "disponible": False}
                        ],
                        "excepciones_preferencias": [
                            {"prof_indices": [0], "dia": 15, "valor": -1}
                        ]
                    },
                    "estrategias": {
                        "sel": "torneo_deterministico",
                        "cross": "bloques_horizontales",
                        "mut": "hibrida_adaptativa"
                    }
                }
            ]
        }
    }

class RespuestaCreacion(BaseModel):
    job_id: str
    mensaje: str
    status_url: str

# --- ENDPOINTS ---

@app.get("/info/opciones", tags=["Metadatos"])
async def obtener_opciones_disponibles():
    """Endpoint para que el Frontend sepa qué estrategias mostrar en los Selects."""
    return {
        "seleccion": list(SELECTION_OPS.keys()),
        "cruce": list(CROSSOVER_OPS.keys()),
        "mutacion": list(MUTATION_OPS.keys())
    }

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

@app.get("/result/{job_id}", tags=["Resultados"])
async def obtener_resultado(job_id: str):
    if job_id not in services.TRABAJOS:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    
    job = services.TRABAJOS[job_id]
    
    if job["status"] == "processing":
        return {"mensaje": "Calculando...", "status_url": f"/status/{job_id}"}
    
    if job["status"] == "failed":
        return {"status": "failed", "error": job.get("error")}
        
    return job["result"]