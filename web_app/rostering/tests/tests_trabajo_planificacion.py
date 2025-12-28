from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import TrabajoPlanificacion, Empleado
from datetime import date
import uuid

class TestTrabajoPlanificacion(TestCase):

    def setUp(self):
        self.especialidad = Empleado.TipoEspecialidad.MEDICO
    
    def crear_trabajo(self, **custom_data):
        default_data = {
            "job_id": uuid.uuid4(),
            "fecha_inicio": date(2025, 1, 1),
            "fecha_fin": date(2025, 1, 31),
            "especialidad": self.especialidad,
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

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        trabajo = TrabajoPlanificacion()

        with self.assertRaises(ValidationError):
            trabajo.full_clean()

    def test_cuando_trabajo_planificado_es_creado_se_settea_la_fecha_de_creacion(self):
        self.crear_trabajo()

        trabajo = TrabajoPlanificacion.objects.get(especialidad=self.especialidad)
        self.assertIsNotNone(trabajo.fecha_creacion)
