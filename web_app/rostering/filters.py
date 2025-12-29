import django_filters
from django import forms
from .models import Empleado

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

    # --- NUEVOS FILTROS NUMÉRICOS ---
    min_turnos = django_filters.NumberFilter(
        field_name='min_turnos_mensuales',
        lookup_expr='gte', # Mayor o igual que
        label='Mínimo de Turnos (>=)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 4'})
    )

    max_turnos = django_filters.NumberFilter(
        field_name='max_turnos_mensuales',
        lookup_expr='lte', # Menor o igual que
        label='Máximo de Turnos (<=)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 20'})
    )
    # -------------------------------

    activo = django_filters.BooleanFilter(
        widget=forms.Select(attrs={'class': 'form-select'}, choices=[(None, 'Todos'), (True, 'Activo'), (False, 'Inactivo')])
    )

    class Meta:
        model = Empleado
        fields = ['especialidad', 'experiencia', 'min_turnos', 'max_turnos', 'activo']

    def filter_search(self, queryset, name, value):
        return queryset.filter(nombre_completo__icontains=value) | queryset.filter(legajo__icontains=value)