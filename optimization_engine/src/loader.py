"""Módulo de Carga y Procesamiento de Datos (Loader)."""
import numpy as np
import json

def procesar_datos_instancia(data: dict) -> dict:
    print("\n" + "="*50)
    print("🕵️‍♂️ DEBUG LOADER: Iniciando procesamiento")
    print(f"🔑 Claves en raíz 'data': {list(data.keys())}")
    
    # 1. Datos Básicos (Pre-procesamiento)
    data = _preprocesar_datos_basicos(data)
    
    # 2. Profesionales
    lista_profs = data.get('lista_profesionales', [])
    data['num_profesionales'] = len(lista_profs)
    data['info_profesionales'] = {
        idx: {
            'id_db': p.get('id_db'), 'nombre': p.get('nombre'),
            'skill': p.get('skill', 'junior'), 
            't_min': p.get('t_min', 0), 't_max': p.get('t_max', 31)
        } for idx, p in enumerate(lista_profs)
    }

    # 3. Lógica de Selección de Estrategia de Carga
    reqs_finales = None

    # ESTRATEGIA 1: Cobertura Explícita (Día por día detallado)
    if 'requerimientos_cobertura_explicita' in data:
        print("✅ ESTRATEGIA: Cobertura Explícita detectada.")
        raw_reqs = data['requerimientos_cobertura_explicita']
        reqs_finales = _procesar_cobertura_explicita(raw_reqs)

    # ESTRATEGIA 2: Reglas de Cobertura (Lo que envía tu API actual)
    elif 'reglas_cobertura' in data:
        print("✅ ESTRATEGIA: Reglas de Cobertura detectadas (API Standard).")
        reqs_finales = _generar_reqs_desde_reglas(data)

    # ESTRATEGIA 3: Datos dentro de 'datos_problema' (Anidamiento)
    elif 'datos_problema' in data and 'reglas_cobertura' in data['datos_problema']:
        print("✅ ESTRATEGIA: Reglas dentro de sub-diccionario 'datos_problema'.")
        # Fusionamos para facilitar acceso
        data.update(data['datos_problema'])
        reqs_finales = _generar_reqs_desde_reglas(data)
        
    # ESTRATEGIA 4: Legacy (Fallback)
    else:
        print("⚠️ ALERTA: Usando estrategia Legacy (puede generar vacíos).")
        reqs_finales = _generar_requerimientos_cobertura_legacy(data)

    data['requerimientos_cobertura'] = reqs_finales

    # 4. Matrices
    data['matriz_disponibilidad'] = _generar_matriz_disponibilidad(data)
    data['matriz_preferencias'] = _generar_matriz_preferencias(data)
    
    print("="*50 + "\n")
    return data

def _preprocesar_datos_basicos(data: dict) -> dict:
    # Aplanado si viene anidado en datos_problema
    if 'datos_problema' in data:
        # Copiamos claves faltantes del hijo al padre
        for k, v in data['datos_problema'].items():
            if k not in data:
                data[k] = v

    # Secuencias
    raw_secuencias = data.get('secuencias_prohibidas', [])
    procesadas = set()
    for item in raw_secuencias:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            procesadas.add((int(item[0]), int(item[1])))
        elif isinstance(item, dict):
            try: procesadas.add((int(item['turno_previo']), int(item['turno_siguiente'])))
            except: pass
    data['secuencias_prohibidas'] = procesadas

    data['turnos_noche'] = set(data.get('turnos_noche', []))
    data['turnos_a_cubrir'] = [int(t) for t in data.get('turnos_a_cubrir', [])]
    
    # Duración turnos
    dur_raw = data.get('duracion_turnos', {})
    clean_dur = {}
    if isinstance(dur_raw, dict):
        for k, v in dur_raw.items():
            try: clean_dur[int(k)] = float(v)
            except: pass
    data['duracion_turnos'] = clean_dur

    if 'dias_no_habiles' in data and isinstance(data['dias_no_habiles'], list):
        data['dias_no_habiles'] = set(data['dias_no_habiles'])
    else:
        data['dias_no_habiles'] = set()
        
    return data

def _procesar_cobertura_explicita(raw_reqs: list) -> list:
    """Procesa la lista explicita día a día."""
    reqs_procesados = []
    for dia_raw in raw_reqs:
        dia_clean = {}
        for turno_str, skills in dia_raw.items():
            try:
                dia_clean[int(turno_str)] = skills
            except ValueError:
                pass 
        reqs_procesados.append(dia_clean)
    return reqs_procesados

def _generar_reqs_desde_reglas(data: dict) -> list:
    """Convierte reglas (días pico/normal) en una lista de demandas por día."""
    num_dias = int(data.get('num_dias', 30))
    reglas = data.get('reglas_cobertura', {})
    
    dias_pico_indices = set(reglas.get('dias_pico', []))
    demanda_pico = reglas.get('demanda_pico', {})
    demanda_normal = reglas.get('demanda_normal', {})
    demanda_finde = reglas.get('demanda_finde', demanda_normal) # Fallback a normal si no hay finde

    reqs_por_dia = []
    
    # Normalizar claves de demanda (str -> int) para evitar errores luego
    def limpiar_demanda(demanda_dict):
        clean = {}
        for turno, skills in demanda_dict.items():
            try: clean[int(turno)] = skills
            except: pass
        return clean

    demanda_pico = limpiar_demanda(demanda_pico)
    demanda_normal = limpiar_demanda(demanda_normal)
    demanda_finde = limpiar_demanda(demanda_finde)

    for d in range(num_dias):
        # Lógica de asignación
        if d in dias_pico_indices:
            reqs_por_dia.append(demanda_pico.copy())
        # Podríamos agregar lógica de fin de semana si tuviéramos dia_inicio
        # Por ahora, usamos pico vs normal que es lo que manda la API
        else:
            reqs_por_dia.append(demanda_normal.copy())
            
    return reqs_por_dia

def _generar_requerimientos_cobertura_legacy(data: dict) -> list:
    """Fallback: Genera los requerimientos si el JSON viene con formato antiguo."""
    # (Mantenemos esta función igual por compatibilidad hacia atrás)
    num_dias = data.get('num_dias', 30)
    demanda_raw = data.get('demanda_semanal', {})
    
    # Si no hay demanda semanal, devolvemos estructura vacía pero válida para evitar crash inmediato
    if not demanda_raw:
        print("⚠️ LEGACY: No se encontró 'demanda_semanal'. Retornando estructura vacía.")
        return [{} for _ in range(num_dias)]

    demanda_semanal = {}
    for k, v in demanda_raw.items():
        try: demanda_semanal[int(k)] = v
        except: pass
            
    excepciones = {ex['dia_indice']: ex['demanda'] for ex in data.get('excepciones_demanda', [])}
    reqs_por_dia = []
    
    dia_inicio = data.get('dia_inicio_semana', 0)
    for d in range(num_dias):
        dia_semana_actual = (dia_inicio + d) % 7
        demanda_base = demanda_semanal.get(dia_semana_actual, {})
        demanda_final = excepciones.get(d, demanda_base)
        
        # Limpieza
        dia_clean = {}
        for t, s in demanda_final.items():
            try: dia_clean[int(t)] = s
            except: pass
        reqs_por_dia.append(dia_clean)
            
    return reqs_por_dia

def _generar_matriz_disponibilidad(data: dict) -> np.ndarray:
    matriz = np.full((data['num_profesionales'], data['num_dias']), True)
    for exc in data.get('excepciones_disponibilidad', []):
        p_idx = exc.get('prof_index')
        if p_idx is not None and p_idx < data['num_profesionales']:
            disponible = 1 if exc.get('disponible', True) else 0
            if 'dias_range' in exc:
                r = exc['dias_range']
                matriz[p_idx, max(0, r[0]):min(data['num_dias'], r[1])] = disponible
    return matriz

def _generar_matriz_preferencias(data: dict) -> np.ndarray:
    matriz = np.zeros((data['num_profesionales'], data['num_dias']), dtype=int)
    for exc in data.get('excepciones_preferencias', []):
        valor = exc.get('valor', 0)
        profs = exc.get('prof_indices', [])
        dias = exc.get('dias', [exc.get('dia')])
        for p in profs:
            if p < data['num_profesionales']:
                for d in dias:
                    if d is not None and 0 <= d < data['num_dias']: matriz[p, d] = valor
    return matriz