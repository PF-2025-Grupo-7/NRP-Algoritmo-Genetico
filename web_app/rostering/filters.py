import django_filters
from django import forms
from .models import Empleado, Cronograma, TipoTurno, NoDisponibilidad, Preferencia, SecuenciaProhibida

# ==============================================================================
# WIDGETS COMUNES (Para no repetir attrs)
# ==============================================================================
WIDGET_TEXT = forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Buscar...'})
WIDGET_NUMBER = forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'})
WIDGET_DATE = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
WIDGET_SELECT = forms.Select(attrs={'class': 'form-select', 'required': False})

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
        required=False,
        widget=WIDGET_SELECT
    )

    experiencia = django_filters.ChoiceFilter(
        choices=Empleado.TipoExperiencia.choices,
        empty_label="Todas las Experiencias",
        required=False,
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

    activo = django_filters.ChoiceFilter(
        choices=[
            ('', 'Todos los Estados'),
            ('1', 'Activo'),
            ('0', 'Inactivo'),
        ],
        empty_label="Todos los Estados",
        required=False,
        method='filter_activo',
        widget=WIDGET_SELECT
    )

    class Meta:
        model = Empleado
        fields = ['especialidad', 'experiencia', 'min_turnos', 'max_turnos', 'activo']

    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(nombre_completo__icontains=value) | queryset.filter(legajo__icontains=value)
        return queryset
    
    def filter_activo(self, queryset, name, value):
        if value == '1':
            return queryset.filter(activo=True)
        elif value == '0':
            return queryset.filter(activo=False)
        return queryset


# ==============================================================================
# FILTROS DE CRONOGRAMAS
# ==============================================================================

class CronogramaFilter(django_filters.FilterSet):
    fecha_desde = django_filters.DateFilter(
        label='Fecha inicio (período dentro de planificado)',
        method='filter_periodo',
        widget=WIDGET_DATE
    )
    fecha_hasta = django_filters.DateFilter(
        label='Fecha fin (período dentro de planificado)',
        method='filter_periodo',
        widget=WIDGET_DATE
    )
    
    estado = django_filters.ChoiceFilter(
        choices=[
            ('PUBLICADO', 'Publicado'),
            ('BORRADOR', 'Borrador'),
        ], 
        empty_label="Todos los Estados",
        required=False,
        widget=WIDGET_SELECT
    )

    especialidad = django_filters.ChoiceFilter(
        choices=Empleado.TipoEspecialidad.choices,
        empty_label="Todas las Especialidades",
        required=False,
        widget=WIDGET_SELECT
    )

    class Meta:
        model = Cronograma
        fields = ['especialidad', 'estado', 'fecha_desde', 'fecha_hasta']

    def filter_periodo(self, queryset, name, value):
        """Filtra cronogramas cuyo período planificado incluya el período buscado.

        Reglas:
        - Si ambos `fecha_desde` y `fecha_hasta` están presentes en los datos de filtro,
          devolvemos cronogramas donde fecha_inicio <= fecha_desde AND fecha_fin >= fecha_hasta.
        - Si solo se pasa `fecha_desde`, devolvemos cronogramas donde fecha_inicio <= fecha_desde <= fecha_fin.
        - Si solo se pasa `fecha_hasta`, devolvemos cronogramas donde fecha_inicio <= fecha_hasta <= fecha_fin.
        """
        # Acceder a los valores crudos de los filtros
        data = self.data
        fdesde = data.get('fecha_desde')
        fhasta = data.get('fecha_hasta')

        # Si ambos vienen y no están vacíos
        if fdesde and fhasta:
            return queryset.filter(fecha_inicio__lte=fdesde, fecha_fin__gte=fhasta)

        # Solo fecha_desde
        if fdesde:
            return queryset.filter(fecha_inicio__lte=fdesde, fecha_fin__gte=fdesde)

        # Solo fecha_hasta
        if fhasta:
            return queryset.filter(fecha_inicio__lte=fhasta, fecha_fin__gte=fhasta)

        return queryset


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
        label='Fecha (incluida en período)',
        method='filter_fecha',
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

    def filter_fecha(self, queryset, name, value):
        """Filtra ausencias cuyo período [fecha_inicio, fecha_fin] incluya la fecha dada."""
        if not value:
            return queryset
        return queryset.filter(fecha_inicio__lte=value, fecha_fin__gte=value)


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