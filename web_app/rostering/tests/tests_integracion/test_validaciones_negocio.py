from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
import json

from rostering.models import PlantillaDemanda, Empleado


class ValidacionesNegocioIntegrationTest(TestCase):
    """
    Tests de integración de validaciones de negocio al iniciar planificación.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin", password="password"
        )
        self.client.login(username="admin", password="password")

        self.url = reverse("api_iniciar_planificacion")

        self.plantilla = PlantillaDemanda.objects.create(
            nombre="Plantilla Prueba",
            especialidad=Empleado.TipoEspecialidad.MEDICO
        )

    def test_fecha_fin_anterior_a_inicio(self):
        payload = {
            "fecha_inicio": "2025-12-31",
            "fecha_fin": "2025-01-01",
            "especialidad": Empleado.TipoEspecialidad.MEDICO,
            "plantilla_id": self.plantilla.id
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("debe ser posterior", response.json().get("error", "").lower())

    def test_sin_empleados_disponibles(self):
        payload = {
            "fecha_inicio": "2025-01-01",
            "fecha_fin": "2025-01-07",
            "especialidad": Empleado.TipoEspecialidad.UCI,
            "plantilla_id": self.plantilla.id
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
