from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import Empleado

legajo = "EMP001"

class TestEmpleado(TestCase):

    def crear_empleado(self, **custom_data):
        empleado_default = {
            "legajo": "EMP001",
            "nombre_completo": "Juan Pérez",
            "especialidad": Empleado.TipoEspecialidad.MEDICO,
            "experiencia": Empleado.TipoExperiencia.SENIOR,
            "min_turnos_mensuales": 10,
            "max_turnos_mensuales": 20,
            "activo": True,
        }

        empleado_default.update(custom_data)

        empleado = Empleado(**empleado_default)
        empleado.full_clean()
        empleado.save()
        return empleado

    def test_cuando_empleado_tiene_datos_validos_deberia_crearse(self):
        
        nombre = "Ana María"

        self.crear_empleado(legajo=legajo, nombre_completo=nombre)

        empleado = Empleado.objects.get(legajo=legajo)
        self.assertIsNotNone(empleado)
        self.assertEqual(nombre, empleado.nombre_completo)

    def test_cuando_faltan_datos_validos_deberia_fallar(self):
        empleado = Empleado.objects.create()
        with self.assertRaises(ValidationError):
            empleado.full_clean()
            
    def test_cuando_no_tiene_datos_deberia_usar_valores_por_defecto(self):

        min_turnos = 10
        max_turnos = 20

        Empleado.objects.create(
            legajo="EMP001",
            nombre_completo="Juan Pérez",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            experiencia=Empleado.TipoExperiencia.SENIOR,
        )

        empleado = Empleado.objects.get(legajo=legajo)
        self.assertTrue(empleado.activo)
        self.assertEqual(min_turnos, empleado.min_turnos_mensuales)
        self.assertEqual(max_turnos, empleado.max_turnos_mensuales)

    def test_cuando_legajo_duplicado_deberia_fallar(self):
        self.crear_empleado()

        with self.assertRaises(ValidationError):
            self.crear_empleado()

    def test_cuando_min_turnos_es_negativo_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_empleado(min_turnos_mensuales=-1)

    def test_cuando_empleado_no_esta_activo_str_deberia_indicar_inactivo(self):
        self.crear_empleado(activo = False)

        empleado = Empleado.objects.get(legajo=legajo)
        self.assertFalse(empleado.activo)
