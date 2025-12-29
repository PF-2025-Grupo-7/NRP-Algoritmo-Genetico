import django_filters
from django import forms
from .models import Empleado

class EmpleadoFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method='filter_search', 
        label='Buscar',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre o Legajo'})
    )
    
    # Campo correcto: especialidad (antes era 'tipo')
    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        empty_label="Todas las Especialidades",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Campo correcto: experiencia
    experiencia = django_filters.ChoiceFilter(
        choices=Empleado.TipoExperiencia.choices,
        empty_label="Cualquier Experiencia",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    activo = django_filters.BooleanFilter(
        widget=forms.Select(attrs={'class': 'form-select'}, choices=[(None, 'Todos'), (True, 'Activo'), (False, 'Inactivo')])
    )

    class Meta:
        model = Empleado
        fields = ['especialidad', 'experiencia', 'activo']

    def filter_search(self, queryset, name, value):
        # CORREGIDO: nombre_completo en vez de nombre
        return queryset.filter(nombre_completo__icontains=value) | queryset.filter(legajo__icontains=value)