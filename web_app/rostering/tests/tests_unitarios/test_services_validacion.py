from django.test import TestCase
from datetime import date, time
from rostering.models import (
    PlantillaDemanda, Empleado, TipoTurno, ReglaDemandaSemanal, ConfiguracionTurnos
)
from rostering.services import validar_cobertura_suficiente

class TestServicesValidacion(TestCase):
    
    def setUp(self):
        # Setup básico
        ConfiguracionTurnos.objects.create(
            especialidad=Empleado.TipoEspecialidad.MEDICO, esquema='2x12', hora_inicio_base="08:00"
        )
        self.turno = TipoTurno.objects.create(
            nombre="G", abreviatura="G", especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8,0), hora_fin=time(20,0), duracion_horas=12
        )
        self.plantilla = PlantillaDemanda.objects.create(
            nombre="P", especialidad=Empleado.TipoEspecialidad.MEDICO
        )
        
        # Crear dotación pequeña: 1 Senior, 1 Junior
        self.emp_senior = Empleado.objects.create(
            nombre_completo="Senior 1", legajo="S1", 
            especialidad=Empleado.TipoEspecialidad.MEDICO, experiencia='SENIOR',
            min_turnos_mensuales=1, max_turnos_mensuales=20
        )
        self.emp_junior = Empleado.objects.create(
            nombre_completo="Junior 1", legajo="J1", 
            especialidad=Empleado.TipoEspecialidad.MEDICO, experiencia='JUNIOR',
            min_turnos_mensuales=1, max_turnos_mensuales=20
        )

    def test_validacion_pico_fisico_detecta_error(self):
        """
        Prueba que si pedimos 2 Seniors en un turno pero solo hay 1 en nómina,
        el sistema detecte el error de pico (aunque las horas mensuales sobren).
        """
        # Regla: Lunes pide 2 Seniors (Imposible, solo hay 1)
        ReglaDemandaSemanal.objects.create(
            plantilla=self.plantilla, turno=self.turno, dias=[0], # Lunes
            cantidad_senior=2, cantidad_junior=0
        )
        
        start = date(2026, 2, 2) # Lunes
        end = date(2026, 2, 2)   # Un solo día
        
        empleados = Empleado.objects.filter(especialidad=Empleado.TipoEspecialidad.MEDICO)
        
        es_valido, error = validar_cobertura_suficiente(start, end, empleados, self.plantilla)
        
        self.assertFalse(es_valido, "Debería fallar por pico físico")
        self.assertTrue(error.get('error_pico'), "El flag error_pico debe ser True")
        self.assertIn("Se piden 2 Seniors", error.get('mensaje'), "El mensaje debe ser específico")

    def test_validacion_demanda_excesiva_global(self):
        """
        Prueba que si pedimos 1 Senior todos los días del mes,
        pero el Senior solo puede trabajar 20 turnos máx, falle por horas.
        """
        # Regla: Todos los días 1 Senior
        ReglaDemandaSemanal.objects.create(
            plantilla=self.plantilla, turno=self.turno, dias=[0,1,2,3,4,5,6],
            cantidad_senior=1, cantidad_junior=0
        )
        
        # Mes completo (28 días)
        start = date(2026, 2, 1)
        end = date(2026, 2, 28)
        
        # Oferta Senior: 20 turnos * 12h = 240h
        # Demanda Senior: 28 turnos * 12h = 336h
        # Déficit: 96h -> Fallo
        
        empleados = Empleado.objects.filter(especialidad=Empleado.TipoEspecialidad.MEDICO)
        
        es_valido, error = validar_cobertura_suficiente(start, end, empleados, self.plantilla)
        
        self.assertFalse(es_valido, "Debería fallar por falta de horas globales")
        self.assertEqual(error['senior']['estado'], 'CRITICO')
        self.assertLess(error['senior']['balance'], 0, "El balance debe ser negativo")
        
    def test_validacion_exito_con_holgura(self):
        """Prueba un caso que sí debería pasar."""
        # Regla: Solo lunes 1 Senior
        ReglaDemandaSemanal.objects.create(
            plantilla=self.plantilla, turno=self.turno, dias=[0],
            cantidad_senior=1, cantidad_junior=0
        )
        
        start = date(2026, 2, 1)
        end = date(2026, 2, 7) # 1 semana
        
        empleados = Empleado.objects.filter(especialidad=Empleado.TipoEspecialidad.MEDICO)
        es_valido, _ = validar_cobertura_suficiente(start, end, empleados, self.plantilla)
        
        self.assertTrue(es_valido, "Debería ser válido (1 turno vs capacidad de 20)")