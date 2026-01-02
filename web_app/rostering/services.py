import json
import traceback
import requests
import os
from datetime import timedelta, datetime, date
from django.core.exceptions import ValidationError
from django.db import transaction

# --- MODELOS ---
from .models import (
    Empleado, TipoTurno, PlantillaDemanda, ReglaDemandaSemanal,
    ExcepcionDemanda, NoDisponibilidad, Preferencia, 
    ConfiguracionAlgoritmo, SecuenciaProhibida, DiaSemana,
    Cronograma, Asignacion
)

def generar_payload_ag(fecha_inicio, fecha_fin, especialidad, plantilla_id=None):
    """
    Construye el diccionario JSON exacto que espera la API de optimización.
    Valida la coherencia de datos y transforma los modelos de Django en estructuras primitivas.
    """
    # 1. Validaciones y Setup Inicial
    num_dias = (fecha_fin - fecha_inicio).days + 1
    if num_dias < 1:
        raise ValueError("La fecha de fin debe ser posterior a la fecha de inicio.")

    # VALIDACIÓN CRÍTICA: Uniformidad de Turnos
    # El algoritmo cuenta slots (1 turno = 1 fatiga), por lo que deben durar lo mismo.
    turnos_qs = TipoTurno.objects.filter(especialidad=especialidad)
    duraciones = set(t.duracion_horas for t in turnos_qs)
    
    if len(duraciones) > 1:
        raise ValidationError(
            f"Error de Uniformidad: Tienes turnos de distintas duraciones ({duraciones} hs). "
            "El algoritmo actual requiere que todos los turnos de la especialidad tengan la misma duración "
            "(ej: todos de 12hs o todos de 24hs) para calcular correctamente la carga laboral."
        )

    # Cargar configuración activa
    config = ConfiguracionAlgoritmo.objects.filter(activa=True).first()
    if not config:
        config = ConfiguracionAlgoritmo() # Fallback por defecto

    # Cargar Plantilla
    if plantilla_id:
        plantilla = PlantillaDemanda.objects.get(pk=plantilla_id)
    else:
        plantilla = PlantillaDemanda.objects.filter(especialidad=especialidad).first()
        if not plantilla:
            raise ValueError(f"No hay plantilla de demanda creada para {especialidad}")

    # ---------------------------------------------------------
    # 2. CONFIGURACIÓN DEL ALGORITMO
    # ---------------------------------------------------------
    payload_config = {
        "pop_size": config.tamano_poblacion,
        "generaciones": config.generaciones,
        "pc": config.prob_cruce,
        "pm": config.prob_mutacion,
        "elitismo": config.elitismo,
        "seed": config.semilla or 42
    }

    # ---------------------------------------------------------
    # 3. ESTRATEGIAS EVOLUTIVAS
    # ---------------------------------------------------------
    payload_estrategias = {
        "sel": config.estrategia_seleccion,
        "cross": config.estrategia_cruce,
        "mut": config.estrategia_mutacion
    }

    # ---------------------------------------------------------
    # 4. DATOS DEL PROBLEMA - PROFESIONALES
    # ---------------------------------------------------------
    
    # Factor de proporción para ajustar límites mensuales al periodo seleccionado
    factor_tiempo = num_dias / 30.0
    
    empleados_qs = Empleado.objects.filter(especialidad=especialidad, activo=True)
    lista_profesionales = []
    
    # Mapa auxiliar: ID base de datos -> Índice en la matriz (0, 1, 2...)
    mapa_id_a_indice = {} 

    for idx, emp in enumerate(empleados_qs):
        mapa_id_a_indice[emp.id] = idx
        
        skill = emp.experiencia.lower() # 'senior' / 'junior'

        # Cálculo de límites de turnos (Slots)
        t_min_periodo = int(emp.min_turnos_mensuales * factor_tiempo)
        t_max_periodo = int(emp.max_turnos_mensuales * factor_tiempo)

        # Ajuste de seguridad
        if t_max_periodo < t_min_periodo:
            t_max_periodo = t_min_periodo

        lista_profesionales.append({
            "id_db": emp.id,
            "nombre": emp.nombre_completo,
            "skill": skill,
            "t_min": t_min_periodo,
            "t_max": t_max_periodo,
        })

    # ---------------------------------------------------------
    # 5. DATOS DEL PROBLEMA - TURNOS
    # ---------------------------------------------------------
    turnos_qs = TipoTurno.objects.filter(especialidad=especialidad)
    
    turnos_a_cubrir = [t.id for t in turnos_qs]
    turnos_noche = [t.id for t in turnos_qs if t.es_nocturno]
    duracion_turnos = {str(t.id): float(t.duracion_horas) for t in turnos_qs}
    
    max_turno_val = max(turnos_a_cubrir) if turnos_a_cubrir else 0

    # ---------------------------------------------------------
    # 6. REGLAS DE COBERTURA (Demandas)
    # ---------------------------------------------------------
    
    def extraer_demanda(regla_qs):
        resultado = {}
        for r in regla_qs:
            t_str = str(r.turno.id)
            resultado[t_str] = {
                "junior": r.cantidad_junior,
                "senior": r.cantidad_senior
            }
        return resultado

    # 6.1. Demanda Normal (Lunes a Viernes)
    reglas_normal = ReglaDemandaSemanal.objects.filter(plantilla=plantilla, dia=DiaSemana.LUNES)
    dict_demanda_normal = extraer_demanda(reglas_normal)

    # 6.2. Demanda Finde (Sábado/Domingo)
    reglas_finde = ReglaDemandaSemanal.objects.filter(plantilla=plantilla, dia=DiaSemana.SABADO)
    dict_demanda_finde = extraer_demanda(reglas_finde)

    # 6.3. Días Pico (Excepciones por fecha específica)
    dias_pico_indices = []
    dict_demanda_pico = {}
    
    fecha_iter = fecha_inicio
    for i in range(num_dias):
        excepcion = ExcepcionDemanda.objects.filter(plantilla=plantilla, fecha=fecha_iter)
        
        if excepcion.exists():
            dias_pico_indices.append(i)
            # Tomamos la definición de la primera ocurrencia encontrada como modelo de pico
            if not dict_demanda_pico:
                dict_demanda_pico = extraer_demanda(excepcion)
        
        fecha_iter += timedelta(days=1)

    reglas_cobertura = {
        "dias_pico": dias_pico_indices,
        "demanda_pico": dict_demanda_pico if dict_demanda_pico else dict_demanda_normal,
        "demanda_finde": dict_demanda_finde,
        "demanda_normal": dict_demanda_normal
    }

    # ---------------------------------------------------------
    # 7. EXCEPCIONES Y PREFERENCIAS
    # ---------------------------------------------------------
    
    # 7.1 Disponibilidad (Licencias, Enfermedad)
    excepciones_disponibilidad = []
    no_disp_qs = NoDisponibilidad.objects.filter(
        empleado__in=empleados_qs,
        fecha_inicio__lte=fecha_fin,
        fecha_fin__gte=fecha_inicio
    )

    for nd in no_disp_qs:
        inicio_rel = (nd.fecha_inicio - fecha_inicio).days
        fin_rel = (nd.fecha_fin - fecha_inicio).days
        
        start_idx = max(0, inicio_rel)
        end_idx = min(num_dias, fin_rel + 1)

        if start_idx < end_idx:
            prof_idx = mapa_id_a_indice[nd.empleado.id]
            excepciones_disponibilidad.append({
                "prof_index": prof_idx,
                "dias_range": [start_idx, end_idx],
                "disponible": False
            })

    # 7.2 Preferencias (Peticiones de días libres o turnos específicos)
    excepciones_preferencias = []
    prefs_qs = Preferencia.objects.filter(
        empleado__in=empleados_qs,
        fecha__range=[fecha_inicio, fecha_fin]
    )
    
    for pref in prefs_qs:
        dia_idx = (pref.fecha - fecha_inicio).days
        prof_idx = mapa_id_a_indice[pref.empleado.id]
        
        peso_base = config.peso_preferencia_turno if pref.tipo_turno else config.peso_preferencia_dias_libres
        valor = peso_base if pref.deseo == 'TRABAJAR' else -peso_base
        
        excepciones_preferencias.append({
            "prof_indices": [prof_idx],
            "dia": dia_idx,
            "valor": valor
        })

    # ---------------------------------------------------------
    # 8. CONSTRUCCIÓN FINAL
    # ---------------------------------------------------------
    
    seq_qs = SecuenciaProhibida.objects.filter(especialidad=especialidad)
    secuencias = [[s.turno_previo.id, s.turno_siguiente.id] for s in seq_qs]

    datos_problema = {
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
    }

    return {
        "config": payload_config,
        "datos_problema": datos_problema,
        "estrategias": payload_estrategias
    }


def invocar_api_planificacion(payload):
    """
    Envía el JSON a la API de optimización y devuelve la respuesta.
    """
    # En entorno Docker, el host 'optimizer' resuelve al contenedor de la API
    url = "http://optimizer:8000/planificar" 
    
    try:
        # DEBUG: Guardar payload localmente si está habilitado
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
    """
    Consulta el endpoint de resultados de la API (Polling).
    """
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
    Procesa la respuesta JSON del motor genético y persiste el Cronograma y sus Asignaciones en la base de datos.
    También enriquece el reporte de análisis con nombres reales para visualización.
    """
    print("--- DEBUG: INICIANDO GUARDADO DB ---")
    try:
        # 1. Validaciones básicas de respuesta
        matriz_solucion = resultado.get('matriz_solucion') or resultado.get('solution')
        if not matriz_solucion:
            raise ValueError("La API devolvió una matriz de solución vacía.")

        fitness = resultado.get('fitness', 0)
        tiempo = resultado.get('tiempo_ejecucion', 0)
        explicabilidad = resultado.get('explicabilidad', {})

        # 2. Configuración activa usada
        config_activa = ConfiguracionAlgoritmo.objects.filter(activa=True).first()

        # 3. Recuperar mapeo de Empleados (Payload Index -> DB ID)
        if 'datos_problema' not in payload_original:
            raise KeyError("El payload original no contiene 'datos_problema'. No se puede mapear empleados.")
            
        lista_empleados_payload = payload_original['datos_problema']['lista_profesionales']
        mapa_idx_a_empleado_id = {idx: emp['id_db'] for idx, emp in enumerate(lista_empleados_payload)}
        
        ids_a_buscar = list(mapa_idx_a_empleado_id.values())
        empleados_db = Empleado.objects.filter(id__in=ids_a_buscar)
        empleados_map = {e.id: e for e in empleados_db}

        # 4. Obtener duración de referencia para cálculos de reporte
        turno_referencia = TipoTurno.objects.filter(especialidad=especialidad).first()
        duracion_horas = 12.0 # Valor por defecto seguro
        
        if turno_referencia:
            if turno_referencia.duracion_horas and turno_referencia.duracion_horas > 0:
                duracion_horas = float(turno_referencia.duracion_horas)
            elif turno_referencia.hora_inicio and turno_referencia.hora_fin:
                # Cálculo fallback si no está el campo explícito
                dummy_date = date(2000, 1, 1)
                dt_ini = datetime.combine(dummy_date, turno_referencia.hora_inicio)
                dt_fin = datetime.combine(dummy_date, turno_referencia.hora_fin)
                diff = dt_fin - dt_ini
                if diff.total_seconds() < 0:
                    diff += timedelta(days=1)
                duracion_horas = diff.total_seconds() / 3600.0

        # 5. Enriquecer reporte de explicabilidad (Nombres y Límites)
        nombres_cortos = []
        nombres_largos = []
        limites_contractuales = []

        for i in range(len(lista_empleados_payload)):
            emp_id = mapa_idx_a_empleado_id.get(i)
            empleado = empleados_map.get(emp_id)
        
            if empleado:
                full_name = getattr(empleado, 'nombre_completo', "").strip()
                n_largo = full_name if full_name else f"Profesional {i+1}"
                
                partes = full_name.split()
                if len(partes) >= 2:
                    n_corto = f"{partes[-1]}, {partes[0][0].upper()}."
                else:
                    n_corto = full_name if full_name else f"P{i+1}"

                # Cálculo de límites en horas para el gráfico
                min_turnos = getattr(empleado, 'min_turnos_mensuales', 0) or 0
                max_turnos = getattr(empleado, 'max_turnos_mensuales', 0) or 0
                
                min_h = float(min_turnos) * duracion_horas
                max_h = float(max_turnos) * duracion_horas
                limites = [min_h, max_h]

            else:
                n_corto = f"P{i+1}"
                n_largo = f"Profesional {i+1}"
                limites = [0.0, 0.0]

            nombres_cortos.append(n_corto)
            nombres_largos.append(n_largo)
            limites_contractuales.append(limites)

        # Inyectar datos en el JSON de reporte para que el Frontend no tenga que recalcular
        if 'datos_equidad' not in explicabilidad:
            explicabilidad['datos_equidad'] = {}
        
        explicabilidad['datos_equidad']['nombres_profesionales'] = nombres_largos
        explicabilidad['datos_equidad']['nombres_cortos'] = nombres_cortos
        explicabilidad['datos_equidad']['limites_contractuales'] = limites_contractuales
        
        # 6. Transacción Atómica para guardar Cronograma y Asignaciones
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
            
            for i, fila_turnos in enumerate(matriz_solucion):
                empleado_id = mapa_idx_a_empleado_id.get(i)
                if not empleado_id: continue 
                
                for j, turno_id_api in enumerate(fila_turnos):
                    if turno_id_api and turno_id_api in turnos_db:
                        nuevas_asignaciones.append(Asignacion(
                            cronograma=cronograma,
                            empleado_id=empleado_id,
                            fecha=fecha_inicio + timedelta(days=j),
                            tipo_turno=turnos_db[turno_id_api]
                        ))
            
            if nuevas_asignaciones:
                Asignacion.objects.bulk_create(nuevas_asignaciones)
            
        print("--- DEBUG: GUARDADO EXITOSO ---")
        return cronograma

    except Exception as e:
        print("\n🔴 CRASH EN GUARDAR_SOLUCION")
        print(traceback.format_exc()) 
        raise e # Re-lanzar para que la vista capture el error 500