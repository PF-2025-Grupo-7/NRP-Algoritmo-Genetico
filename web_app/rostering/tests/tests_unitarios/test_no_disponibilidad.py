from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from datetime import date, time
from rostering.models import NoDisponibilidad, Empleado, TipoTurno

class TestNoDisponibilidad(TestCase):

    def setUp(self):
        self.empleado = Empleado.objects.create(
            legajo="EMP001",
            nombre_completo="Juan Pérez",
            especialidad=Empleado.TipoEspecialidad.MEDICO
        )

        self.turno_medico = TipoTurno.objects.create(
            nombre="Mañana",
            abreviatura="M",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8, 0),
            hora_fin=time(12, 0)
        )

        self.turno_enfermero = TipoTurno.objects.create(
            nombre="Tarde",
            abreviatura="T",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(14, 0),
            hora_fin=time(20, 0)
        )

    def crear_no_disponibilidad(self, **custom_data):
        default_data = {
            "empleado": self.empleado,
            "fecha_inicio": date(2026, 1, 10),
            "fecha_fin": date(2026, 1, 15),
            "tipo_turno": self.turno_medico,
            "motivo": "Vacaciones"
        }

        default_data.update(custom_data)

        no_disp = NoDisponibilidad(**default_data)
        no_disp.full_clean()
        no_disp.save()
        return no_disp
    
    def test_cuando_no_disponibilidad_tiene_datos_validos_deberia_crearse(self):
        motivo = "Licencia médica"
        fecha_actual = date(2026, 1, 25)

        self.crear_no_disponibilidad(motivo=motivo, fecha_fin=fecha_actual)

        no_disp = NoDisponibilidad.objects.get(motivo=motivo)
        self.assertIsNotNone(no_disp)
        self.assertEqual(no_disp.fecha_fin, fecha_actual)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        no_disp = NoDisponibilidad()

        with self.assertRaises(ValidationError):
            no_disp.full_clean()

    def test_cuando_turno_no_corresponde_a_especialidad_del_empleado_deberia_fallar(self):
        turno_enfermero = self.turno_enfermero = TipoTurno.objects.create(
            nombre="Mañana",
            abreviatura="M",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(8, 0),
            hora_fin=time(12, 0)
        )

        with self.assertRaises(ValidationError):
            self.crear_no_disponibilidad(tipo_turno=turno_enfermero)

    def test_cuando_no_se_especifica_turno_es_valido_para_todo_el_dia(self):
        self.crear_no_disponibilidad(tipo_turno=None)

        no_disp = NoDisponibilidad.objects.get(motivo="Vacaciones")
        self.assertIsNone(no_disp.tipo_turno)

    def test_fecha_inicio_y_fin_iguales_es_valido(self):
        self.crear_no_disponibilidad(
            fecha_inicio=date(2025, 1, 10),
            fecha_fin=date(2025, 1, 10)
        )

        no_disp = NoDisponibilidad.objects.get(motivo="Vacaciones")
        self.assertEqual(no_disp.fecha_fin, no_disp.fecha_inicio)

    def test_fecha_fin_anterior_a_fecha_inicio_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_no_disponibilidad(fecha_inicio=date(2025, 1, 20),fecha_fin=date(2025, 1, 10))

    def test_cuando_se_edita_no_disponibilidad_con_datos_validos_deberia_actualizarse(self):
        no_disp = self.crear_no_disponibilidad()

        nueva_fecha_inicio = date(2026, 2, 1)
        nueva_fecha_fin = date(2026, 2, 5)
        nuevo_motivo = "Capacitación"
        nuevo_empleado = Empleado.objects.create(
            legajo="EMP010",
            nombre_completo="Lucas Martínez",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO
        )

        no_disp.empleado = nuevo_empleado
        no_disp.fecha_inicio = nueva_fecha_inicio
        no_disp.fecha_fin = nueva_fecha_fin
        no_disp.tipo_turno = self.turno_enfermero
        no_disp.motivo = nuevo_motivo

        no_disp.full_clean()
        no_disp.save()

        no_disp_actualizada = NoDisponibilidad.objects.get(pk=no_disp.pk)

        self.assertEqual(nuevo_empleado, no_disp_actualizada.empleado)
        self.assertEqual(nueva_fecha_inicio, no_disp_actualizada.fecha_inicio)
        self.assertEqual(nueva_fecha_fin, no_disp_actualizada.fecha_fin)
        self.assertEqual(self.turno_enfermero, no_disp_actualizada.tipo_turno)
        self.assertEqual(nuevo_motivo, no_disp_actualizada.motivo)

    def test_cuando_se_edita_fecha_fin_anterior_a_fecha_inicio_deberia_fallar(self):
        no_disp = self.crear_no_disponibilidad()

        no_disp.fecha_inicio = date(2026, 3, 10)
        no_disp.fecha_fin = date(2026, 3, 1)

        with self.assertRaises(ValidationError):
            no_disp.full_clean()

    def test_cuando_se_edita_turno_con_especialidad_distinta_a_empleado_deberia_fallar(self):
        no_disp = self.crear_no_disponibilidad()

        no_disp.tipo_turno = self.turno_enfermero

        with self.assertRaises(ValidationError):
            no_disp.full_clean()

    def test_cuando_se_edita_tipo_turno_a_none_deberia_de_actualizarse(self):
        no_disp = self.crear_no_disponibilidad()

        no_disp.tipo_turno = None
        no_disp.full_clean()
        no_disp.save()

        no_disp_actualizada = NoDisponibilidad.objects.get(pk=no_disp.pk)
        self.assertIsNone(no_disp_actualizada.tipo_turno)

    def test_cuando_se_edita_fecha_inicio_y_fin_iguales_deberia_de_actualizarse(self):
        no_disp = self.crear_no_disponibilidad()

        misma_fecha = date(2026, 4, 10)

        no_disp.fecha_inicio = misma_fecha
        no_disp.fecha_fin = misma_fecha

        no_disp.full_clean()
        no_disp.save()

        no_disp_actualizada = NoDisponibilidad.objects.get(pk=no_disp.pk)
        self.assertEqual(no_disp_actualizada.fecha_inicio, no_disp_actualizada.fecha_fin)
