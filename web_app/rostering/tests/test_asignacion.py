from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import Cronograma, Empleado, TipoTurno, Asignacion
from datetime import time, date

class TestAsignacion(TestCase):

    def setUp(self):
        self.fecha = date(2025, 1, 10)

        self.empleado = Empleado.objects.create(
            legajo="EMP001",
            nombre_completo="Juan Pérez",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            experiencia=Empleado.TipoExperiencia.SENIOR
        )

        self.turno = TipoTurno.objects.create(
            nombre="Día",
            abreviatura="D",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8, 0),
            hora_fin=time(20, 0)
        )

        self.cronograma = Cronograma.objects.create(
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            fecha_inicio=date(2025, 1, 1),
            fecha_fin=date(2025, 1, 31)
        )
        
    def crear_asignacion(self, **custom_data):
        default_data = {
            "cronograma": self.cronograma,
            "empleado": self.empleado,
            "fecha": self.fecha,
            "tipo_turno": self.turno
        }

        default_data.update(custom_data)

        asignacion = Asignacion(**default_data)
        asignacion.full_clean()
        asignacion.save()
        return asignacion
    
    def test_cuando_asignacion_tiene_datos_validos_deberia_crearse(self):
        fecha = date(2025, 1, 25)

        self.crear_asignacion(fecha=fecha)

        asignacion = Asignacion.objects.get(empleado=self.empleado)
        self.assertIsNotNone(asignacion)
        self.assertEqual(asignacion.fecha, fecha)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        asignacion = Asignacion()

        with self.assertRaises(ValidationError):
            asignacion.full_clean()

    def test_cuando_cronograma_empleado_y_fecha_estan_duplicados_deberia_fallar(self):
        self.crear_asignacion()

        with self.assertRaises(ValidationError):
            self.crear_asignacion()
