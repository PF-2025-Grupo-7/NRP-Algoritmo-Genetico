import json
from datetime import datetime, date
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt 
from django.core.exceptions import ValidationError # <--- IMPORTAR ESTO

# Importamos modelos
from .models import Empleado, Cronograma, TrabajoPlanificacion
from .services import (
    generar_payload_ag, 
    invocar_api_planificacion, 
    consultar_resultado_ag, 
    guardar_solucion_db
)

# --- VISTA 1: INICIAR EL PROCESO ---

@csrf_exempt 
@require_POST
def iniciar_planificacion(request):
    try:
        # 1. Leer datos
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido en el cuerpo de la petición.'}, status=400)
        
        fecha_inicio_str = data.get('fecha_inicio')
        fecha_fin_str = data.get('fecha_fin')
        especialidad = data.get('especialidad')

        # Validaciones básicas
        if not all([fecha_inicio_str, fecha_fin_str, especialidad]):
            return JsonResponse({'error': 'Faltan parámetros obligatorios (fecha_inicio, fecha_fin, especialidad).'}, status=400)

        inicio = parse_date(fecha_inicio_str)
        fin = parse_date(fecha_fin_str)
        
        if not inicio or not fin:
            return JsonResponse({'error': 'Formato de fecha inválido. Usar YYYY-MM-DD.'}, status=400)

        # 2. Generar el Payload (Aquí salta el ValidationError si los turnos no son uniformes)
        payload = generar_payload_ag(inicio, fin, especialidad)

        # 3. Invocar a la API
        respuesta_api = invocar_api_planificacion(payload)

        if not respuesta_api or 'job_id' not in respuesta_api:
            # Si la API devuelve un mensaje de error específico, intentamos mostrarlo
            msg = 'No se pudo iniciar el trabajo en el motor de IA.'
            if respuesta_api and 'detail' in respuesta_api:
                msg += f" Detalle: {respuesta_api['detail']}"
            return JsonResponse({'error': msg}, status=503)

        job_id = respuesta_api['job_id']

        # 4. Guardar contexto
        TrabajoPlanificacion.objects.create(
            job_id=job_id,
            fecha_inicio=inicio,
            fecha_fin=fin,
            especialidad=especialidad,
            payload_original=payload
        )

        return JsonResponse({
            'status': 'started',
            'job_id': job_id,
            'mensaje': 'Optimización iniciada correctamente.'
        })

    # MANEJO DE ERRORES DE LÓGICA (Validaciones de services.py)
    except ValidationError as ve:
        return JsonResponse({'error': f"Error de validación: {ve.message}"}, status=400)
    except ValueError as ve:
        return JsonResponse({'error': str(ve)}, status=400)
    except Exception as e:
        # Loguear error real en consola del servidor para debug
        print(f"Error 500 en iniciar_planificacion: {e}")
        return JsonResponse({'error': f"Error interno del servidor: {str(e)}"}, status=500)


# --- VISTA 2: POLLING (CONSULTAR ESTADO) ---

@csrf_exempt
@require_GET
def verificar_estado_planificacion(request, job_id):
    try:
        # 1. Recuperar contexto
        try:
            trabajo = TrabajoPlanificacion.objects.get(job_id=job_id)
        except TrabajoPlanificacion.DoesNotExist:
            return JsonResponse({'error': 'Job ID no encontrado o expirado.'}, status=404)

        # 2. Consultar a la API
        resultado = consultar_resultado_ag(job_id)
        
        if not resultado:
            return JsonResponse({'status': 'error', 'mensaje': 'Error de conexión con la API'}, status=503)

        if 'status' in resultado and resultado['status'] == 'error':
             return JsonResponse({'status': 'failed', 'error': resultado.get('error', 'Error desconocido en el motor.')})

        # 3. Verificar si terminó
        if 'fitness' in resultado or resultado.get('status') == 'completed':
            try:
                cronograma = guardar_solucion_db(
                    trabajo.fecha_inicio, 
                    trabajo.fecha_fin, 
                    trabajo.especialidad, 
                    trabajo.payload_original, 
                    resultado
                )
                
                # Limpieza
                trabajo.delete()

                return JsonResponse({
                    'status': 'completed',
                    'cronograma_id': cronograma.id,
                    'fitness': resultado.get('fitness'),
                    'mensaje': 'Planificación guardada con éxito.'
                })
                
            except Exception as save_error:
                print(f"Error guardando DB: {save_error}")
                return JsonResponse({'error': f"Error guardando cronograma: {str(save_error)}"}, status=500)

        # 4. Sigue corriendo
        return JsonResponse({'status': 'running'})

    except Exception as e:
        print(f"Error polling: {e}")
        return JsonResponse({'error': str(e)}, status=500)
    
def pagina_generador(request):
    return render(request, 'rostering/generador.html') # Asegurate que sea .html