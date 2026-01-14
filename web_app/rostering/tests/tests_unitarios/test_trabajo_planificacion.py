from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import TrabajoPlanificacion, Empleado, PlantillaDemanda
from datetime import date
import uuid

class TestTrabajoPlanificacion(TestCase):

    def setUp(self):
        self.especialidad = Empleado.TipoEspecialidad.MEDICO

        self.plantilla_demanda = PlantillaDemanda.objects.create(
            nombre="Plantilla Test",
            especialidad=self.especialidad,
            descripcion = "Descripción Plantilla",
        )
    
    def crear_trabajo(self, **custom_data):
        default_data = {
            "job_id": uuid.uuid4(),
            "fecha_inicio": date(2025, 1, 1),
            "fecha_fin": date(2025, 1, 31),
            "especialidad": self.especialidad,
            "plantilla_demanda": self.plantilla_demanda,
            "payload_original": {
                    "parametros": {
                        "tamano_poblacion": 100,
                        "generaciones": 50
                    },
                    "restricciones": {
                        "equidad": True,
                        "descansos": True
                    }
                }
        }

        default_data.update(custom_data)

        trabajo = TrabajoPlanificacion(**default_data)
        trabajo.full_clean()
        trabajo.save()
        return trabajo

    def test_cuando_trabajo_planificacion_tiene_datos_validos_deberia_crearse(self):
        id = uuid.uuid4()
        especialidad = Empleado.TipoEspecialidad.ENFERMERO

        trabajo = self.crear_trabajo(job_id=id, especialidad=especialidad)

        TrabajoPlanificacion.objects.get(job_id=id)
        self.assertIsNotNone(trabajo)
        self.assertEqual(trabajo.especialidad, especialidad)
        self.assertEqual(trabajo.plantilla_demanda, self.plantilla_demanda)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        trabajo = TrabajoPlanificacion()

        with self.assertRaises(ValidationError):
            trabajo.full_clean()

    def test_cuando_trabajo_planificado_es_creado_se_settea_la_fecha_de_creacion(self):
        self.crear_trabajo()

        trabajo = TrabajoPlanificacion.objects.get(especialidad=self.especialidad)
        self.assertIsNotNone(trabajo.fecha_creacion)

    def test_cuando_se_edita_trabajo_planificacion_con_datos_validos_deberia_actualizarse(self):
        trabajo = self.crear_trabajo()

        nueva_fecha_inicio = date(2025, 2, 1)
        nueva_fecha_fin = date(2025, 2, 28)
        nueva_especialidad = Empleado.TipoEspecialidad.ENFERMERO

        trabajo.fecha_inicio = nueva_fecha_inicio
        trabajo.fecha_fin = nueva_fecha_fin
        trabajo.especialidad = nueva_especialidad

        trabajo.full_clean()
        trabajo.save()

        trabajo_actualizado = TrabajoPlanificacion.objects.get(job_id=trabajo.job_id)

        self.assertEqual(nueva_fecha_inicio, trabajo_actualizado.fecha_inicio)
        self.assertEqual(nueva_fecha_fin, trabajo_actualizado.fecha_fin)
        self.assertEqual(nueva_especialidad, trabajo_actualizado.especialidad)

    def test_cuando_se_settea_plantilla_demanda_como_null_deberia_de_actualizarse(self):
        trabajo = self.crear_trabajo()

        self.plantilla_demanda.delete()

        trabajo_actualizado = TrabajoPlanificacion.objects.get(job_id=trabajo.job_id)
        self.assertIsNone(trabajo_actualizado.plantilla_demanda)