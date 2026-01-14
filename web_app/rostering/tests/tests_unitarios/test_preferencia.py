from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from datetime import date, time
from rostering.models import Preferencia, Empleado, TipoTurno

class TestPreferencia(TestCase):

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
            hora_fin=time(22, 0)
        )

    def crear_preferencia(self, **custom_data):
        default_data = {
            "empleado": self.empleado,
            "fecha": date(2026, 2, 10),
            "tipo_turno": self.turno_medico,
            "deseo": Preferencia.Deseo.TRABAJAR,
            "comentario": "Prefiere turno mañana"
        }

        default_data.update(custom_data)

        pref = Preferencia(**default_data)
        pref.full_clean()
        pref.save()
        return pref
    
    def test_cuando_preferencia_tiene_datos_validos_deberia_crearse(self):
        deseo = Preferencia.Deseo.DESCANSAR
        comentario = "No le gusta el turno mañana"
        
        self.crear_preferencia(deseo=deseo, comentario=comentario)

        pref = Preferencia.objects.get(deseo=deseo)
        self.assertIsNotNone(pref)
        self.assertEqual(comentario, pref.comentario)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        pref = Preferencia()

        with self.assertRaises(ValidationError):
            pref.full_clean()

    def test_cuando_turno_no_corresponde_a_especialidad_del_empleado_deberia_fallar(self):
        turno_enfermero = self.turno_enfermero = TipoTurno.objects.create(
            nombre="Mañana",
            abreviatura="M",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(8, 0),
            hora_fin=time(12, 0)
        )

        with self.assertRaises(ValidationError):
            self.crear_preferencia(tipo_turno=turno_enfermero)

    def test_cuando_no_se_especifica_turno_es_valido_para_dia_completo(self):
        self.crear_preferencia(tipo_turno=None)

        pref = Preferencia.objects.get(empleado=self.empleado)
        self.assertIsNone(pref.tipo_turno)

    def test_comentario_puede_ser_vacio(self):
        self.crear_preferencia(comentario="")

        pref = Preferencia.objects.get(empleado=self.empleado)
        self.assertEqual(pref.comentario, "")

    def test_cuando_se_edita_preferencia_con_datos_validos_deberia_actualizarse(self):
        pref = self.crear_preferencia()

        nueva_fecha = date(2026, 3, 5)
        nuevo_deseo = Preferencia.Deseo.DESCANSAR
        nuevo_comentario = "Prefiere no trabajar ese día"
        nuevo_empleado = Empleado.objects.create(
            legajo="EMP002",
            nombre_completo="José Castaño",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO
        )

        pref.empleado = nuevo_empleado
        pref.fecha = nueva_fecha
        pref.tipo_turno = self.turno_enfermero
        pref.deseo = nuevo_deseo
        pref.comentario = nuevo_comentario

        pref.full_clean()
        pref.save()

        pref_actualizada = Preferencia.objects.get(pk=pref.pk)

        self.assertEqual(nuevo_empleado, pref_actualizada.empleado)
        self.assertEqual(nueva_fecha, pref_actualizada.fecha)
        self.assertEqual(self.turno_enfermero, pref_actualizada.tipo_turno)
        self.assertEqual(nuevo_deseo, pref_actualizada.deseo)
        self.assertEqual(nuevo_comentario, pref_actualizada.comentario)

    def test_cuando_se_edita_turno_con_especialidad_distinta_a_empleado_deberia_fallar(self):
        pref = self.crear_preferencia()

        pref.tipo_turno = self.turno_enfermero

        with self.assertRaises(ValidationError):
            pref.full_clean()

    def test_cuando_se_edita_tipo_turno_a_none_deberia_actualizarse(self):
        pref = self.crear_preferencia()

        pref.tipo_turno = None
        pref.full_clean()
        pref.save()

        pref_actualizada = Preferencia.objects.get(pk=pref.pk)
        self.assertIsNone(pref_actualizada.tipo_turno)

    def test_cuando_se_edita_comentario_a_vacio_deberia_actualizarse(self):
        pref = self.crear_preferencia(comentario="Comentario inicial")

        pref.comentario = ""
        pref.full_clean()
        pref.save()

        pref_actualizada = Preferencia.objects.get(pk=pref.pk)
        self.assertEqual("", pref_actualizada.comentario)

    def test_cuando_se_edita_deseo_deberia_actualizarse(self):
        pref = self.crear_preferencia(deseo=Preferencia.Deseo.TRABAJAR)

        pref.deseo = Preferencia.Deseo.DESCANSAR
        pref.full_clean()
        pref.save()

        pref_actualizada = Preferencia.objects.get(pk=pref.pk)
        self.assertEqual(Preferencia.Deseo.DESCANSAR, pref_actualizada.deseo)
