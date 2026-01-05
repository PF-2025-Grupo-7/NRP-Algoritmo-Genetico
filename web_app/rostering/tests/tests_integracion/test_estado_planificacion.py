from django.test import TestCase, Client
from unittest.mock import patch
from datetime import date
import uuid

from rostering.models import TrabajoPlanificacion


class EstadoPlanificacionIntegrationTest(TestCase):
    """
    Tests de integración del endpoint:
    GET /api/planificar/estado/<job_id>/
    """

    def setUp(self):
        self.client = Client()
        self.job_id = str(uuid.uuid4())

        self.trabajo = TrabajoPlanificacion.objects.create(
            job_id=self.job_id,
            fecha_inicio=date(2025, 1, 1),
            fecha_fin=date(2025, 1, 7),
            especialidad="ENFERMERO",
            payload_original={"datos_problema": {"lista_profesionales": []}},
            plantilla_demanda=None
        )

        self.url = f"/api/planificar/estado/{self.job_id}/"

    def test_estado_job_no_existe(self):
        response = self.client.get(f"/api/planificar/estado/{str(uuid.uuid4())}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["error"],
            "Job ID no encontrado o expirado."
        )

    @patch("rostering.views.consultar_resultado_ag")
    def test_estado_error_conexion_motor(self, mock_consultar):
        mock_consultar.return_value = None

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)

        data = response.json()
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(data["mensaje"], "Error de conexión")

    @patch("rostering.views.consultar_resultado_ag")
    def test_estado_failed_motor(self, mock_consultar):
        mock_consultar.return_value = {
            "status": "error",
            "error": "API Error: 404"
        }

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")

    @patch("rostering.views.consultar_resultado_ag")
    def test_estado_running_no_elimina_trabajo(self, mock_consultar):
        mock_consultar.return_value = {"status": "running"}

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            TrabajoPlanificacion.objects.filter(job_id=self.job_id).exists()
        )

    @patch("rostering.views.guardar_solucion_db")
    @patch("rostering.views.consultar_resultado_ag")
    def test_estado_completed_persiste_y_limpia(self, mock_consultar, mock_guardar):
        mock_consultar.return_value = {
            "status": "completed",
            "fitness": 123.45
        }

        class DummyCronograma:
            id = 99

        mock_guardar.return_value = DummyCronograma()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            TrabajoPlanificacion.objects.filter(job_id=self.job_id).exists()
        )

    @patch("rostering.views.guardar_solucion_db")
    @patch("rostering.views.consultar_resultado_ag")
    def test_estado_error_guardando_resultado(self, mock_consultar, mock_guardar):
        mock_consultar.return_value = {
            "status": "completed",
            "fitness": 10
        }

        mock_guardar.side_effect = Exception("DB explotó")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 500)
