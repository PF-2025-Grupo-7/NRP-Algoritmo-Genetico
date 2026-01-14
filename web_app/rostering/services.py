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
def validar_cobertura_suficiente(fecha_inicio, fecha_fin, empleados_qs, plantilla):
    """
    Verifica capacidad con desglose Junior/Senior, descuento de ausencias y margen de seguridad.
    """
    # 1. Configuración Básica
    MARGEN_SEGURIDAD = 0.10
    dias_totales = (fecha_fin - fecha_inicio).days + 1
    factor_periodo = dias_totales / 30.0 
    
    turnos = TipoTurno.objects.filter(especialidad=plantilla.especialidad)
    if not turnos.exists():
        return False, {"error_generico": "No hay tipos de turno definidos."}
        
    duracion_promedio = sum(t.duracion_horas for t in turnos) / len(turnos)
    duracion_promedio = float(duracion_promedio)

    # 2. Cálculo de la Oferta (Horas Reales Disponibles)
    oferta = {'SENIOR': 0.0, 'JUNIOR': 0.0}
    ausencias_total_horas = 0.0
    
    ausencias = NoDisponibilidad.objects.filter(
        empleado__in=empleados_qs,
        fecha_fin__gte=fecha_inicio,
        fecha_inicio__lte=fecha_fin
    )

    for emp in empleados_qs:
        t_max = float(emp.max_turnos_mensuales or 0)
        horas_teoricas = t_max * duracion_promedio * factor_periodo
        
        horas_ausencia = 0.0
        mis_ausencias = [a for a in ausencias if a.empleado_id == emp.id]
        
        for aus in mis_ausencias:
            inicio_cruce = max(aus.fecha_inicio, fecha_inicio)
            fin_cruce = min(aus.fecha_fin, fecha_fin)
            dias_cruce = (fin_cruce - inicio_cruce).days + 1
            
            if dias_cruce > 0:
                if aus.tipo_turno:
                    horas_ausencia += (dias_cruce * float(aus.tipo_turno.duracion_horas))
                else:
                    horas_ausencia += (dias_cruce * duracion_promedio)

        horas_netas = max(0, horas_teoricas - horas_ausencia)
        ausencias_total_horas += horas_ausencia
        
        rol = emp.experiencia.upper() if emp.experiencia else 'JUNIOR'
        if rol not in oferta: rol = 'JUNIOR'
        oferta[rol] += horas_netas

    # 3. Cálculo de la Demanda (Requerimiento Exacto)
    demanda = {'SENIOR': 0.0, 'JUNIOR': 0.0}
    
    reglas = ReglaDemandaSemanal.objects.filter(plantilla=plantilla).select_related('turno')
    mapa_reglas = {d: [] for d in range(7)}
    for r in reglas:
        # r.dias es una lista de días (ej: [0, 1, 2, 3, 4] para lunes-viernes)
        for dia in r.dias:
            mapa_reglas[dia].append(r)
        
    # --- CORRECCIÓN: REPLICACIÓN DE REGLAS (Lunes->Viernes, Sábado->Domingo) ---
    # Esto alinea la validación con lo que realmente hace el algoritmo después.
    if mapa_reglas[0]: # Si hay reglas el Lunes
        for d in range(1, 5): # Martes(1) a Viernes(4)
            if not mapa_reglas[d]:
                mapa_reglas[d] = mapa_reglas[0] # Copiamos la referencia
    
    if mapa_reglas[5]: # Si hay reglas el Sábado
        if not mapa_reglas[6]: # Y Domingo vacío
            mapa_reglas[6] = mapa_reglas[5]
    # --------------------------------------------------------------------------

    excepciones = ExcepcionDemanda.objects.filter(
        plantilla=plantilla, 
        fecha__range=[fecha_inicio, fecha_fin]
    ).select_related('turno')
    
    mapa_excepciones = {}
    for ex in excepciones:
        f_str = ex.fecha.strftime("%Y-%m-%d")
        if f_str not in mapa_excepciones: mapa_excepciones[f_str] = []
        mapa_excepciones[f_str].append(ex)

    fecha_iter = fecha_inicio
    while fecha_iter <= fecha_fin:
        dia_sem = fecha_iter.weekday()
        f_str = fecha_iter.strftime("%Y-%m-%d")
        
        items_dia = []
        if f_str in mapa_excepciones:
            items_dia = mapa_excepciones[f_str]
        else:
            items_dia = mapa_reglas[dia_sem]
            
        for item in items_dia:
            dur = float(item.turno.duracion_horas)
            demanda['SENIOR'] += (item.cantidad_senior * dur)
            demanda['JUNIOR'] += (item.cantidad_junior * dur)
            
        fecha_iter += timedelta(days=1)

    demanda_con_margen = {k: v * (1 + MARGEN_SEGURIDAD) for k, v in demanda.items()}
    
    # 4. Balance y Veredicto
    balance_senior = oferta['SENIOR'] - demanda_con_margen['SENIOR']
    balance_junior = oferta['JUNIOR'] - demanda_con_margen['JUNIOR']
    
    es_viable_senior = balance_senior >= -5.0 
    es_viable_junior = balance_junior >= -5.0
    
    if not es_viable_senior or not es_viable_junior:
        datos_error = {
            "senior": {
                "oferta": int(oferta['SENIOR']),
                "demanda": int(demanda_con_margen['SENIOR']),
                "balance": int(balance_senior),
                "estado": "CRITICO" if not es_viable_senior else "OK"
            },
            "junior": {
                "oferta": int(oferta['JUNIOR']),
                "demanda": int(demanda_con_margen['JUNIOR']),
                "balance": int(balance_junior),
                "estado": "CRITICO" if not es_viable_junior else "OK"
            },
            "global": {
                "ausencias_impacto": int(ausencias_total_horas),
                "margen_seguridad": int(MARGEN_SEGURIDAD * 100),
                "dias": dias_totales
            }
        }
        return False, datos_error

    return True, None

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

    # Validación RF04
    plantilla = PlantillaDemanda.objects.get(pk=plantilla_id)
    empleados_qs = Empleado.objects.filter(especialidad=especialidad, activo=True)
    
    es_viable, datos_error = validar_cobertura_suficiente(inicio, fin, empleados_qs, plantilla)
    
    if not es_viable:
        # Lanzamos ValidationError pasando el diccionario. 
        # Django permite pasar dicts o listas en ValidationError.
        raise ValidationError(
            message="Imposible cubrir la demanda con la dotación actual.",
            params=datos_error # Adjuntamos los datos técnicos aquí
        )
    
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
import copy
from datetime import timedelta
# Asegúrate de importar tus modelos y DiaSemana
from .models import (
    ConfiguracionAlgoritmo, PlantillaDemanda, Empleado, TipoTurno, 
    ReglaDemandaSemanal, DiaSemana, ExcepcionDemanda, NoDisponibilidad, 
    Preferencia, SecuenciaProhibida
)

def generar_payload_ag(fecha_inicio, fecha_fin, especialidad, plantilla_id=None):
    """Construye el JSON con estructura de Demanda Semanal Explícita Plana."""
    num_dias = (fecha_fin - fecha_inicio).days + 1
    if num_dias < 1: raise ValueError("Fechas inválidas.")

    # 1. Configuración y Plantilla
    config = ConfiguracionAlgoritmo.objects.filter(activa=True).first() or ConfiguracionAlgoritmo()
    if plantilla_id:
        plantilla = PlantillaDemanda.objects.get(pk=plantilla_id)
    else:
        plantilla = PlantillaDemanda.objects.filter(especialidad=especialidad).first()
        if not plantilla: raise ValueError(f"No hay plantilla para {especialidad}")

    # 2. Configuración Básica
    payload_config = {
        "pop_size": config.tamano_poblacion,
        "generaciones": config.generaciones,
        "pc": config.prob_cruce,
        "pm": config.prob_mutacion,
        "elitismo": config.elitismo,
        "seed": config.semilla or 42
    }

    # 3. Profesionales
    factor_tiempo = 1.0 if 28 <= num_dias <= 31 else (num_dias / 30.0)
    empleados_qs = Empleado.objects.filter(especialidad=especialidad, activo=True)
    lista_profesionales = []
    mapa_id_a_indice = {} 

    for idx, emp in enumerate(empleados_qs):
        mapa_id_a_indice[emp.id] = idx
        lista_profesionales.append({
            "id_db": emp.id,
            "id": emp.id, 
            "nombre": emp.nombre_completo,
            "skill": emp.experiencia.strip().lower() if emp.experiencia else "junior",
            "t_min": int(emp.min_turnos_mensuales * factor_tiempo),
            "t_max": int(emp.max_turnos_mensuales * factor_tiempo),
        })

    # 4. Turnos
    turnos_qs = TipoTurno.objects.filter(especialidad=especialidad)
    turnos_a_cubrir = [t.id for t in turnos_qs]
    turnos_noche = [t.id for t in turnos_qs if t.es_nocturno]
    duracion_turnos = {str(t.id): float(t.duracion_horas) for t in turnos_qs}
    max_turno_val = max(turnos_a_cubrir) if turnos_a_cubrir else 0

    # =========================================================================
    # 5. GENERACIÓN DE DEMANDA EXPLÍCITA (LISTA PLANA DÍA A DÍA)
    # =========================================================================
    
    # A. Cargar reglas base en un diccionario temporal (0=Lunes ... 6=Domingo)
    plantilla_semanal = {d: {} for d in range(7)}
    
    reglas_db = ReglaDemandaSemanal.objects.filter(plantilla=plantilla).select_related('turno')
    mapa_dias_db = {
        DiaSemana.LUNES: 0, DiaSemana.MARTES: 1, DiaSemana.MIERCOLES: 2,
        DiaSemana.JUEVES: 3, DiaSemana.VIERNES: 4, DiaSemana.SABADO: 5, DiaSemana.DOMINGO: 6
    }

    for regla in reglas_db:
        # AQUÍ ES DONDE ANTES HUBO PROBLEMAS CON 'dia' vs 'dias'
        # Asumimos que el modelo ya se arregló o usás la versión correcta.
        # Si tu modelo actual usa 'dias' (lista), hay que iterar. 
        # Si usa 'dia' (entero), es directo.
        # Basado en tu último código de models.py, 'dias' es un JSONField (lista de enteros).
        
        lista_dias = regla.dias if isinstance(regla.dias, list) else []
        
        for d_int in lista_dias:
            # IMPORTANTE: Usamos str(ID) para compatibilidad JSON
            turno_str = str(regla.turno.id)
            if d_int not in plantilla_semanal: plantilla_semanal[d_int] = {}
            
            plantilla_semanal[d_int][turno_str] = {
                "junior": regla.cantidad_junior,
                "senior": regla.cantidad_senior
            }

    # B. Aplicar lógica de replicación (Si no hay datos explícitos)
    # NOTA: Al pasar a Reglas con lista de días explícita, la replicación automática
    # Lunes->Viernes pierde un poco de sentido si el usuario ya eligió los días,
    # pero la dejamos por seguridad si la lista viene vacía en días clave.
    demanda_lunes = plantilla_semanal.get(0)
    if demanda_lunes: 
        for d in range(1, 5): # 1, 2, 3, 4
            if not plantilla_semanal[d]:
                plantilla_semanal[d] = copy.deepcopy(demanda_lunes)
    
    demanda_sabado = plantilla_semanal.get(5)
    if demanda_sabado: 
        if not plantilla_semanal[6]: 
            plantilla_semanal[6] = copy.deepcopy(demanda_sabado)

    # C. Construir la LISTA MAESTRA día por día
    requerimientos_cobertura_explicita = []
    dias_no_habiles_indices = []
    
    fecha_iter = fecha_inicio
    for i in range(num_dias):
        dia_semana = fecha_iter.weekday() # 0=Lunes
        
        # 1. Obtener base del día de la semana
        demanda_dia = copy.deepcopy(plantilla_semanal.get(dia_semana, {}))
        
        # 2. Detectar Finde (Sábado y Domingo)
        if dia_semana >= 5: 
            dias_no_habiles_indices.append(i)
        
        # 3. Aplicar Excepciones (Feriados, Picos)
        excepciones_db = ExcepcionDemanda.objects.filter(plantilla=plantilla, fecha=fecha_iter).select_related('turno')
        
        if excepciones_db.exists():
            if i not in dias_no_habiles_indices:
                dias_no_habiles_indices.append(i)
            
            for ex in excepciones_db:
                demanda_dia[str(ex.turno.id)] = {
                    "junior": ex.cantidad_junior,
                    "senior": ex.cantidad_senior,
                    # --- NUEVO: Pasamos el flag al algoritmo ---
                    "es_dificil": ex.es_turno_dificil 
                    # -------------------------------------------
                }

        # 4. Agregar a la lista maestra
        requerimientos_cobertura_explicita.append(demanda_dia)
        
        fecha_iter += timedelta(days=1)

    # =========================================================================

    # 6. Excepciones Disponibilidad
    excepciones_disponibilidad = []
    for nd in NoDisponibilidad.objects.filter(empleado__in=empleados_qs, fecha_inicio__lte=fecha_fin, fecha_fin__gte=fecha_inicio):
        start = max(0, (nd.fecha_inicio - fecha_inicio).days)
        end = min(num_dias, (nd.fecha_fin - fecha_inicio).days + 1)
        prof_idx = mapa_id_a_indice.get(nd.empleado.id)
        if start < end and prof_idx is not None:
            excepciones_disponibilidad.append({"prof_index": prof_idx, "dias_range": [start, end], "disponible": False})

    # =========================================================================
    # 7. PROCESAMIENTO DE PREFERENCIAS (Con Límite MVP #34)
    # =========================================================================
    MAX_PREFERENCIAS_MVP = 3  # Límite hardcodeado para equidad
    
    # 1. Recuperamos TODAS las preferencias del periodo ordenadas por carga
    todas_prefs = Preferencia.objects.filter(
        empleado__in=empleados_qs, 
        fecha__range=[fecha_inicio, fecha_fin]
    ).order_by('id') # ID ascendente = orden cronológico de carga

    # 2. Agrupamos por empleado
    prefs_por_empleado = {}
    for p in todas_prefs:
        if p.empleado_id not in prefs_por_empleado:
            prefs_por_empleado[p.empleado_id] = []
        prefs_por_empleado[p.empleado_id].append(p)

    excepciones_preferencias = []
    
    for emp_id, lista_prefs in prefs_por_empleado.items():
        # A. Aplicamos el recorte: Nos quedamos con las ÚLTIMAS (más recientes)
        if len(lista_prefs) > MAX_PREFERENCIAS_MVP:
            seleccionadas = lista_prefs[-MAX_PREFERENCIAS_MVP:]
            print(f"⚖️ EQUIDAD: Empleado {emp_id} tenía {len(lista_prefs)} prefs. Se recortaron a las últimas {MAX_PREFERENCIAS_MVP}.")
        else:
            seleccionadas = lista_prefs

        # B. Generamos el payload solo con las aprobadas
        for pref in seleccionadas:
            dia_idx = (pref.fecha - fecha_inicio).days
            
            # Peso según tipo
            if pref.tipo_turno:
                peso = config.peso_preferencia_turno
            else:
                peso = config.peso_preferencia_dias_libres
            
            # Signo según deseo
            valor = peso if pref.deseo == 'TRABAJAR' else -peso
            
            prof_idx = mapa_id_a_indice.get(pref.empleado.id)
            if prof_idx is not None:
                excepciones_preferencias.append({
                    "prof_indices": [prof_idx], 
                    "dia": dia_idx, 
                    "valor": valor
                })

    # =========================================================================

    secuencias = []
    for s in SecuenciaProhibida.objects.filter(especialidad=especialidad):
        secuencias.append([s.turno_previo.id, s.turno_siguiente.id])

    return {
        "config": payload_config,
        "datos_problema": {
            "num_dias": num_dias,
            "requerimientos_cobertura_explicita": requerimientos_cobertura_explicita, 
            
            "dias_no_habiles": dias_no_habiles_indices,
            "reglas_cobertura": {}, # Se usa explicita ahora
            
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
            "secuencias_prohibidas": secuencias,
            "excepciones_disponibilidad": excepciones_disponibilidad,
            "excepciones_preferencias": excepciones_preferencias
        },
        "estrategias": {
            "sel": config.estrategia_seleccion,
            "cross": config.estrategia_cruce,
            "mut": config.estrategia_mutacion
        }
    }

import json
import requests

def invocar_api_planificacion(payload):
    """Envía el JSON a la API de optimización."""
    url = "http://optimizer:8000/planificar" 
    
    # --- BLOQUE ESPÍA: GUARDAR PAYLOAD ---
    print("🕵️ INTERCEPTANDO PAYLOAD...")
    try:
        with open('debug_payload.json', 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=4, default=str)
        print("✅ Payload guardado en 'debug_payload.json'")
    except Exception as e:
        print(f"⚠️ Error al guardar payload: {e}")
    # -------------------------------------

    try:
        response = requests.post(url, json=payload, timeout=300)
        
        # SI ES 422, LANZAMOS UNA EXCEPCIÓN MANUAL CON EL TEXTO DEL ERROR
        if response.status_code == 422:
            # Esto forzará a que el error aparezca en tus logs sí o sí
            raise ValueError(f"🛑 LA API RECHAZÓ EL JSON: {response.text}")

        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        # Si lanzamos el ValueError arriba, caerá aquí o en el try/catch superior
        print(f"Error fatal: {e}")
        raise e # Re-lanzamos para que se vea

    except requests.exceptions.HTTPError as e:
        # Si fue un 422, ya lo imprimimos arriba. 
        # Si fue otro error (500, 404), se imprimirá aquí.
        print(f"❌ Error HTTP: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")
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
    """
    Persiste el Cronograma y Asignaciones.
    AHORA INCLUYE: 
    1. Validación Post-Algoritmo (RF04).
    2. Detección Inteligente de Patrones (Insights).
    """
    print("--- DEBUG: INICIANDO GUARDADO CON VALIDACIÓN Y BI ---")
    try:
        matriz_solucion = resultado.get('matriz_solucion') or resultado.get('solution')
        if not matriz_solucion:
            raise ValueError("La API devolvió una matriz de solución vacía.")

        fitness = resultado.get('fitness', 0)
        tiempo = resultado.get('tiempo_ejecucion', 0)
        explicabilidad = resultado.get('explicabilidad', {})
        
        # Estructuras de reporte
        violaciones_blandas = explicabilidad.get('violaciones_blandas', {})
        if 'preferencia_libre_incumplida' not in violaciones_blandas: violaciones_blandas['preferencia_libre_incumplida'] = []
        if 'preferencia_turno_incumplida' not in violaciones_blandas: violaciones_blandas['preferencia_turno_incumplida'] = []
        
        violaciones_duras = explicabilidad.get('violaciones_duras', {})
        violaciones_duras['deficit_cobertura'] = [] 
        violaciones_duras['deficit_critico_senior'] = []

        config_activa = ConfiguracionAlgoritmo.objects.filter(activa=True).first()

        if isinstance(payload_original, str):
            try: payload_original = json.loads(payload_original)
            except: pass

        # 1. Recuperación de Datos Maestros
        datos_problema = payload_original.get('datos_problema', {})
        lista_empleados_payload = datos_problema.get('lista_profesionales', [])
        
        mapa_idx_a_empleado = {} 
        mapa_empleado_id_a_exp = {} 
        mapa_idx_a_empleado_id = {idx: emp['id_db'] for idx, emp in enumerate(lista_empleados_payload)}

        empleados_ids = [e['id_db'] for e in lista_empleados_payload]
        empleados_db = {e.id: e for e in Empleado.objects.filter(id__in=empleados_ids)}

        for i, emp_p in enumerate(lista_empleados_payload):
            emp_obj = empleados_db.get(emp_p['id_db'])
            if emp_obj:
                mapa_idx_a_empleado[i] = emp_obj
                mapa_empleado_id_a_exp[emp_obj.id] = emp_obj.experiencia.upper()

        # Datos Visuales
        num_dias = (fecha_fin - fecha_inicio).days + 1
        factor_tiempo = 1.0 if 28 <= num_dias <= 31 else (num_dias / 30.0)
        turno_ref = TipoTurno.objects.filter(especialidad=especialidad).first()
        duracion_horas = float(turno_ref.duracion_horas) if (turno_ref and turno_ref.duracion_horas) else 12.0
        
        nombres_cortos, nombres_largos, limites_contractuales = [], [], []
        for i, emp_payload in enumerate(lista_empleados_payload):
            emp = empleados_db.get(emp_payload['id_db'])
            if emp:
                full_name = emp.nombre_completo.strip()
                n_largo = full_name
                partes = full_name.split()
                n_corto = f"{partes[-1]}, {partes[0][0].upper()}." if len(partes) >= 2 else full_name
                
                min_mensual = float(emp.min_turnos_mensuales or 0)
                max_mensual = float(emp.max_turnos_mensuales or 0)
                limites = [round(min_mensual * factor_tiempo * duracion_horas, 1), 
                           round(max_mensual * factor_tiempo * duracion_horas, 1)]
            else:
                n_largo, n_corto, limites = f"P{i+1}", f"P{i+1}", [0.0, 0.0]
            
            nombres_cortos.append(n_corto)
            nombres_largos.append(n_largo)
            limites_contractuales.append(limites)

        # 2. Análisis de Asignaciones Reales
        asignaciones_reales = {} 
        conteo_cobertura = {} 

        for i, fila in enumerate(matriz_solucion):
            emp = mapa_idx_a_empleado.get(i)
            if not emp: continue
            
            if emp.id not in asignaciones_reales: asignaciones_reales[emp.id] = {}
            
            for j, t_id in enumerate(fila):
                if t_id:
                    fecha_dia = (fecha_inicio + timedelta(days=j)).strftime("%Y-%m-%d")
                    asignaciones_reales[emp.id][fecha_dia] = t_id
                    
                    if fecha_dia not in conteo_cobertura: conteo_cobertura[fecha_dia] = {}
                    if t_id not in conteo_cobertura[fecha_dia]: conteo_cobertura[fecha_dia][t_id] = {'SENIOR': 0, 'JUNIOR': 0}
                    
                    exp = mapa_empleado_id_a_exp.get(emp.id, 'JUNIOR').upper()
                    if exp in conteo_cobertura[fecha_dia][t_id]:
                        conteo_cobertura[fecha_dia][t_id][exp] += 1

        # 3. Auditoría de Preferencias
        prefs = Preferencia.objects.filter(
            fecha__range=[fecha_inicio, fecha_fin],
            empleado__in=empleados_db.values()
        ).select_related('empleado', 'tipo_turno')

        for p in prefs:
            fecha_str = p.fecha.strftime("%Y-%m-%d")
            turno_asignado_id = asignaciones_reales.get(p.empleado.id, {}).get(fecha_str)
            es_descanso = (p.deseo == Preferencia.Deseo.DESCANSAR)
            es_trabajo = (p.deseo == Preferencia.Deseo.TRABAJAR)

            if es_descanso:
                violation = False
                detalle = ""
                if turno_asignado_id: 
                    if p.tipo_turno is None:
                        violation = True; detalle = 'Se asignó guardia pese a pedido de descanso total'
                    elif p.tipo_turno.id == turno_asignado_id:
                        violation = True; detalle = f'Se asignó turno {p.tipo_turno.nombre} pese a bloqueo'
                if violation:
                    violaciones_blandas['preferencia_libre_incumplida'].append({
                        'empleado_id': p.empleado.id,
                        'nombre': p.empleado.nombre_completo,
                        'fecha': fecha_str,
                        'detalle': detalle
                    })
            elif es_trabajo:
                violation = False
                detalle = ""
                if not turno_asignado_id:
                     violation = True; detalle = 'No se asignó turno solicitado'
                elif p.tipo_turno and turno_asignado_id != p.tipo_turno.id:
                     violation = True; detalle = f'Se asignó turno distinto al {p.tipo_turno.nombre}'
                if violation:
                    violaciones_blandas['preferencia_turno_incumplida'].append({
                        'empleado_id': p.empleado.id,
                        'nombre': p.empleado.nombre_completo,
                        'fecha': fecha_str,
                        'detalle': detalle
                    })

        # 4. Auditoría de Cobertura y Detección de Patrones
        contador_slots_vacios_total = 0
        contador_slots_vacios_senior = 0
        demanda_total_teorica = 0
        
        # --- NUEVO: Estructuras para detección de patrones ---
        patron_deficit_semanal = {0:0, 1:0, 2:0, 3:0, 4:0, 5:0, 6:0}
        nombres_dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        # -----------------------------------------------------

        estado_cronograma = Cronograma.Estado.BORRADOR
        mensaje_validacion = "Optimización finalizada correctamente."

        if plantilla_demanda:
            reglas = plantilla_demanda.reglas.all().select_related('turno')
            excepciones = plantilla_demanda.excepciones.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('turno')
            cache_nombres_turnos = {t.id: t.nombre for t in TipoTurno.objects.filter(especialidad=especialidad)}

            mapa_reglas = {}
            for r in reglas:
                # Para cada día en la lista de días de la regla
                for dia in r.dias:
                    if dia not in mapa_reglas: 
                        mapa_reglas[dia] = {}
                    mapa_reglas[dia][r.turno.id] = r
            
            mapa_excepciones = {}
            for ex in excepciones:
                f_str = ex.fecha.strftime("%Y-%m-%d")
                if f_str not in mapa_excepciones: mapa_excepciones[f_str] = {}
                mapa_excepciones[f_str][ex.turno.id] = ex

            delta_dias = (fecha_fin - fecha_inicio).days + 1
            
            for d in range(delta_dias):
                fecha_actual = fecha_inicio + timedelta(days=d)
                fecha_str = fecha_actual.strftime("%Y-%m-%d")
                dia_semana_real = fecha_actual.weekday() 
                
                dia_referencia = 0 if dia_semana_real < 5 else 5
                
                reglas_del_dia = mapa_reglas.get(dia_semana_real)
                if not reglas_del_dia: reglas_del_dia = mapa_reglas.get(dia_referencia, {})
                
                ids_reglas = set(reglas_del_dia.keys())
                ids_excepciones = set(mapa_excepciones.get(fecha_str, {}).keys())
                todos_turnos_ids = ids_reglas.union(ids_excepciones)
                
                for turno_id in todos_turnos_ids:
                    regla = reglas_del_dia.get(turno_id)
                    obj_senior = regla.cantidad_senior if regla else 0
                    obj_junior = regla.cantidad_junior if regla else 0
                    
                    excepcion = mapa_excepciones.get(fecha_str, {}).get(turno_id)
                    if excepcion:
                        obj_senior = excepcion.cantidad_senior
                        obj_junior = excepcion.cantidad_junior

                    demanda_total_teorica += (obj_senior + obj_junior)

                    datos_reales = conteo_cobertura.get(fecha_str, {}).get(turno_id, {'SENIOR': 0, 'JUNIOR': 0})
                    real_senior = datos_reales['SENIOR']
                    real_junior = datos_reales['JUNIOR']
                    
                    falta_senior = max(0, obj_senior - real_senior)
                    falta_junior = max(0, obj_junior - real_junior)
                    
                    if falta_senior > 0 or falta_junior > 0:
                        turno_nombre = cache_nombres_turnos.get(turno_id, f"Turno {turno_id}")
                        
                        total_faltantes_evento = falta_senior + falta_junior
                        contador_slots_vacios_total += total_faltantes_evento
                        contador_slots_vacios_senior += falta_senior
                        
                        # --- NUEVO: Acumular para Insight ---
                        patron_deficit_semanal[dia_semana_real] += total_faltantes_evento
                        # ------------------------------------

                        detalle = []
                        if falta_senior > 0: 
                            detalle.append(f"Faltan {falta_senior} Seniors")
                            violaciones_duras['deficit_critico_senior'].append({
                                'fecha': fecha_str,
                                'turno': turno_nombre,
                                'detalle': f"Faltan {falta_senior} Seniors (Obj: {obj_senior} vs Real: {real_senior})"
                            })
                            
                        if falta_junior > 0: detalle.append(f"Faltan {falta_junior} Juniors")
                        
                        violaciones_duras['deficit_cobertura'].append({
                            'fecha': fecha_str,
                            'turno': turno_nombre,
                            'detalle': ", ".join(detalle) + f" (Obj: S{obj_senior}/J{obj_junior} vs Real: S{real_senior}/J{real_junior})"
                        })

            # 5. Generación de Insights (Detectives de patrones)
            insights = []
            total_deficit_mes = sum(patron_deficit_semanal.values())

            if total_deficit_mes > 0:
                dia_peor_idx = max(patron_deficit_semanal, key=patron_deficit_semanal.get)
                cantidad_peor = patron_deficit_semanal[dia_peor_idx]
                
                # Regla: Si un día concentra más del 25% de los fallos (y hay al menos 3 fallos ese día)
                porcentaje_concentracion = (cantidad_peor / total_deficit_mes) * 100
                
                if porcentaje_concentracion > 25 and cantidad_peor >= 3:
                    dia_nombre = nombres_dias[dia_peor_idx]
                    insights.append({
                        "tipo": "PATRON_DIA",
                        "titulo": f"Cuello de Botella: {dia_nombre}",
                        "mensaje": f"El {int(porcentaje_concentracion)}% de los déficits ocurren los días {dia_nombre}. "
                                   f"Se recomienda revisar ausencias recurrentes o reforzar la dotación para ese día.",
                        "nivel": "warning"
                    })
            
            explicabilidad['insights'] = insights

            # 6. Validación de Umbrales (RF04)
            porcentaje_deficit = 0
            if demanda_total_teorica > 0:
                porcentaje_deficit = (contador_slots_vacios_total / demanda_total_teorica) * 100
            
            print(f"📊 ANÁLISIS FINAL: Vacíos {contador_slots_vacios_total} ({porcentaje_deficit:.2f}%)")

            if contador_slots_vacios_senior > 0:
                estado_cronograma = 'FALLIDO'
                mensaje_validacion = f"FALLIDO: Faltan cubrir {contador_slots_vacios_senior} puestos Críticos de Senior."
                explicabilidad['estado_validacion'] = 'REJECTED'
                explicabilidad['motivo_rechazo'] = mensaje_validacion
            
            elif porcentaje_deficit > 1.5:
                estado_cronograma = 'FALLIDO'
                mensaje_validacion = f"FALLIDO: Déficit de cobertura ({porcentaje_deficit:.2f}%) supera el 1.5% permitido."
                explicabilidad['estado_validacion'] = 'REJECTED'
                explicabilidad['motivo_rechazo'] = mensaje_validacion
            
            else:
                estado_cronograma = Cronograma.Estado.BORRADOR
                explicabilidad['estado_validacion'] = 'APPROVED'
                if porcentaje_deficit > 0:
                    mensaje_validacion = f"ADVERTENCIA: Cronograma generado con {contador_slots_vacios_total} huecos menores ({porcentaje_deficit:.2f}%)."
                    explicabilidad['validacion_warning'] = mensaje_validacion

        # Guardar reporte
        explicabilidad['violaciones_duras'] = violaciones_duras
        explicabilidad['violaciones_blandas'] = violaciones_blandas
        explicabilidad['mensaje_validacion_final'] = mensaje_validacion
        
        if 'datos_equidad' not in explicabilidad: explicabilidad['datos_equidad'] = {}
        explicabilidad['datos_equidad'].update({
            'nombres_profesionales': nombres_largos,
            'nombres_cortos': nombres_cortos,
            'limites_contractuales': limites_contractuales
        })

        # 7. Persistencia
        with transaction.atomic():
            cronograma = Cronograma.objects.create(
                especialidad=especialidad,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                estado=estado_cronograma,
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
                    if t_id and t_id in turnos_db:
                        nuevas_asignaciones.append(Asignacion(
                            cronograma=cronograma, 
                            empleado_id=emp_id, 
                            fecha=fecha_inicio + timedelta(days=j), 
                            tipo_turno=turnos_db[t_id]
                        ))
            if nuevas_asignaciones: Asignacion.objects.bulk_create(nuevas_asignaciones)
            
        return cronograma

    except Exception as e:
        print("\n🔴 CRASH EN GUARDAR_SOLUCION")
        print(traceback.format_exc()) 
        raise e