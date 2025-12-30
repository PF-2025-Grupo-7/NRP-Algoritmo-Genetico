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
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
# Importar SecuenciaProhibida
from .models import Empleado, Cronograma, TipoTurno, NoDisponibilidad, Preferencia, SecuenciaProhibida, Asignacion
# Importar Form y Filter
from .forms import (
    EmpleadoForm, TipoTurnoForm, NoDisponibilidadForm, PreferenciaForm, SecuenciaProhibidaForm
)
from .filters import (
    EmpleadoFilter, CronogramaFilter, NoDisponibilidadFilter, PreferenciaFilter, TipoTurnoFilter, SecuenciaProhibidaFilter
)
from .services import (
    generar_payload_ag, 
    invocar_api_planificacion, 
    consultar_resultado_ag, 
    guardar_solucion_db
)
from .models import PlantillaDemanda, ReglaDemandaSemanal, ExcepcionDemanda
from .forms import PlantillaDemandaForm, ReglaDemandaSemanalForm, ExcepcionDemandaForm
from .models import TrabajoPlanificacion


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
        plantilla_id = data.get('plantilla_id')

        # Validaciones básicas
        if not all([fecha_inicio_str, fecha_fin_str, especialidad,plantilla_id]):
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
            payload_original=payload,
            plantilla_demanda_id=plantilla_id
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

# En rostering/views.py

@csrf_exempt
@require_GET
def verificar_estado_planificacion(request, job_id):
    try:
        # 1. Recuperar contexto (la memoria temporal)
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
                # --- AQUÍ ESTÁ LA CORRECCIÓN ---
                # Pasamos el objeto plantilla_demanda recuperado del trabajo temporal
                cronograma = guardar_solucion_db(
                    fecha_inicio=trabajo.fecha_inicio, 
                    fecha_fin=trabajo.fecha_fin, 
                    especialidad=trabajo.especialidad, 
                    payload_original=trabajo.payload_original, 
                    resultado=resultado,
                    plantilla_demanda=trabajo.plantilla_demanda # <--- NUEVO PARÁMETRO
                )
                
                # Limpieza: Borramos la memoria temporal
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

class CronogramaListView(LoginRequiredMixin, ListView):
    model = Cronograma
    template_name = 'rostering/cronograma_list.html'
    context_object_name = 'cronogramas'
    # CORREGIDO: Ordenar por fecha_inicio descendente
    ordering = ['-fecha_inicio', '-fecha_creacion'] 
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        self.filterset = CronogramaFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filterset.form
        return context

# Solo necesitamos Delete. El Create es el Generador, y el Update es la Matriz.
class CronogramaDeleteView(LoginRequiredMixin, DeleteView):
    model = Cronograma
    template_name = 'rostering/cronograma_confirm_delete.html'
    success_url = reverse_lazy('cronograma_list')

class TipoTurnoListView(LoginRequiredMixin, ListView):
    model = TipoTurno
    template_name = 'rostering/tipoturno_list.html'
    context_object_name = 'turnos'
    ordering = ['especialidad', 'hora_inicio'] # Ordenar por especialidad queda mejor ahora

    def get_queryset(self):
        queryset = super().get_queryset()
        # Conectamos el filtro
        self.filterset = TipoTurnoFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasamos el formulario del filtro al template
        context['filter_form'] = self.filterset.form
        return context

class TipoTurnoCreateView(LoginRequiredMixin, CreateView):
    model = TipoTurno
    form_class = TipoTurnoForm
    template_name = 'rostering/tipoturno_form.html'
    success_url = reverse_lazy('tipoturno_list')
    extra_context = {'titulo': 'Crear Tipo de Turno'}

class TipoTurnoUpdateView(LoginRequiredMixin, UpdateView):
    model = TipoTurno
    form_class = TipoTurnoForm
    template_name = 'rostering/tipoturno_form.html'
    success_url = reverse_lazy('tipoturno_list')
    extra_context = {'titulo': 'Editar Tipo de Turno'}

class TipoTurnoDeleteView(LoginRequiredMixin, DeleteView):
    model = TipoTurno
    template_name = 'rostering/tipoturno_confirm_delete.html'
    success_url = reverse_lazy('tipoturno_list')


class NoDisponibilidadListView(LoginRequiredMixin, ListView):
    model = NoDisponibilidad
    template_name = 'rostering/nodisponibilidad_list.html'
    context_object_name = 'ausencias'
    ordering = ['-fecha_inicio']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('empleado') # <--- ESTO OPTIMIZA
        self.filterset = NoDisponibilidadFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filterset.form
        return context

class NoDisponibilidadCreateView(LoginRequiredMixin, CreateView):
    model = NoDisponibilidad
    form_class = NoDisponibilidadForm
    template_name = 'rostering/nodisponibilidad_form.html'
    success_url = reverse_lazy('nodisponibilidad_list')
    extra_context = {'titulo': 'Registrar Ausencia / Licencia'}

class NoDisponibilidadUpdateView(LoginRequiredMixin, UpdateView):
    model = NoDisponibilidad
    form_class = NoDisponibilidadForm
    template_name = 'rostering/nodisponibilidad_form.html'
    success_url = reverse_lazy('nodisponibilidad_list')
    extra_context = {'titulo': 'Editar Ausencia'}

class NoDisponibilidadDeleteView(LoginRequiredMixin, DeleteView):
    model = NoDisponibilidad
    template_name = 'rostering/confirm_delete_generic.html' # Usaremos uno genérico para ahorrar archivos
    success_url = reverse_lazy('nodisponibilidad_list')

# --- PREFERENCIAS ---

class PreferenciaListView(LoginRequiredMixin, ListView):
    model = Preferencia
    template_name = 'rostering/preferencia_list.html'
    context_object_name = 'preferencias'
    ordering = ['-fecha']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('empleado') # <--- ESTO OPTIMIZA
        self.filterset = PreferenciaFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filterset.form
        return context

class PreferenciaCreateView(LoginRequiredMixin, CreateView):
    model = Preferencia
    form_class = PreferenciaForm
    template_name = 'rostering/preferencia_form.html'
    success_url = reverse_lazy('preferencia_list')
    extra_context = {'titulo': 'Nueva Preferencia'}

class PreferenciaUpdateView(LoginRequiredMixin, UpdateView):
    model = Preferencia
    form_class = PreferenciaForm
    template_name = 'rostering/preferencia_form.html'
    success_url = reverse_lazy('preferencia_list')
    extra_context = {'titulo': 'Editar Preferencia'}

class PreferenciaDeleteView(LoginRequiredMixin, DeleteView):
    model = Preferencia
    template_name = 'rostering/confirm_delete_generic.html'
    success_url = reverse_lazy('preferencia_list')


# --- SECUENCIAS PROHIBIDAS ---

class SecuenciaProhibidaListView(LoginRequiredMixin, ListView):
    model = SecuenciaProhibida
    template_name = 'rostering/secuenciaprohibida_list.html'
    context_object_name = 'secuencias'
    ordering = ['especialidad', 'turno_previo']

    def get_queryset(self):
        # Optimizamos consultas con select_related
        queryset = super().get_queryset().select_related('turno_previo', 'turno_siguiente')
        self.filterset = SecuenciaProhibidaFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filterset.form
        return context

class SecuenciaProhibidaCreateView(LoginRequiredMixin, CreateView):
    model = SecuenciaProhibida
    form_class = SecuenciaProhibidaForm
    template_name = 'rostering/secuenciaprohibida_form.html' # Reusaremos el genérico si querés, o uno específico
    success_url = reverse_lazy('secuencia_list')
    extra_context = {'titulo': 'Nueva Secuencia Prohibida'}

class SecuenciaProhibidaUpdateView(LoginRequiredMixin, UpdateView):
    model = SecuenciaProhibida
    form_class = SecuenciaProhibidaForm
    template_name = 'rostering/secuenciaprohibida_form.html'
    success_url = reverse_lazy('secuencia_list')
    extra_context = {'titulo': 'Editar Regla'}

class SecuenciaProhibidaDeleteView(LoginRequiredMixin, DeleteView):
    model = SecuenciaProhibida
    template_name = 'rostering/confirm_delete_generic.html'
    success_url = reverse_lazy('secuencia_list')

# --- PLANTILLAS (MAESTRO) ---

class PlantillaListView(LoginRequiredMixin, ListView):
    model = PlantillaDemanda
    template_name = 'rostering/plantilla_list.html'
    context_object_name = 'plantillas'

class PlantillaCreateView(LoginRequiredMixin, CreateView):
    model = PlantillaDemanda
    form_class = PlantillaDemandaForm
    template_name = 'rostering/plantilla_form.html'
    success_url = reverse_lazy('plantilla_list')
    extra_context = {'titulo': 'Nueva Plantilla de Demanda'}

class PlantillaDetailView(LoginRequiredMixin, DetailView):
    """ Este es el DASHBOARD de la plantilla """
    model = PlantillaDemanda
    template_name = 'rostering/plantilla_detail.html'
    context_object_name = 'plantilla'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ordenamos reglas: Lunes(0) a Domingo(6)
        context['reglas'] = self.object.reglas.all().order_by('dia', 'turno__hora_inicio')
        context['excepciones'] = self.object.excepciones.all().order_by('fecha')
        return context

class PlantillaDeleteView(LoginRequiredMixin, DeleteView):
    model = PlantillaDemanda
    template_name = 'rostering/confirm_delete_generic.html'
    success_url = reverse_lazy('plantilla_list')

# --- REGLAS (DETALLE) ---

class ReglaCreateView(LoginRequiredMixin, CreateView):
    model = ReglaDemandaSemanal
    form_class = ReglaDemandaSemanalForm
    template_name = 'rostering/regla_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['plantilla_id'] = self.kwargs['plantilla_id']
        return kwargs

    def form_valid(self, form):
        # CORRECCIÓN: Buscamos el objeto y lo asignamos completo
        plantilla = PlantillaDemanda.objects.get(pk=self.kwargs['plantilla_id'])
        form.instance.plantilla = plantilla 
        # Al asignar el objeto 'plantilla' en lugar de solo 'plantilla_id',
        # el método clean() del modelo ya no fallará.
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('plantilla_detail', kwargs={'pk': self.kwargs['plantilla_id']})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plantilla = PlantillaDemanda.objects.get(pk=self.kwargs['plantilla_id'])
        context['titulo'] = f"Agregar Regla a {plantilla.nombre}"
        return context

class ReglaDeleteView(LoginRequiredMixin, DeleteView):
    model = ReglaDemandaSemanal
    template_name = 'rostering/confirm_delete_generic.html'
    
    def get_success_url(self):
        return reverse_lazy('plantilla_detail', kwargs={'pk': self.object.plantilla.id})

# --- EXCEPCIONES (DETALLE) ---

class ExcepcionCreateView(LoginRequiredMixin, CreateView):
    model = ExcepcionDemanda
    form_class = ExcepcionDemandaForm
    template_name = 'rostering/regla_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['plantilla_id'] = self.kwargs['plantilla_id']
        return kwargs

    def form_valid(self, form):
        # CORRECCIÓN: Lo mismo aquí para evitar el error en Excepciones
        plantilla = PlantillaDemanda.objects.get(pk=self.kwargs['plantilla_id'])
        form.instance.plantilla = plantilla
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('plantilla_detail', kwargs={'pk': self.kwargs['plantilla_id']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plantilla = PlantillaDemanda.objects.get(pk=self.kwargs['plantilla_id'])
        context['titulo'] = f"Agregar Excepción a {plantilla.nombre}"
        return context

class ExcepcionDeleteView(LoginRequiredMixin, DeleteView):
    model = ExcepcionDemanda
    template_name = 'rostering/confirm_delete_generic.html'
    
    def get_success_url(self):
        return reverse_lazy('plantilla_detail', kwargs={'pk': self.object.plantilla.id})
    
def api_get_plantillas(request):
    """Retorna JSON con las plantillas filtradas por especialidad"""
    especialidad = request.GET.get('especialidad')
    if not especialidad:
        return JsonResponse({'plantillas': []})
    
    # Filtramos por la especialidad seleccionada
    plantillas = PlantillaDemanda.objects.filter(especialidad=especialidad).values('id', 'nombre')
    return JsonResponse({'plantillas': list(plantillas)})