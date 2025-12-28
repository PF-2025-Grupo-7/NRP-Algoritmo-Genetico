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
