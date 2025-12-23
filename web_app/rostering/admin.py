from django.contrib import admin
from .models import (
    Empleado, 
    TipoTurno, 
    Preferencia, 
    Cronograma, 
    Asignacion, 
    NoDisponibilidad,
    PlantillaDemanda, 
    ReglaDemandaSemanal, 
    ExcepcionDemanda
)
from .models import ConfiguracionAlgoritmo, SecuenciaProhibida

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('legajo', 'nombre_completo', 'especialidad', 'experiencia', 'min_horas_mensuales', 'max_horas_mensuales')
    list_filter = ('especialidad', 'experiencia')
    search_fields = ('nombre_completo', 'legajo')

@admin.register(TipoTurno)
class TipoTurnoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura', 'hora_inicio', 'hora_fin', 'duracion_horas')


class ReglaSemanalInline(admin.TabularInline):
    model = ReglaDemandaSemanal
    extra = 0
    min_num = 1
    ordering = ('dia', 'turno')
    fields = ('dia', 'turno', 'cantidad_senior', 'cantidad_junior')

@admin.register(ExcepcionDemanda)
class ExcepcionDemandaAdmin(admin.ModelAdmin):
    # Agregamos las columnas nuevas a la lista
    list_display = ('fecha', 'turno', 'cantidad_senior', 'cantidad_junior', 'motivo')
    list_filter = ('turno', 'fecha')
    date_hierarchy = 'fecha'

@admin.register(PlantillaDemanda)
class PlantillaDemandaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    inlines = [ReglaSemanalInline]  # <--- Esto conecta la tabla de días con la plantilla


@admin.register(NoDisponibilidad)
class NoDisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin', 'tipo_turno', 'motivo')
    list_filter = ('fecha_inicio', 'tipo_turno')
    search_fields = ('empleado__nombre_completo', 'motivo')

@admin.register(Preferencia)
class PreferenciaAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha', 'tipo_turno', 'deseo')
    list_filter = ('tipo_turno', 'deseo', 'fecha')

@admin.register(Cronograma)
class CronogramaAdmin(admin.ModelAdmin):
    list_display = ('especialidad', 'mes', 'anio', 'estado', 'plantilla_demanda','fecha_creacion')
    list_filter = ('especialidad', 'estado', 'anio')

@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ('cronograma', 'empleado', 'fecha', 'tipo_turno')
    list_filter = ('fecha', 'tipo_turno', 'cronograma')

@admin.register(ConfiguracionAlgoritmo)
class ConfiguracionAlgoritmoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activa', 'peso_equidad_general', 'tolerancia_general')
    list_filter = ('activa',)
    
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'activa')
        }),
        ('Ponderación de Objetivos (Fitness Weights)', {
            'description': 'Ajuste la importancia relativa de cada restricción blanda.',
            'fields': (
                ('peso_equidad_general', 'peso_equidad_dificil'),
                ('peso_preferencia_dias_libres', 'peso_preferencia_turno'),
                'factor_alpha_pte'
            ),
        }),
        ('Umbrales de Tolerancia', {
            'description': 'Márgenes permitidos antes de considerar una distribución como injusta.',
            'fields': (
                ('tolerancia_general', 'tolerancia_dificil'),
            ),
        }),
    )

    def has_add_permission(self, request):
        if self.model.objects.exists():
             return False
        return super().has_add_permission(request)

@admin.register(SecuenciaProhibida)
class SecuenciaProhibidaAdmin(admin.ModelAdmin):
    list_display = ('especialidad', 'turno_previo', 'turno_siguiente')
    list_filter = ('especialidad',)
    ordering = ('especialidad', 'turno_previo')