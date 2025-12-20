import pytest
from fastapi.testclient import TestClient
from src.api import app
import json

client = TestClient(app)

def test_health_check_planificar_schema():
    """Verifica que el endpoint rechace datos que no son diccionarios."""
    # Enviamos un string en lugar de un diccionario para forzar el error 422
    response = client.post("/planificar", json={"config": "esto no es un dict", "datos_problema": {}})
    assert response.status_code == 422

def test_evaluar_solucion_mock():
    """Verifica que el endpoint de auditoría responda correctamente."""
    with open("payload_api_auditoria.json", "r") as f:
        payload = json.load(f)

    response = client.post("/soluciones/evaluar", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # El fitness ahora está dentro de 'metricas' según tu problema.py
    assert "metricas" in data
    assert "fitness_total" in data["metricas"]
    assert "violaciones_duras" in data