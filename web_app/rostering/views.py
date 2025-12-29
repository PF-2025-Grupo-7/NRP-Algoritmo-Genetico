import json
from datetime import datetime, date
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt 
from django.core.exceptions import ValidationError # <--- IMPORTAR ESTO
from django.shortcuts import render, redirect # Asegurate de tener redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from .models import Cronograma, Asignacion, Empleado
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .forms import EmpleadoForm
from .filters import EmpleadoFilter

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
@login_required
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
    
@login_required
def pagina_generador(request):
    return render(request, 'rostering/generador.html') # Asegurate que sea .html


def registrar_usuario(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Loguear al usuario inmediatamente después de registrarse
            login(request, user)
            messages.success(request, "¡Registro exitoso! Bienvenido.")
            return redirect('vista_generador') # Redirige al home
        else:
            messages.error(request, "Por favor corrige los errores abajo.")
    else:
        form = UserCreationForm()
        
    return render(request, 'registration/register.html', {'form': form})


@login_required
def ver_cronograma(request, cronograma_id):
    # 1. Obtener el cronograma
    cronograma = get_object_or_404(Cronograma, pk=cronograma_id)
    
    # 2. Generar el rango de fechas (encabezados de columnas)
    rango_fechas = []
    fecha_iter = cronograma.fecha_inicio
    while fecha_iter <= cronograma.fecha_fin:
        rango_fechas.append(fecha_iter)
        fecha_iter += timedelta(days=1)
        
    # 3. Obtener todas las asignaciones de golpe (Optimización DB)
    asignaciones = Asignacion.objects.filter(
        cronograma=cronograma
    ).select_related('empleado', 'tipo_turno')
    
    # 4. Construir la Matriz:  dict[empleado_id][fecha_str] = turno
    # Esto facilita buscar en el template: "¿Qué hace el Empleado X el día Y?"
    matriz_asignaciones = {}
    
    for asig in asignaciones:
        emp_id = asig.empleado.id
        fecha_str = asig.fecha.strftime("%Y-%m-%d")
        
        if emp_id not in matriz_asignaciones:
            matriz_asignaciones[emp_id] = {}
        
        matriz_asignaciones[emp_id][fecha_str] = asig.tipo_turno

    # 5. Obtener lista de empleados ordenada (Filas)
    # Filtramos solo los que tienen asignaciones o pertenecen a la especialidad
    empleados = Empleado.objects.filter(
        especialidad=cronograma.especialidad, 
        activo=True
    ).order_by('experiencia', 'legajo') # Seniors primero, luego Juniors

    # 6. Preparar estructura final para el template
    # Lista de filas, donde cada fila tiene el empleado y sus celdas ordenadas
    filas_tabla = []
    
    for emp in empleados:
        celdas = []
        horas_totales = 0
        turnos_totales = 0
        
        for fecha in rango_fechas:
            fecha_key = fecha.strftime("%Y-%m-%d")
            # Buscamos si hay turno ese día para este empleado
            turno = matriz_asignaciones.get(emp.id, {}).get(fecha_key)
            
            celdas.append({
                'fecha': fecha,
                'turno': turno, # Puede ser None (Franco)
            })
            
            if turno:
                # Sumamos para estadísticas rápidas
                horas_totales += turno.duracion_horas
                turnos_totales += 1
                
        filas_tabla.append({
            'empleado': emp,
            'celdas': celdas,
            'stats': {'horas': horas_totales, 'turnos': turnos_totales}
        })

    return render(request, 'rostering/cronograma_detail.html', {
        'cronograma': cronograma,
        'rango_fechas': rango_fechas,
        'filas_tabla': filas_tabla,
    })

# rostering/views.py

def ver_cronograma_diario(request, cronograma_id):
    cronograma = get_object_or_404(Cronograma, pk=cronograma_id)
    
    # Obtenemos todas las asignaciones ordenadas por fecha y hora de turno
    asignaciones = Asignacion.objects.filter(cronograma=cronograma).select_related(
        'empleado', 'tipo_turno'
    ).order_by('fecha', 'tipo_turno__hora_inicio')

    # Estructura: agenda[fecha_date] = { 'Turno Mañana': [Emp1, Emp2], 'Turno Tarde': [...] }
    agenda = {}
    
    # Tipos de turno para ordenar la visualización (Mañana primero, Noche al final)
    tipos_turno = list(asignaciones.values_list('tipo_turno__nombre', flat=True).distinct())
    # Opcional: Ordenar tipos_turno manualmente si querés un orden específico
    
    for asig in asignaciones:
        fecha = asig.fecha
        turno_nombre = asig.tipo_turno.nombre
        
        if fecha not in agenda:
            agenda[fecha] = {}
        
        if turno_nombre not in agenda[fecha]:
            agenda[fecha][turno_nombre] = []
            
        agenda[fecha][turno_nombre].append(asig.empleado)

    return render(request, 'rostering/cronograma_diario.html', {
        'cronograma': cronograma,
        'agenda': agenda,
    })


# --- ABM DE EMPLEADOS ---

class EmpleadoListView(LoginRequiredMixin, ListView):
    model = Empleado
    template_name = 'rostering/empleado_list.html'
    context_object_name = 'empleados'
    paginate_by = 15 

    def get_queryset(self):
        queryset = super().get_queryset()
        
        self.filterset = EmpleadoFilter(self.request.GET, queryset=queryset)
        queryset = self.filterset.qs

        ordering = self.request.GET.get('order_by')
        if ordering:
            # CORREGIDO: Campos reales del modelo
            valid_fields = ['legajo', 'nombre_completo', 'especialidad', 'experiencia', 'min_turnos_mensuales', 'max_turnos_mensuales', 'activo']
            check_field = ordering[1:] if ordering.startswith('-') else ordering
            if check_field in valid_fields:
                queryset = queryset.order_by(ordering)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filterset.form
        context['current_order'] = self.request.GET.get('order_by', '')
        return context

class EmpleadoCreateView(LoginRequiredMixin, CreateView):
    model = Empleado
    form_class = EmpleadoForm
    template_name = 'rostering/empleado_form.html'
    success_url = reverse_lazy('empleado_list')
    extra_context = {'titulo': 'Nuevo Empleado'}

class EmpleadoUpdateView(LoginRequiredMixin, UpdateView):
    model = Empleado
    form_class = EmpleadoForm
    template_name = 'rostering/empleado_form.html' # Reutilizamos el template
    success_url = reverse_lazy('empleado_list')
    extra_context = {'titulo': 'Editar Empleado'}

class EmpleadoDeleteView(LoginRequiredMixin, DeleteView):
    model = Empleado
    template_name = 'rostering/empleado_confirm_delete.html'
    success_url = reverse_lazy('empleado_list')