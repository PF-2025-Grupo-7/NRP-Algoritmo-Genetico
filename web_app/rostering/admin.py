from django.contrib import admin
from .models import (
    Empleado, TipoTurno, PlantillaDemanda, ReglaDemandaSemanal, 
    ExcepcionDemanda, NoDisponibilidad, Preferencia, 
    Cronograma, Asignacion, ConfiguracionAlgoritmo, SecuenciaProhibida
)

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('legajo', 'nombre_completo', 'especialidad', 'experiencia', 'activo')
    list_filter = ('especialidad', 'experiencia', 'activo')
    search_fields = ('nombre_completo', 'legajo')

@admin.register(TipoTurno)
class TipoTurnoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura', 'especialidad', 'es_nocturno', 'hora_inicio', 'hora_fin', 'duracion_horas')
    list_filter = ('especialidad', 'es_nocturno')

class ReglaDemandaInline(admin.TabularInline):
    model = ReglaDemandaSemanal
    extra = 0

class ExcepcionDemandaInline(admin.TabularInline):
    model = ExcepcionDemanda
    extra = 0

@admin.register(PlantillaDemanda)
class PlantillaDemandaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'especialidad')
    list_filter = ('especialidad',)
    inlines = [ReglaDemandaInline, ExcepcionDemandaInline]

@admin.register(NoDisponibilidad)
class NoDisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin', 'tipo_turno', 'motivo')
    list_filter = ('fecha_inicio', 'empleado__especialidad')
    search_fields = ('empleado__nombre_completo',)

@admin.register(Preferencia)
class PreferenciaAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha', 'tipo_turno', 'deseo')
    list_filter = ('deseo', 'fecha')

@admin.register(Cronograma)
class CronogramaAdmin(admin.ModelAdmin):
    # CORREGIDO: Cambiamos mes/anio por fechas
    list_display = ('especialidad', 'fecha_inicio', 'fecha_fin', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'especialidad', 'fecha_inicio')
    readonly_fields = ('fecha_creacion',)

@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ('cronograma', 'fecha', 'empleado', 'tipo_turno')
    list_filter = ('cronograma', 'tipo_turno')

# --- NUEVOS MODELOS REGISTRADOS ---

@admin.register(ConfiguracionAlgoritmo)
class ConfiguracionAlgoritmoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activa', 'tamano_poblacion', 'generaciones')
    list_filter = ('activa',)
    fieldsets = (
        ('Estado', {
            'fields': ('nombre', 'activa')
        }),
        ('Parámetros Técnicos (AG)', {
            'fields': (
                ('tamano_poblacion', 'generaciones'),
                ('prob_cruce', 'prob_mutacion'),
                ('elitismo', 'semilla'),
                'estrategia_seleccion', 'estrategia_cruce', 'estrategia_mutacion'
            )
        }),
        ('Pesos de Negocio', {
            'fields': (
                ('peso_equidad_general', 'peso_equidad_dificil'),
                ('peso_preferencia_dias_libres', 'peso_preferencia_turno'),
                'factor_alpha_pte',
                ('tolerancia_general', 'tolerancia_dificil')
            )
        }),
    )

@admin.register(SecuenciaProhibida)
class SecuenciaProhibidaAdmin(admin.ModelAdmin):
    list_display = ('especialidad', 'turno_previo', 'turno_siguiente')
    list_filter = ('especialidad',)