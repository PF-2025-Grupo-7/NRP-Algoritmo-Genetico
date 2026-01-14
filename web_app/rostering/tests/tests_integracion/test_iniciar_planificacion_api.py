import json
import uuid
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from unittest.mock import patch

from rostering.models import (
    TrabajoPlanificacion,
    PlantillaDemanda,
    Empleado,
    ConfiguracionTurnos, 
    TipoTurno
)


class ApiIniciarPlanificacionIntegrationTest(TestCase):
    """
    Tests de integración del endpoint:
    POST /api/planificar/iniciar/
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="tester",
            password="1234"
        )
        self.client.login(username="tester", password="1234")

        # Configuración de Turnos requerida
        ConfiguracionTurnos.objects.create(
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            esquema='2x12',
            hora_inicio_base="08:00"
        )

        self.plantilla = PlantillaDemanda.objects.create(
            nombre="Plantilla Test",
            especialidad=Empleado.TipoEspecialidad.MEDICO
        )

        self.emp1 = Empleado.objects.create(
            nombre_completo="Dr. House",
            legajo="EMP-001",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            max_turnos_mensuales=20
        )

        self.payload_valido = {
            "fecha_inicio": "2025-01-01",
            "fecha_fin": "2025-01-07",
            "especialidad": Empleado.TipoEspecialidad.MEDICO,
            "plantilla_id": self.plantilla.id
        }

        # CORRECCIÓN: Usamos el nombre exacto definido en urls.py
        self.url = reverse("api_iniciar_planificacion")

    @patch("rostering.views.iniciar_proceso_optimizacion")
    def test_iniciar_planificacion_ok(self, mock_proceso):
        # Simulamos éxito en el servicio
        mock_proceso.return_value = str(uuid.uuid4())

        response = self.client.post(
            self.url,
            data=json.dumps(self.payload_valido),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "started")
        self.assertIn("job_id", data)

    def test_iniciar_planificacion_json_invalido(self):
        response = self.client.post(
            self.url,
            data="esto no es json",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_iniciar_planificacion_faltan_parametros(self):
        response = self.client.post(
            self.url,
            data=json.dumps({
                "fecha_inicio": "2025-01-01"
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue("error" in response.json())

    def test_iniciar_planificacion_fecha_invalida(self):
        payload = self.payload_valido.copy()
        payload["fecha_inicio"] = "01-01-2025"

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_iniciar_planificacion_sin_login(self):
        self.client.logout()

        response = self.client.post(
            self.url,
            data=json.dumps(self.payload_valido),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 302)

    def test_iniciar_planificacion_get_no_permitido(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)