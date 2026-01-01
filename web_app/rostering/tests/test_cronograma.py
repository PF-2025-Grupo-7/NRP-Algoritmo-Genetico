from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import Cronograma, Empleado, PlantillaDemanda, ConfiguracionAlgoritmo
from datetime import date

class TestCronograma(TestCase):

    def setUp(self):
        self.especialidad_medico = Empleado.TipoEspecialidad.MEDICO

        self.fecha_inicio = date(2026, 1, 1)
        self.fecha_fin = date(2026, 1, 31)

        self.plantilla_medico = PlantillaDemanda.objects.create(
            nombre="Demanda Médicos Enero",
            especialidad=self.especialidad_medico
        )

        self.plantilla_enfermero = PlantillaDemanda.objects.create(
            nombre="Demanda Enfermeros Enero",
            especialidad= Empleado.TipoEspecialidad.ENFERMERO
        )

        self.configuracion = ConfiguracionAlgoritmo.objects.create(
            nombre="Config Test"
        )

    def crear_cronograma(self, **custom_data):
        default_data = {
            "especialidad": self.especialidad_medico,
            "fecha_inicio": self.fecha_inicio,
            "fecha_fin": self.fecha_fin,
            "estado": Cronograma.Estado.BORRADOR,
            "plantilla_demanda": self.plantilla_medico,
            "configuracion_usada": self.configuracion,
            "fitness": 1.7,
            "tiempo_ejecucion": 115,
            "reporte_analisis": {
                "violaciones": {
                    "preferencias_no_respetadas": 2,
                },
                "equidad": {
                    "desvio": 1.3
                }
        }
        }

        default_data.update(custom_data)

        cronograma = Cronograma(**default_data)
        cronograma.full_clean()
        cronograma.save()
        return cronograma
    
    def test_cuando_cronograma_tiene_datos_validos_deberia_crearse(self):
        fecha_inicio = date(2026, 2, 1)
        fecha_fin = date(2026, 2, 28)

        cronograma = self.crear_cronograma(fecha_inicio=fecha_inicio,fecha_fin=fecha_fin)

        cronograma = Cronograma.objects.get(fecha_inicio=fecha_inicio)
        self.assertIsNotNone(cronograma)
        self.assertEqual(cronograma.fecha_fin, fecha_fin)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        cronograma = Cronograma()

        with self.assertRaises(ValidationError):
            cronograma.full_clean()

    def test_cuando_no_tiene_datos_deberia_usar_valores_por_defecto(self):
        Cronograma.objects.create(
            especialidad=self.especialidad_medico,
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin
        )

        cronograma = Cronograma.objects.get(fecha_inicio=self.fecha_inicio)
        self.assertEqual(cronograma.estado, Cronograma.Estado.BORRADOR)

    def test_cuando_plantilla_no_corresponde_a_especialidad_de_cronograma_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_cronograma(
                especialidad=self.especialidad_medico,
                plantilla_demanda=self.plantilla_enfermero
            )

    def test_fecha_inicio_y_fin_iguales_es_valido(self):
        self.crear_cronograma(
            fecha_inicio=date(2025, 1, 10),
            fecha_fin=date(2025, 1, 10)
        )

        cronograma = Cronograma.objects.get(especialidad=self.especialidad_medico)
        self.assertEqual(cronograma.fecha_fin, cronograma.fecha_inicio)

    def test_fecha_fin_anterior_a_fecha_inicio_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_cronograma(fecha_inicio=date(2025, 1, 20),fecha_fin=date(2025, 1, 10))

    def test_cuando_cronograma_es_creado_se_settea_la_fecha_de_creacion(self):
        self.crear_cronograma()

        cronograma = Cronograma.objects.get(especialidad=self.especialidad_medico)
        self.assertIsNotNone(cronograma.fecha_creacion)
