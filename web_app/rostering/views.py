import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.core.exceptions import ValidationError
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, 
    DetailView, TemplateView, FormView
)

# --- MODELOS ---
from .models import (
    Empleado, Cronograma, TipoTurno, NoDisponibilidad, 
    Preferencia, SecuenciaProhibida, Asignacion,
    PlantillaDemanda, ReglaDemandaSemanal, ExcepcionDemanda,
    TrabajoPlanificacion, ConfiguracionAlgoritmo
)

# --- FORMS ---
from .forms import (
    EmpleadoForm, TipoTurnoForm, NoDisponibilidadForm, 
    PreferenciaForm, SecuenciaProhibidaForm,
    PlantillaDemandaForm, ReglaDemandaSemanalForm, ExcepcionDemandaForm,
    ConfiguracionSimpleForm, ConfiguracionAvanzadaForm
)

# --- FILTROS ---
from .filters import (
    EmpleadoFilter, CronogramaFilter, NoDisponibilidadFilter, 
    PreferenciaFilter, TipoTurnoFilter, SecuenciaProhibidaFilter
)

# --- SERVICIOS ---
from .services import (
    generar_payload_ag, 
    invocar_api_planificacion, 
    consultar_resultado_ag, 
    guardar_solucion_db
)


# ==============================================================================
# VISTAS GENERALES Y DE GESTIÓN
# ==============================================================================

def dashboard(request):
    """
    Vista principal: KPIs, accesos rápidos y estado actual del sistema.
    """
    total_empleados = Empleado.objects.count()
    borradores_pendientes = Cronograma.objects.filter(estado=Cronograma.Estado.BORRADOR).count()
    
    # Obtenemos el último generado y los recientes
    ultimo_cronograma = Cronograma.objects.order_by('-fecha_creacion').first()
    recientes = Cronograma.objects.all().order_by('-fecha_creacion')[:5]

    # Lógica para sugerir el próximo mes a planificar
    hoy = timezone.now().date()
    if hoy.month == 12:
        prox_mes, prox_anio = 1, hoy.year + 1
    else:
        prox_mes, prox_anio = hoy.month + 1, hoy.year
    
    existe_proximo = Cronograma.objects.filter(
        fecha_inicio__month=prox_mes, 
        fecha_inicio__year=prox_anio
    ).exists()

    nombre_mes_objetivo = f"{prox_mes:02d}/{prox_anio}"

    context = {
        'total_empleados': total_empleados,
        'borradores': borradores_pendientes,
        'ultimo': ultimo_cronograma,
        'recientes': recientes,
        'existe_proximo': existe_proximo,
        'mes_objetivo': nombre_mes_objetivo,
    }
    return render(request, 'rostering/dashboard.html', context)


def registrar_usuario(request):
    """Permite el registro de nuevos usuarios en el sistema."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Logueo automático tras registro
            messages.success(request, "¡Registro exitoso! Bienvenido.")
            return redirect('dashboard')
        else:
            messages.error(request, "Por favor corrige los errores abajo.")
    else:
        form = UserCreationForm()
        
    return render(request, 'registration/register.html', {'form': form})


# ==============================================================================
# MOTOR DE PLANIFICACIÓN (API ORCHESTRATION)
# ==============================================================================

@login_required
def pagina_generador(request):
    """Renderiza la pantalla para configurar y lanzar una nueva planificación."""
    return render(request, 'rostering/generador.html')


@csrf_exempt 
@login_required
@require_POST
def iniciar_planificacion(request):
    """
    Endpoint AJAX: Recibe parámetros, valida, genera payload y llama a la API de optimización.
    """
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido en el cuerpo de la petición.'}, status=400)
        
        fecha_inicio_str = data.get('fecha_inicio')
        fecha_fin_str = data.get('fecha_fin')
        especialidad = data.get('especialidad')
        plantilla_id = data.get('plantilla_id')

        # Validaciones básicas
        if not all([fecha_inicio_str, fecha_fin_str, especialidad, plantilla_id]):
            return JsonResponse({'error': 'Faltan parámetros obligatorios.'}, status=400)

        inicio = parse_date(fecha_inicio_str)
        fin = parse_date(fecha_fin_str)
        
        if not inicio or not fin:
            return JsonResponse({'error': 'Formato de fecha inválido. Usar YYYY-MM-DD.'}, status=400)

        # 1. Generar el Payload (Lógica de negocio en services.py)
        payload = generar_payload_ag(inicio, fin, especialidad)

        # 2. Invocar a la API Python
        respuesta_api = invocar_api_planificacion(payload)

        if not respuesta_api or 'job_id' not in respuesta_api:
            msg = 'No se pudo iniciar el trabajo en el motor de IA.'
            if respuesta_api and 'detail' in respuesta_api:
                msg += f" Detalle: {respuesta_api['detail']}"
            return JsonResponse({'error': msg}, status=503)

        job_id = respuesta_api['job_id']

        # 3. Guardar contexto para recuperarlo cuando termine el algoritmo
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

    except ValidationError as ve:
        return JsonResponse({'error': f"Error de validación: {ve.message}"}, status=400)
    except ValueError as ve:
        return JsonResponse({'error': str(ve)}, status=400)
    except Exception as e:
        print(f"Error 500 en iniciar_planificacion: {e}")
        return JsonResponse({'error': f"Error interno del servidor: {str(e)}"}, status=500)


@csrf_exempt
@require_GET
def verificar_estado_planificacion(request, job_id):
    """
    Polling: El frontend consulta esto periódicamente para ver si el AG terminó.
    Si terminó, guarda los resultados en la DB.
    """
    try:
        try:
            trabajo = TrabajoPlanificacion.objects.get(job_id=job_id)
        except TrabajoPlanificacion.DoesNotExist:
            return JsonResponse({'error': 'Job ID no encontrado o expirado.'}, status=404)

        # 1. Consultar a la API
        resultado = consultar_resultado_ag(job_id)
        
        if not resultado:
            return JsonResponse({'status': 'error', 'mensaje': 'Error de conexión con la API'}, status=503)

        if 'status' in resultado and resultado['status'] == 'error':
             return JsonResponse({'status': 'failed', 'error': resultado.get('error', 'Error desconocido en el motor.')})

        # 2. Verificar si terminó
        if 'fitness' in resultado or resultado.get('status') == 'completed':
            try:
                # Guardar solución en Base de Datos
                cronograma = guardar_solucion_db(
                    fecha_inicio=trabajo.fecha_inicio, 
                    fecha_fin=trabajo.fecha_fin, 
                    especialidad=trabajo.especialidad, 
                    payload_original=trabajo.payload_original, 
                    resultado=resultado,
                    plantilla_demanda=trabajo.plantilla_demanda
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

        # 3. Sigue corriendo
        return JsonResponse({'status': 'running'})

    except Exception as e:
        print(f"Error polling: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def api_get_plantillas(request):
    """Retorna JSON con las plantillas filtradas por especialidad para el select del frontend."""
    especialidad = request.GET.get('especialidad')
    if not especialidad:
        return JsonResponse({'plantillas': []})
    
    plantillas = PlantillaDemanda.objects.filter(especialidad=especialidad).values('id', 'nombre')
    return JsonResponse({'plantillas': list(plantillas)})


# ==============================================================================
# VISUALIZACIÓN DE CRONOGRAMAS
# ==============================================================================

@login_required
def ver_cronograma(request, cronograma_id):
    """
    Vista Detallada (Matriz): Muestra la tabla Empleados vs Fechas.
    """
    cronograma = get_object_or_404(Cronograma, pk=cronograma_id)
    
    # 1. Generar encabezados de columnas (Fechas)
    rango_fechas = []
    fecha_iter = cronograma.fecha_inicio
    while fecha_iter <= cronograma.fecha_fin:
        rango_fechas.append(fecha_iter)
        fecha_iter += timedelta(days=1)
        
    # 2. Obtener todas las asignaciones (Eager loading para optimizar)
    asignaciones = Asignacion.objects.filter(
        cronograma=cronograma
    ).select_related('empleado', 'tipo_turno')
    
    # 3. Construir Matriz rápida: dict[empleado_id][fecha_str] = turno
    matriz_asignaciones = {}
    for asig in asignaciones:
        emp_id = asig.empleado.id
        fecha_str = asig.fecha.strftime("%Y-%m-%d")
        
        if emp_id not in matriz_asignaciones:
            matriz_asignaciones[emp_id] = {}
        
        matriz_asignaciones[emp_id][fecha_str] = asig.tipo_turno

    # 4. Obtener lista de empleados ordenada
    empleados = Empleado.objects.filter(
        especialidad=cronograma.especialidad, 
        activo=True
    ).order_by('experiencia', 'legajo')

    # 5. Construir estructura para el template
    filas_tabla = []
    for emp in empleados:
        celdas = []
        horas_totales = 0
        turnos_totales = 0
        
        for fecha in rango_fechas:
            fecha_key = fecha.strftime("%Y-%m-%d")
            turno = matriz_asignaciones.get(emp.id, {}).get(fecha_key)
            
            celdas.append({
                'fecha': fecha,
                'turno': turno, # Puede ser None
            })
            
            if turno:
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
    """
    Vista Diaria: Muestra quién trabaja en qué turno para cada día.
    """
    cronograma = get_object_or_404(Cronograma, pk=cronograma_id)
    
    asignaciones = Asignacion.objects.filter(cronograma=cronograma).select_related(
        'empleado', 'tipo_turno'
    ).order_by('fecha', 'tipo_turno__hora_inicio')

    # Estructura: agenda[fecha] = { 'Mañana': [Emp1], 'Tarde': [Emp2] }
    agenda = {}
    
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


class CronogramaAnalisisView(LoginRequiredMixin, DetailView):
    """
    Muestra las estadísticas detalladas, métricas y violaciones de restricciones del cronograma.
    """
    model = Cronograma
    template_name = 'rostering/cronograma_analisis.html'
    context_object_name = 'cronograma'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Deserializamos el JSON de reporte
        reporte = self.object.reporte_analisis or {}
        
        context['metricas'] = reporte.get('metricas', {})
        context['violaciones_duras'] = reporte.get('violaciones_duras', {})
        context['violaciones_blandas'] = reporte.get('violaciones_blandas', {})
        context['equidad'] = reporte.get('datos_equidad', {})
        
        return context


@login_required
@require_POST
def publicar_cronograma(request, pk):
    """Cambia el estado del cronograma de Borrador a Publicado."""
    cronograma = get_object_or_404(Cronograma, pk=pk)
    
    if cronograma.estado == Cronograma.Estado.PUBLICADO:
        messages.warning(request, "Este cronograma ya está publicado.")
    else:
        cronograma.estado = Cronograma.Estado.PUBLICADO
        cronograma.save()
        messages.success(request, f"¡La planificación {cronograma.fecha_inicio} ha sido PUBLICADA exitosamente!")
    
    return redirect('ver_cronograma', cronograma_id=pk)


# ==============================================================================
# ABM: EMPLEADOS
# ==============================================================================

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
    template_name = 'rostering/empleado_form.html'
    success_url = reverse_lazy('empleado_list')
    extra_context = {'titulo': 'Editar Empleado'}

class EmpleadoDeleteView(LoginRequiredMixin, DeleteView):
    model = Empleado
    template_name = 'rostering/empleado_confirm_delete.html'
    success_url = reverse_lazy('empleado_list')


# ==============================================================================
# ABM: CRONOGRAMAS
# ==============================================================================

class CronogramaListView(LoginRequiredMixin, ListView):
    model = Cronograma
    template_name = 'rostering/cronograma_list.html'
    context_object_name = 'cronogramas'
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

class CronogramaDeleteView(LoginRequiredMixin, DeleteView):
    model = Cronograma
    template_name = 'rostering/cronograma_confirm_delete.html'
    success_url = reverse_lazy('cronograma_list')


# ==============================================================================
# ABM: TIPOS DE TURNO
# ==============================================================================

class TipoTurnoListView(LoginRequiredMixin, ListView):
    model = TipoTurno
    template_name = 'rostering/tipoturno_list.html'
    context_object_name = 'turnos'
    ordering = ['especialidad', 'hora_inicio']

    def get_queryset(self):
        queryset = super().get_queryset()
        self.filterset = TipoTurnoFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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


# ==============================================================================
# ABM: AUSENCIAS (NO DISPONIBILIDAD)
# ==============================================================================

class NoDisponibilidadListView(LoginRequiredMixin, ListView):
    model = NoDisponibilidad
    template_name = 'rostering/nodisponibilidad_list.html'
    context_object_name = 'ausencias'
    ordering = ['-fecha_inicio']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('empleado')
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
    template_name = 'rostering/confirm_delete_generic.html'
    success_url = reverse_lazy('nodisponibilidad_list')


# ==============================================================================
# ABM: PREFERENCIAS
# ==============================================================================

class PreferenciaListView(LoginRequiredMixin, ListView):
    model = Preferencia
    template_name = 'rostering/preferencia_list.html'
    context_object_name = 'preferencias'
    ordering = ['-fecha']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('empleado')
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


# ==============================================================================
# ABM: SECUENCIAS PROHIBIDAS
# ==============================================================================

class SecuenciaProhibidaListView(LoginRequiredMixin, ListView):
    model = SecuenciaProhibida
    template_name = 'rostering/secuenciaprohibida_list.html'
    context_object_name = 'secuencias'
    ordering = ['especialidad', 'turno_previo']

    def get_queryset(self):
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
    template_name = 'rostering/secuenciaprohibida_form.html'
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


# ==============================================================================
# GESTIÓN DE PLANTILLAS Y REGLAS (Master-Detail)
# ==============================================================================

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
    """ Este es el DASHBOARD de la plantilla: muestra reglas semanales y excepciones."""
    model = PlantillaDemanda
    template_name = 'rostering/plantilla_detail.html'
    context_object_name = 'plantilla'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reglas'] = self.object.reglas.all().order_by('dia', 'turno__hora_inicio')
        context['excepciones'] = self.object.excepciones.all().order_by('fecha')
        return context

class PlantillaDeleteView(LoginRequiredMixin, DeleteView):
    model = PlantillaDemanda
    template_name = 'rostering/confirm_delete_generic.html'
    success_url = reverse_lazy('plantilla_list')


# --- REGLAS SEMANALES ---

class ReglaCreateView(LoginRequiredMixin, CreateView):
    model = ReglaDemandaSemanal
    form_class = ReglaDemandaSemanalForm
    template_name = 'rostering/regla_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['plantilla_id'] = self.kwargs['plantilla_id']
        return kwargs

    def form_valid(self, form):
        plantilla = PlantillaDemanda.objects.get(pk=self.kwargs['plantilla_id'])
        form.instance.plantilla = plantilla 
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


# --- EXCEPCIONES DE DEMANDA ---

class ExcepcionCreateView(LoginRequiredMixin, CreateView):
    model = ExcepcionDemanda
    form_class = ExcepcionDemandaForm
    template_name = 'rostering/regla_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['plantilla_id'] = self.kwargs['plantilla_id']
        return kwargs

    def form_valid(self, form):
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


# ==============================================================================
# CONFIGURACIÓN DEL SISTEMA
# ==============================================================================

class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

def get_config_activa():
    """Helper para obtener o crear la config activa"""
    config, created = ConfiguracionAlgoritmo.objects.get_or_create(activa=True)
    return config

class ConfiguracionDashboardView(SuperUserRequiredMixin, TemplateView):
    template_name = 'rostering/config_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['config'] = get_config_activa()
        return context

class ConfiguracionSimpleView(SuperUserRequiredMixin, FormView):
    template_name = 'rostering/config_simple.html'
    form_class = ConfiguracionSimpleForm
    success_url = reverse_lazy('config_dashboard')

    def form_valid(self, form):
        config = get_config_activa()
        form.save(config)
        messages.success(self.request, f"¡Configuración actualizada a modo {form.cleaned_data['modo']}!")
        return super().form_valid(form)

class ConfiguracionAvanzadaView(SuperUserRequiredMixin, UpdateView):
    model = ConfiguracionAlgoritmo
    form_class = ConfiguracionAvanzadaForm
    template_name = 'rostering/config_avanzada.html'
    success_url = reverse_lazy('config_dashboard')

    def get_object(self):
        # Forzamos la edición de la activa, ignorando el PK de la URL
        return get_config_activa()

    def form_valid(self, form):
        messages.success(self.request, "Parámetros avanzados guardados correctamente.")
        return super().form_valid(form)