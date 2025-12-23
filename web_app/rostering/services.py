import json
from datetime import timedelta, date
from django.db.models import Q
from .models import (
    Empleado, TipoTurno, PlantillaDemanda, ReglaDemandaSemanal,
    ExcepcionDemanda, NoDisponibilidad, Preferencia, 
    ConfiguracionAlgoritmo, SecuenciaProhibida, DiaSemana
)

def generar_payload_ag(fecha_inicio, fecha_fin, especialidad, plantilla_id=None):
    """
    Construye el diccionario JSON exacto que espera la API de optimización.
    """
    # 1. Validaciones y Setup Inicial
    num_dias = (fecha_fin - fecha_inicio).days + 1
    if num_dias < 1:
        raise ValueError("La fecha de fin debe ser posterior a la fecha de inicio.")

    # Cargar configuración activa
    config = ConfiguracionAlgoritmo.objects.filter(activa=True).first()
    if not config:
        # Fallback si no hay config creada (útil para tests)
        config = ConfiguracionAlgoritmo() 

    # Cargar Plantilla (Si no se pasa ID, busca la primera de esa especialidad)
    if plantilla_id:
        plantilla = PlantillaDemanda.objects.get(pk=plantilla_id)
    else:
        plantilla = PlantillaDemanda.objects.filter(especialidad=especialidad).first()
        if not plantilla:
            raise ValueError(f"No hay plantilla de demanda creada para {especialidad}")

    # ---------------------------------------------------------
    # 2. SECCIÓN CONFIG (Técnica)
    # ---------------------------------------------------------
    payload_config = {
        "pop_size": config.tamano_poblacion,
        "generaciones": config.generaciones,
        "pc": config.prob_cruce,
        "pm": config.prob_mutacion,
        "elitismo": config.elitismo,
        "seed": config.semilla or 42 # Semilla por defecto si es None
    }

    # ---------------------------------------------------------
    # 3. SECCIÓN ESTRATEGIAS
    # ---------------------------------------------------------
    payload_estrategias = {
        "sel": config.estrategia_seleccion,
        "cross": config.estrategia_cruce,
        "mut": config.estrategia_mutacion
    }

    # ---------------------------------------------------------
    # 4. DATOS DEL PROBLEMA - PROFESIONALES
    # ---------------------------------------------------------
    
    # Calcular factor de proporción para horas (Ej: Si planificas 15 días, las horas contrato son la mitad)
    # Asumimos que min_horas_mensuales está pensado para un mes de 30 días.
    factor_tiempo = num_dias / 30.0
    
    empleados_qs = Empleado.objects.filter(especialidad=especialidad, activo=True)
    lista_profesionales = []
    
    # Mapa auxiliar para saber el índice (0, 1, 2...) de cada ID de empleado
    mapa_id_a_indice = {} 

    for idx, emp in enumerate(empleados_qs):
        mapa_id_a_indice[emp.id] = idx
        
        # Skill: Convertimos 'SENIOR' -> 'senior'
        skill = emp.experiencia.lower()
        
        # Horas ajustadas
        t_min_ajustado = int(emp.min_horas_mensuales * factor_tiempo)
        t_max_ajustado = int(emp.max_horas_mensuales * factor_tiempo)

        lista_profesionales.append({
            "id_db": emp.id,
            "nombre": emp.nombre_completo,
            "skill": skill,
            "t_min": t_min_ajustado,
            "t_max": t_max_ajustado
        })

    # ---------------------------------------------------------
    # 5. DATOS DEL PROBLEMA - TURNOS
    # ---------------------------------------------------------
    turnos_qs = TipoTurno.objects.filter(especialidad=especialidad)
    
    # Arrays de IDs
    turnos_a_cubrir = [t.id for t in turnos_qs]
    turnos_noche = [t.id for t in turnos_qs if t.es_nocturno]
    
    # Diccionario duraciones: "1": 12, "2": 24... (La API espera keys como strings)
    duracion_turnos = {str(t.id): float(t.duracion_horas) for t in turnos_qs}
    
    # Max value es simplemente el ID más alto o la cantidad? 
    # OJO: La API suele usar enteros para la matriz. Si tus IDs son 1, 5, 9... la API puede confundirse
    # si espera un rango contiguo [1..N].
    # *POR AHORA*: Asumimos que la API maneja los IDs que le mandamos en `turnos_a_cubrir`.
    # Si la API necesita índices 1..N estrictos, habría que hacer un mapeo extra aquí.
    max_turno_val = max(turnos_a_cubrir) if turnos_a_cubrir else 0

    # ---------------------------------------------------------
    # 6. REGLAS DE COBERTURA (Demandas)
    # ---------------------------------------------------------
    
    # Helpers para extraer demanda de un objeto Regla o Excepcion
    def extraer_demanda(regla_qs):
        # Devuelve dict: {"1": {"junior": X, "senior": Y}, ...}
        resultado = {}
        for r in regla_qs:
            t_str = str(r.turno.id)
            resultado[t_str] = {
                "junior": r.cantidad_junior,
                "senior": r.cantidad_senior
            }
        return resultado

    # 6.1. Demanda Normal (Lunes a Viernes)
    # Buscamos la regla del LUNES (0) como representativa
    reglas_normal = ReglaDemandaSemanal.objects.filter(plantilla=plantilla, dia=DiaSemana.LUNES)
    dict_demanda_normal = extraer_demanda(reglas_normal)

    # 6.2. Demanda Finde (Sábado/Domingo)
    # Buscamos la regla del SÁBADO (5)
    reglas_finde = ReglaDemandaSemanal.objects.filter(plantilla=plantilla, dia=DiaSemana.SABADO)
    dict_demanda_finde = extraer_demanda(reglas_finde)

    # 6.3. Días Pico (Excepciones)
    dias_pico_indices = []
    dict_demanda_pico = {}
    
    # Iteramos todos los días del rango para ver si caen en una excepción
    # Y de paso construimos el mapa de fechas -> índices
    fecha_iter = fecha_inicio
    for i in range(num_dias):
        # Buscamos excepción para esta fecha específica
        excepcion = ExcepcionDemanda.objects.filter(plantilla=plantilla, fecha=fecha_iter)
        
        if excepcion.exists():
            dias_pico_indices.append(i)
            # Tomamos la definición de demanda de la primera ocurrencia (asumiendo consistencia)
            if not dict_demanda_pico:
                dict_demanda_pico = extraer_demanda(excepcion)
        
        fecha_iter += timedelta(days=1)

    reglas_cobertura = {
        "dias_pico": dias_pico_indices,
        "demanda_pico": dict_demanda_pico if dict_demanda_pico else dict_demanda_normal, # Fallback
        "demanda_finde": dict_demanda_finde,
        "demanda_normal": dict_demanda_normal
    }

    # ---------------------------------------------------------
    # 7. EXCEPCIONES Y PREFERENCIAS
    # ---------------------------------------------------------
    
    # 7.1 Disponibilidad
    excepciones_disponibilidad = []
    # Buscamos ausencias que solapen con el rango
    no_disp_qs = NoDisponibilidad.objects.filter(
        empleado__in=empleados_qs,
        fecha_inicio__lte=fecha_fin,
        fecha_fin__gte=fecha_inicio
    )

    for nd in no_disp_qs:
        # Calcular índices relativos
        inicio_rel = (nd.fecha_inicio - fecha_inicio).days
        fin_rel = (nd.fecha_fin - fecha_inicio).days
        
        # Recortar al rango actual (clamp)
        start_idx = max(0, inicio_rel)
        end_idx = min(num_dias, fin_rel + 1) # +1 para range de python exclusivo

        if start_idx < end_idx: # Solo si hay solapamiento real
            prof_idx = mapa_id_a_indice[nd.empleado.id]
            excepciones_disponibilidad.append({
                "prof_index": prof_idx,
                "dias_range": [start_idx, end_idx], # API espera [start, end_exclusive]
                "disponible": False
            })

    # 7.2 Preferencias
    excepciones_preferencias = []
    prefs_qs = Preferencia.objects.filter(
        empleado__in=empleados_qs,
        fecha__range=[fecha_inicio, fecha_fin]
    )
    
    # Agrupar preferencias por (dia, tipo_turno, deseo) podría ser complejo
    # La API actual recibe: {"prof_indices": [0, 1], "dia": 5, "valor": -1}
    # Por simplicidad, mandaremos una entrada por cada preferencia individual
    # (La API debería bancarse esto, o si no agrupamos)
    
    for pref in prefs_qs:
        dia_idx = (pref.fecha - fecha_inicio).days
        prof_idx = mapa_id_a_indice[pref.empleado.id]
        
        # Valor: Trabajar (+) / Descansar (-)
        # Peso base de la configuración * signo
        peso_base = config.peso_preferencia_turno if pref.tipo_turno else config.peso_preferencia_dias_libres
        valor = peso_base if pref.deseo == 'TRABAJAR' else -peso_base
        
        excepciones_preferencias.append({
            "prof_indices": [prof_idx], # Lista de 1 elemento
            "dia": dia_idx,
            "valor": valor
        })

    # ---------------------------------------------------------
    # 8. CONSTRUCCIÓN FINAL
    # ---------------------------------------------------------
    
    # Secuencias prohibidas
    seq_qs = SecuenciaProhibida.objects.filter(especialidad=especialidad)
    secuencias = [[s.turno_previo.id, s.turno_siguiente.id] for s in seq_qs]

    datos_problema = {
        "num_dias": num_dias,
        "max_turno_val": max_turno_val,
        "turnos_a_cubrir": turnos_a_cubrir,
        "skills_a_cubrir": ["junior", "senior"], # Hardcodeado según tu modelo
        "turnos_noche": turnos_noche,
        "duracion_turnos": duracion_turnos,
        "pesos_fitness": {
            "eq": config.peso_equidad_general,
            "dif": config.peso_equidad_dificil,
            "pdl": config.peso_preferencia_dias_libres,
            "pte": config.peso_preferencia_turno,
            "alpha_pte": config.factor_alpha_pte
        },
        "tolerancia_equidad_general": config.tolerancia_general,
        "tolerancia_equidad_dificil": config.tolerancia_dificil,
        "lista_profesionales": lista_profesionales,
        "reglas_cobertura": reglas_cobertura,
        "secuencias_prohibidas": secuencias,
        "excepciones_disponibilidad": excepciones_disponibilidad,
        "excepciones_preferencias": excepciones_preferencias
    }

    return {
        "config": payload_config,
        "datos_problema": datos_problema,
        "estrategias": payload_estrategias
    }

import requests

def invocar_api_planificacion(payload):
    """
    Envía el JSON a la API de optimización y devuelve la respuesta.
    """
    # URL del servicio de optimización dentro de la red de Docker
    # El nombre del host suele ser el nombre del servicio en docker-compose.yml
    # Si tu servicio de API se llama 'optimization_engine' o 'api', úsalo aquí.
    # Por defecto en tu repo suele ser: http://optimization_engine:5000/planificar
    
    url = "http://optimizer:8000/planificar"
    
    try:
        response = requests.post(url, json=payload, timeout=300) # 5 min timeout por si el AG tarda
        response.raise_for_status() # Lanza error si no es 200 OK
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error conectando con la API: {e}")
        return None
    

def consultar_resultado_ag(job_id):
    """
    Consulta el endpoint de resultados de la API para ver si el trabajo terminó.
    """
    # IMPORTANTE: Usamos el nombre del servicio Docker 'optimizer'
    url = f"http://optimizer:8000/result/{job_id}"
    
    try:
        response = requests.get(url, timeout=10)
        # Si la API devuelve 202 (Processing) o 200 (OK)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 202:
            return {"status": "running", "mensaje": "El algoritmo sigue ejecutando..."}
        else:
            return {"status": "error", "error": f"API Error: {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        print(f"Error consultando estado: {e}")
        return None