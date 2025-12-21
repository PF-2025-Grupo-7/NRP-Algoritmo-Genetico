from django.contrib import admin
from .models import Empleado, NoDisponibilidad, TipoTurno, RequerimientoTurno, Preferencia, Cronograma, Asignacion

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('legajo', 'nombre_completo', 'especialidad', 'experiencia')
    list_filter = ('especialidad', 'experiencia')
    search_fields = ('nombre_completo', 'legajo')

@admin.register(TipoTurno)
class TipoTurnoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura', 'hora_inicio', 'hora_fin', 'duracion_horas')

@admin.register(RequerimientoTurno)
class RequerimientoTurnoAdmin(admin.ModelAdmin):
    list_display = ('dia_semana', 'tipo_turno', 'cantidad_minima_senior', 'cantidad_minima_junior')
    list_filter = ('dia_semana', 'tipo_turno')

@admin.register(NoDisponibilidad)
class NoDisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin', 'tipo_turno', 'motivo')
    list_filter = ('fecha_inicio', 'tipo_turno')
    search_fields = ('empleado__nombre_completo', 'motivo')

@admin.register(Preferencia)
class PreferenciaAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha', 'tipo_turno', 'nivel')
    list_filter = ('tipo_turno', 'nivel', 'fecha')

@admin.register(Cronograma)
class CronogramaAdmin(admin.ModelAdmin):
    list_display = ('especialidad', 'mes', 'anio', 'estado', 'fecha_creacion')
    list_filter = ('especialidad', 'estado', 'anio')

@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    list_display = ('cronograma', 'empleado', 'fecha', 'tipo_turno')
    list_filter = ('fecha', 'tipo_turno', 'cronograma')