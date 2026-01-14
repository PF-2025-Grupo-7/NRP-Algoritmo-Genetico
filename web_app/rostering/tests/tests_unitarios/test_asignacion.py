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

    def test_cuando_cronograma_tiene_otra_especialidad_deberia_fallar(self):
        cronograma_enfermero = Cronograma.objects.create(
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            fecha_inicio=date(2025, 1, 1),
            fecha_fin=date(2025, 1, 31)
        )

        with self.assertRaises(ValidationError):
            self.crear_asignacion(cronograma=cronograma_enfermero)

    def test_cuando_tipo_turno_tiene_otra_especialidad_deberia_fallar(self):
        turno_enfermero = TipoTurno.objects.create(
            nombre="Mañana",
            abreviatura="M",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(0, 0),
            hora_fin=time(8, 0)
        )

        with self.assertRaises(ValidationError):
            self.crear_asignacion(tipo_turno=turno_enfermero)

    def test_cuando_se_edita_asignacion_con_datos_validos_deberia_actualizarse(self):
        self.crear_asignacion()

        nuevo_empleado = Empleado.objects.create(
            legajo="EMP010",
            nombre_completo="Juan Pires",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            experiencia=Empleado.TipoExperiencia.JUNIOR
        )

        nuevo_turno = TipoTurno.objects.create(
            nombre="Noche",
            abreviatura="N",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(22, 0),
            hora_fin=time(6, 0)
        )

        nueva_fecha = date(2025,1,10)

        nuevo_cronograma = Cronograma.objects.create(
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            fecha_inicio=date(2025, 1, 1),
            fecha_fin=date(2025, 1, 31)
        )

        asignacion = Asignacion.objects.get(empleado=self.empleado)
        asignacion.tipo_turno = nuevo_turno
        asignacion.empleado = nuevo_empleado
        asignacion.fecha = nueva_fecha
        asignacion.cronograma = nuevo_cronograma
        asignacion.full_clean()
        asignacion.save()

        asignacion_editada = Asignacion.objects.get(pk=asignacion.pk)
        self.assertEqual(asignacion_editada.tipo_turno, nuevo_turno)
        self.assertEqual(asignacion_editada.empleado, nuevo_empleado)
        self.assertEqual(asignacion_editada.fecha, nueva_fecha)
        self.assertEqual(asignacion_editada.cronograma, nuevo_cronograma)

    def test_cuando_se_edita_asignacion_generando_duplicado_deberia_fallar(self):
        self.crear_asignacion(
            fecha=date(2025, 1, 10)
        )

        asignacion = self.crear_asignacion(
            fecha=date(2025, 1, 11)
        )

        asignacion.fecha = date(2025, 1, 10)

        with self.assertRaises(ValidationError):
            asignacion.full_clean()

    def test_cuando_se_edita_cronograma_con_especialidad_distinta_deberia_fallar(self):
        asignacion = self.crear_asignacion()

        cronograma_enfermero = Cronograma.objects.create(
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            fecha_inicio=date(2025, 1, 1),
            fecha_fin=date(2025, 1, 31)
        )

        asignacion.cronograma = cronograma_enfermero

        with self.assertRaises(ValidationError):
            asignacion.full_clean()

    def test_cuando_se_edita_tipo_turno_con_especialidad_distinta_deberia_fallar(self):
        asignacion = self.crear_asignacion()

        turno_enfermero = TipoTurno.objects.create(
            nombre="Noche",
            abreviatura="N",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(22, 0),
            hora_fin=time(6, 0)
        )

        asignacion.tipo_turno = turno_enfermero

        with self.assertRaises(ValidationError):
            asignacion.full_clean()

