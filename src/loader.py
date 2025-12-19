"""Módulo de Carga y Procesamiento de Datos (Loader).

Este módulo se encarga de transformar las solicitudes crudas provenientes de la 
API en estructuras de datos optimizadas (Sets, Tuplas y matrices NumPy) para 
su procesamiento eficiente en el Algoritmo Genético.
"""

import numpy as np

def procesar_datos_instancia(data: dict) -> dict:
    """Orquestador que transforma el JSON de la API en el formato para el GA.

    Coordina la limpieza, la generación de perfiles profesionales, el cálculo 
    de cobertura y la creación de matrices de restricciones.

    Args:
        data (dict): Diccionario crudo recibido desde el endpoint de la API.

    Returns:
        dict: Diccionario procesado con todos los objetos necesarios para 
            instanciar la clase ProblemaGAPropio.
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

    # 5. Limpieza final de llaves temporales para optimizar memoria
    for k in ['reglas_cobertura', 'info_profesionales_base', 
              'excepciones_disponibilidad', 'excepciones_preferencias']:
        data.pop(k, None)

    return data

def _preprocesar_datos_basicos(data: dict) -> dict:
    """Convierte listas de JSON a sets y asegura tipos numéricos consistentes.

    Realiza el casting de IDs de turnos a enteros y precalcula los índices de 
    días correspondientes a fines de semana.

    Args:
        data (dict): Diccionario de datos en proceso de carga.

    Returns:
        dict: Diccionario con tipos de datos básicos normalizados.
    """
    data['secuencias_prohibidas'] = set(tuple(x) for x in data.get('secuencias_prohibidas', []))
    data['turnos_noche'] = set(data.get('turnos_noche', [3]))
    data['turnos_a_cubrir'] = [int(t) for t in data.get('turnos_a_cubrir', [1, 2, 3])]
    
    if "duracion_turnos" in data:
        data['duracion_turnos'] = {int(k): v for k, v in data['duracion_turnos'].items()}

    # Cálculo de días no hábiles (Sábados y Domingos)
    data['dias_no_habiles'] = {d for d in range(data['num_dias']) if d % 7 in [5, 6]}
    return data

def _generar_info_profesionales(num_p: int, base: dict) -> list:
    """Genera la lista de perfiles (skills y horas) para cada profesional.

    Distribuye las habilidades (senior/junior) y asigna los límites de carga 
    horaria permitida según la configuración base.

    Args:
        num_p (int): Número total de profesionales.
        base (dict): Configuración base de horas y cantidad de seniors.

    Returns:
        list: Lista de diccionarios, uno por profesional, con su skill y límites.
    """
    senior_count = base.get('senior_count', num_p // 2)
    return [{
        'skill': 'senior' if i < senior_count else 'junior',
        't_min': base.get('t_min', 0),
        't_max': base.get('t_max', 160)
    } for i in range(num_p)]

def _generar_requerimientos_cobertura(data: dict) -> dict:
    """Calcula la demanda de personal según el tipo de día.

    Analiza cada día del horizonte para determinar si es un día de pico, 
    fin de semana o normal, y asigna la demanda de skills correspondiente.

    Args:
        data (dict): Diccionario con reglas de cobertura y metadatos de días.

    Returns:
        dict: Mapeo {dia: {turno: {skill: cantidad}}} usado por el evaluador.
    """
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
            if s in [1, 2]: # Mañana o Tarde
                perfil = reglas.get('demanda_pico') if es_pico else (
                    reglas.get('demanda_finde') if es_finde else reglas.get('demanda_normal')
                )
            else: # Noche (usualmente demanda de fin de semana/fija)
                perfil = reglas.get('demanda_finde') 
                
            demandas = perfil.get(s_key, reglas.get('demanda_normal', {}).get(s_key, {"junior": 1, "senior": 1}))
            reqs[d][s] = {"junior": demandas['junior'], "senior": demandas['senior']}
            
    return reqs

def _generar_matriz_disponibilidad(data: dict) -> np.ndarray:
    """Crea la matriz booleana de disponibilidad aplicando excepciones.

    Inicializa una matriz de 'True' y marca como 'False' los días donde el 
    profesional tiene licencias, vacaciones o indisponibilidad forzada.

    Args:
        data (dict): Diccionario con excepciones de disponibilidad y dimensiones.

    Returns:
        np.ndarray: Matriz booleana de dimensiones P x D.
    """
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
    """Crea la matriz de pesos de preferencias (PTE/PDL).

    Asigna valores positivos (preferencia de turno) o negativos 
    (preferencia de descanso) a celdas específicas de la planificación.

    Args:
        data (dict): Diccionario con excepciones de preferencias.

    Returns:
        np.ndarray: Matriz de enteros de dimensiones P x D.
    """
    matriz = np.zeros((data['num_profesionales'], data['num_dias']), dtype=int)
    for exc in data.get('excepciones_preferencias', []):
        valor = exc['valor']
        profs = exc.get('prof_indices', [])
        dias = exc.get('dias', [exc.get('dia')] if 'dia' in exc else [])
        for p in profs:
            for d in dias:
                if d is not None: 
                    matriz[p, d] = valor
    return matriz