import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
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

# --- SERVICIOS (Lógica de Negocio) ---
from .services import (
    iniciar_proceso_optimizacion, # <--- Nueva función orquestadora
    consultar_resultado_ag, 
    guardar_solucion_db,
    invocar_api_planificacion,
    construir_matriz_cronograma   # <--- Nueva función de presentación
)


# ==============================================================================
# VISTAS GENERALES Y DE GESTIÓN
# ==============================================================================

def dashboard(request):
    """Vista principal: KPIs, accesos rápidos y estado actual del sistema."""
    total_empleados = Empleado.objects.count()
    borradores_pendientes = Cronograma.objects.filter(estado=Cronograma.Estado.BORRADOR).count()
    ultimo_cronograma = Cronograma.objects.order_by('-fecha_creacion').first()
    recientes = Cronograma.objects.all().order_by('-fecha_creacion')[:5]

    hoy = timezone.now().date()
    if hoy.month == 12:
        prox_mes, prox_anio = 1, hoy.year + 1
    else:
        prox_mes, prox_anio = hoy.month + 1, hoy.year
    
    existe_proximo = Cronograma.objects.filter(fecha_inicio__month=prox_mes, fecha_inicio__year=prox_anio).exists()
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
            login(request, user)
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
    Endpoint AJAX: Recibe JSON, delega la lógica al servicio y devuelve estado.
    Ahora es una vista muy limpia (Skinny View).
    """
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido.'}, status=400)
        
        # Delegamos TODA la lógica pesada al servicio
        job_id = iniciar_proceso_optimizacion(data)

        return JsonResponse({
            'status': 'started',
            'job_id': job_id,
            'mensaje': 'Optimización iniciada correctamente.'
        })

    except (ValidationError, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=400)
    except ConnectionError as e:
        return JsonResponse({'error': str(e)}, status=503)
    except Exception as e:
        print(f"Error 500: {e}")
        return JsonResponse({'error': f"Error interno: {str(e)}"}, status=500)


@csrf_exempt
@require_GET
def verificar_estado_planificacion(request, job_id):
    """
    Polling: El frontend consulta esto periódicamente.
    """
    try:
        try:
            trabajo = TrabajoPlanificacion.objects.get(job_id=job_id)
        except TrabajoPlanificacion.DoesNotExist:
            return JsonResponse({'error': 'Job ID no encontrado o expirado.'}, status=404)

        resultado = consultar_resultado_ag(job_id)
        
        if not resultado:
            return JsonResponse({'status': 'error', 'mensaje': 'Error de conexión'}, status=503)

        if resultado.get('status') == 'error':
             return JsonResponse({'status': 'failed', 'error': resultado.get('error')})

        # Si terminó, persistimos
        if 'fitness' in resultado or resultado.get('status') == 'completed':
            try:
                cronograma = guardar_solucion_db(
                    fecha_inicio=trabajo.fecha_inicio, 
                    fecha_fin=trabajo.fecha_fin, 
                    especialidad=trabajo.especialidad, 
                    payload_original=trabajo.payload_original, 
                    resultado=resultado,
                    plantilla_demanda=trabajo.plantilla_demanda
                )
                trabajo.delete() # Limpieza

                return JsonResponse({
                    'status': 'completed',
                    'cronograma_id': cronograma.id,
                    'fitness': resultado.get('fitness'),
                    'mensaje': 'Planificación guardada con éxito.'
                })
            except Exception as e:
                print(f"Error guardando DB: {e}")
                return JsonResponse({'error': f"Error guardando: {str(e)}"}, status=500)

        return JsonResponse({'status': 'running'})

    except Exception as e:
        print(f"Error polling: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def api_get_plantillas(request):
    especialidad = request.GET.get('especialidad')
    if not especialidad: return JsonResponse({'plantillas': []})
    plantillas = PlantillaDemanda.objects.filter(especialidad=especialidad).values('id', 'nombre')
    return JsonResponse({'plantillas': list(plantillas)})


# ==============================================================================
# VISUALIZACIÓN DE CRONOGRAMAS
# ==============================================================================

@login_required
def ver_cronograma(request, cronograma_id):
    """
    Vista Detallada (Matriz): Ahora solo pide los datos procesados al servicio.
    """
    cronograma = get_object_or_404(Cronograma, pk=cronograma_id)
    
    # Delegamos la construcción de la matriz al servicio
    context_data = construir_matriz_cronograma(cronograma)
    
    return render(request, 'rostering/cronograma_detail.html', {
        'cronograma': cronograma,
        **context_data # Expande 'rango_fechas' y 'filas_tabla'
    })


def ver_cronograma_diario(request, cronograma_id):
    """Vista Diaria: Muestra quién trabaja en qué turno para cada día."""
    cronograma = get_object_or_404(Cronograma, pk=cronograma_id)
    
    asignaciones = Asignacion.objects.filter(cronograma=cronograma).select_related(
        'empleado', 'tipo_turno'
    ).order_by('fecha', 'tipo_turno__hora_inicio')

    agenda = {}
    for asig in asignaciones:
        if asig.fecha not in agenda: agenda[asig.fecha] = {}
        t_nom = asig.tipo_turno.nombre
        if t_nom not in agenda[asig.fecha]: agenda[asig.fecha][t_nom] = []
        agenda[asig.fecha][t_nom].append(asig.empleado)

    return render(request, 'rostering/cronograma_diario.html', {'cronograma': cronograma, 'agenda': agenda})


class CronogramaAnalisisView(LoginRequiredMixin, DetailView):
    model = Cronograma
    template_name = 'rostering/cronograma_analisis.html'
    context_object_name = 'cronograma'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reporte = self.object.reporte_analisis or {}
        context['metricas'] = reporte.get('metricas', {})
        context['violaciones_duras'] = reporte.get('violaciones_duras', {})
        context['violaciones_blandas'] = reporte.get('violaciones_blandas', {})
        context['equidad'] = reporte.get('datos_equidad', {})
        return context


@login_required
@require_POST
def publicar_cronograma(request, pk):
    cronograma = get_object_or_404(Cronograma, pk=pk)
    if cronograma.estado == Cronograma.Estado.PUBLICADO:
        messages.warning(request, "Este cronograma ya está publicado.")
    else:
        cronograma.estado = Cronograma.Estado.PUBLICADO
        cronograma.save()
        messages.success(request, f"¡Planificación {cronograma.fecha_inicio} PUBLICADA!")
    return redirect('ver_cronograma', cronograma_id=pk)


# ==============================================================================
# ABM (CRUDs) - SIN CAMBIOS IMPORTANTES (Ya usan CBVs estándar)
# ==============================================================================

class EmpleadoListView(LoginRequiredMixin, ListView):
    model = Empleado
    template_name = 'rostering/empleado_list.html'
    context_object_name = 'empleados'
    paginate_by = 15 

    def get_queryset(self):
        qs = super().get_queryset()
        self.filterset = EmpleadoFilter(self.request.GET, queryset=qs)
        qs = self.filterset.qs
        order = self.request.GET.get('order_by')
        if order and order.lstrip('-') in ['legajo', 'nombre_completo', 'especialidad', 'experiencia', 'activo']:
            qs = qs.order_by(order)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filterset.form
        ctx['current_order'] = self.request.GET.get('order_by', '')
        return ctx

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

# --- Cronogramas ---
class CronogramaListView(LoginRequiredMixin, ListView):
    model = Cronograma
    template_name = 'rostering/cronograma_list.html'
    context_object_name = 'cronogramas'
    ordering = ['-fecha_inicio', '-fecha_creacion'] 
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        self.filterset = CronogramaFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filterset.form
        return ctx

class CronogramaDeleteView(LoginRequiredMixin, DeleteView):
    model = Cronograma
    template_name = 'rostering/cronograma_confirm_delete.html'
    success_url = reverse_lazy('cronograma_list')

# --- Tipos de Turno ---
class TipoTurnoListView(LoginRequiredMixin, ListView):
    model = TipoTurno
    template_name = 'rostering/tipoturno_list.html'
    context_object_name = 'turnos'
    ordering = ['especialidad', 'hora_inicio']

    def get_queryset(self):
        qs = super().get_queryset()
        self.filterset = TipoTurnoFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filterset.form
        return ctx

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

# --- Ausencias ---
class NoDisponibilidadListView(LoginRequiredMixin, ListView):
    model = NoDisponibilidad
    template_name = 'rostering/nodisponibilidad_list.html'
    context_object_name = 'ausencias'
    ordering = ['-fecha_inicio']
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().select_related('empleado')
        self.filterset = NoDisponibilidadFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filterset.form
        return ctx

class NoDisponibilidadCreateView(LoginRequiredMixin, CreateView):
    model = NoDisponibilidad
    form_class = NoDisponibilidadForm
    template_name = 'rostering/nodisponibilidad_form.html'
    success_url = reverse_lazy('nodisponibilidad_list')
    extra_context = {'titulo': 'Registrar Ausencia'}

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

# --- Preferencias ---
class PreferenciaListView(LoginRequiredMixin, ListView):
    model = Preferencia
    template_name = 'rostering/preferencia_list.html'
    context_object_name = 'preferencias'
    ordering = ['-fecha']
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().select_related('empleado')
        self.filterset = PreferenciaFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filterset.form
        return ctx

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

# --- Secuencias Prohibidas ---
class SecuenciaProhibidaListView(LoginRequiredMixin, ListView):
    model = SecuenciaProhibida
    template_name = 'rostering/secuenciaprohibida_list.html'
    context_object_name = 'secuencias'
    ordering = ['especialidad', 'turno_previo']

    def get_queryset(self):
        qs = super().get_queryset().select_related('turno_previo', 'turno_siguiente')
        self.filterset = SecuenciaProhibidaFilter(self.request.GET, queryset=qs)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = self.filterset.form
        return ctx

class SecuenciaProhibidaCreateView(LoginRequiredMixin, CreateView):
    model = SecuenciaProhibida
    form_class = SecuenciaProhibidaForm
    template_name = 'rostering/secuenciaprohibida_form.html'
    success_url = reverse_lazy('secuencia_list')
    extra_context = {'titulo': 'Nueva Secuencia'}

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

# --- Plantillas ---
class PlantillaListView(LoginRequiredMixin, ListView):
    model = PlantillaDemanda
    template_name = 'rostering/plantilla_list.html'
    context_object_name = 'plantillas'

class PlantillaCreateView(LoginRequiredMixin, CreateView):
    model = PlantillaDemanda
    form_class = PlantillaDemandaForm
    template_name = 'rostering/plantilla_form.html'
    success_url = reverse_lazy('plantilla_list')
    extra_context = {'titulo': 'Nueva Plantilla'}

class PlantillaDetailView(LoginRequiredMixin, DetailView):
    model = PlantillaDemanda
    template_name = 'rostering/plantilla_detail.html'
    context_object_name = 'plantilla'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['reglas'] = self.object.reglas.all().order_by('dia', 'turno__hora_inicio')
        ctx['excepciones'] = self.object.excepciones.all().order_by('fecha')
        return ctx

class PlantillaDeleteView(LoginRequiredMixin, DeleteView):
    model = PlantillaDemanda
    template_name = 'rostering/confirm_delete_generic.html'
    success_url = reverse_lazy('plantilla_list')

class ReglaCreateView(LoginRequiredMixin, CreateView):
    model = ReglaDemandaSemanal
    form_class = ReglaDemandaSemanalForm
    template_name = 'rostering/regla_form.html'

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['plantilla_id'] = self.kwargs['plantilla_id']
        return kw

    def form_valid(self, form):
        form.instance.plantilla = PlantillaDemanda.objects.get(pk=self.kwargs['plantilla_id'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('plantilla_detail', kwargs={'pk': self.kwargs['plantilla_id']})
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = PlantillaDemanda.objects.get(pk=self.kwargs['plantilla_id'])
        ctx['titulo'] = f"Agregar Regla a {p.nombre}"
        return ctx

class ReglaDeleteView(LoginRequiredMixin, DeleteView):
    model = ReglaDemandaSemanal
    template_name = 'rostering/confirm_delete_generic.html'
    def get_success_url(self):
        return reverse_lazy('plantilla_detail', kwargs={'pk': self.object.plantilla.id})

class ExcepcionCreateView(LoginRequiredMixin, CreateView):
    model = ExcepcionDemanda
    form_class = ExcepcionDemandaForm
    template_name = 'rostering/regla_form.html'

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['plantilla_id'] = self.kwargs['plantilla_id']
        return kw

    def form_valid(self, form):
        form.instance.plantilla = PlantillaDemanda.objects.get(pk=self.kwargs['plantilla_id'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('plantilla_detail', kwargs={'pk': self.kwargs['plantilla_id']})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = PlantillaDemanda.objects.get(pk=self.kwargs['plantilla_id'])
        ctx['titulo'] = f"Agregar Excepción a {p.nombre}"
        return ctx

class ExcepcionDeleteView(LoginRequiredMixin, DeleteView):
    model = ExcepcionDemanda
    template_name = 'rostering/confirm_delete_generic.html'
    def get_success_url(self):
        return reverse_lazy('plantilla_detail', kwargs={'pk': self.object.plantilla.id})

# --- Configuración ---
class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self): return self.request.user.is_superuser

def get_config_activa():
    config, _ = ConfiguracionAlgoritmo.objects.get_or_create(activa=True)
    return config

class ConfiguracionDashboardView(SuperUserRequiredMixin, TemplateView):
    template_name = 'rostering/config_dashboard.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['config'] = get_config_activa()
        return ctx

class ConfiguracionSimpleView(SuperUserRequiredMixin, FormView):
    template_name = 'rostering/config_simple.html'
    form_class = ConfiguracionSimpleForm
    success_url = reverse_lazy('config_dashboard')

    def form_valid(self, form):
        form.save(get_config_activa())
        messages.success(self.request, f"¡Configuración actualizada a modo {form.cleaned_data['modo']}!")
        return super().form_valid(form)

class ConfiguracionAvanzadaView(SuperUserRequiredMixin, UpdateView):
    model = ConfiguracionAlgoritmo
    form_class = ConfiguracionAvanzadaForm
    template_name = 'rostering/config_avanzada.html'
    success_url = reverse_lazy('config_dashboard')

    def get_object(self):
        return get_config_activa()

    def form_valid(self, form):
        messages.success(self.request, "Parámetros avanzados guardados.")
        return super().form_valid(form)