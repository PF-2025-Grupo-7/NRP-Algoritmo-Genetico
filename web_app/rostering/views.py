import json
from datetime import datetime, date
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt 

# Importamos modelos (incluyendo la tabla temporal TrabajoPlanificacion)
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
        # 1. Leer datos del cuerpo del request (JSON)
        data = json.loads(request.body)
        
        fecha_inicio_str = data.get('fecha_inicio')
        fecha_fin_str = data.get('fecha_fin')
        especialidad = data.get('especialidad')

        # Validaciones básicas
        if not all([fecha_inicio_str, fecha_fin_str, especialidad]):
            return JsonResponse({'error': 'Faltan parámetros obligatorios.'}, status=400)

        # Convertir strings a objetos date
        inicio = parse_date(fecha_inicio_str)
        fin = parse_date(fecha_fin_str)

        # 2. Generar el Payload usando tu servicio
        payload = generar_payload_ag(inicio, fin, especialidad)

        # 3. Invocar a la API de Optimización (Docker)
        respuesta_api = invocar_api_planificacion(payload)

        if not respuesta_api or 'job_id' not in respuesta_api:
            return JsonResponse({'error': 'No se pudo iniciar el trabajo en el motor de IA.'}, status=503)

        job_id = respuesta_api['job_id']

        # 4. GUARDAR CONTEXTO EN BASE DE DATOS (CRÍTICO)
        # Usamos la tabla TrabajoPlanificacion para persistir los datos 
        # independientemente de si el usuario tiene cookies o no.
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
            'mensaje': 'Optimización iniciada. Contexto guardado en BD.'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# --- VISTA 2: POLLING (CONSULTAR ESTADO) ---

@csrf_exempt
@require_GET
def verificar_estado_planificacion(request, job_id):
    try:
        # 1. Recuperar contexto de la BD (Si no existe, es un error)
        try:
            trabajo = TrabajoPlanificacion.objects.get(job_id=job_id)
        except TrabajoPlanificacion.DoesNotExist:
            return JsonResponse({'error': 'Job ID no encontrado o expirado.'}, status=404)

        # 2. Consultar a la API
        resultado = consultar_resultado_ag(job_id)
        
        if not resultado:
            return JsonResponse({'status': 'error', 'mensaje': 'Error de conexión con la API'}, status=503)

        # 3. Verificar si hay error en el algoritmo
        if 'error' in resultado:
            return JsonResponse({'status': 'failed', 'error': resultado['error']})

        # 4. Verificar si terminó (Buscamos 'fitness' o si el status es completed)
        if 'fitness' in resultado or resultado.get('status') == 'completed':
            
            # --- ÉXITO: GUARDAR EN BD ---
            
            # Recuperamos los datos desde el objeto 'trabajo' (BD)
            # Ya no dependemos de request.session
            
            try:
                # Llamamos a tu servicio de guardado
                cronograma = guardar_solucion_db(
                    trabajo.fecha_inicio, 
                    trabajo.fecha_fin, 
                    trabajo.especialidad, 
                    trabajo.payload_original, 
                    resultado # Respuesta completa de la API
                )
                
                # IMPORTANTE: Borrar el trabajo temporal para no acumular basura
                trabajo.delete()

                return JsonResponse({
                    'status': 'completed',
                    'cronograma_id': cronograma.id,
                    'fitness': resultado.get('fitness'),
                    'mensaje': 'Planificación guardada con éxito.'
                })
                
            except Exception as save_error:
                return JsonResponse({'error': f"Error guardando cronograma: {str(save_error)}"}, status=500)

        # 5. Si no terminó, sigue corriendo
        return JsonResponse({'status': 'running'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def pagina_generador(request):
    """
    Renderiza la pantalla HTML donde el usuario elige fechas y dispara el proceso.
    """
    return render(request, 'rostering/generador.html')