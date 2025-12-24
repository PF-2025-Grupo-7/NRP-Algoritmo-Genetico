from django.contrib import admin
from .models import (
    Empleado, TipoTurno, PlantillaDemanda, ReglaDemandaSemanal,
    ExcepcionDemanda, NoDisponibilidad, Preferencia, 
    ConfiguracionAlgoritmo, SecuenciaProhibida, 
    Cronograma, Asignacion
)

# --- 1. CONFIGURACIÓN DE EMPLEADOS ---
@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('legajo', 'nombre_completo', 'especialidad', 'experiencia', 'activo')
    list_filter = ('especialidad', 'experiencia', 'activo')
    search_fields = ('nombre_completo', 'legajo') # Necesario para el autocompletado en otros paneles

# --- 2. CONFIGURACIÓN DE TURNOS Y REGLAS ---
@admin.register(TipoTurno)
class TipoTurnoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'abreviatura', 'especialidad', 'hora_inicio', 'hora_fin', 'es_nocturno')
    list_filter = ('especialidad', 'es_nocturno')
    search_fields = ('nombre', 'abreviatura')

class ReglaInline(admin.TabularInline):
    model = ReglaDemandaSemanal
    extra = 0
    ordering = ('dia',)

class ExcepcionInline(admin.TabularInline):
    model = ExcepcionDemanda
    extra = 0
    ordering = ('fecha',)

@admin.register(PlantillaDemanda)
class PlantillaDemandaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'especialidad')
    inlines = [ReglaInline, ExcepcionInline]

# --- 3. CONFIGURACIÓN DE PREFERENCIAS Y AUSENCIAS ---
@admin.register(NoDisponibilidad)
class NoDisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha_inicio', 'fecha_fin', 'tipo_turno')
    list_filter = ('empleado__especialidad', 'tipo_turno')
    search_fields = ('empleado__nombre_completo',)

@admin.register(Preferencia)
class PreferenciaAdmin(admin.ModelAdmin):
    list_display = ('empleado', 'fecha', 'deseo', 'tipo_turno')
    list_filter = ('deseo', 'fecha')

# --- 4. CONFIGURACIÓN DEL CRONOGRAMA (LO QUE PEDISTE) ---

# Esta clase define la tabla de asignaciones DENTRO del cronograma
class AsignacionInline(admin.TabularInline):
    model = Asignacion
    extra = 0 # No mostrar filas vacías extra
    
    # Optimizaciones de rendimiento (Crucial si tienes muchos turnos)
    # Usamos raw_id_fields o autocomplete_fields para que no cargue un dropdown con 1000 empleados
    autocomplete_fields = ['empleado', 'tipo_turno'] 
    
    # Hacemos que sea de solo lectura si el cronograma ya está publicado (opcional, pero buena práctica)
    # readonly_fields = ('fecha', 'empleado', 'tipo_turno') 
    
    # Paginación dentro del inline (Django 4.0+)
    show_change_link = True # Permite ir a editar la asignación en detalle

@admin.register(Cronograma)
class CronogramaAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'especialidad', 'estado', 'fecha_creacion', 'ver_asignaciones_link')
    list_filter = ('estado', 'especialidad', 'fecha_inicio')
    inlines = [AsignacionInline]
    search_fields = ('id', 'especialidad', 'estado')

    # --- DISEÑO VISUAL ---
    fieldsets = (
        ('Gestión', {
            'fields': ('estado', 'ver_asignaciones_link_readonly')
        }),
        ('Metadatos (Inmutables tras creación)', {
            'fields': ('especialidad', 'fecha_inicio', 'fecha_fin', 'plantilla_demanda', 'configuracion_usada'),
            'classes': ('collapse',), # Opcional: permite colapsar esta sección
            'description': 'Estos parámetros definieron la optimización y no deben cambiarse a posteriori.'
        }),
    )

    # Creamos un campo de solo lectura para mostrar el link dentro del formulario también
    readonly_fields = ('ver_asignaciones_link_readonly', 'fecha_creacion')

    def ver_asignaciones_link(self, obj):
        # Este es para la LISTA (columnas)
        from django.utils.html import format_html
        from django.urls import reverse
        url = reverse('admin:rostering_asignacion_changelist') + f'?cronograma__id__exact={obj.id}'
        return format_html('<a class="button" href="{}" style="padding: 2px 8px;">Gestionar Turnos</a>', url)
    
    ver_asignaciones_link.short_description = "Acciones"

    def ver_asignaciones_link_readonly(self, obj):
        # Este es para el FORMULARIO (dentro de la edición)
        from django.utils.html import format_html
        from django.urls import reverse
        if obj.id:
            url = reverse('admin:rostering_asignacion_changelist') + f'?cronograma__id__exact={obj.id}'
            return format_html('<a class="button" href="{}" target="_blank">🔍 Ver/Filtrar Asignaciones de este plan</a>', url)
        return "-"
    ver_asignaciones_link_readonly.short_description = "Detalle de Asignaciones"

    # --- LÓGICA DE PROTECCIÓN DE DATOS ---
    def get_readonly_fields(self, request, obj=None):
        """
        Si el objeto ya existe (obj is not None), bloqueamos los campos estructurales.
        """
        if obj: 
            # Modo EDICIÓN: Bloquear inputs críticos
            return self.readonly_fields + (
                'especialidad', 
                'fecha_inicio', 
                'fecha_fin', 
                'plantilla_demanda', 
                'configuracion_usada'
            )
        # Modo CREACIÓN: Permitir todo
        return self.readonly_fields


@admin.register(Asignacion)
class AsignacionAdmin(admin.ModelAdmin):
    """
    Panel individual de Asignaciones. 
    Es útil para filtrar cosas como: "¿Qué turnos hace Juan Pérez en Noviembre?"
    sin tener que entrar al cronograma entero.
    """
    list_display = ('fecha', 'empleado', 'tipo_turno', 'cronograma')
    list_filter = (
        'cronograma',          # Filtrar por qué plan es
        'tipo_turno',          # Filtrar mañanas/tardes
        'empleado__especialidad', 
        'fecha',               # Filtrar por día específico
        'empleado'             # Filtrar por persona
    )
    search_fields = ('empleado__nombre_completo', 'fecha')
    autocomplete_fields = ['empleado', 'tipo_turno', 'cronograma']

# --- 5. EXTRAS ---

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