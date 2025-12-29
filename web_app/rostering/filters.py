import django_filters
from django import forms
from .models import Empleado, TipoTurno  # <--- SIN 'Servicio'

class EmpleadoFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method='filter_search', 
        label='Buscar',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre o Legajo'})
    )
    
    # Asumiendo que 'tipo' es un choice field en tu modelo
    tipo = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices, # Ajusta esto si tu campo se llama diferente
        empty_label="Todas las Especialidades",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Si 'experiencia' es un campo choice en tu modelo Empleado:
    # experiencia = django_filters.ChoiceFilter( ... ) 
    # Si no estás seguro de que existe 'experiencia', comentalo por ahora.

    activo = django_filters.BooleanFilter(
        widget=forms.Select(attrs={'class': 'form-select'}, choices=[(None, 'Todos'), (True, 'Activo'), (False, 'Inactivo')])
    )

    class Meta:
        model = Empleado
        fields = ['tipo', 'activo'] # Agrega 'experiencia' aquí solo si existe

    def filter_search(self, queryset, name, value):
        return queryset.filter(nombre__icontains=value) | queryset.filter(legajo__icontains=value)