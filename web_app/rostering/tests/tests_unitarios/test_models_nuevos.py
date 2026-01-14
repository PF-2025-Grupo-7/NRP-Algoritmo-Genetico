from django.test import TestCase
from django.db import IntegrityError
from rostering.models import (
    ConfiguracionTurnos, Empleado, ExcepcionDemanda, 
    PlantillaDemanda, TipoTurno, ConfiguracionAlgoritmo
)
from datetime import date, time

class TestModelosNuevos(TestCase):

    def setUp(self):
        self.plantilla = PlantillaDemanda.objects.create(
            nombre="Plantilla Base", especialidad=Empleado.TipoEspecialidad.MEDICO
        )
        self.turno = TipoTurno.objects.create(
            nombre="Guardia", abreviatura="G", especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8,0), hora_fin=time(20,0)
        )

    # 1. Test ConfiguracionTurnos (Singleton lógico)
    def test_configuracion_turnos_unica_por_especialidad(self):
        """No debería ser posible tener dos configs para MEDICO."""
        ConfiguracionTurnos.objects.create(
            especialidad=Empleado.TipoEspecialidad.MEDICO, esquema='2x12', hora_inicio_base="08:00"
        )
        
        with self.assertRaises(IntegrityError):
            ConfiguracionTurnos.objects.create(
                especialidad=Empleado.TipoEspecialidad.MEDICO, # Repetida
                esquema='3x8', hora_inicio_base="06:00"
            )

    # 2. Test ExcepcionDemanda (Campo Nuevo)
    def test_excepcion_demanda_flag_dificil(self):
        """Verifica que el campo es_turno_dificil se persista correctamente."""
        excepcion = ExcepcionDemanda.objects.create(
            plantilla=self.plantilla,
            fecha=date(2025, 12, 25), # Navidad
            turno=self.turno,
            cantidad_senior=2, cantidad_junior=2,
            es_turno_dificil=True # <--- Lo que probamos
        )
        
        excepcion.refresh_from_db()
        self.assertTrue(excepcion.es_turno_dificil)
        
        # Probar default
        excepcion_normal = ExcepcionDemanda.objects.create(
            plantilla=self.plantilla,
            fecha=date(2025, 1, 15),
            turno=self.turno,
            cantidad_senior=1, cantidad_junior=1
        )
        self.assertFalse(excepcion_normal.es_turno_dificil)

    # 3. Test ConfiguracionAlgoritmo (Lógica Singleton Activa)
    def test_configuracion_algoritmo_solo_una_activa(self):
        """Al activar una nueva config, la anterior debe desactivarse automáticamente."""
        config_A = ConfiguracionAlgoritmo.objects.create(nombre="Config A", activa=True)
        
        self.assertTrue(config_A.activa)
        
        # Creamos B activa
        config_B = ConfiguracionAlgoritmo.objects.create(nombre="Config B", activa=True)
        
        # Refrescamos A desde la DB
        config_A.refresh_from_db()
        
        self.assertTrue(config_B.activa)
        self.assertFalse(config_A.activa, "Config A debió desactivarse automáticamente.")
        
        # Caso edición: Si reactivo A, B se apaga
        config_A.activa = True
        config_A.save()
        
        config_B.refresh_from_db()
        self.assertFalse(config_B.activa, "Config B debió desactivarse.")