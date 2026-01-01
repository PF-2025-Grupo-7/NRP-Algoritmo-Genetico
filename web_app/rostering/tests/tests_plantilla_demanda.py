from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import PlantillaDemanda, Empleado

nombre_default = "Demanda Estándar 2025"

class TestPlantillaDemanda(TestCase):

    def crear_plantilla_demanda(self, **custom_data):
        plantilla_default = {
            "nombre": nombre_default,
            "especialidad": Empleado.TipoEspecialidad.MEDICO,
            "descripcion": "Plantilla base para planificación anual",
        }

        plantilla_default.update(custom_data)

        plantilla = PlantillaDemanda(**plantilla_default)
        plantilla.full_clean()
        plantilla.save()
        return plantilla
    
    def test_cuando_plantilla_demanda_tiene_datos_validos_deberia_crearse(self):
        nombre = "Demanda Verano"
        especialidad = Empleado.TipoEspecialidad.MEDICO

        self.crear_plantilla_demanda(nombre=nombre)

        plantilla = PlantillaDemanda.objects.get(nombre=nombre)
        self.assertIsNotNone(plantilla)
        self.assertEqual(plantilla.especialidad, especialidad)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        plantilla = PlantillaDemanda()
        with self.assertRaises(ValidationError):
            plantilla.full_clean()

    def test_cuando_no_tiene_datos_deberia_usar_valores_por_defecto(self):
        nombre = "Demanda Default"

        PlantillaDemanda.objects.create(nombre= nombre)

        plantilla = PlantillaDemanda.objects.get(nombre="Demanda Default")
        self.assertEqual(plantilla.especialidad, Empleado.TipoEspecialidad.MEDICO)

    def test_cuando_nombre_duplicado_deberia_fallar(self):
        self.crear_plantilla_demanda()

        with self.assertRaises(Exception):
            self.crear_plantilla_demanda()

    def test_descripcion_puede_ser_vacia_sin_fallar(self):
        
        plantilla = self.crear_plantilla_demanda(descripcion="")

        plantilla = PlantillaDemanda.objects.get(nombre=nombre_default)
        self.assertEqual(plantilla.descripcion, "")
