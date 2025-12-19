from src.loader import procesar_datos_instancia

def test_procesar_datos_instancia_integridad():
    datos_crudos = {
        "num_profesionales": 2,
        "num_dias": 7,
        "duracion_turnos": {"1": 8, "2": 8, "3": 8},
        "info_profesionales_base": {"senior_count": 1, "t_min": 10, "t_max": 40},
        "secuencias_prohibidas": [[3, 1]],
        "turnos_noche": [3],
        "turnos_a_cubrir": [1, 2, 3],
        "skills_a_cubrir": ["junior", "senior"],
        "reglas_cobertura": {
            "dias_pico": [],
            # Agregamos demandas mínimas para que el loader no falle
            "demanda_pico":   {"1": {"junior": 1, "senior": 1}, "2": {"junior": 1, "senior": 0}, "3": {"junior": 0, "senior": 1}},
            "demanda_finde":  {"1": {"junior": 1, "senior": 0}, "2": {"junior": 1, "senior": 0}, "3": {"junior": 0, "senior": 1}},
            "demanda_normal": {"1": {"junior": 1, "senior": 1}, "2": {"junior": 1, "senior": 0}, "3": {"junior": 0, "senior": 1}}
        },
        "excepciones_disponibilidad": [],
        "excepciones_preferencias": [],
        "pesos_fitness": {"eq": 1, "dif": 1, "pdl": 1, "pte": 1, "alpha_pte": 0.5}
    }
    procesados = procesar_datos_instancia(datos_crudos)
    assert "requerimientos_cobertura" in procesados
    assert isinstance(procesados['requerimientos_cobertura'][0][1], dict)