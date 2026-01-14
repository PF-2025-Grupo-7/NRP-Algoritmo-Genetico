from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from datetime import time
from rostering.models import ReglaDemandaSemanal, TipoTurno, Empleado, PlantillaDemanda, DiaSemana

class TestReglaDemandaSemanal(TestCase):

    def setUp(self):
        self.plantilla = PlantillaDemanda.objects.create(
            nombre="Demanda Médicos",
            especialidad=Empleado.TipoEspecialidad.MEDICO
        )

        self.turno = TipoTurno.objects.create(
            nombre="Día",
            abreviatura="D",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8, 0),
            hora_fin=time(16, 0)
        )

        self.turno_enfermero = TipoTurno.objects.create(
            nombre="Noche Enfermería",
            abreviatura="NE",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(20, 0),
            hora_fin=time(8, 0)
        )

    def crear_regla_demanda(self, **custom_data):
        regla_default = {
            "plantilla": self.plantilla,
            "dia": DiaSemana.LUNES,
            "turno": self.turno,
            "cantidad_senior": 1,
            "cantidad_junior": 2,
        }

        regla_default.update(custom_data)

        regla = ReglaDemandaSemanal(**regla_default)
        regla.full_clean()
        regla.save()
        return regla

    def test_cuando_regla_demanda_tiene_datos_validos_deberia_crearse(self):
        dia = DiaSemana.MARTES
        cant_senior = 8

        self.crear_regla_demanda(dia=dia, cantidad_senior=cant_senior)

        regla = ReglaDemandaSemanal.objects.get(dia = dia)

        self.assertIsNotNone(regla)
        self.assertEqual(cant_senior, regla.cantidad_senior)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        regla = ReglaDemandaSemanal()

        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_cuando_no_tiene_datos_deberia_usar_valores_por_defecto(self):
        regla = ReglaDemandaSemanal.objects.create(
            plantilla=self.plantilla,
            dia=DiaSemana.MARTES,
            turno=self.turno
        )

        self.assertEqual(regla.cantidad_senior, 1)
        self.assertEqual(regla.cantidad_junior, 2)

    def test_cuando_plantilla_turno_y_dia_estan_duplicados_deberia_fallar(self):
        self.crear_regla_demanda()

        with self.assertRaises(ValidationError):
            self.crear_regla_demanda()

    def test_cuando_turno_no_corresponde_a_especialidad_deberia_fallar(self):
        turno_enfermero = TipoTurno.objects.create(
            nombre="Día Enfermería",
            abreviatura="DE",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(8, 0),
            hora_fin=time(16, 0)
        )

        with self.assertRaises(ValidationError):
            self.crear_regla_demanda(turno=turno_enfermero)

    def test_cuando_dia_es_invalido_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_regla_demanda(dia=7)

    def test_cuando_cantidad_senior_es_negativa_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_regla_demanda(cantidad_senior=-1)


    def test_cuando_cantidad_junior_es_negativa_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_regla_demanda(cantidad_junior=-1)

    def test_cuando_se_edita_regla_demanda_con_datos_validos_deberia_actualizarse(self):
        regla = self.crear_regla_demanda()

        nuevo_dia = DiaSemana.MIERCOLES
        nueva_cantidad_senior = 3
        nueva_cantidad_junior = 6
        plantilla_enfermero = PlantillaDemanda.objects.create(
            nombre="Demanda Enfermeros",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO
        )

        regla.plantilla = plantilla_enfermero
        regla.dia = nuevo_dia
        regla.turno = self.turno_enfermero
        regla.cantidad_senior = nueva_cantidad_senior
        regla.cantidad_junior = nueva_cantidad_junior

        regla.full_clean()
        regla.save()

        regla_actualizada = ReglaDemandaSemanal.objects.get(pk=regla.pk)

        self.assertEqual(plantilla_enfermero, regla_actualizada.plantilla)
        self.assertEqual(nuevo_dia, regla_actualizada.dia)
        self.assertEqual(self.turno_enfermero, regla_actualizada.turno)
        self.assertEqual(nueva_cantidad_senior, regla_actualizada.cantidad_senior)
        self.assertEqual(nueva_cantidad_junior, regla_actualizada.cantidad_junior)

    def test_cuando_se_edita_cantidad_senior_a_valor_negativo_deberia_fallar(self):
        regla = self.crear_regla_demanda()

        regla.cantidad_senior = -1

        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_cuando_se_edita_cantidad_junior_a_valor_negativo_deberia_fallar(self):
        regla = self.crear_regla_demanda()

        regla.cantidad_junior = -1

        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_cuando_se_edita_turno_con_especialidad_distinta_a_plantilla_deberia_fallar(self):
        regla = self.crear_regla_demanda()

        regla.turno = self.turno_enfermero

        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_cuando_se_edita_dia_a_valor_invalido_deberia_fallar(self):
        regla = self.crear_regla_demanda()

        regla.dia = 7

        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_cuando_se_edita_plantilla_dia_y_turno_a_duplicados_deberia_fallar(self):
        self.crear_regla_demanda()

        regla = self.crear_regla_demanda(
            dia=DiaSemana.MARTES
        )

        regla.dia = DiaSemana.LUNES
        regla.turno = self.turno
        regla.plantilla = self.plantilla

        with self.assertRaises(ValidationError):
            regla.full_clean()
