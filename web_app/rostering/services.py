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
    RF04: Verifica si la capacidad total de horas de los empleados alcanza
    para cubrir la demanda teórica de la plantilla.
    Retorna (False, mensaje) si falta gente, o (True, "OK") si alcanza.
    """
    print(f"\n🔍 --- INICIO VALIDACIÓN DOTACIÓN (RF04) ---")
    
    dias_totales = (fecha_fin - fecha_inicio).days + 1
    print(f"📅 Periodo: {fecha_inicio} al {fecha_fin} ({dias_totales} días)")

    # 1. CALCULAR OFERTA (Horas Disponibles)
    horas_oferta = 0.0
    factor_periodo = dias_totales / 30.0 
    
    # Cacheamos duraciones
    turnos = TipoTurno.objects.filter(especialidad=plantilla.especialidad)
    mapa_duraciones = {t.id: (float(t.duracion_horas) if t.duracion_horas else 12.0) for t in turnos}
    
    if mapa_duraciones:
        duracion_promedio = sum(mapa_duraciones.values()) / len(mapa_duraciones)
    else:
        duracion_promedio = 12.0

    count_emps = 0
    for emp in empleados_qs:
        t_max = float(emp.max_turnos_mensuales or 0)
        horas_capacidad = t_max * duracion_promedio * factor_periodo
        horas_oferta += horas_capacidad
        count_emps += 1
        
    print(f"👥 Oferta: {count_emps} empleados activos. Total Horas Disponibles: {int(horas_oferta)}")

    # 2. CALCULAR DEMANDA (Horas Requeridas)
    horas_demanda = 0.0
    
    # Usamos filter directo para evitar problemas de atributos
    reglas = ReglaDemandaSemanal.objects.filter(plantilla=plantilla).select_related('turno')
    
    # IMPRIMIR REGLAS PARA DEBUG
    print(f"📋 Reglas encontradas en BD para la plantilla: {reglas.count()}")
    
    # MAPA SEGURO: Usamos los valores reales del ENUM DiaSemana
    # Orden de weekday(): 0=Lunes, 6=Domingo
    mapa_dias = [
        DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.MIERCOLES, 
        DiaSemana.JUEVES, DiaSemana.VIERNES, DiaSemana.SABADO, DiaSemana.DOMINGO
    ]
    
    fecha_iter = fecha_inicio
    while fecha_iter <= fecha_fin:
        # Obtenemos el valor correcto del Enum para este día
        dia_enum_val = mapa_dias[fecha_iter.weekday()]
        
        # Excepciones (Días pico)
        es_pico = False
        excepciones = ExcepcionDemanda.objects.filter(plantilla=plantilla, fecha=fecha_iter)
        
        if excepciones.exists():
            es_pico = True
            for ex in excepciones:
                cant = ex.cantidad_junior + ex.cantidad_senior
                dur = float(ex.turno.duracion_horas) if ex.turno and ex.turno.duracion_horas else duracion_promedio
                horas_demanda += (cant * dur)
        
        # Si no es pico, usamos regla semanal
        if not es_pico:
            # Comparamos contra el valor del Enum, no contra un string hardcodeado
            reglas_dia = [r for r in reglas if r.dia == dia_enum_val]
            
            for r in reglas_dia:
                cant = r.cantidad_junior + r.cantidad_senior
                dur = float(r.turno.duracion_horas) if r.turno and r.turno.duracion_horas else duracion_promedio
                horas_demanda += (cant * dur)
            
        fecha_iter += timedelta(days=1)

    print(f"📉 Demanda Calculada: {int(horas_demanda)} horas necesarias.")

    # 3. COMPARACIÓN
    balance = horas_oferta - horas_demanda
    margen_error = horas_demanda * 0.10 
    
    if balance < -margen_error:
        deficit = abs(int(balance))
        
        # CAMBIO: Devolvemos un diccionario con DATOS, no solo texto
        datos_error = {
            "horas_necesarias": int(horas_demanda),
            "horas_disponibles": int(horas_oferta),
            "deficit": deficit,
            "porcentaje_cobertura": int((horas_oferta / horas_demanda) * 100) if horas_demanda > 0 else 0,
            "empleados_activos": empleados_qs.count()
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
        d_idx = mapa_dias_db.get(regla.dia)
        if d_idx is not None:
            # IMPORTANTE: Usamos str(ID) para compatibilidad JSON
            turno_str = str(regla.turno.id)
            plantilla_semanal[d_idx][turno_str] = {
                "junior": regla.cantidad_junior,
                "senior": regla.cantidad_senior
            }

    # B. Aplicar lógica de replicación (Lunes->Viernes, Sábado->Domingo)
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
                    "senior": ex.cantidad_senior
                }

        # 4. Agregar a la lista maestra
        requerimientos_cobertura_explicita.append(demanda_dia)
        
        fecha_iter += timedelta(days=1)

    # =========================================================================

    # 6. Excepciones Disponibilidad y Preferencias
    excepciones_disponibilidad = []
    for nd in NoDisponibilidad.objects.filter(empleado__in=empleados_qs, fecha_inicio__lte=fecha_fin, fecha_fin__gte=fecha_inicio):
        start = max(0, (nd.fecha_inicio - fecha_inicio).days)
        end = min(num_dias, (nd.fecha_fin - fecha_inicio).days + 1)
        prof_idx = mapa_id_a_indice.get(nd.empleado.id)
        if start < end and prof_idx is not None:
            excepciones_disponibilidad.append({"prof_index": prof_idx, "dias_range": [start, end], "disponible": False})

    excepciones_preferencias = []
    for pref in Preferencia.objects.filter(empleado__in=empleados_qs, fecha__range=[fecha_inicio, fecha_fin]):
        dia_idx = (pref.fecha - fecha_inicio).days
        peso = config.peso_preferencia_turno if pref.tipo_turno else config.peso_preferencia_dias_libres
        valor = peso if pref.deseo == 'TRABAJAR' else -peso
        prof_idx = mapa_id_a_indice.get(pref.empleado.id)
        if prof_idx is not None:
            excepciones_preferencias.append({"prof_indices": [prof_idx], "dia": dia_idx, "valor": valor})

    secuencias = []
    for s in SecuenciaProhibida.objects.filter(especialidad=especialidad):
        secuencias.append([s.turno_previo.id, s.turno_siguiente.id])

    return {
        "config": payload_config,
        "datos_problema": {
            "num_dias": num_dias,
            "requerimientos_cobertura_explicita": requerimientos_cobertura_explicita, 
            
            "dias_no_habiles": dias_no_habiles_indices,
            # --- CORRECCIÓN AQUÍ: Diccionario {} en lugar de Lista [] ---
            "reglas_cobertura": {}, 
            # -----------------------------------------------------------
            
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
    AHORA INCLUYE: Validación Post-Algoritmo (RF04 - Dotación Insuficiente).
    Si el resultado tiene déficits graves, el cronograma se marca como FALLIDO.
    """
    print("--- DEBUG: INICIANDO GUARDADO CON VALIDACIÓN DE COBERTURA ---")
    try:
        matriz_solucion = resultado.get('matriz_solucion') or resultado.get('solution')
        if not matriz_solucion:
            raise ValueError("La API devolvió una matriz de solución vacía.")

        fitness = resultado.get('fitness', 0)
        tiempo = resultado.get('tiempo_ejecucion', 0)
        explicabilidad = resultado.get('explicabilidad', {})
        
        # Inicializar estructuras de reporte
        violaciones_blandas = explicabilidad.get('violaciones_blandas', {})
        if 'preferencia_libre_incumplida' not in violaciones_blandas: violaciones_blandas['preferencia_libre_incumplida'] = []
        if 'preferencia_turno_incumplida' not in violaciones_blandas: violaciones_blandas['preferencia_turno_incumplida'] = []
        
        violaciones_duras = explicabilidad.get('violaciones_duras', {})
        # Limpiamos basura del AG para llenar con nuestra auditoría precisa
        violaciones_duras['deficit_cobertura'] = [] 
        violaciones_duras['deficit_critico_senior'] = [] # Nueva categoría crítica

        config_activa = ConfiguracionAlgoritmo.objects.filter(activa=True).first()

        # Parsear Payload si viene como string
        if isinstance(payload_original, str):
            try: payload_original = json.loads(payload_original)
            except: pass

        # ---------------------------------------------------------
        # 1. Recuperación de Datos Maestros (Empleados y Turnos)
        # ---------------------------------------------------------
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

        # Datos para reporte visual
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

        # ---------------------------------------------------------
        # 2. Análisis de Asignaciones Reales (Matriz Resultante)
        # ---------------------------------------------------------
        asignaciones_reales = {} 
        conteo_cobertura = {} 

        for i, fila in enumerate(matriz_solucion):
            emp = mapa_idx_a_empleado.get(i)
            if not emp: continue
            
            if emp.id not in asignaciones_reales: asignaciones_reales[emp.id] = {}
            
            for j, t_id in enumerate(fila):
                if t_id: # Si hay turno asignado
                    fecha_dia = (fecha_inicio + timedelta(days=j)).strftime("%Y-%m-%d")
                    asignaciones_reales[emp.id][fecha_dia] = t_id
                    
                    if fecha_dia not in conteo_cobertura: conteo_cobertura[fecha_dia] = {}
                    if t_id not in conteo_cobertura[fecha_dia]: conteo_cobertura[fecha_dia][t_id] = {'SENIOR': 0, 'JUNIOR': 0}
                    
                    exp = mapa_empleado_id_a_exp.get(emp.id, 'JUNIOR').upper()
                    if exp in conteo_cobertura[fecha_dia][t_id]:
                        conteo_cobertura[fecha_dia][t_id][exp] += 1

        # ---------------------------------------------------------
        # 3. Auditoría de Preferencias (Igual que antes)
        # ---------------------------------------------------------
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
                        violation = True
                        detalle = 'Se asignó guardia pese a pedido de descanso total'
                    elif p.tipo_turno.id == turno_asignado_id:
                        violation = True
                        detalle = f'Se asignó turno {p.tipo_turno.nombre} pese a bloqueo'
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
                     violation = True
                     detalle = 'No se asignó turno solicitado'
                elif p.tipo_turno and turno_asignado_id != p.tipo_turno.id:
                     violation = True
                     detalle = f'Se asignó turno distinto al {p.tipo_turno.nombre}'
                if violation:
                    violaciones_blandas['preferencia_turno_incumplida'].append({
                        'empleado_id': p.empleado.id,
                        'nombre': p.empleado.nombre_completo,
                        'fecha': fecha_str,
                        'detalle': detalle
                    })

        # ---------------------------------------------------------
        # 4. Auditoría de Cobertura y VALIDACIÓN DE CALIDAD
        # ---------------------------------------------------------
        contador_slots_vacios_total = 0
        contador_slots_vacios_senior = 0
        demanda_total_teorica = 0
        
        # Estado por defecto
        estado_cronograma = Cronograma.Estado.BORRADOR # O 'COMPLETADO' si pasa la validación
        mensaje_validacion = "Optimización finalizada correctamente."

        if plantilla_demanda:
            reglas = plantilla_demanda.reglas.all().select_related('turno')
            excepciones = plantilla_demanda.excepciones.filter(fecha__range=[fecha_inicio, fecha_fin]).select_related('turno')
            cache_nombres_turnos = {t.id: t.nombre for t in TipoTurno.objects.filter(especialidad=especialidad)}

            mapa_reglas = {}
            for r in reglas:
                if r.dia not in mapa_reglas: mapa_reglas[r.dia] = {}
                mapa_reglas[r.dia][r.turno.id] = r
            
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
                
                # Lógica Lunes/Sábado como referencia
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
                        
                        # Acumuladores para validación
                        contador_slots_vacios_total += (falta_senior + falta_junior)
                        contador_slots_vacios_senior += falta_senior

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

            # =================================================================
            # LÓGICA DE VALIDACIÓN POST-ALGORITMO (Umbrales)
            # =================================================================
            porcentaje_deficit = 0
            if demanda_total_teorica > 0:
                porcentaje_deficit = (contador_slots_vacios_total / demanda_total_teorica) * 100
            
            print(f"📊 ANÁLISIS FINAL: Demanda {demanda_total_teorica}, Vacíos {contador_slots_vacios_total} ({porcentaje_deficit:.2f}%)")
            print(f"   Seniors Faltantes: {contador_slots_vacios_senior}")

            # REGLA 1: Tolerancia Cero con Seniors
            if contador_slots_vacios_senior > 0:
                estado_cronograma = 'FALLIDO' # Tendrías que agregar este estado en tu modelo o usar BORRADOR con flag
                mensaje_validacion = f"FALLIDO: Faltan cubrir {contador_slots_vacios_senior} puestos Críticos de Senior."
                # Nota: Si no quieres agregar un estado nuevo a la DB, podrías guardarlo como BORRADOR 
                # e inyectar un error en el JSON de reporte para que el front lo lea.
                explicabilidad['estado_validacion'] = 'REJECTED'
                explicabilidad['motivo_rechazo'] = mensaje_validacion
            
            # REGLA 2: Umbral Global (1.5%)
            elif porcentaje_deficit > 1.5:
                estado_cronograma = 'FALLIDO'
                mensaje_validacion = f"FALLIDO: Déficit de cobertura ({porcentaje_deficit:.2f}%) supera el 1.5% permitido."
                explicabilidad['estado_validacion'] = 'REJECTED'
                explicabilidad['motivo_rechazo'] = mensaje_validacion
            
            else:
                # ÉXITO O ADVERTENCIA LEVE
                estado_cronograma = Cronograma.Estado.BORRADOR # Se guarda como borrador listo para revisar
                explicabilidad['estado_validacion'] = 'APPROVED'
                if porcentaje_deficit > 0:
                    mensaje_validacion = f"ADVERTENCIA: Cronograma generado con {contador_slots_vacios_total} huecos menores ({porcentaje_deficit:.2f}%)."
                    explicabilidad['validacion_warning'] = mensaje_validacion

        # Guardar reportes finales en el JSON
        explicabilidad['violaciones_duras'] = violaciones_duras
        explicabilidad['violaciones_blandas'] = violaciones_blandas
        explicabilidad['mensaje_validacion_final'] = mensaje_validacion
        
        if 'datos_equidad' not in explicabilidad: explicabilidad['datos_equidad'] = {}
        explicabilidad['datos_equidad'].update({
            'nombres_profesionales': nombres_largos,
            'nombres_cortos': nombres_cortos,
            'limites_contractuales': limites_contractuales
        })

        # ---------------------------------------------------------
        # 5. Persistencia en Base de Datos
        # ---------------------------------------------------------
        with transaction.atomic():
            cronograma = Cronograma.objects.create(
                especialidad=especialidad,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                estado=estado_cronograma, # Usamos el estado calculado
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
            
        print(f"--- GUARDADO FINALIZADO: ID {cronograma.id} | Estado: {estado_cronograma} ---")
        return cronograma

    except Exception as e:
        print("\n🔴 CRASH EN GUARDAR_SOLUCION")
        print(traceback.format_exc()) 
        raise e