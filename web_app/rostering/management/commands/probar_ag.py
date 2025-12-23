import time
from django.core.management.base import BaseCommand
from datetime import date
import json
from rostering.services import generar_payload_ag, invocar_api_planificacion, consultar_resultado_ag
from rostering.models import Empleado

class Command(BaseCommand):
    help = 'Genera JSON, envía a la API y espera el resultado (detectando "fitness")'

    def handle(self, *args, **kwargs):
        self.stdout.write("--- Iniciando prueba de Integración ---")

        inicio = date(2025, 11, 1)
        fin = date(2025, 11, 30)
        especialidad = Empleado.TipoEspecialidad.MEDICO 

        try:
            # 1. Generar Payload
            self.stdout.write(f"Generando datos para {especialidad}...")
            json_resultado = generar_payload_ag(inicio, fin, especialidad)
            
            # 2. Iniciar Trabajo (POST)
            self.stdout.write("Enviando a la API...")
            respuesta_inicial = invocar_api_planificacion(json_resultado)
            
            if not respuesta_inicial or 'job_id' not in respuesta_inicial:
                self.stdout.write(self.style.ERROR("❌ Error al iniciar: No se recibió job_id"))
                if respuesta_inicial:
                    self.stdout.write(f"Respuesta: {respuesta_inicial}")
                return

            job_id = respuesta_inicial['job_id']
            self.stdout.write(self.style.SUCCESS(f"✅ Trabajo iniciado. ID: {job_id}"))
            self.stdout.write("Esperando resultados (Polling)...")

            # 3. Bucle de Espera
            intentos = 0
            tiempo_entre_intentos = 2  # Segundos
            max_intentos = 300         # 10 minutos aprox
            
            while intentos < max_intentos:
                time.sleep(tiempo_entre_intentos) 
                
                resultado = consultar_resultado_ag(job_id)
                
                if resultado:
                    # CRITERIO DE ÉXITO: Si existe el campo 'fitness', terminó.
                    if 'fitness' in resultado:
                        self.stdout.write(self.style.SUCCESS("\n🏆 ¡Optimización Terminada!"))
                        
                        fit = resultado.get('fitness')
                        tiempo = resultado.get('execution_time', 'N/A')
                        solucion = resultado.get('solution', [])
                        
                        self.stdout.write(f"  > Fitness Final: {fit}")
                        self.stdout.write(f"  > Tiempo Ejecución: {tiempo}s")
                        self.stdout.write(f"  > Turnos Asignados: {len(solucion)}")
                        
                        # Opcional: Imprimir un pedacito de la solución
                        # self.stdout.write(f"  > Muestra: {solucion[:2]}")
                        break
                        
                    # CRITERIO DE FALLO
                    elif 'error' in resultado:
                        self.stdout.write(self.style.ERROR(f"\n❌ Error reportado por API: {resultado['error']}"))
                        break
                    
                    # CRITERIO DE ESPERA (Status 'running' viene de services.py cuando es HTTP 202)
                    elif resultado.get('status') == 'running':
                        self.stdout.write(".", ending="")
                        self.stdout.flush()
                    
                    else:
                        # Caso raro (ni error, ni running, ni fitness)
                        self.stdout.write("?", ending="")
                        self.stdout.flush()
                
                intentos += 1
            
            if intentos >= max_intentos:
                self.stdout.write(self.style.WARNING("\n⏳ Tiempo de espera agotado."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error crítico en script: {e}'))