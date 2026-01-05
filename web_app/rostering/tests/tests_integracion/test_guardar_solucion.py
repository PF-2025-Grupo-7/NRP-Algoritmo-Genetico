from django.test import TestCase
from datetime import date, time
import uuid

from rostering.models import (
    TrabajoPlanificacion,
    PlantillaDemanda,
    Empleado,
    ConfiguracionAlgoritmo,
    TipoTurno,
)
from rostering.views import guardar_solucion_db


class PersistenciaResultadoIntegrationTest(TestCase):
    """
    Tests de integración de la persistencia del resultado del motor.
    """

    def setUp(self):
        ConfiguracionAlgoritmo.objects.create(nombre="Test Config", activa=True)

        self.plantilla = PlantillaDemanda.objects.create(
            nombre="Plantilla Base",
            especialidad=Empleado.TipoEspecialidad.MEDICO
        )
        
        self.emp1 = Empleado.objects.create(
            nombre_completo="Dr. House", 
            legajo="EMP-001", 
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            max_turnos_mensuales=20
        )
        self.emp2 = Empleado.objects.create(
            nombre_completo="Dra. Cuddy", 
            legajo="EMP-002", 
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            max_turnos_mensuales=20
        )

        self.turno_m = TipoTurno.objects.create(
            nombre="Mañana",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            duracion_horas=12.0,
            hora_inicio=time(8, 0),
            hora_fin=time(20, 0),
        )

        self.payload_simulado = {
            'datos_problema': {
                'lista_profesionales': [
                    {'id_db': self.emp1.id},
                    {'id_db': self.emp2.id}
                ]
            }
        }

        self.trabajo = TrabajoPlanificacion.objects.create(
            job_id=str(uuid.uuid4()),
            fecha_inicio=date(2025, 1, 1),
            fecha_fin=date(2025, 1, 2), # 2 días para el test
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            plantilla_demanda=self.plantilla,
            payload_original=self.payload_simulado
        )

    def test_guarda_cronograma_y_asignaciones(self):
        resultado_motor = {
            "fitness": 0.95,
            "tiempo_ejecucion": 1.5,
            "matriz_solucion": [
                [self.turno_m.id, 0], # Emp 1 trabaja día 1, no día 2
                [0, self.turno_m.id], # Emp 2 no día 1, trabaja día 2
            ],
            "explicabilidad": {"datos_equidad": {}}
        }

        cronograma = guardar_solucion_db(
            fecha_inicio=self.trabajo.fecha_inicio,
            fecha_fin=self.trabajo.fecha_fin,
            especialidad=self.trabajo.especialidad,
            payload_original=self.payload_simulado,
            resultado=resultado_motor,
            plantilla_demanda=self.plantilla
        )

        self.assertIsNotNone(cronograma.id)
        self.assertEqual(float(cronograma.fitness), 0.95)
        self.assertEqual(cronograma.asignaciones.count(), 2)
        
        # Verificar que se guardó el reporte de explicabilidad
        self.assertIn('nombres_profesionales', cronograma.reporte_analisis['datos_equidad'])

    def test_matriz_vacia_lanza_error(self):
        with self.assertRaises(ValueError):
            guardar_solucion_db(
                self.trabajo.fecha_inicio,
                self.trabajo.fecha_fin,
                self.trabajo.especialidad,
                self.trabajo.payload_original,
                {"fitness": 0}
            )
