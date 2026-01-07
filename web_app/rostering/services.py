import json
import traceback
import requests
import os
from datetime import timedelta, datetime, date
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.dateparse import parse_date

# --- MODELOS ---
from .models import (
    Empleado, TipoTurno, PlantillaDemanda, ReglaDemandaSemanal,
    ExcepcionDemanda, NoDisponibilidad, Preferencia, 
    ConfiguracionAlgoritmo, SecuenciaProhibida, DiaSemana,
    Cronograma, Asignacion, TrabajoPlanificacion
)

# ==============================================================================
# LÓGICA DE ORQUESTACIÓN Y NEGOCIO (NUEVO)
# ==============================================================================

def iniciar_proceso_optimizacion(data):
    """
    Orquesta todo el flujo de inicio de una planificación:
    1. Valida los datos de entrada.
    2. Genera el payload matemático.
    3. Invoca al motor de optimización.
    4. Guarda el estado inicial en TrabajoPlanificacion.
    
    Retorna: job_id (str)
    Raises: ValueError, ValidationError, ConnectionError
    """
    # 1. Extracción y Validación de Parámetros
    fecha_inicio_str = data.get('fecha_inicio')
    fecha_fin_str = data.get('fecha_fin')
    especialidad = data.get('especialidad')
    plantilla_id = data.get('plantilla_id')

    if not all([fecha_inicio_str, fecha_fin_str, especialidad, plantilla_id]):
        raise ValueError('Faltan parámetros obligatorios (fecha_inicio, fecha_fin, especialidad, plantilla_id).')

    inicio = parse_date(fecha_inicio_str)
    fin = parse_date(fecha_fin_str)
    
    if not inicio or not fin:
        raise ValueError('Formato de fecha inválido. Usar YYYY-MM-DD.')

    # 2. Generar el Payload (Aquí ocurren las validaciones de negocio como uniformidad de turnos)
    payload = generar_payload_ag(inicio, fin, especialidad, plantilla_id)

    # 3. Invocar a la API Python
    respuesta_api = invocar_api_planificacion(payload)

    if not respuesta_api or 'job_id' not in respuesta_api:
        msg = 'No se pudo iniciar el trabajo en el motor de IA.'
        if respuesta_api and 'detail' in respuesta_api:
            msg += f" Detalle: {respuesta_api['detail']}"
        raise ConnectionError(msg)

    job_id = respuesta_api['job_id']

    # 4. Guardar contexto para recuperarlo cuando termine el algoritmo
    TrabajoPlanificacion.objects.create(
        job_id=job_id,
        fecha_inicio=inicio,
        fecha_fin=fin,
        especialidad=especialidad,
        payload_original=payload,
        plantilla_demanda_id=plantilla_id
    )

    return job_id


def construir_matriz_cronograma(cronograma):
    """
    Transforma la data relacional del cronograma en una estructura de matriz
    fácil de renderizar en HTML (Filas = Empleados, Columnas = Días).
    
    Retorna un diccionario con 'rango_fechas' y 'filas_tabla'.
    """
    # 1. Generar encabezados de columnas (Fechas)
    rango_fechas = []
    fecha_iter = cronograma.fecha_inicio
    while fecha_iter <= cronograma.fecha_fin:
        rango_fechas.append(fecha_iter)
        fecha_iter += timedelta(days=1)
        
    # 2. Obtener todas las asignaciones (Eager loading para optimizar)
    asignaciones = Asignacion.objects.filter(
        cronograma=cronograma
    ).select_related('empleado', 'tipo_turno')
    
    # 3. Construir Matriz rápida: dict[empleado_id][fecha_str] = turno
    matriz_asignaciones = {}
    for asig in asignaciones:
        emp_id = asig.empleado.id
        fecha_str = asig.fecha.strftime("%Y-%m-%d")
        
        if emp_id not in matriz_asignaciones:
            matriz_asignaciones[emp_id] = {}
        
        matriz_asignaciones[emp_id][fecha_str] = asig.tipo_turno

    # 4. Obtener lista de empleados ordenada
    empleados = Empleado.objects.filter(
        especialidad=cronograma.especialidad, 
        activo=True
    ).order_by('experiencia', 'legajo')

    # 5. Construir estructura para el template
    filas_tabla = []
    for emp in empleados:
        celdas = []
        horas_totales = 0
        turnos_totales = 0
        
        for fecha in rango_fechas:
            fecha_key = fecha.strftime("%Y-%m-%d")
            turno = matriz_asignaciones.get(emp.id, {}).get(fecha_key)
            
            celdas.append({
                'fecha': fecha,
                'turno': turno, # Puede ser None
            })
            
            if turno:
                horas_totales += turno.duracion_horas
                turnos_totales += 1
                
        filas_tabla.append({
            'empleado': emp,
            'celdas': celdas,
            'stats': {'horas': horas_totales, 'turnos': turnos_totales}
        })
        
    return {
        'rango_fechas': rango_fechas,
        'filas_tabla': filas_tabla
    }


# ==============================================================================
# FUNCIONES AUXILIARES EXISTENTES (YA LIMPIAS)
# ==============================================================================

def generar_payload_ag(fecha_inicio, fecha_fin, especialidad, plantilla_id=None):
    """Construye el diccionario JSON para la API."""
    num_dias = (fecha_fin - fecha_inicio).days + 1
    if num_dias < 1:
        raise ValueError("La fecha de fin debe ser posterior a la fecha de inicio.")

    # --- VALIDACIÓN NUEVA ---
    if num_dias < 7:
        raise ValueError(f"El período es demasiado corto ({num_dias} días). Mínimo 7 días.")
    if num_dias > 31:
        raise ValueError(f"El período excede el límite permitido ({num_dias} días). Máximo 31 días.")
    # ------------------------

    turnos_qs = TipoTurno.objects.filter(especialidad=especialidad)
    duraciones = set(t.duracion_horas for t in turnos_qs)
    
    if len(duraciones) > 1:
        raise ValidationError(f"Error de Uniformidad: Tienes turnos de distintas duraciones ({duraciones} hs).")

    config = ConfiguracionAlgoritmo.objects.filter(activa=True).first() or ConfiguracionAlgoritmo()

    if plantilla_id:
        plantilla = PlantillaDemanda.objects.get(pk=plantilla_id)
    else:
        plantilla = PlantillaDemanda.objects.filter(especialidad=especialidad).first()
        if not plantilla:
            raise ValueError(f"No hay plantilla de demanda creada para {especialidad}")

    # Configuración del AG
    payload_config = {
        "pop_size": config.tamano_poblacion,
        "generaciones": config.generaciones,
        "pc": config.prob_cruce,
        "pm": config.prob_mutacion,
        "elitismo": config.elitismo,
        "seed": config.semilla or 42
    }
    payload_estrategias = {
        "sel": config.estrategia_seleccion,
        "cross": config.estrategia_cruce,
        "mut": config.estrategia_mutacion
    }

    # Datos Profesionales
    factor_tiempo = num_dias / 30.0
    empleados_qs = Empleado.objects.filter(especialidad=especialidad, activo=True)
    lista_profesionales = []
    mapa_id_a_indice = {} 

    for idx, emp in enumerate(empleados_qs):
        mapa_id_a_indice[emp.id] = idx
        skill = emp.experiencia.lower()
        t_min = int(emp.min_turnos_mensuales * factor_tiempo)
        t_max = int(emp.max_turnos_mensuales * factor_tiempo)
        if t_max < t_min: t_max = t_min

        lista_profesionales.append({
            "id_db": emp.id,
            "nombre": emp.nombre_completo,
            "skill": skill,
            "t_min": t_min,
            "t_max": t_max,
        })

    # Datos Turnos
    turnos_a_cubrir = [t.id for t in turnos_qs]
    turnos_noche = [t.id for t in turnos_qs if t.es_nocturno]
    duracion_turnos = {str(t.id): float(t.duracion_horas) for t in turnos_qs}
    max_turno_val = max(turnos_a_cubrir) if turnos_a_cubrir else 0

    # Reglas de Cobertura
    def extraer_demanda(regla_qs):
        resultado = {}
        for r in regla_qs:
            resultado[str(r.turno.id)] = {"junior": r.cantidad_junior, "senior": r.cantidad_senior}
        return resultado

    dict_demanda_normal = extraer_demanda(ReglaDemandaSemanal.objects.filter(plantilla=plantilla, dia=DiaSemana.LUNES))
    dict_demanda_finde = extraer_demanda(ReglaDemandaSemanal.objects.filter(plantilla=plantilla, dia=DiaSemana.SABADO))
    
    dias_pico_indices = []
    dict_demanda_pico = {}
    fecha_iter = fecha_inicio
    for i in range(num_dias):
        excepcion = ExcepcionDemanda.objects.filter(plantilla=plantilla, fecha=fecha_iter)
        if excepcion.exists():
            dias_pico_indices.append(i)
            if not dict_demanda_pico: dict_demanda_pico = extraer_demanda(excepcion)
        fecha_iter += timedelta(days=1)

    reglas_cobertura = {
        "dias_pico": dias_pico_indices,
        "demanda_pico": dict_demanda_pico if dict_demanda_pico else dict_demanda_normal,
        "demanda_finde": dict_demanda_finde,
        "demanda_normal": dict_demanda_normal
    }

    # Excepciones y Preferencias
    excepciones_disponibilidad = []
    for nd in NoDisponibilidad.objects.filter(empleado__in=empleados_qs, fecha_inicio__lte=fecha_fin, fecha_fin__gte=fecha_inicio):
        start = max(0, (nd.fecha_inicio - fecha_inicio).days)
        end = min(num_dias, (nd.fecha_fin - fecha_inicio).days + 1)
        if start < end:
            excepciones_disponibilidad.append({"prof_index": mapa_id_a_indice[nd.empleado.id], "dias_range": [start, end], "disponible": False})

    excepciones_preferencias = []
    for pref in Preferencia.objects.filter(empleado__in=empleados_qs, fecha__range=[fecha_inicio, fecha_fin]):
        dia_idx = (pref.fecha - fecha_inicio).days
        peso = config.peso_preferencia_turno if pref.tipo_turno else config.peso_preferencia_dias_libres
        valor = peso if pref.deseo == 'TRABAJAR' else -peso
        excepciones_preferencias.append({"prof_indices": [mapa_id_a_indice[pref.empleado.id]], "dia": dia_idx, "valor": valor})

    # Construcción final
    secuencias = [[s.turno_previo.id, s.turno_siguiente.id] for s in SecuenciaProhibida.objects.filter(especialidad=especialidad)]

    return {
        "config": payload_config,
        "datos_problema": {
            "num_dias": num_dias,
            "max_turno_val": max_turno_val,
            "turnos_a_cubrir": turnos_a_cubrir,
            "skills_a_cubrir": ["junior", "senior"],
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
        },
        "estrategias": payload_estrategias
    }


def invocar_api_planificacion(payload):
    """Envía el JSON a la API de optimización."""
    url = "http://optimizer:8000/planificar" 
    try:
        if os.getenv('DEBUG_PAYLOAD', 'False') == 'True':
            with open('debug_payload.json', 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, default=str)
        response = requests.post(url, json=payload, timeout=300) 
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error conectando con la API: {e}")
        return None
    

def consultar_resultado_ag(job_id):
    """Polling al endpoint de resultados."""
    url = f"http://optimizer:8000/result/{job_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 202:
            return {"status": "running", "mensaje": "El algoritmo sigue ejecutando..."}
        else:
            return {"status": "error", "error": f"API Error: {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}


def guardar_solucion_db(fecha_inicio, fecha_fin, especialidad, payload_original, resultado, plantilla_demanda=None):
    """Persiste el Cronograma y Asignaciones."""
    print("--- DEBUG: INICIANDO GUARDADO DB ---")
    try:
        matriz_solucion = resultado.get('matriz_solucion') or resultado.get('solution')
        if not matriz_solucion:
            raise ValueError("La API devolvió una matriz de solución vacía.")

        fitness = resultado.get('fitness', 0)
        tiempo = resultado.get('tiempo_ejecucion', 0)
        explicabilidad = resultado.get('explicabilidad', {})
        config_activa = ConfiguracionAlgoritmo.objects.filter(activa=True).first()

        # 1. Recuperar empleados del payload original para mantener el orden
        lista_empleados_payload = payload_original['datos_problema']['lista_profesionales']
        mapa_idx_a_empleado_id = {idx: emp['id_db'] for idx, emp in enumerate(lista_empleados_payload)}
        
        # Traer objetos reales de la DB
        empleados_db = Empleado.objects.filter(id__in=mapa_idx_a_empleado_id.values())
        empleados_map = {e.id: e for e in empleados_db}

        # 2. Calcular factor de tiempo para escalar el reporte (SOLUCIÓN GRÁFICO)
        # Si planifico 15 días, el objetivo debe ser la mitad del mensual.
        num_dias = (fecha_fin - fecha_inicio).days + 1
        factor_tiempo = num_dias / 30.0

        # Obtener duración de referencia (protección contra None)
        turno_ref = TipoTurno.objects.filter(especialidad=especialidad).first()
        duracion_horas = float(turno_ref.duracion_horas) if (turno_ref and turno_ref.duracion_horas) else 12.0
        
        nombres_cortos, nombres_largos, limites_contractuales = [], [], []

        for i, emp_payload in enumerate(lista_empleados_payload):
            emp = empleados_map.get(emp_payload['id_db'])
            if emp:
                full_name = emp.nombre_completo.strip()
                n_largo = full_name
                partes = full_name.split()
                n_corto = f"{partes[-1]}, {partes[0][0].upper()}." if len(partes) >= 2 else full_name
                
                # --- CÁLCULO ROBUSTO DE LÍMITES ---
                # Usamos (or 0) para evitar crash si el campo está vacío en DB
                min_mensual = float(emp.min_turnos_mensuales or 0)
                max_mensual = float(emp.max_turnos_mensuales or 0)
                
                # Escalamos proporcionalmente a los días planificados
                min_periodo_horas = min_mensual * factor_tiempo * duracion_horas
                max_periodo_horas = max_mensual * factor_tiempo * duracion_horas
                
                # Guardamos con 1 decimal
                limites = [round(min_periodo_horas, 1), round(max_periodo_horas, 1)]
            else:
                n_largo = f"Profesional {i+1}"
                n_corto = f"P{i+1}"
                limites = [0.0, 0.0]
            
            nombres_cortos.append(n_corto)
            nombres_largos.append(n_largo)
            limites_contractuales.append(limites)

        # 3. Actualizar el JSON de explicabilidad con los nuevos datos escalados
        if 'datos_equidad' not in explicabilidad: explicabilidad['datos_equidad'] = {}
        
        explicabilidad['datos_equidad'].update({
            'nombres_profesionales': nombres_largos,
            'nombres_cortos': nombres_cortos,
            'limites_contractuales': limites_contractuales # Este es el dato que lee el gráfico
        })
        
        # 4. Transacción Atómica para guardar todo
        with transaction.atomic():
            cronograma = Cronograma.objects.create(
                especialidad=especialidad,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                estado=Cronograma.Estado.BORRADOR,
                plantilla_demanda=plantilla_demanda,
                configuracion_usada=config_activa,
                fitness=fitness,
                tiempo_ejecucion=tiempo,
                reporte_analisis=explicabilidad 
            )
            
            turnos_db = {t.id: t for t in TipoTurno.objects.filter(especialidad=especialidad)}
            nuevas_asignaciones = []
            
            for i, fila in enumerate(matriz_solucion):
                emp_id = mapa_idx_a_empleado_id.get(i)
                if not emp_id: continue
                
                for j, t_id in enumerate(fila):
                    # t_id puede ser 0 o None (día libre), solo guardamos si hay turno
                    if t_id and t_id in turnos_db:
                        nuevas_asignaciones.append(Asignacion(
                            cronograma=cronograma, 
                            empleado_id=emp_id, 
                            fecha=fecha_inicio + timedelta(days=j), 
                            tipo_turno=turnos_db[t_id]
                        ))
            
            if nuevas_asignaciones: 
                Asignacion.objects.bulk_create(nuevas_asignaciones)
            
        print(f"--- DEBUG: GUARDADO EXITOSO (ID: {cronograma.id}) ---")
        return cronograma

    except Exception as e:
        print("\n🔴 CRASH EN GUARDAR_SOLUCION")
        print(traceback.format_exc()) 
        raise e