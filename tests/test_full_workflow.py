import pytest
import httpx # Recomendado para tests asincrónicos, o podés seguir con requests
import time
import json
from src.api import app

# Si usás TestClient de FastAPI, las BackgroundTasks se ejecutan sincrónicamente 
# por defecto, lo cual facilita el testeo.
from fastapi.testclient import TestClient

client = TestClient(app)

def test_flujo_planificacion_completo():
    # 1. Preparar Datos (usando tus archivos de ejemplo)
    with open("payload_api_planificar.json", "r") as f:
        payload = json.load(f)
    
    # Reducimos generaciones para que el test sea rápido (Smoke Test)
    payload["config"]["generaciones"] = 5 

    # 2. Iniciar Planificación
    response = client.post("/planificar", json=payload)
    assert response.status_code == 200
    data = response.json()
    job_id = data["job_id"]
    assert job_id is not None

    # 3. Polling de Estado con Timeout
    max_intentos = 20
    intentos = 0
    completado = False
    
    while intentos < max_intentos:
        status_resp = client.get(f"/status/{job_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        
        if status_data["status"] == "completed":
            completado = True
            break
        elif status_data["status"] == "failed":
            pytest.fail(f"El trabajo falló: {status_data.get('error')}")
        
        time.sleep(1) # Esperar 1 segundo entre chequeos
        intentos += 1

    assert completado, "El test superó el tiempo de espera máximo sin completar"

    # 4. Verificar Resultados Finales
    result_resp = client.get(f"/result/{job_id}")
    assert result_resp.status_code == 200
    resultado = result_resp.json()
    
    assert "solucion" in resultado
    assert "fitness" in resultado
    assert len(resultado["solucion"]) == payload["datos_problema"]["num_profesionales"]