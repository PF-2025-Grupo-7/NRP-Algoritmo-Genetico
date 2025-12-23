"""Módulo de Carga y Procesamiento de Datos (Loader).

Este módulo se encarga de transformar las solicitudes crudas provenientes de la 
API en estructuras de datos optimizadas (Sets, Tuplas y matrices NumPy) para 
su procesamiento eficiente en el Algoritmo Genético.
"""

import numpy as np

def procesar_datos_instancia(data: dict) -> dict:
    """Orquestador que transforma el JSON de la API en el formato para el GA.

    Coordina la limpieza, el mapeo de perfiles profesionales reales, el cálculo 
    de cobertura y la creación de matrices de restricciones.

    Args:
        data (dict): Diccionario crudo recibido desde el endpoint de la API.

    Returns:
        dict: Diccionario procesado con todos los objetos necesarios para 
            instanciar la clase ProblemaGAPropio.
    """
    # 1. Limpieza y conversión de tipos básicos
    data = _preprocesar_datos_basicos(data)
    
    # 2. Procesamiento de Profesionales (NUEVA LÓGICA)
    # Extraemos la lista real y calculamos el total dinámicamente
    lista_profs = data['lista_profesionales']
    num_profesionales = len(lista_profs)
    data['num_profesionales'] = num_profesionales
    
    # Mapeamos la lista a un diccionario indexado por posición (0, 1, 2...)
    # que es lo que necesita el motor matemático del GA.
    data['info_profesionales'] = {
        idx: {
            'id_db': p['id_db'],
            'nombre': p['nombre'],
            'skill': p['skill'],
            't_min': p['t_min'],
            't_max': p['t_max']
        } 
        for idx, p in enumerate(lista_profs)
    }
    
    # 3. Calcular requerimientos de cobertura por día/turno/skill
    data['requerimientos_cobertura'] = _generar_requerimientos_cobertura(data)
    
    # 4. Generar matrices de restricciones (NumPy)
    data['matriz_disponibilidad'] = _generar_matriz_disponibilidad(data)
    data['matriz_preferencias'] = _generar_matriz_preferencias(data)

    # 5. Limpieza final de llaves temporales para optimizar memoria
    # Eliminamos lista_profesionales porque ya la convertimos a info_profesionales
    keys_to_remove = [
        'reglas_cobertura', 'lista_profesionales', 
        'excepciones_disponibilidad', 'excepciones_preferencias'
    ]
    for k in keys_to_remove:
        data.pop(k, None)

    return data

def _preprocesar_datos_basicos(data: dict) -> dict:
    """Convierte listas de JSON a sets y asegura tipos numéricos consistentes.

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

    # Cálculo de días no hábiles (Sábados y Domingos) para usar en reglas de cobertura
    data['dias_no_habiles'] = {d for d in range(data['num_dias']) if d % 7 in [5, 6]}
    return data

def _generar_requerimientos_cobertura(data: dict) -> dict:
    """Calcula la demanda de personal según el tipo de día.

    Analiza cada día del horizonte para determinar si es un día de pico, 
    fin de semana o normal, y asigna la demanda de skills correspondiente.
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
    """
    # Usamos num_profesionales que calculamos en el paso 2
    matriz = np.full((data['num_profesionales'], data['num_dias']), True)
    
    for exc in data.get('excepciones_disponibilidad', []):
        p_idx = exc.get('prof_index')
        
        # Validación de seguridad para evitar out of bounds
        if p_idx >= data['num_profesionales']: continue

        disponible = 1 if exc.get('disponible', True) else 0
        
        if 'dias_range' in exc:
            matriz[p_idx, exc['dias_range'][0]:exc['dias_range'][1]] = disponible
        elif exc.get('tipo') == 'fines_de_semana':
            for d in data['dias_no_habiles']:
                matriz[p_idx, d] = disponible
                
    return matriz

def _generar_matriz_preferencias(data: dict) -> np.ndarray:
    """Crea la matriz de pesos de preferencias (PTE/PDL).

    Asigna valores positivos (preferencia de turno) o negativos 
    (preferencia de descanso) a celdas específicas de la planificación.
    """
    matriz = np.zeros((data['num_profesionales'], data['num_dias']), dtype=int)
    
    for exc in data.get('excepciones_preferencias', []):
        valor = exc['valor']
        profs = exc.get('prof_indices', [])
        dias = exc.get('dias', [exc.get('dia')] if 'dia' in exc else [])
        
        for p in profs:
            if p >= data['num_profesionales']: continue # Validación
            for d in dias:
                if d is not None and 0 <= d < data['num_dias']: 
                    matriz[p, d] = valor
                    
    return matriz