import numpy as np

def procesar_datos_instancia(data: dict) -> dict:
    """
    Orquestador que transforma el JSON de la API en el formato 
    requerido por el Algoritmo Genético.
    """
    # 1. Limpieza y conversión de tipos básicos
    data = _preprocesar_datos_basicos(data)
    
    # 2. Generar información detallada de profesionales
    data['info_profesionales'] = _generar_info_profesionales(
        data['num_profesionales'], 
        data.get('info_profesionales_base', {})
    )
    
    # 3. Calcular requerimientos de cobertura por día/turno/skill
    data['requerimientos_cobertura'] = _generar_requerimientos_cobertura(data)
    
    # 4. Generar matrices de restricciones (NumPy)
    data['matriz_disponibilidad'] = _generar_matriz_disponibilidad(data)
    data['matriz_preferencias'] = _generar_matriz_preferencias(data)

    # 5. Limpieza final de llaves temporales
    for k in ['reglas_cobertura', 'info_profesionales_base', 
              'excepciones_disponibilidad', 'excepciones_preferencias']:
        data.pop(k, None)

    return data

def _preprocesar_datos_basicos(data: dict) -> dict:
    """Convierte listas de JSON a sets y asegura tipos numéricos."""
    data['secuencias_prohibidas'] = set(tuple(x) for x in data.get('secuencias_prohibidas', []))
    data['turnos_noche'] = set(data.get('turnos_noche', [3]))
    data['turnos_a_cubrir'] = [int(t) for t in data.get('turnos_a_cubrir', [1, 2, 3])]
    
    if "duracion_turnos" in data:
        data['duracion_turnos'] = {int(k): v for k, v in data['duracion_turnos'].items()}

    # Cálculo de días no hábiles (Sábados y Domingos)
    data['dias_no_habiles'] = {d for d in range(data['num_dias']) if d % 7 in [5, 6]}
    return data

def _generar_info_profesionales(num_p: int, base: dict) -> list:
    """Genera la lista de perfiles (skills y horas) para cada profesional."""
    senior_count = base.get('senior_count', num_p // 2)
    return [{
        'skill': 'senior' if i < senior_count else 'junior',
        't_min': base.get('t_min', 0),
        't_max': base.get('t_max', 160)
    } for i in range(num_p)]

def _generar_requerimientos_cobertura(data: dict) -> dict:
    """Calcula la demanda de personal según el tipo de día (pico, finde, normal)."""
    reqs = {}
    reglas = data.get('reglas_cobertura', {})
    dias_no_habiles = data['dias_no_habiles']
    
    for d in range(data['num_dias']):
        reqs[d] = {}
        es_finde = (d in dias_no_habiles)
        es_pico = ((d % 7) in reglas.get('dias_pico', []))
        
        for s in data['turnos_a_cubrir']:
            s_key = str(s)
            # Lógica de selección de perfil de demanda
            if s in [1, 2]: # Mañana/Tarde
                perfil = reglas.get('demanda_pico') if es_pico else (
                    reglas.get('demanda_finde') if es_finde else reglas.get('demanda_normal')
                )
            else: # Noche
                perfil = reglas.get('demanda_finde') 
                
            demandas = perfil.get(s_key, reglas.get('demanda_normal', {}).get(s_key, {"junior": 1, "senior": 1}))
            reqs[d][s] = {"junior": demandas['junior'], "senior": demandas['senior']}
            
    return reqs

def _generar_matriz_disponibilidad(data: dict) -> np.ndarray:
    """Crea la matriz booleana de disponibilidad aplicando excepciones."""
    matriz = np.full((data['num_profesionales'], data['num_dias']), True)
    for exc in data.get('excepciones_disponibilidad', []):
        p_idx = exc.get('prof_index')
        if 'dias_range' in exc:
            matriz[p_idx, exc['dias_range'][0]:exc['dias_range'][1]] = exc['disponible']
        elif exc.get('tipo') == 'fines_de_semana':
            for d in data['dias_no_habiles']:
                matriz[p_idx, d] = exc['disponible']
    return matriz

def _generar_matriz_preferencias(data: dict) -> np.ndarray:
    """Crea la matriz de pesos de preferencias (PTE/PDL)."""
    matriz = np.zeros((data['num_profesionales'], data['num_dias']), dtype=int)
    for exc in data.get('excepciones_preferencias', []):
        valor = exc['valor']
        profs = exc.get('prof_indices', [])
        dias = exc.get('dias', [exc.get('dia')] if 'dia' in exc else [])
        for p in profs:
            for d in dias:
                if d is not None: matriz[p, d] = valor
    return matriz