from django import forms
from django.core.exceptions import ValidationError
from .models import Empleado, TipoTurno, NoDisponibilidad, Preferencia, SecuenciaProhibida

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