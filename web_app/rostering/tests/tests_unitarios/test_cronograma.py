from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import Cronograma, Empleado, PlantillaDemanda, ConfiguracionAlgoritmo
from datetime import date, timedelta

class TestCronograma(TestCase):

    def setUp(self):
        self.especialidad_medico = Empleado.TipoEspecialidad.MEDICO
        self.especialidad_enfermero = Empleado.TipoEspecialidad.ENFERMERO

        self.fecha_inicio = date(2026, 1, 1)
        self.fecha_fin = date(2026, 1, 31)

        self.plantilla_medico = PlantillaDemanda.objects.create(
            nombre="Demanda Médicos Enero",
            especialidad=self.especialidad_medico
        )

        self.plantilla_enfermero = PlantillaDemanda.objects.create(
            nombre="Demanda Enfermeros Enero",
            especialidad= self.especialidad_enfermero
        )

        self.configuracion = ConfiguracionAlgoritmo.objects.create(
            nombre="Config Test"
        )

        self.configuracion2 = ConfiguracionAlgoritmo.objects.create(
            nombre="Config Test2"
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

    def test_cuando_se_edita_cronograma_con_datos_validos_deberia_actualizarse(self):
        cronograma = self.crear_cronograma()

        nueva_fecha_inicio = date(2026, 2, 1)
        nueva_fecha_fin = date(2026, 2, 28)

        nuevo_reporte = {
            "violaciones": {
                "preferencias_no_respetadas": 5,
                "descansos_insuficientes": 1
            },
            "equidad": {
                "desvio": 0.9,
                "max_diff": 2
            }
        }

        cronograma.especialidad = self.especialidad_enfermero
        cronograma.fecha_inicio = nueva_fecha_inicio
        cronograma.fecha_fin = nueva_fecha_fin
        cronograma.estado = Cronograma.Estado.PUBLICADO
        cronograma.plantilla_demanda = self.plantilla_enfermero
        cronograma.configuracion_usada = self.configuracion2
        cronograma.fitness = 2.35
        cronograma.tiempo_ejecucion = 98.4
        cronograma.reporte_analisis = nuevo_reporte

        cronograma.full_clean()
        cronograma.save()

        cronograma_editado = Cronograma.objects.get(pk=cronograma.pk)
        self.assertEqual(self.especialidad_enfermero, cronograma_editado.especialidad)
        self.assertEqual(nueva_fecha_inicio, cronograma_editado.fecha_inicio)
        self.assertEqual(nueva_fecha_fin, cronograma_editado.fecha_fin)
        self.assertEqual(Cronograma.Estado.PUBLICADO, cronograma_editado.estado)
        self.assertEqual(self.plantilla_enfermero, cronograma_editado.plantilla_demanda)
        self.assertEqual(self.configuracion2, cronograma_editado.configuracion_usada)
        self.assertEqual(2.35, cronograma_editado.fitness)
        self.assertEqual(98.4, cronograma_editado.tiempo_ejecucion)
        self.assertEqual(nuevo_reporte, cronograma_editado.reporte_analisis)

    def test_cuando_se_edita_fecha_fin_anterior_a_inicio_deberia_fallar(self):
        cronograma = self.crear_cronograma()

        cronograma.fecha_inicio = date(2026, 3, 10)
        cronograma.fecha_fin = date(2026, 3, 1)

        with self.assertRaises(ValidationError):
            cronograma.full_clean()

    def test_cuando_se_edita_plantilla_con_especialidad_incorrecta_deberia_fallar(self):
        cronograma = self.crear_cronograma()

        cronograma.plantilla_demanda = self.plantilla_enfermero

        with self.assertRaises(ValidationError):
            cronograma.full_clean()

    def test_cuando_se_quita_plantilla_demanda_deberia_ser_valido(self):
        cronograma = self.crear_cronograma()

        cronograma.plantilla_demanda = None
        cronograma.full_clean()
        cronograma.save()

        cronograma_editado = Cronograma.objects.get(pk=cronograma.pk)
        self.assertIsNone(cronograma_editado.plantilla_demanda)

    def test_cuando_se_edita_cronograma_la_fecha_de_creacion_no_deberia_cambiar(self):
        self.crear_cronograma()
        cronograma = Cronograma.objects.get(especialidad=self.especialidad_medico)

        cronograma.fecha_fin = cronograma.fecha_inicio + timedelta(days=1)

        cronograma_editado = Cronograma.objects.get(pk = cronograma.pk)
        self.assertEqual(cronograma_editado.fecha_creacion, cronograma.fecha_creacion)
