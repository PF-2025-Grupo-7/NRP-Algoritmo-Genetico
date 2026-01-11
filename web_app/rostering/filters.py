import django_filters
from django import forms
from .models import Empleado, Cronograma, TipoTurno, NoDisponibilidad, Preferencia, SecuenciaProhibida

# ==============================================================================
# WIDGETS COMUNES (Para no repetir attrs)
# ==============================================================================
WIDGET_TEXT = forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Buscar...'})
WIDGET_NUMBER = forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'})
WIDGET_DATE = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
WIDGET_SELECT = forms.Select(attrs={'class': 'form-select'})

# ==============================================================================
# FILTROS DE EMPLEADOS
# ==============================================================================

class EmpleadoFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method='filter_search', 
        label='Buscar',
        widget=WIDGET_TEXT
    )
    
    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        empty_label="Todas las Especialidades",
        widget=WIDGET_SELECT
    )

    experiencia = django_filters.ChoiceFilter(
        choices=Empleado.TipoExperiencia.choices,
        empty_label="Cualquier Experiencia",
        widget=WIDGET_SELECT
    )

    min_turnos = django_filters.NumberFilter(
        field_name='min_turnos_mensuales',
        lookup_expr='gte',
        label='Mínimo de Turnos (>=)',
        widget=WIDGET_NUMBER
    )

    max_turnos = django_filters.NumberFilter(
        field_name='max_turnos_mensuales',
        lookup_expr='lte',
        label='Máximo de Turnos (<=)',
        widget=WIDGET_NUMBER
    )

    activo = django_filters.BooleanFilter(
        widget=WIDGET_SELECT
    )

    class Meta:
        model = Empleado
        fields = ['especialidad', 'experiencia', 'min_turnos', 'max_turnos', 'activo']

    def filter_search(self, queryset, name, value):
        return queryset.filter(nombre_completo__icontains=value) | queryset.filter(legajo__icontains=value)


# ==============================================================================
# FILTROS DE CRONOGRAMAS
# ==============================================================================

class CronogramaFilter(django_filters.FilterSet):
    fecha_desde = django_filters.DateFilter(
        field_name='fecha_inicio', 
        lookup_expr='gte',
        label='Desde',
        widget=WIDGET_DATE
    )
    fecha_hasta = django_filters.DateFilter(
        field_name='fecha_inicio', 
        lookup_expr='lte',
        label='Hasta',
        widget=WIDGET_DATE
    )
    
    estado = django_filters.ChoiceFilter(
        choices=[
            ('PUBLICADO', 'Publicado'),
            ('BORRADOR', 'Borrador'),
        ], 
        empty_label="Todos los Estados",
        widget=WIDGET_SELECT
    )

    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        empty_label="Todas las Especialidades",
        widget=WIDGET_SELECT
    )

    class Meta:
        model = Cronograma
        fields = ['especialidad', 'estado', 'fecha_desde', 'fecha_hasta']


# ==============================================================================
# FILTROS DE NOVEDADES Y PREFERENCIAS
# ==============================================================================

class NoDisponibilidadFilter(django_filters.FilterSet):
    empleado = django_filters.CharFilter(
        field_name='empleado__nombre_completo', 
        lookup_expr='icontains', 
        label='Empleado',
        widget=WIDGET_TEXT
    )
    fecha = django_filters.DateFilter(
        field_name='fecha_inicio', 
        lookup_expr='gte', 
        label='A partir de (Fecha)', 
        widget=WIDGET_DATE
    )
    especialidad = django_filters.ChoiceFilter(
        field_name='empleado__especialidad',
        choices=Empleado.TipoEspecialidad.choices,
        label='Especialidad',
        widget=WIDGET_SELECT
    )

    class Meta:
        model = NoDisponibilidad
        fields = ['empleado', 'fecha', 'especialidad']


class PreferenciaFilter(django_filters.FilterSet):
    empleado = django_filters.CharFilter(
        field_name='empleado__nombre_completo', 
        lookup_expr='icontains', 
        label='Empleado',
        widget=WIDGET_TEXT
    )
    fecha = django_filters.DateFilter(
        field_name='fecha', 
        label='Fecha exacta', 
        widget=WIDGET_DATE
    )
    deseo = django_filters.ChoiceFilter(
        choices=Preferencia.Deseo.choices, 
        widget=WIDGET_SELECT
    )
    especialidad = django_filters.ChoiceFilter(
        field_name='empleado__especialidad',
        choices=Empleado.TipoEspecialidad.choices,
        label='Especialidad',
        widget=WIDGET_SELECT
    )

    class Meta:
        model = Preferencia
        fields = ['empleado', 'fecha', 'deseo', 'especialidad']


# ==============================================================================
# FILTROS DE CONFIGURACIÓN
# ==============================================================================

class TipoTurnoFilter(django_filters.FilterSet):
    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        empty_label="Todas",
        widget=WIDGET_SELECT
    )

    class Meta:
        model = TipoTurno
        fields = ['especialidad']


class SecuenciaProhibidaFilter(django_filters.FilterSet):
    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        widget=WIDGET_SELECT,
        empty_label="Todas las Especialidades"
    )

    class Meta:
        model = SecuenciaProhibida
        fields = ['especialidad']