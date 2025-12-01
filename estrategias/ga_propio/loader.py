import json
import numpy as np

def cargar_configuracion_ga(ruta_archivo):
    with open(ruta_archivo, 'r') as f:
        return json.load(f)

def cargar_instancia_problema(ruta_archivo):
    with open(ruta_archivo, 'r') as f:
        data = json.load(f)
    
    P = data['num_profesionales']
    D = data['num_dias']

    # --- 1. CONVERSIONES BÁSICAS ---
    # Convertir listas a Sets/Tuplas
    data['secuencias_prohibidas'] = set(tuple(x) for x in data['secuencias_prohibidas'])
    data['turnos_noche'] = set(data['turnos_noche'])
    
    # Duración turnos (keys de json siempre son str, pasar a int)
    if "duracion_turnos" in data:
        data['duracion_turnos'] = {int(k): v for k, v in data['duracion_turnos'].items()}

    # Calcular días no hábiles (fines de semana)
    dias_no_habiles = set()
    for d in range(D):
        if d % 7 == 5 or d % 7 == 6: # Sábado(5) o Domingo(6)
            dias_no_habiles.add(d)
    data['dias_no_habiles'] = dias_no_habiles

    # --- 2. GENERAR INFO PROFESIONALES ---
    # Reconstruye la lista de diccionarios [{'skill': 'senior'...}, ...]
    info_prof = []
    base_info = data['info_profesionales_base']
    for i in range(P):
        skill = 'senior' if i < base_info['senior_count'] else 'junior'
        info_prof.append({
            'skill': skill,
            't_min': base_info['t_min'],
            't_max': base_info['t_max']
        })
    data['info_profesionales'] = info_prof

    # --- 3. GENERAR REQUERIMIENTOS DE COBERTURA ---
    # Reconstruye el diccionario gigante reqs[dia][turno][skill] = cantidad
    reqs = {}
    reglas = data['reglas_cobertura']
    
    for d in range(D):
        reqs[d] = {}
        dia_semana = d % 7
        es_finde = (d in dias_no_habiles)
        es_pico = (dia_semana in reglas['dias_pico'])
        
        for s_str in data['turnos_a_cubrir']: # iteramos sobre [1, 2, 3]
            s = int(s_str) # asegurar entero
            s_key = str(s) # key para buscar en el json
            
            reqs[d][s] = {}
            
            # Seleccionar perfil de demanda
            if s == 1: # Mañana
                perfil = reglas['demanda_pico'] if es_pico else (reglas['demanda_finde'] if es_finde else reglas['demanda_normal'])
            elif s == 2: # Tarde
                perfil = reglas['demanda_pico'] if es_pico else (reglas['demanda_finde'] if es_finde else reglas['demanda_normal'])
            else: # Noche
                perfil = reglas['demanda_finde'] # Noche siempre igual en este caso
                
            # Extraer valores del perfil seleccionado
            # Nota: El JSON tiene estructura "1": {"junior": X...}. Accedemos con s_key.
            demandas_turno = perfil.get(s_key, reglas['demanda_normal'][s_key])
            
            reqs[d][s]['junior'] = demandas_turno['junior']
            reqs[d][s]['senior'] = demandas_turno['senior']

    data['requerimientos_cobertura'] = reqs

    # --- 4. GENERAR MATRIZ DISPONIBILIDAD ---
    dispon = np.full((P, D), True)
    for excepcion in data.get('excepciones_disponibilidad', []):
        p_idx = excepcion.get('prof_index')
        
        # Caso: Rango de días
        if 'dias_range' in excepcion:
            start, end = excepcion['dias_range']
            # Python slice no incluye el último, ajustar si es necesario según tu lógica original
            # En el original era 0:7 (días 0..6).
            dispon[p_idx, start:end] = excepcion['disponible']
            
        # Caso: Tipo especial (fines de semana)
        elif excepcion.get('tipo') == 'fines_de_semana':
            for d in dias_no_habiles:
                dispon[p_idx, d] = excepcion['disponible']
                
    data['matriz_disponibilidad'] = dispon

    # --- 5. GENERAR MATRIZ PREFERENCIAS ---
    prefs = np.zeros((P, D), dtype=int)
    for exc in data.get('excepciones_preferencias', []):
        valor = exc['valor']
        # Lista de profesionales afectados
        profesionales = exc.get('prof_indices', [])
        
        # Caso: Un día específico
        if 'dia' in exc:
            d = exc['dia']
            for p in profesionales:
                prefs[p, d] = valor
                
        # Caso: Lista de días
        if 'dias' in exc:
            for d in exc['dias']:
                for p in profesionales:
                    prefs[p, d] = valor

    data['matriz_preferencias'] = prefs

    # Limpieza de claves auxiliares que no necesita la clase Problema
    claves_a_borrar = ['reglas_cobertura', 'info_profesionales_base', 
                       'excepciones_disponibilidad', 'excepciones_preferencias']
    for k in claves_a_borrar:
        if k in data:
            del data[k]

    return data