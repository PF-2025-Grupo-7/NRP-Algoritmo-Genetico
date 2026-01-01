from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import TipoTurno, Empleado
from datetime import time

class TestTipoTurno(TestCase):

    def crear_tipo_turno(self, **custom_data):
        tipo_turno_default = {
            "nombre": "Día",
            "abreviatura": "D",
            "especialidad": Empleado.TipoEspecialidad.MEDICO,
            "es_nocturno": False,
            "hora_inicio": time(8, 0),
            "hora_fin": time(16, 0)
        }

        tipo_turno_default.update(custom_data)

        tipo_turno = TipoTurno(**tipo_turno_default)
        tipo_turno.full_clean()
        tipo_turno.save()
        return tipo_turno

    def test_cuando_tipo_turno_tiene_datos_validos_deberia_crearse(self):
        nombre = "Noche"
        
        self.crear_tipo_turno(nombre = nombre, abreviatura = "N")

        tipo_turno = TipoTurno.objects.get(abreviatura = "N")
        self.assertIsNotNone(tipo_turno)
        self.assertEqual(tipo_turno.nombre, nombre)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        tipo_turno = TipoTurno()
        with self.assertRaises(ValidationError):
            tipo_turno.full_clean()

    def test_cuando_no_tiene_datos_deberia_usar_valores_por_defecto(self):
        TipoTurno.objects.create(
            nombre = "Día",
            abreviatura = "D",
            hora_inicio = time(8, 0),
            hora_fin = time(16, 0),
        )

        tipoTurno = TipoTurno.objects.get(nombre = "Día")
        self.assertIsNotNone(tipoTurno)
        self.assertEqual(tipoTurno.especialidad, Empleado.TipoEspecialidad.MEDICO)
        self.assertFalse(tipoTurno.es_nocturno)
        self.assertEqual(tipoTurno.duracion_horas, 8)

    def test_cuando_turno_es_diurno_duracion_se_calcula_correctamente(self):
        tipo_turno = self.crear_tipo_turno(
            hora_inicio=time(8, 0),
            hora_fin=time(16, 30)
        )

        self.assertEqual(tipo_turno.duracion_horas, 8.5)

    def test_cuando_turno_cruza_medianoche_duracion_se_calcula_correctamente(self):
        tipo_turno = self.crear_tipo_turno(
            hora_inicio=time(20, 0),
            hora_fin=time(8, 0),
            es_nocturno=True
        )

        self.assertEqual(tipo_turno.duracion_horas, 12)

    def test_turno_cruza_medianoche_y_no_es_nocturno_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_tipo_turno(
                hora_inicio=time(20, 0),
                hora_fin=time(8, 0),
                es_nocturno=False
            )

    def test_duracion_horas_se_recalcula_al_guardar(self):
        tipo_turno = self.crear_tipo_turno(
            hora_inicio=time(10, 0),
            hora_fin=time(18, 0),
            duracion_horas=99
        )

        self.assertEqual(tipo_turno.duracion_horas, 8)
