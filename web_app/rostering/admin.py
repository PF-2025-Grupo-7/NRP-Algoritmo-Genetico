from django.contrib import admin
from django.db.models import Sum
from .models import (
    Empleado, TipoTurno, PlantillaDemanda, ReglaDemandaSemanal,
    ExcepcionDemanda, NoDisponibilidad, Preferencia, 
    ConfiguracionAlgoritmo, SecuenciaProhibida,
    Cronograma, Asignacion, TrabajoPlanificacion
)

# --- EMPLEADOS ---
@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('legajo', 'nombre_completo', 'especialidad', 'experiencia', 'min_turnos_mensuales', 'max_turnos_mensuales', 'activo')
    list_filter = ('especialidad', 'experiencia', 'activo')
    search_fields = ('nombre_completo', 'legajo')
    
    fieldsets = (
        ('Datos Personales', {
            'fields': ('legajo', 'nombre_completo', 'activo')
        }),
        ('Perfil Profesional', {
            'fields': ('especialidad', 'experiencia')
        }),
        ('Restricciones Contractuales (Turnos/Slots)', {
            'fields': ('min_turnos_mensuales', 'max_turnos_mensuales'),
            'description': 'Defina la cantidad de turnos (slots) permitidos. El sistema multiplicará estos valores por la duración del turno para reportes.'
        }),
    )

# --- TURNOS ---
@admin.register(TipoTurno)
class TipoTurnoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura', 'especialidad', 'hora_inicio', 'hora_fin', 'duracion_horas', 'es_nocturno')
    list_filter = ('especialidad', 'es_nocturno')
    readonly_fields = ('duracion_horas',) # Se calcula solo

# --- DEMANDA (PLANTILLAS Y REGLAS) ---
class ReglaInline(admin.TabularInline):
    model = ReglaDemandaSemanal
    extra = 0
    # Ordenamos solo por turno ya que dias es ahora un JSONField
    ordering = ('turno',)
    readonly_fields = ('get_dias_display',)
    
    def get_dias_display(self, obj):
        """Muestra los días seleccionados en formato legible."""
        if obj and obj.pk:
            return obj.get_dias_display()
        return "-"
    get_dias_display.short_description = "Días"

class ExcepcionInline(admin.TabularInline):
    model = ExcepcionDemanda
    extra = 0
    classes = ('collapse',)

@admin.register(PlantillaDemanda)
class PlantillaDemandaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'especialidad', 'conteo_reglas')
    list_filter = ('especialidad',)
    inlines = [ReglaInline, ExcepcionInline]

    def conteo_reglas(self, obj):
        return obj.reglas.count()
    conteo_reglas.short_description = "# Reglas Semanales"

# --- CONFIGURACIÓN ---
@admin.register(ConfiguracionAlgoritmo)
class ConfiguracionAlgoritmoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activa', 'tamano_poblacion', 'generaciones', 'estrategia_cruce')
    list_editable = ('activa',)
    
    fieldsets = (
        ('General', {
            'fields': ('nombre', 'activa')
        }),
        ('Parámetros Técnicos (Algoritmo Genético)', {
            'fields': (
                ('tamano_poblacion', 'generaciones'),
                ('prob_cruce', 'prob_mutacion'),
                ('elitismo', 'semilla'),
                'estrategia_seleccion', 'estrategia_cruce', 'estrategia_mutacion'
            )
        }),
        ('Pesos de Negocio (Función Fitness)', {
            'fields': (
                ('peso_equidad_general', 'peso_equidad_dificil'),
                ('peso_preferencia_dias_libres', 'peso_preferencia_turno'),
                'factor_alpha_pte'
            ),
            'description': 'Ajuste la importancia relativa de cada objetivo (valores mayores = mayor prioridad).'
        }),
        ('Tolerancias', {
            'fields': ('tolerancia_general', 'tolerancia_dificil'),
            'description': 'Umbrales de desviación permitida antes de penalizar fuertemente.'
        }),
    )

# --- RESTRICCIONES Y PREFERENCIAS ---
@admin.register(SecuenciaProhibida)
class SecuenciaProhibidaAdmin(admin.ModelAdmin):
    list_display = ('especialidad', 'turno_previo', 'turno_siguiente')
    list_filter = ('especialidad',)

@admin.register(NoDisponibilidad)
class NoDisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin', 'tipo_turno', 'motivo')
    list_filter = ('fecha_inicio', 'empleado__especialidad')
    search_fields = ('empleado__nombre_completo',)

@admin.register(Preferencia)
class PreferenciaAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha', 'deseo', 'tipo_turno', 'comentario')
    list_filter = ('fecha', 'deseo')

# --- RESULTADOS (CRONOGRAMAS) ---
class AsignacionInline(admin.TabularInline):
    model = Asignacion
    extra = 0
    #readonly_fields = ('empleado', 'fecha', 'tipo_turno')
    #can_delete = False

    def get_queryset(self, request):
        # Optimización: Cargar relaciones para no matar la DB
        qs = super().get_queryset(request)
        return qs.select_related('empleado', 'tipo_turno')

@admin.register(Cronograma)
class CronogramaAdmin(admin.ModelAdmin):
    list_display = ('id', 'especialidad', 'fecha_inicio', 'fecha_fin', 'estado', 'fitness', 'fecha_creacion')
    list_filter = ('estado', 'especialidad', 'fecha_creacion')
    date_hierarchy = 'fecha_inicio'
    readonly_fields = ('fecha_creacion', 'fitness', 'tiempo_ejecucion', 'reporte_analisis')
    
    inlines = [AsignacionInline]

# --- UTILIDADES INTERNAS ---
@admin.register(TrabajoPlanificacion)
class TrabajoPlanificacionAdmin(admin.ModelAdmin):
    list_display = ('job_id', 'especialidad', 'fecha_inicio', 'fecha_creacion')
    readonly_fields = ('job_id', 'fecha_creacion', 'payload_original')
    
    def has_add_permission(self, request):
        return False # Solo lectura/borrado, esto lo crea el sistema