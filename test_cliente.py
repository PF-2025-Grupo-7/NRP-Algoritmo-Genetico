import requests
import json
import time
import sys

# URL base de tu API local
BASE_URL = "http://127.0.0.1:8000"

def probar_api():
    print("--- INICIANDO PRUEBA DE INTEGRACIÓN CON REPORTE EN VIVO ---")

    # 1. Cargar datos de ejemplo
    # Nota: Si querés ver la barra de progreso moverse, usá una instancia más grande
    # o aumentá las generaciones en el JSON de config.
    try:
        # Asegurate de apuntar a los archivos correctos en tu carpeta 'examples'
        with open("examples/instancia_01_base.json", "r") as f:
            datos_problema = json.load(f)
        with open("examples/config_ga_fast.json", "r") as f:
            config_ga = json.load(f)
            
        # Opcional: Forzar más generaciones para apreciar el progreso si la instancia es chica
        # config_ga['generaciones'] = 200 
        
    except FileNotFoundError:
        print("❌ Error: No encuentro los archivos JSON en la carpeta 'examples'.")
        return

    # 2. Armar el Payload
    payload = {
        "config": config_ga,
        "datos_problema": datos_problema,
        "estrategias": {
            "sel": "torneo_deterministico",
            "cross": "bloques_verticales",
            "mut": "hibrida_adaptativa"
        }
    }

    # 3. Enviar solicitud POST
    print(f"📡 Enviando solicitud a {BASE_URL}/planificar ...")
    start_req = time.time()
    try:
        resp = requests.post(f"{BASE_URL}/planificar", json=payload)
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar a la API. ¿Está corriendo uvicorn?")
        return
    
    if resp.status_code != 200:
        print(f"❌ Error al planificar: {resp.text}")
        return

    data = resp.json()
    job_id = data["job_id"]
    print(f"✅ Trabajo iniciado. ID: {job_id}")
    print(f"🔗 URL Estado: {data['status_url']}")

    # 4. Polling con barra de progreso
    print("\n⏳ Ejecutando Algoritmo Genético...")
    
    while True:
        try:
            resp_status = requests.get(f"{BASE_URL}/status/{job_id}")
            resp_data = resp_status.json()
            estado = resp_data["status"]
            progreso = resp_data.get("progreso") # Puede ser dict o str
        except Exception as e:
            print(f"\n❌ Error consultando status: {e}")
            break

        if estado == "processing":
            # Si hay datos detallados de progreso, los mostramos
            if isinstance(progreso, dict):
                p = progreso.get('porcentaje', 0)
                gen_info = progreso.get('generacion', '?')
                fit = progreso.get('fitness_actual', '?')
                
                # Formato: [ 45% ] Gen: 90/200 | Mejor Fit: 1200.0
                msg = f"🚀 [{str(p).rjust(3)}%] Gen: {gen_info} | Mejor Fit: {fit}"
            else:
                # Si es el mensaje inicial "Iniciando..." o similar
                msg = f"⏳ {progreso if progreso else 'Procesando...'}"

            # Imprimir con retorno de carro (\r) para sobreescribir la línea
            # .ljust(80) asegura borrar caracteres viejos si el mensaje se acorta
            sys.stdout.write(f"\r{msg.ljust(80)}")
            sys.stdout.flush()

        elif estado == "completed":
            print(f"\n✅ ¡Trabajo completado exitosamente!")
            break
            
        elif estado == "failed":
            print(f"\n❌ El trabajo falló.")
            err_resp = requests.get(f"{BASE_URL}/result/{job_id}")
            print("Detalle del error:", err_resp.json())
            return
        
        # Ajustá este tiempo según lo rápido que quieras refrescar la consola
        time.sleep(0.5) 

    # 5. Obtener Resultados Finales
    total_time = time.time() - start_req
    print(f"\n📥 Descargando resultados (Tiempo total cliente: {total_time:.2f}s)...")
    
    resp_result = requests.get(f"{BASE_URL}/result/{job_id}")
    resultado = resp_result.json()

    # Mostrar resumen
    print("=" * 40)
    print(f"🏆 Fitness Final:      {resultado.get('fitness')}")
    print(f"⏱️  Tiempo Motor GA:    {resultado.get('tiempo_ejecucion'):.4f}s")
    print(f"🧬 Generaciones Total: {resultado.get('generaciones_completadas')}")
    
    solucion = resultado.get('solucion')
    if solucion:
        filas = len(solucion)
        columnas = len(solucion[0]) if filas > 0 else 0
        print(f"📅 Matriz Solución:    {filas} Profesionales x {columnas} Días")
    
    print("=" * 40)

if __name__ == "__main__":
    probar_api()