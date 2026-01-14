from django.test import TestCase
from django.urls import reverse

from rostering.models import PlantillaDemanda, Empleado


class ApiPlantillasIntegrationTest(TestCase):
    """
    Tests de integración del endpoint:
    GET /api/plantillas/
    """

    def setUp(self):
        self.plantilla_medico_1 = PlantillaDemanda.objects.create(
            nombre="Demanda Test 1",
            especialidad=Empleado.TipoEspecialidad.MEDICO
        )
        self.plantilla_medico_2 = PlantillaDemanda.objects.create(
            nombre="Demanda Test 2",
            especialidad=Empleado.TipoEspecialidad.MEDICO
        )
        self.plantilla_enfermero = PlantillaDemanda.objects.create(
            nombre="Demanda Test 3",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO
        )

    def test_filtra_por_especialidad(self):
        url = reverse("api_get_plantillas")

        response = self.client.get(url, {
            "especialidad": Empleado.TipoEspecialidad.MEDICO
        })

        self.assertEqual(len(response.json()["plantillas"]), 2)

    def test_especialidad_sin_resultados_devuelve_lista_vacia(self):
        url = reverse("api_get_plantillas")

        response = self.client.get(url, {
            "especialidad": Empleado.TipoEspecialidad.UCI
        })

        self.assertEqual(response.json()["plantillas"], [])

    def test_sin_especialidad_devuelve_vacio(self):
        response = self.client.get(reverse("api_get_plantillas"))
        self.assertEqual(response.json()["plantillas"], [])

    def test_especialidad_invalida_devuelve_vacio(self):
        url = reverse("api_get_plantillas")

        response = self.client.get(
            url,
            {"especialidad": 'INVALIDO'}
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["plantillas"], [])
