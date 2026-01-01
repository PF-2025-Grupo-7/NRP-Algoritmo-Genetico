import django_filters
from django import forms
from .models import Empleado, Cronograma, TipoTurno, NoDisponibilidad, Preferencia, SecuenciaProhibida

class EmpleadoFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method='filter_search', 
        label='Buscar',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre o Legajo'})
    )
    
    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        empty_label="Todas las Especialidades",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    experiencia = django_filters.ChoiceFilter(
        choices=Empleado.TipoExperiencia.choices,
        empty_label="Cualquier Experiencia",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    min_turnos = django_filters.NumberFilter(
        field_name='min_turnos_mensuales',
        lookup_expr='gte',
        label='Mínimo de Turnos (>=)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 4'})
    )

    max_turnos = django_filters.NumberFilter(
        field_name='max_turnos_mensuales',
        lookup_expr='lte',
        label='Máximo de Turnos (<=)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 20'})
    )

    activo = django_filters.BooleanFilter(
        widget=forms.Select(attrs={'class': 'form-select'}, choices=[(None, 'Todos'), (True, 'Activo'), (False, 'Inactivo')])
    )

    class Meta:
        model = Empleado
        fields = ['especialidad', 'experiencia', 'min_turnos', 'max_turnos', 'activo']

    def filter_search(self, queryset, name, value):
        return queryset.filter(nombre_completo__icontains=value) | queryset.filter(legajo__icontains=value)

class CronogramaFilter(django_filters.FilterSet):
    # Rango de Fechas (Desde - Hasta)
    fecha_desde = django_filters.DateFilter(
        field_name='fecha_inicio', 
        lookup_expr='gte',  # Greater than or equal (>=)
        label='Desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    fecha_hasta = django_filters.DateFilter(
        field_name='fecha_inicio', 
        lookup_expr='lte',  # Less than or equal (<=)
        label='Hasta',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    # Filtro de Estado
    estado = django_filters.ChoiceFilter(
        choices=Cronograma.Estado.choices, 
        empty_label="Todos los Estados",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Filtro de Especialidad
    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        empty_label="Todas las Especialidades",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Cronograma
        fields = ['especialidad', 'estado', 'fecha_desde', 'fecha_hasta']

class NoDisponibilidadFilter(django_filters.FilterSet):
    empleado = django_filters.CharFilter(field_name='empleado__nombre_completo', lookup_expr='icontains', label='Empleado')
    fecha = django_filters.DateFilter(field_name='fecha_inicio', lookup_expr='gte', label='A partir de (Fecha)', widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    especialidad = django_filters.ChoiceFilter(
        field_name='empleado__especialidad',
        choices=Empleado.TipoEspecialidad.choices,
        label='Especialidad',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = NoDisponibilidad
        fields = ['empleado', 'fecha']

class PreferenciaFilter(django_filters.FilterSet):
    empleado = django_filters.CharFilter(field_name='empleado__nombre_completo', lookup_expr='icontains', label='Empleado')
    fecha = django_filters.DateFilter(field_name='fecha', label='Fecha exacta', widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    deseo = django_filters.ChoiceFilter(choices=Preferencia.Deseo.choices, widget=forms.Select(attrs={'class': 'form-select'}))
    especialidad = django_filters.ChoiceFilter(
        field_name='empleado__especialidad',
        choices=Empleado.TipoEspecialidad.choices,
        label='Especialidad',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Preferencia
        fields = ['empleado', 'fecha', 'deseo']
    
class TipoTurnoFilter(django_filters.FilterSet):
    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        empty_label="Todas",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = TipoTurno
        fields = ['especialidad']

class SecuenciaProhibidaFilter(django_filters.FilterSet):
    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Todas las Especialidades"
    )

    class Meta:
        model = SecuenciaProhibida
        fields = ['especialidad']