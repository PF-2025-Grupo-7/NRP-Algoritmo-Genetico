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

        self.fecha = date(2026, 2, 10)

    def crear_preferencia(self, **custom_data):
        default_data = {
            "empleado": self.empleado,
            "fecha": self.fecha,
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
