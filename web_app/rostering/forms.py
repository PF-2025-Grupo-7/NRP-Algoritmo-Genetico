from django import forms
from django.core.exceptions import ValidationError
from .models import (
    ConfiguracionAlgoritmo, ConfiguracionTurnos, Empleado, TipoTurno, NoDisponibilidad, 
    Preferencia, SecuenciaProhibida, PlantillaDemanda, 
    ReglaDemandaSemanal, ExcepcionDemanda
)

# ==============================================================================
# WIDGETS Y MIXINS COMUNES
# ==============================================================================

# Definimos widgets estándar para reutilizar y mantener consistencia visual
DATE_INPUT = forms.DateInput(attrs={'type': 'date'})
TIME_INPUT = forms.TimeInput(attrs={'type': 'time'})
SELECT_WIDGET = forms.Select(attrs={'class': 'form-select'})
TEXTAREA_WIDGET = forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})

class BootstrapFormMixin:
    """Mixin para aplicar estilos de Bootstrap 5 a todos los campos automáticamente."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            # Preservar clases existentes si las hubiera
            clase_actual = field.widget.attrs.get('class', '')
            
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = f'{clase_actual} form-check-input'.strip()
            elif isinstance(field.widget, forms.RadioSelect):
                # Los radios suelen manejarse distinto, pero lo dejamos genérico por ahora
                pass
            else:
                field.widget.attrs['class'] = f'{clase_actual} form-control'.strip()

# ==============================================================================
# FORMULARIOS DE CATÁLOGOS BASE
# ==============================================================================

class EmpleadoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Empleado
        fields = '__all__'

# Borrá o comentá la clase TipoTurnoForm vieja

class ConfiguracionTurnosForm(BootstrapFormMixin, forms.ModelForm):
    # Campos virtuales para definir nombres y abreviaturas (No guardados directamente en este modelo)
    nombre_t1 = forms.CharField(label="Nombre Turno 1", initial="Mañana")
    abrev_t1 = forms.CharField(label="Abrev. T1", max_length=5, initial="M")
    nocturno_t1 = forms.BooleanField(label="Es Nocturno", required=False)

    nombre_t2 = forms.CharField(label="Nombre Turno 2", initial="Noche")
    abrev_t2 = forms.CharField(label="Abrev. T2", max_length=5, initial="N")
    nocturno_t2 = forms.BooleanField(label="Es Nocturno", required=False)

    # Opcionales para esquema de 3 turnos
    nombre_t3 = forms.CharField(label="Nombre Turno 3", required=False, initial="Tarde")
    abrev_t3 = forms.CharField(label="Abrev. T3", max_length=5, required=False, initial="T")
    nocturno_t3 = forms.BooleanField(label="Es Nocturno", required=False)

    class Meta:
        model = ConfiguracionTurnos
        fields = ['esquema', 'hora_inicio_base']
        widgets = {
            'esquema': SELECT_WIDGET,
            'hora_inicio_base': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        esquema = cleaned_data.get('esquema')

        # Validación condicional
        if esquema == ConfiguracionTurnos.TipoEsquema.TURNO_08_HS:
            if not cleaned_data.get('nombre_t3') or not cleaned_data.get('abrev_t3'):
                self.add_error('nombre_t3', 'Requerido para esquema de 3 turnos.')
                self.add_error('abrev_t3', 'Requerido.')
        
        return cleaned_data

class NoDisponibilidadForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = NoDisponibilidad
        fields = '__all__'
        widgets = {
            'fecha_inicio': DATE_INPUT,
            'fecha_fin': DATE_INPUT,
            'empleado': SELECT_WIDGET,
            'tipo_turno': SELECT_WIDGET,
        }

class PreferenciaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Preferencia
        fields = '__all__'
        widgets = {
            'fecha': DATE_INPUT,
            'empleado': SELECT_WIDGET,
            'tipo_turno': SELECT_WIDGET,
            'deseo': SELECT_WIDGET,
            'comentario': TEXTAREA_WIDGET
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class SecuenciaProhibidaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SecuenciaProhibida
        fields = '__all__'
        widgets = {
            'especialidad': SELECT_WIDGET,
            'turno_previo': SELECT_WIDGET,
            'turno_siguiente': SELECT_WIDGET,
        }
        help_texts = {
            'turno_previo': 'El turno que termina el día anterior.',
            'turno_siguiente': 'El turno que NO puede comenzar el día siguiente.',
        }

# ==============================================================================
# FORMULARIOS DE GESTIÓN DE DEMANDA (PLANTILLAS)
# ==============================================================================

class PlantillaDemandaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PlantillaDemanda
        fields = '__all__'
        widgets = {
            'especialidad': SELECT_WIDGET,
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }

class PlantillaDemandaUpdateForm(forms.ModelForm):
    class Meta:
        model = PlantillaDemanda
        fields = ['nombre', 'especialidad', 'descripcion']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bloqueamos el campo especialidad para que sea de solo lectura
        # Usamos 'disabled' para que el usuario lo vea grisado y no pueda tocarlo
        if 'especialidad' in self.fields:
            self.fields['especialidad'].disabled = True
            self.fields['especialidad'].help_text = "La especialidad no se puede modificar una vez creada la plantilla."

class ReglaDemandaSemanalForm(BootstrapFormMixin, forms.ModelForm):
    # Creamos campos individuales para cada día de la semana
    dia_lunes = forms.BooleanField(required=False, label='Lunes')
    dia_martes = forms.BooleanField(required=False, label='Martes')
    dia_miercoles = forms.BooleanField(required=False, label='Miércoles')
    dia_jueves = forms.BooleanField(required=False, label='Jueves')
    dia_viernes = forms.BooleanField(required=False, label='Viernes')
    dia_sabado = forms.BooleanField(required=False, label='Sábado')
    dia_domingo = forms.BooleanField(required=False, label='Domingo')
    
    class Meta:
        model = ReglaDemandaSemanal
        fields = ['turno', 'cantidad_senior', 'cantidad_junior']
        widgets = {
            'turno': SELECT_WIDGET,
        }

    def __init__(self, *args, **kwargs):
        """Filtra los turnos disponibles según la especialidad de la plantilla padre."""
        plantilla_id = kwargs.pop('plantilla_id', None)
        super().__init__(*args, **kwargs)
        
        if plantilla_id:
            try:
                plantilla = PlantillaDemanda.objects.get(id=plantilla_id)
                self.fields['turno'].queryset = TipoTurno.objects.filter(especialidad=plantilla.especialidad)
            except PlantillaDemanda.DoesNotExist:
                pass
        
        # Si estamos editando, marcar los días seleccionados
        if self.instance and self.instance.pk:
            dias_seleccionados = self.instance.dias or []
            if 0 in dias_seleccionados:
                self.fields['dia_lunes'].initial = True
            if 1 in dias_seleccionados:
                self.fields['dia_martes'].initial = True
            if 2 in dias_seleccionados:
                self.fields['dia_miercoles'].initial = True
            if 3 in dias_seleccionados:
                self.fields['dia_jueves'].initial = True
            if 4 in dias_seleccionados:
                self.fields['dia_viernes'].initial = True
            if 5 in dias_seleccionados:
                self.fields['dia_sabado'].initial = True
            if 6 in dias_seleccionados:
                self.fields['dia_domingo'].initial = True
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Construir la lista de días seleccionados
        dias_seleccionados = []
        if cleaned_data.get('dia_lunes'):
            dias_seleccionados.append(0)
        if cleaned_data.get('dia_martes'):
            dias_seleccionados.append(1)
        if cleaned_data.get('dia_miercoles'):
            dias_seleccionados.append(2)
        if cleaned_data.get('dia_jueves'):
            dias_seleccionados.append(3)
        if cleaned_data.get('dia_viernes'):
            dias_seleccionados.append(4)
        if cleaned_data.get('dia_sabado'):
            dias_seleccionados.append(5)
        if cleaned_data.get('dia_domingo'):
            dias_seleccionados.append(6)
        
        # Validar que se haya seleccionado al menos un día
        if not dias_seleccionados:
            raise ValidationError("Debe seleccionar al menos un día de la semana.")
        
        cleaned_data['dias'] = dias_seleccionados
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.dias = self.cleaned_data['dias']
        if commit:
            instance.save()
        return instance

class ExcepcionDemandaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExcepcionDemanda
        # Agregamos 'es_turno_dificil' a la lista de campos
        fields = ['fecha', 'turno', 'cantidad_senior', 'cantidad_junior', 'es_turno_dificil', 'motivo']
        widgets = {
            'fecha': DATE_INPUT,
            'turno': SELECT_WIDGET,
            # Checkbox estilizado (opcional, el mixin ya le pone form-check-input)
            'es_turno_dificil': forms.CheckboxInput(attrs={'class': 'form-check-input ms-2'}),
        }

    def __init__(self, *args, **kwargs):
        """Filtra los turnos disponibles según la especialidad de la plantilla padre."""
        plantilla_id = kwargs.pop('plantilla_id', None)
        super().__init__(*args, **kwargs)
        
        if plantilla_id:
            try:
                plantilla = PlantillaDemanda.objects.get(id=plantilla_id)
                self.fields['turno'].queryset = TipoTurno.objects.filter(especialidad=plantilla.especialidad)
            except PlantillaDemanda.DoesNotExist:
                pass
            
# ==============================================================================
# FORMULARIOS DE CONFIGURACIÓN DEL MOTOR
# ==============================================================================

class ConfiguracionSimpleForm(forms.Form):
    TIPO_BUSQUEDA = [
        ('RAPIDA', '⚡ Búsqueda Rápida (Borrador)'),
        ('EQUILIBRADA', '⚖️ Búsqueda Equilibrada (Recomendada)'),
        ('PROFUNDA', '🧠 Búsqueda Profunda (Alta Calidad)'),
        ('PERSONALIZADA', '🎯 Búsqueda Personalizada (Expertos)'),
    ]

    modo = forms.ChoiceField(
        choices=TIPO_BUSQUEDA, 
        widget=forms.RadioSelect(attrs={'class': 'btn-check'}),
        label="Seleccione el tipo de optimización"
    )

    def save(self, config_instance):
        """Aplica presets (patrón Facade) sobre la configuración compleja."""
        modo = self.cleaned_data['modo']
        
        presets = {
            'RAPIDA': {'pop': 100, 'gen': 75, 'pm': 0.3, 'nombre': "Configuración Rápida"},
            'EQUILIBRADA': {'pop': 100, 'gen': 150, 'pm': 0.2, 'nombre': "Configuración Equilibrada"},
            'PROFUNDA': {'pop': 150, 'gen': 250, 'pm': 0.15, 'nombre': "Configuración Profunda"},
        }
        
        if modo in presets:
            p = presets[modo]
            config_instance.tamano_poblacion = p['pop']
            config_instance.generaciones = p['gen']
            config_instance.prob_mutacion = p['pm']
            config_instance.nombre = p['nombre']
            config_instance.save()
        elif modo == 'PERSONALIZADA':
            # Para personalizada, solo asegurarse de que el nombre esté correcto
            config_instance.nombre = "Búsqueda Personalizada"
            config_instance.save()

class ConfiguracionAvanzadaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracionAlgoritmo
        fields = '__all__'
        exclude = ['activa'] # No permitimos desactivarla desde aquí
        widgets = {
            'estrategia_seleccion': SELECT_WIDGET,
            'estrategia_cruce': SELECT_WIDGET,
            'estrategia_mutacion': SELECT_WIDGET,
        }