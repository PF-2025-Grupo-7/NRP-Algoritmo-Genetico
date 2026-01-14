from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from datetime import date, time
from rostering.models import ExcepcionDemanda, PlantillaDemanda, Empleado, TipoTurno

class TestExcepcionDemanda(TestCase):

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

        self.fecha = date(2025, 12, 25)

    def crear_excepcion_demanda(self, **custom_data):
        excepcion_default = {
            "plantilla": self.plantilla,
            "fecha": self.fecha,
            "turno": self.turno,
            "cantidad_senior": 1,
            "cantidad_junior": 2,
            "motivo": "Navidad",
        }

        excepcion_default.update(custom_data)

        excepcion = ExcepcionDemanda(**excepcion_default)
        excepcion.full_clean()
        excepcion.save()
        return excepcion
    
    def test_cuando_excepcion_demanda_tiene_datos_validos_deberia_crearse(self):
        motivo = "Feriado"
        cant_juniors = 7
        
        self.crear_excepcion_demanda(motivo=motivo,cantidad_junior=cant_juniors)

        excepcion = ExcepcionDemanda.objects.get(motivo = motivo)

        self.assertIsNotNone(excepcion)
        self.assertEqual(cant_juniors, excepcion.cantidad_junior)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        excepcion = ExcepcionDemanda()

        with self.assertRaises(ValidationError):
            excepcion.full_clean()

    def test_cuando_no_tiene_datos_deberia_usar_valores_por_defecto(self):
        
        excepcion = ExcepcionDemanda.objects.create(
            plantilla=self.plantilla,
            fecha=self.fecha,
            turno=self.turno
        )

        excepcion = ExcepcionDemanda.objects.get(plantilla=self.plantilla)

        self.assertEqual(excepcion.cantidad_senior, 0)
        self.assertEqual(excepcion.cantidad_junior, 0)

    def test_motivo_puede_ser_vacio(self):
        excepcion = self.crear_excepcion_demanda(motivo="")

        excepcion = ExcepcionDemanda.objects.get(cantidad_senior = 1)
        self.assertEqual(excepcion.motivo, "")
        
    def test_cuando_plantilla_turno_y_fecha_estan_duplicados_deberia_fallar(self):
        self.crear_excepcion_demanda()

        with self.assertRaises(ValidationError):
            self.crear_excepcion_demanda()

    def test_cuando_turno_no_corresponde_a_especialidad_de_plantilla_deberia_fallar(self):
        turno_enfermero = TipoTurno.objects.create(
            nombre="Día Enfermería",
            abreviatura="DE",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(8, 0),
            hora_fin=time(16, 0)
        )

        with self.assertRaises(ValidationError):
            self.crear_excepcion_demanda(turno=turno_enfermero)

    def test_excepcion_sin_plantilla_es_valida(self):
        self.crear_excepcion_demanda(plantilla=None)

        excepcion = ExcepcionDemanda.objects.get(cantidad_senior = 1)
        self.assertIsNone(excepcion.plantilla)

    def test_cuando_cantidad_senior_es_negativa_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_excepcion_demanda(cantidad_senior=-1)

    def test_cuando_cantidad_junior_es_negativa_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_excepcion_demanda(cantidad_junior=-1)

    def test_cuando_se_edita_excepcion_demanda_con_datos_validos_deberia_actualizarse(self):
        excepcion = self.crear_excepcion_demanda()

        nueva_fecha = date(2025, 1, 1)
        nuevo_motivo = "Año Nuevo"

        excepcion.plantilla = self.plantilla
        excepcion.fecha = nueva_fecha
        excepcion.turno = self.turno
        excepcion.cantidad_senior = 3
        excepcion.cantidad_junior = 5
        excepcion.motivo = nuevo_motivo

        excepcion.full_clean()
        excepcion.save()

        excepcion_actualizada = ExcepcionDemanda.objects.get(pk=excepcion.pk)
        self.assertEqual(self.plantilla, excepcion_actualizada.plantilla)
        self.assertEqual(nueva_fecha, excepcion_actualizada.fecha)
        self.assertEqual(self.turno, excepcion_actualizada.turno)
        self.assertEqual(3, excepcion_actualizada.cantidad_senior)
        self.assertEqual(5, excepcion_actualizada.cantidad_junior)
        self.assertEqual(nuevo_motivo, excepcion_actualizada.motivo)

    def test_cuando_se_edita_cantidad_senior_a_valor_negativo_deberia_fallar(self):
        excepcion = self.crear_excepcion_demanda()

        excepcion.cantidad_senior = -1

        with self.assertRaises(ValidationError):
            excepcion.full_clean()

    def test_cuando_se_edita_cantidad_junior_a_valor_negativo_deberia_fallar(self):
        excepcion = self.crear_excepcion_demanda()

        excepcion.cantidad_junior = -1

        with self.assertRaises(ValidationError):
            excepcion.full_clean()

    def test_cuando_se_edita_turno_con_especialidad_distinta_a_plantilla_deberia_fallar(self):
        excepcion = self.crear_excepcion_demanda()

        turno_enfermero = TipoTurno.objects.create(
            nombre="Noche Enfermería",
            abreviatura="NE",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(20, 0),
            hora_fin=time(8, 0)
        )

        excepcion.turno = turno_enfermero

        with self.assertRaises(ValidationError):
            excepcion.full_clean()

    def test_cuando_se_edita_plantilla_fecha_y_turno_a_duplicados_deberia_fallar(self):
        self.crear_excepcion_demanda()

        excepcion = self.crear_excepcion_demanda(fecha=date(2025, 12, 31))

        excepcion.fecha = self.fecha
        excepcion.turno = self.turno
        excepcion.plantilla = self.plantilla

        with self.assertRaises(ValidationError):
            excepcion.full_clean()

    def test_cuando_se_edita_motivo_a_vacio_deberia_de_actualizarse(self):
        excepcion = self.crear_excepcion_demanda(motivo="Feriado Especial")

        excepcion.motivo = ""
        excepcion.full_clean()
        excepcion.save()

        excepcion_actualizada = ExcepcionDemanda.objects.get(pk=excepcion.pk)
        self.assertEqual("", excepcion_actualizada.motivo)