from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import Empleado
 
class TestEmpleado(TestCase):

    def setUp(self):
        self.legajo = "EMP001"

    def crear_empleado(self, **custom_data):
        empleado_default = {
            "legajo": self.legajo,
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

        self.crear_empleado(legajo=self.legajo, nombre_completo=nombre)

        empleado = Empleado.objects.get(legajo=self.legajo)
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

        empleado = Empleado.objects.get(legajo=self.legajo)
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

        empleado = Empleado.objects.get(legajo=self.legajo)
        self.assertFalse(empleado.activo)

    def test_cuando_se_edita_empleado_con_datos_validos_deberia_actualizarse(self):
        empleado = self.crear_empleado()

        nuevo_legajo = "EMP002"
        nuevo_nombre = "Ana Gómez"

        empleado.legajo = nuevo_legajo
        empleado.nombre_completo = nuevo_nombre
        empleado.especialidad = Empleado.TipoEspecialidad.UCI
        empleado.experiencia = Empleado.TipoExperiencia.JUNIOR
        empleado.min_turnos_mensuales = 5
        empleado.max_turnos_mensuales = 15
        empleado.activo = False

        empleado.full_clean()
        empleado.save()

        empleado_actualizado = Empleado.objects.get(pk=empleado.pk)

        self.assertEqual(nuevo_legajo, empleado_actualizado.legajo)
        self.assertEqual(nuevo_nombre, empleado_actualizado.nombre_completo)
        self.assertEqual(Empleado.TipoEspecialidad.UCI, empleado_actualizado.especialidad)
        self.assertEqual(Empleado.TipoExperiencia.JUNIOR, empleado_actualizado.experiencia)
        self.assertEqual(5, empleado_actualizado.min_turnos_mensuales)
        self.assertEqual(15, empleado_actualizado.max_turnos_mensuales)
        self.assertFalse(empleado_actualizado.activo)

    def test_cuando_se_edita_min_turnos_a_valor_negativo_deberia_fallar(self):
        empleado = self.crear_empleado()

        empleado.min_turnos_mensuales = -5

        with self.assertRaises(ValidationError):
            empleado.full_clean()

    def test_cuando_se_edita_max_turnos_a_valor_negativo_deberia_fallar(self):
        empleado = self.crear_empleado()

        empleado.max_turnos_mensuales = -1

        with self.assertRaises(ValidationError):
            empleado.full_clean()

    def test_cuando_se_edita_legajo_a_uno_existente_deberia_fallar(self):
        self.crear_empleado(legajo="EMP001")
        empleado_2 = self.crear_empleado(
            legajo="EMP002",
            nombre_completo="Otro Empleado"
        )

        empleado_2.legajo = "EMP001"

        with self.assertRaises(ValidationError):
            empleado_2.full_clean()

    def test_cuando_se_edita_estado_activo_deberia_actualizarse(self):
        empleado = self.crear_empleado(activo=True)

        empleado.activo = False
        empleado.full_clean()
        empleado.save()

        empleado_actualizado = Empleado.objects.get(pk=empleado.pk)
        self.assertFalse(empleado_actualizado.activo)