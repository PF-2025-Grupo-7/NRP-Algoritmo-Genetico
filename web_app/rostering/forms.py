from django import forms
from .models import Empleado

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