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
        # --- BLOQUE ESPÍA: GUARDAR PAYLOAD SIEMPRE PARA DEBUG ---
        print("🕵️ INTERCEPTANDO PAYLOAD...")
        try:
            with open('debug_payload.json', 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=4, default=str)
            print("✅ Payload guardado exitosamente en 'debug_payload.json'")
        except Exception as e:
            print(f"⚠️ Error al guardar payload de debug: {e}")
        # --------------------------------------------------------

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
    """Persiste el Cronograma, Asignaciones y AUDITA la cobertura."""
    print("--- DEBUG: INICIANDO GUARDADO CON AUDITORÍA ---")
    try:
        matriz_solucion = resultado.get('matriz_solucion') or resultado.get('solution')
        if not matriz_solucion:
            raise ValueError("La API devolvió una matriz de solución vacía.")

        fitness = resultado.get('fitness', 0)
        tiempo = resultado.get('tiempo_ejecucion', 0)
        
        # Blindaje Explicabilidad
        explicabilidad = resultado.get('explicabilidad')
        if explicabilidad is None: explicabilidad = {}
        
        violaciones_blandas = explicabilidad.get('violaciones_blandas', {})
        if 'preferencia_libre_incumplida' not in violaciones_blandas: violaciones_blandas['preferencia_libre_incumplida'] = []
        if 'preferencia_turno_incumplida' not in violaciones_blandas: violaciones_blandas['preferencia_turno_incumplida'] = []
        
        violaciones_duras = explicabilidad.get('violaciones_duras', {})
        if 'deficit_cobertura' not in violaciones_duras: violaciones_duras['deficit_cobertura'] = []

        config_activa = ConfiguracionAlgoritmo.objects.filter(activa=True).first()

        # Blindaje Payload
        if isinstance(payload_original, str):
            try: payload_original = json.loads(payload_original)
            except: pass
        
        # 1. Recuperar empleados y Mapear ID
        datos_problema = payload_original.get('datos_problema', {})
        lista_empleados_payload = datos_problema.get('lista_profesionales', [])
        
        mapa_idx_a_empleado = {} # idx -> objeto Empleado
        mapa_empleado_id_a_exp = {} # id_db -> 'SENIOR'/'JUNIOR'
        
        # Mapa para recuperar por indice del algoritmo
        mapa_idx_a_empleado_id = {idx: emp['id_db'] for idx, emp in enumerate(lista_empleados_payload)}

        empleados_ids = [e['id_db'] for e in lista_empleados_payload]
        empleados_db = {e.id: e for e in Empleado.objects.filter(id__in=empleados_ids)}

        for i, emp_p in enumerate(lista_empleados_payload):
            emp_obj = empleados_db.get(emp_p['id_db'])
            if emp_obj:
                mapa_idx_a_empleado[i] = emp_obj
                mapa_empleado_id_a_exp[emp_obj.id] = emp_obj.experiencia

        # 2. Datos Visuales (Nombres, Limites)
        # Lógica de Contrato Mensual vs Proporcional
        num_dias = (fecha_fin - fecha_inicio).days + 1
        if 28 <= num_dias <= 31:
            factor_tiempo = 1.0 
        else:
            factor_tiempo = num_dias / 30.0

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
                
                min_periodo = min_mensual * factor_tiempo * duracion_horas
                max_periodo = max_mensual * factor_tiempo * duracion_horas
                
                limites = [round(min_periodo, 1), round(max_periodo, 1)]
            else:
                n_largo = f"Profesional {i+1}"
                n_corto = f"P{i+1}"
                limites = [0.0, 0.0]
            
            nombres_cortos.append(n_corto)
            nombres_largos.append(n_largo)
            limites_contractuales.append(limites)

        # ---------------------------------------------------------------------
        # 3. Auditoría de Preferencias
        # ---------------------------------------------------------------------
        # Mapa: {empleado_id: {fecha_str: turno_id}}
        asignaciones_reales = {} 
        # Mapa: {fecha_str: {turno_id: {'SENIOR': count, 'JUNIOR': count}}}
        conteo_cobertura = {} 

        for i, fila in enumerate(matriz_solucion):
            emp = mapa_idx_a_empleado.get(i)
            if not emp: continue
            
            if emp.id not in asignaciones_reales: asignaciones_reales[emp.id] = {}
            
            for j, t_id in enumerate(fila):
                if t_id:
                    fecha_dia = (fecha_inicio + timedelta(days=j)).strftime("%Y-%m-%d")
                    asignaciones_reales[emp.id][fecha_dia] = t_id
                    
                    # Contar para auditoría de demanda
                    if fecha_dia not in conteo_cobertura: conteo_cobertura[fecha_dia] = {}
                    if t_id not in conteo_cobertura[fecha_dia]: conteo_cobertura[fecha_dia][t_id] = {'SENIOR': 0, 'JUNIOR': 0}
                    
                    exp = mapa_empleado_id_a_exp.get(emp.id, 'JUNIOR') # Default Junior
                    if exp in conteo_cobertura[fecha_dia][t_id]:
                        conteo_cobertura[fecha_dia][t_id][exp] += 1

        prefs = Preferencia.objects.filter(
            fecha__range=[fecha_inicio, fecha_fin],
            empleado__in=empleados_db.values()
        ).select_related('empleado', 'tipo_turno')

        for p in prefs:
            fecha_str = p.fecha.strftime("%Y-%m-%d")
            turno_asignado_id = asignaciones_reales.get(p.empleado.id, {}).get(fecha_str)

            es_descanso = (p.deseo == Preferencia.Deseo.DESCANSAR)
            es_trabajo = (p.deseo == Preferencia.Deseo.TRABAJAR)

            # CASO A: Quería Descansar
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

            # CASO B: Quería Trabajar
            elif es_trabajo:
                violation = False
                detalle = ""
                if not turno_asignado_id:
                     violation = True
                     detalle = 'No se asignó turno solicitado'
                elif p.tipo_turno and turno_asignado_id != p.tipo_turno.id:
                     violation = True
                     detalle = f'Se asignó otro turno distinto al {p.tipo_turno.nombre}'
                
                if violation:
                    violaciones_blandas['preferencia_turno_incumplida'].append({
                        'empleado_id': p.empleado.id,
                        'nombre': p.empleado.nombre_completo,
                        'fecha': fecha_str,
                        'detalle': detalle
                    })

        # ---------------------------------------------------------------------
        # 4. Auditoría de Cobertura (NUEVO: DETECTAR FALTANTES)
        # ---------------------------------------------------------------------
        if plantilla_demanda:
            # Traemos todas las reglas y excepciones para comparar
            reglas = plantilla_demanda.reglas.all()
            excepciones = plantilla_demanda.excepciones.filter(fecha__range=[fecha_inicio, fecha_fin])
            
            # Mapa rápido de reglas: {dia_semana_int: {turno_id: ReglaObj}}
            mapa_reglas = {}
            for r in reglas:
                if r.dia not in mapa_reglas: mapa_reglas[r.dia] = {}
                mapa_reglas[r.dia][r.turno.id] = r
            
            # Mapa excepciones: {fecha_str: {turno_id: ExcepcionObj}}
            mapa_excepciones = {}
            for ex in excepciones:
                f_str = ex.fecha.strftime("%Y-%m-%d")
                if f_str not in mapa_excepciones: mapa_excepciones[f_str] = {}
                mapa_excepciones[f_str][ex.turno.id] = ex

            # Recorremos día por día del cronograma
            delta_dias = (fecha_fin - fecha_inicio).days + 1
            for d in range(delta_dias):
                fecha_actual = fecha_inicio + timedelta(days=d)
                fecha_str = fecha_actual.strftime("%Y-%m-%d")
                dia_semana = fecha_actual.weekday() # 0=Lunes
                
                # Turnos a revisar en este día (según reglas base)
                turnos_del_dia = mapa_reglas.get(dia_semana, {})
                
                # Verificar cada turno requerido
                for turno_id, regla in turnos_del_dia.items():
                    # Definir objetivo (Base o Excepción)
                    obj_senior = regla.cantidad_senior
                    obj_junior = regla.cantidad_junior
                    
                    # Si hay excepción para hoy, pisa la regla
                    excepcion = mapa_excepciones.get(fecha_str, {}).get(turno_id)
                    if excepcion:
                        obj_senior = excepcion.cantidad_senior
                        obj_junior = excepcion.cantidad_junior

                    # Obtener realidad
                    datos_reales = conteo_cobertura.get(fecha_str, {}).get(turno_id, {'SENIOR': 0, 'JUNIOR': 0})
                    real_senior = datos_reales['SENIOR']
                    real_junior = datos_reales['JUNIOR']
                    
                    # Chequear Déficit
                    falta_senior = obj_senior - real_senior
                    falta_junior = obj_junior - real_junior
                    
                    if falta_senior > 0 or falta_junior > 0:
                        # ¡ENCONTRAMOS EL PROBLEMA!
                        turno_nombre = regla.turno.nombre
                        detalle = []
                        if falta_senior > 0: detalle.append(f"Faltan {falta_senior} Seniors")
                        if falta_junior > 0: detalle.append(f"Faltan {falta_junior} Juniors")
                        
                        violaciones_duras['deficit_cobertura'].append({
                            'fecha': fecha_str,
                            'turno': turno_nombre,
                            'detalle': ", ".join(detalle) + f" (Obj: S{obj_senior}/J{obj_junior} vs Real: S{real_senior}/J{real_junior})"
                        })
                        print(f"⚠️ DÉFICIT {fecha_str} {turno_nombre}: {detalle}")

        # Guardar en explicabilidad
        explicabilidad['violaciones_duras'] = violaciones_duras
        explicabilidad['violaciones_blandas'] = violaciones_blandas
        
        # Actualizar datos visuales
        if 'datos_equidad' not in explicabilidad: explicabilidad['datos_equidad'] = {}
        explicabilidad['datos_equidad'].update({
            'nombres_profesionales': nombres_largos,
            'nombres_cortos': nombres_cortos,
            'limites_contractuales': limites_contractuales
        })

        # 5. Transacción Atómica y Guardado
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
                    if t_id and t_id in turnos_db:
                        nuevas_asignaciones.append(Asignacion(
                            cronograma=cronograma, 
                            empleado_id=emp_id, 
                            fecha=fecha_inicio + timedelta(days=j), 
                            tipo_turno=turnos_db[t_id]
                        ))
            if nuevas_asignaciones: Asignacion.objects.bulk_create(nuevas_asignaciones)
            
        print(f"--- DEBUG: GUARDADO EXITOSO (ID: {cronograma.id}) ---")
        return cronograma

    except Exception as e:
        print("\n🔴 CRASH EN GUARDAR_SOLUCION")
        print(traceback.format_exc()) 
        raise e