from django import forms
from django.core.exceptions import ValidationError
from .models import ConfiguracionAlgoritmo, Empleado, TipoTurno, NoDisponibilidad, Preferencia, SecuenciaProhibida, PlantillaDemanda, ReglaDemandaSemanal, ExcepcionDemanda

# Este Mixin sirve para darle estilo Bootstrap a cualquier form que hagan
class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            # Añadimos la clase form-control a todos los campos visibles
            field.widget.attrs.update({'class': 'form-control'})
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})

class EmpleadoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Empleado
        fields = '__all__' # O listen los campos específicos si quieren ocultar algo
        # widgets = { ... } # Si necesitan personalizar fechas, etc.

class TipoTurnoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TipoTurno
        fields = '__all__'
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
            # Si tienes un campo 'color', usa type='color'
        }

class NoDisponibilidadForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = NoDisponibilidad
        fields = '__all__'
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}),
            'empleado': forms.Select(attrs={'class': 'form-select'}),
            'tipo_turno': forms.Select(attrs={'class': 'form-select'}),
        }

class PreferenciaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Preferencia
        fields = '__all__'
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'empleado': forms.Select(attrs={'class': 'form-select'}),
            'tipo_turno': forms.Select(attrs={'class': 'form-select'}),
            'deseo': forms.Select(attrs={'class': 'form-select'}),
            'comentario': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Opcional...'})
        }

class SecuenciaProhibidaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SecuenciaProhibida
        fields = '__all__'
        widgets = {
            'especialidad': forms.Select(attrs={'class': 'form-select'}),
            'turno_previo': forms.Select(attrs={'class': 'form-select'}),
            'turno_siguiente': forms.Select(attrs={'class': 'form-select'}),
        }
        help_texts = {
            'turno_previo': 'El turno que termina el día anterior.',
            'turno_siguiente': 'El turno que NO puede comenzar el día siguiente.',
        }

    def clean(self):
        cleaned_data = super().clean()
        # La validación cruzada de especialidades ya está en el modelo (método clean),
        # Django la ejecuta automáticamente y asigna los errores al form.
        return cleaned_data
    
# --- PLANTILLAS DE DEMANDA ---

class PlantillaDemandaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PlantillaDemanda
        fields = '__all__'
        widgets = {
            'especialidad': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }

class ReglaDemandaSemanalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ReglaDemandaSemanal
        fields = ['dia', 'turno', 'cantidad_senior', 'cantidad_junior']
        widgets = {
            'dia': forms.Select(attrs={'class': 'form-select'}),
            'turno': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        # Recibimos la plantilla para filtrar los turnos
        plantilla_id = kwargs.pop('plantilla_id', None)
        super().__init__(*args, **kwargs)
        
        if plantilla_id:
            plantilla = PlantillaDemanda.objects.get(id=plantilla_id)
            # Solo mostramos turnos de la misma especialidad
            self.fields['turno'].queryset = TipoTurno.objects.filter(especialidad=plantilla.especialidad)

class ExcepcionDemandaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExcepcionDemanda
        fields = ['fecha', 'turno', 'cantidad_senior', 'cantidad_junior', 'motivo']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'turno': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        plantilla_id = kwargs.pop('plantilla_id', None)
        super().__init__(*args, **kwargs)
        
        if plantilla_id:
            plantilla = PlantillaDemanda.objects.get(id=plantilla_id)
            self.fields['turno'].queryset = TipoTurno.objects.filter(especialidad=plantilla.especialidad)

class ConfiguracionSimpleForm(forms.Form):
    TIPO_BUSQUEDA = [
        ('RAPIDA', '⚡ Búsqueda Rápida (Borrador)'),
        ('EQUILIBRADA', '⚖️ Búsqueda Equilibrada (Recomendada)'),
        ('PROFUNDA', '🧠 Búsqueda Profunda (Alta Calidad)'),
    ]

    modo = forms.ChoiceField(
        choices=TIPO_BUSQUEDA, 
        widget=forms.RadioSelect(attrs={'class': 'btn-check'}),
        label="Seleccione el tipo de optimización"
    )

    def save(self, config_instance):
        """Aplica los presets al objeto de configuración según el modo elegido"""
        modo = self.cleaned_data['modo']
        
        if modo == 'RAPIDA':
            config_instance.tamano_poblacion = 100
            config_instance.generaciones = 75
            config_instance.prob_mutacion = 0.3  # Más caos para salir rápido de mínimos locales
            config_instance.nombre = "Configuración Rápida"
            
        elif modo == 'EQUILIBRADA':
            config_instance.tamano_poblacion = 100
            config_instance.generaciones = 150
            config_instance.prob_mutacion = 0.2
            config_instance.nombre = "Configuración Equilibrada"
            
        elif modo == 'PROFUNDA':
            config_instance.tamano_poblacion = 150
            config_instance.generaciones = 250
            config_instance.prob_mutacion = 0.15 # Mutación fina
            config_instance.nombre = "Configuración Profunda"
            
        config_instance.save()

class ConfiguracionAvanzadaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracionAlgoritmo
        fields = '__all__'
        exclude = ['activa'] # Siempre editamos la activa
        widgets = {
            'estrategia_seleccion': forms.Select(attrs={'class': 'form-select'}),
            'estrategia_cruce': forms.Select(attrs={'class': 'form-select'}),
            'estrategia_mutacion': forms.Select(attrs={'class': 'form-select'}),
        }