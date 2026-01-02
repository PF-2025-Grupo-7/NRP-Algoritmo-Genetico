from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from rostering.models import ConfiguracionAlgoritmo

class TestConfiguracionAlgoritmo(TestCase):

    def setUp(self):
        self.nombre = "Configuración Test"

    def crear_configuracion(self, **custom_data):
        default_data = {
            "nombre": self.nombre,
            "activa": True,
            "tamano_poblacion": 100,
            "generaciones": 15,
            "prob_cruce": 0.85,
            "prob_mutacion": 0.20,
            "elitismo": True,
            "semilla": None,
            "estrategia_seleccion": ConfiguracionAlgoritmo.EstrategiaSeleccion.TORNEO,
            "estrategia_cruce": ConfiguracionAlgoritmo.EstrategiaCruce.BLOQUES_VERTICALES,
            "estrategia_mutacion": ConfiguracionAlgoritmo.EstrategiaMutacion.HIBRIDA,
            "peso_equidad_general": 1.0,
            "peso_equidad_dificil": 1.5,
            "peso_preferencia_dias_libres": 2.0,
            "peso_preferencia_turno": 0.5,
            "factor_alpha_pte": 0.5,
            "tolerancia_general": 8,
            "tolerancia_dificil": 4,
        }

        default_data.update(custom_data)

        config = ConfiguracionAlgoritmo(**default_data)
        config.full_clean()
        config.save()
        return config
    
    def test_cuando_configuracion_tiene_datos_validos_deberia_crearse(self):
        nombre = "Config Principal"
        activa = False

        self.crear_configuracion(nombre=nombre, activa=activa)

        config = ConfiguracionAlgoritmo.objects.get(nombre=nombre)
        self.assertIsNotNone(config)
        self.assertFalse(config.activa)

    def test_cuando_no_se_pasan_parametros_deberia_usar_valores_por_defecto(self):
        config = ConfiguracionAlgoritmo.objects.create()
        config.full_clean()

        self.assertEqual("Configuración Estándar", config.nombre)
        self.assertTrue(config.activa)
        self.assertEqual(100, config.tamano_poblacion)
        self.assertEqual(15, config.generaciones)
        self.assertEqual(0.85, config.prob_cruce)
        self.assertEqual(0.20, config.prob_mutacion)
        self.assertTrue(config.elitismo)
        self.assertIsNone(config.semilla)
        self.assertEqual(ConfiguracionAlgoritmo.EstrategiaSeleccion.TORNEO, config.estrategia_seleccion)
        self.assertEqual(ConfiguracionAlgoritmo.EstrategiaCruce.BLOQUES_VERTICALES, config.estrategia_cruce)
        self.assertEqual(ConfiguracionAlgoritmo.EstrategiaMutacion.HIBRIDA, config.estrategia_mutacion)
        self.assertEqual(1.0, config.peso_equidad_general)
        self.assertEqual(1.5, config.peso_equidad_dificil)
        self.assertEqual(2.0, config.peso_preferencia_dias_libres)
        self.assertEqual(0.5, config.peso_preferencia_turno)
        self.assertEqual(0.5, config.factor_alpha_pte)
        self.assertEqual(8, config.tolerancia_general)
        self.assertEqual(4, config.tolerancia_dificil)

    def test_cuando_tamano_poblacion_es_menor_a_10_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_configuracion(tamano_poblacion=5)

    def test_cuando_generaciones_es_menor_a_10_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_configuracion(generaciones=5)

    def test_cuando_prob_cruce_esta_fuera_de_rango_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_configuracion(prob_cruce=1.5)

    def test_cuando_prob_mutacion_es_negativo_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_configuracion(prob_mutacion=-0.1)

    def test_cuando_factor_alpha_esta_fuera_de_rango_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_configuracion(factor_alpha_pte=1.2)

    def test_cuando_estrategia_seleccion_invalida_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_configuracion(estrategia_seleccion="no_existe")

    def test_cuando_se_crea_una_nueva_configuracion_activa_deberia_desactivar_la_anterior(self):
        nombre_1 = "Config 1"
        nombre_2 = "Config 2"
        
        self.crear_configuracion(nombre=nombre_1, activa=True)
        self.crear_configuracion(nombre=nombre_2, activa=True)

        config_1 = ConfiguracionAlgoritmo.objects.get(nombre=nombre_1)
        config_2 = ConfiguracionAlgoritmo.objects.get(nombre=nombre_2)
        self.assertFalse(config_1.activa)
        self.assertTrue(config_2.activa)

    def test_cuando_hay_multiples_configuraciones_inactivas_no_deberia_fallar(self):
        self.crear_configuracion(nombre="Config 1", activa=False)
        self.crear_configuracion(nombre="Config 2", activa=False)

        self.assertEqual(2, ConfiguracionAlgoritmo.objects.filter(activa=False).count())
