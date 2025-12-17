import requests
import json
import time
import sys

# URL base de tu API local
BASE_URL = "http://127.0.0.1:8000"

def probar_api():
    print("--- INICIANDO PRUEBA DE INTEGRACIÓN ---")

    # 1. Cargar datos de ejemplo desde la carpeta 'examples'
    # Asegurate de que los nombres de archivo coincidan con los que moviste
    try:
        with open("examples/instancia_01_base.json", "r") as f:
            datos_problema = json.load(f)
        with open("examples/config_ga_fast.json", "r") as f:
            config_ga = json.load(f)
    except FileNotFoundError:
        print("❌ Error: No encuentro los archivos JSON en la carpeta 'examples'.")
        return

    # 2. Armar el Payload (el cuerpo del mensaje)
    payload = {
        "config": config_ga,
        "datos_problema": datos_problema,
        "estrategias": {
            "sel": "torneo_deterministico",
            "cross": "bloques_verticales",
            "mut": "hibrida_adaptativa"
        }
    }

    # 3. Enviar solicitud POST para iniciar el trabajo
    print(f"📡 Enviando solicitud a {BASE_URL}/planificar ...")
    start_req = time.time()
    resp = requests.post(f"{BASE_URL}/planificar", json=payload)
    
    if resp.status_code != 200:
        print(f"❌ Error al planificar: {resp.text}")
        return

    data = resp.json()
    job_id = data["job_id"]
    print(f"✅ Trabajo iniciado. ID: {job_id}")
    print(f"🔗 URL Estado: {data['status_url']}")

    # 4. Polling (Consultar estado cada cierto tiempo)
    print("\n⏳ Esperando resultados (Polling)...")
    while True:
        resp_status = requests.get(f"{BASE_URL}/status/{job_id}")
        estado = resp_status.json()["status"]
        
        sys.stdout.write(f"\r   Estado actual: {estado}   ")
        sys.stdout.flush()

        if estado == "completed":
            print("\n✅ ¡Trabajo completado!")
            break
        elif estado == "failed":
            print("\n❌ El trabajo falló.")
            # Intentar ver el error
            err_resp = requests.get(f"{BASE_URL}/result/{job_id}")
            print("Detalle:", err_resp.json())
            return
        
        time.sleep(1) # Esperar 1 segundo antes de volver a preguntar

    # 5. Obtener Resultados
    total_time = time.time() - start_req
    print(f"\n📥 Descargando resultados finalizados (Tiempo total cliente: {total_time:.2f}s)...")
    resp_result = requests.get(f"{BASE_URL}/result/{job_id}")
    resultado = resp_result.json()

    # Mostrar resumen
    print("-" * 30)
    print(f"🏆 Fitness obtenido: {resultado.get('fitness')}")
    print(f"⏱️  Tiempo motor GA: {resultado.get('tiempo_ejecucion'):.4f}s")
    print(f"🧬 Generaciones: {resultado.get('generaciones_completadas')}")
    
    solucion = resultado.get('solucion')
    if solucion:
        print(f"📅 Tamaño de la matriz solución: {len(solucion)} profesionales x {len(solucion[0])} días")
    print("-" * 30)

if __name__ == "__main__":
    # Necesitamos la librería 'requests' para este script de prueba
    # pip install requests
    probar_api()