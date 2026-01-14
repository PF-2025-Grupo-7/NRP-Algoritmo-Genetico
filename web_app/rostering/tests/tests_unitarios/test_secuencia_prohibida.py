from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import TipoTurno, Empleado, SecuenciaProhibida
from datetime import time

class TestSecuenciaProhibida(TestCase):

    def setUp(self):
        self.especialidad = Empleado.TipoEspecialidad.ENFERMERO

        self.turno_noche = TipoTurno.objects.create(
            nombre="Noche",
            abreviatura="N",
            especialidad=self.especialidad,
            hora_inicio=time(20, 0),
            hora_fin=time(8, 0)
        )

        self.turno_manana = TipoTurno.objects.create(
            nombre="Mañana",
            abreviatura="M",
            especialidad=self.especialidad,
            hora_inicio=time(8, 0),
            hora_fin=time(14, 0)
        )

        self.turno_medico = TipoTurno.objects.create(
            nombre="Día",
            abreviatura="D",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8, 0),
            hora_fin=time(16, 0)
        )

    def crear_secuencia(self, **custom_data):
        default_data = {
            "especialidad": self.especialidad,
            "turno_previo": self.turno_noche,
            "turno_siguiente": self.turno_manana
        }

        default_data.update(custom_data)

        secuencia = SecuenciaProhibida(**default_data)
        secuencia.full_clean()
        secuencia.save()
        return secuencia

    def test_cuando_secuencia_prohibida_tiene_datos_validos_deberia_crearse(self):
        self.crear_secuencia()

        secuencia = SecuenciaProhibida.objects.get(turno_siguiente=self.turno_manana)
        self.assertEqual(secuencia.especialidad, self.especialidad)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        secuencia = SecuenciaProhibida()

        with self.assertRaises(ValidationError):
            secuencia.full_clean()

    def test_cuando_turno_previo_no_corresponde_a_especialidad_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_secuencia(turno_previo=self.turno_medico)

    def test_cuando_turno_siguiente_no_corresponde_a_especialidad_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_secuencia(turno_siguiente=self.turno_medico)

    def test_cuando_especialidad_turno_previo_y_turno_siguiente_se_duplican_deberia_fallar(self):
        self.crear_secuencia()

        with self.assertRaises(ValidationError):
            self.crear_secuencia()

    def test_cuando_se_edita_secuencia_prohibida_con_datos_validos_deberia_actualizarse(self):
        secuencia = self.crear_secuencia()

        nueva_especialidad = Empleado.TipoEspecialidad.MEDICO

        turno_medico_noche = TipoTurno.objects.create(
            nombre="Noche Médica",
            abreviatura="NM",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(20, 0),
            hora_fin=time(8, 0)
        )

        turno_medico_dia = TipoTurno.objects.create(
            nombre="Día Médico",
            abreviatura="DM",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8, 0),
            hora_fin=time(16, 0)
        )

        secuencia.especialidad = nueva_especialidad
        secuencia.turno_previo = turno_medico_noche
        secuencia.turno_siguiente = turno_medico_dia

        secuencia.full_clean()
        secuencia.save()

        secuencia_actualizada = SecuenciaProhibida.objects.get(pk=secuencia.pk)

        self.assertEqual(nueva_especialidad, secuencia_actualizada.especialidad)
        self.assertEqual(turno_medico_noche, secuencia_actualizada.turno_previo)
        self.assertEqual(turno_medico_dia, secuencia_actualizada.turno_siguiente)

    def test_cuando_se_edita_turno_previo_con_especialidad_distinta_deberia_fallar(self):
        secuencia = self.crear_secuencia()

        secuencia.turno_previo = self.turno_medico

        with self.assertRaises(ValidationError):
            secuencia.full_clean()

    def test_cuando_se_edita_turno_siguiente_con_especialidad_distinta_deberia_fallar(self):
        secuencia = self.crear_secuencia()

        secuencia.turno_siguiente = self.turno_medico

        with self.assertRaises(ValidationError):
            secuencia.full_clean()

    def test_cuando_se_edita_especialidad_sin_coincidir_con_turnos_deberia_fallar(self):
        secuencia = self.crear_secuencia()

        secuencia.especialidad = Empleado.TipoEspecialidad.MEDICO

        with self.assertRaises(ValidationError):
            secuencia.full_clean()

    def test_cuando_se_edita_secuencia_duplicada_deberia_fallar(self):
        self.crear_secuencia()

        secuencia = self.crear_secuencia(
            turno_previo=self.turno_manana,
            turno_siguiente=self.turno_noche
        )

        secuencia.turno_previo = self.turno_noche
        secuencia.turno_siguiente = self.turno_manana
        secuencia.especialidad = self.especialidad

        with self.assertRaises(ValidationError):
            secuencia.full_clean()
