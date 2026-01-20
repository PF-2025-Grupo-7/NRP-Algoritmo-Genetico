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

    def test_cuando_generaciones_es_menor_a_1_deberia_fallar(self):
        """El mínimo ahora es 1, así que probamos con 0 para forzar el error."""
        with self.assertRaises(ValidationError):
            self.crear_configuracion(generaciones=0)

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

    def test_cuando_estrategia_cruce_invalida_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_configuracion(estrategia_cruce="no_existe")

    def test_cuando_estrategia_mutacion_invalida_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_configuracion(estrategia_mutacion="no_existe")

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

    def test_cuando_se_edita_configuracion_con_datos_validos_deberia_actualizarse(self):
        config = self.crear_configuracion()

        config.nombre = "Configuración Editada"
        config.activa = False
        config.tamano_poblacion = 200
        config.generaciones = 30
        config.prob_cruce = 0.9
        config.prob_mutacion = 0.1
        config.elitismo = False
        config.semilla = 12345
        config.estrategia_seleccion = ConfiguracionAlgoritmo.EstrategiaSeleccion.RANKING
        config.estrategia_cruce = ConfiguracionAlgoritmo.EstrategiaCruce.DOS_PUNTOS
        config.estrategia_mutacion = ConfiguracionAlgoritmo.EstrategiaMutacion.INTERCAMBIO
        config.peso_equidad_general = 2.0
        config.peso_equidad_dificil = 3.0
        config.peso_preferencia_dias_libres = 1.0
        config.peso_preferencia_turno = 0.8
        config.factor_alpha_pte = 0.75
        config.tolerancia_general = 10
        config.tolerancia_dificil = 6

        config.full_clean()
        config.save()
        config_refrescada = ConfiguracionAlgoritmo.objects.get(pk=config.pk)

        self.assertEqual("Configuración Editada", config_refrescada.nombre)
        self.assertFalse(config_refrescada.activa)
        self.assertEqual(200, config_refrescada.tamano_poblacion)
        self.assertEqual(30, config_refrescada.generaciones)
        self.assertEqual(0.9, config_refrescada.prob_cruce)
        self.assertEqual(0.1, config_refrescada.prob_mutacion)
        self.assertFalse(config_refrescada.elitismo)
        self.assertEqual(12345, config_refrescada.semilla)
        self.assertEqual(
            ConfiguracionAlgoritmo.EstrategiaSeleccion.RANKING,
            config_refrescada.estrategia_seleccion
        )
        self.assertEqual(
            ConfiguracionAlgoritmo.EstrategiaCruce.DOS_PUNTOS,
            config_refrescada.estrategia_cruce
        )
        self.assertEqual(
            ConfiguracionAlgoritmo.EstrategiaMutacion.INTERCAMBIO,
            config_refrescada.estrategia_mutacion
        )
        self.assertEqual(2.0, config_refrescada.peso_equidad_general)
        self.assertEqual(3.0, config_refrescada.peso_equidad_dificil)
        self.assertEqual(1.0, config_refrescada.peso_preferencia_dias_libres)
        self.assertEqual(0.8, config_refrescada.peso_preferencia_turno)
        self.assertEqual(0.75, config_refrescada.factor_alpha_pte)
        self.assertEqual(10, config_refrescada.tolerancia_general)
        self.assertEqual(6, config_refrescada.tolerancia_dificil)

    def test_cuando_se_edita_tamano_poblacion_a_valor_invalido_deberia_fallar(self):
        config = self.crear_configuracion()

        config.tamano_poblacion = 5

        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_cuando_se_edita_estrategia_seleccion_invalida_deberia_fallar(self):
        config = self.crear_configuracion()

        config.estrategia_seleccion = "invalida"

        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_cuando_se_edita_estrategia_cruce_invalida_deberia_fallar(self):
        config = self.crear_configuracion()

        config.estrategia_cruce = "invalida"

        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_cuando_se_edita_estrategia_mutacion_invalida_deberia_fallar(self):
        config = self.crear_configuracion()

        config.estrategia_mutacion = "invalida"

        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_cuando_se_edita_configuracion_inactiva_a_activa_deberia_desactivar_la_actual(self):
        config_activa = self.crear_configuracion(nombre="Activa", activa=True)
        config_inactiva = self.crear_configuracion(nombre="Inactiva", activa=False)

        config_inactiva.activa = True
        config_inactiva.full_clean()
        config_inactiva.save()

        config_activa_inactiva = ConfiguracionAlgoritmo.objects.get(pk = config_activa.pk)
        config_inactiva_activa = ConfiguracionAlgoritmo.objects.get(pk = config_inactiva.pk)

        self.assertFalse(config_activa_inactiva.activa)
        self.assertTrue(config_inactiva_activa.activa)

    def test_cuando_se_edita_configuracion_activa_a_inactiva_no_deberia_activar_otra(self):
        config_1 = self.crear_configuracion(nombre="Config 1", activa=True)
        config_2 = self.crear_configuracion(nombre="Config 2", activa=False)

        config_1.activa = False
        config_1.full_clean()
        config_1.save()

        config_1_inactiva = ConfiguracionAlgoritmo.objects.get(pk = config_1.pk)
        config_2_inactiva = ConfiguracionAlgoritmo.objects.get(pk = config_2.pk)

        self.assertFalse(config_1_inactiva.activa)
        self.assertFalse(config_2_inactiva.activa)

    def test_cuando_se_edita_generacion_a_valor_invalido_deberia_fallar(self):
        config = self.crear_configuracion()
        config.generaciones = 0  # Antes probábamos con 5, ahora 0 es el inválido
        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_cuando_se_edita_prob_cruce_a_valor_invalido_deberia_fallar(self):
        config = self.crear_configuracion()

        config.tamano_poblacion = 1.01
 
        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_cuando_se_edita_prob_mutacion_a_valor_invalido_deberia_fallar(self):
        config = self.crear_configuracion()

        config.tamano_poblacion = -0.01

        with self.assertRaises(ValidationError):
            config.full_clean()
