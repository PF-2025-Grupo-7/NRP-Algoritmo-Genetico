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

    def test_cuando_se_edita_tipo_turno_con_datos_validos_deberia_actualizarse(self):
        tipo_turno = self.crear_tipo_turno()

        nuevo_nombre = "Turno Extendido"
        nueva_abreviatura = "TE"
        nueva_especialidad = Empleado.TipoEspecialidad.ENFERMERO
        nueva_hora_inicio = time(9, 0)
        nueva_hora_fin = time(21, 0)

        tipo_turno.nombre = nuevo_nombre
        tipo_turno.abreviatura = nueva_abreviatura
        tipo_turno.especialidad = nueva_especialidad
        tipo_turno.hora_inicio = nueva_hora_inicio
        tipo_turno.hora_fin = nueva_hora_fin
        tipo_turno.es_nocturno = False

        tipo_turno.full_clean()
        tipo_turno.save()

        tipo_turno_actualizado = TipoTurno.objects.get(pk=tipo_turno.pk)
        self.assertEqual(nuevo_nombre, tipo_turno_actualizado.nombre)
        self.assertEqual(nueva_abreviatura, tipo_turno_actualizado.abreviatura)
        self.assertEqual(nueva_especialidad, tipo_turno_actualizado.especialidad)
        self.assertEqual(12, tipo_turno_actualizado.duracion_horas)

    def test_cuando_se_edita_turno_para_que_cruce_medianoche_y_es_nocturno_es_valido(self):
        tipo_turno = self.crear_tipo_turno()

        tipo_turno.hora_inicio = time(22, 0)
        tipo_turno.hora_fin = time(6, 0)
        tipo_turno.es_nocturno = True

        tipo_turno.full_clean()
        tipo_turno.save()

        tipo_turno_actualizado = TipoTurno.objects.get(pk=tipo_turno.pk)

        self.assertTrue(tipo_turno_actualizado.es_nocturno)
        self.assertEqual(8, tipo_turno_actualizado.duracion_horas)

    def test_cuando_se_edita_turno_para_que_cruce_medianoche_y_no_es_nocturno_deberia_fallar(self):
        tipo_turno = self.crear_tipo_turno()

        tipo_turno.hora_inicio = time(22, 0)
        tipo_turno.hora_fin = time(6, 0)
        tipo_turno.es_nocturno = False

        with self.assertRaises(ValidationError):
            tipo_turno.full_clean()

    def test_duracion_horas_se_recalcula_al_editar_horarios(self):
        tipo_turno = self.crear_tipo_turno(
            hora_inicio=time(8, 0),
            hora_fin=time(12, 0)
        )

        self.assertEqual(tipo_turno.duracion_horas, 4)

        tipo_turno.hora_inicio = time(7, 30)
        tipo_turno.hora_fin = time(16, 0)

        tipo_turno.full_clean()
        tipo_turno.save()

        tipo_turno_actualizado = TipoTurno.objects.get(pk=tipo_turno.pk)
        self.assertEqual(8.5, tipo_turno_actualizado.duracion_horas)

    def test_cuando_se_puede_forzar_duracion_horas_manual_al_editar(self):
        tipo_turno = self.crear_tipo_turno()

        tipo_turno.duracion_horas = 99
        tipo_turno.hora_inicio = time(8, 0)
        tipo_turno.hora_fin = time(16, 0)

        tipo_turno.full_clean()
        tipo_turno.save()

        tipo_turno_actualizado = TipoTurno.objects.get(pk=tipo_turno.pk)
        self.assertEqual(8, tipo_turno_actualizado.duracion_horas)
