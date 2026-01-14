from django.test import TestCase
from datetime import date, time, timedelta
from rostering.models import (
    PlantillaDemanda, Empleado, ConfiguracionTurnos, TipoTurno, 
    Preferencia, ConfiguracionAlgoritmo
)
from rostering.services import generar_payload_ag

class TestServicesPayload(TestCase):
    
    def setUp(self):
        # Configuración mínima necesaria
        ConfiguracionAlgoritmo.objects.create(activa=True)
        ConfiguracionTurnos.objects.create(
            especialidad=Empleado.TipoEspecialidad.MEDICO, esquema='2x12', hora_inicio_base="08:00"
        )
        self.turno = TipoTurno.objects.create(
            nombre="G", abreviatura="G", especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8,0), hora_fin=time(20,0)
        )
        self.plantilla = PlantillaDemanda.objects.create(
            nombre="P", especialidad=Empleado.TipoEspecialidad.MEDICO
        )
        self.empleado = Empleado.objects.create(
            nombre_completo="Test User", legajo="T01", 
            especialidad=Empleado.TipoEspecialidad.MEDICO, activo=True
        )

    def test_equidad_preferencias_recorte_a_3(self):
        """
        Prueba que si un usuario carga 4 preferencias, el payload solo incluya las 3 últimas.
        """
        inicio = date(2026, 2, 1)
        fin = date(2026, 2, 28)
        
        # 1. Crear 4 preferencias cronológicamente (ID 1, 2, 3, 4)
        # La más vieja (ID 1) debería ser descartada.
        
        # Pref 1 (Vieja - Debería borrarse) - Día 5
        p1 = Preferencia.objects.create(
            empleado=self.empleado, fecha=inicio + timedelta(days=5),
            deseo='TRABAJAR', tipo_turno=self.turno
        )
        
        # Pref 2 (Nueva) - Día 10
        p2 = Preferencia.objects.create(
            empleado=self.empleado, fecha=inicio + timedelta(days=10),
            deseo='DESCANSAR', tipo_turno=self.turno
        )
        
        # Pref 3 (Nueva) - Día 15
        p3 = Preferencia.objects.create(
            empleado=self.empleado, fecha=inicio + timedelta(days=15),
            deseo='TRABAJAR', tipo_turno=None # Día libre completo
        )
        
        # Pref 4 (Más Nueva) - Día 20
        p4 = Preferencia.objects.create(
            empleado=self.empleado, fecha=inicio + timedelta(days=20),
            deseo='TRABAJAR', tipo_turno=self.turno
        )
        
        # 2. Generar Payload
        payload = generar_payload_ag(inicio, fin, Empleado.TipoEspecialidad.MEDICO, self.plantilla.id)
        
        # 3. Analizar 'excepciones_preferencias'
        prefs_payload = payload['datos_problema']['excepciones_preferencias']
        
        # A. Verificar cantidad
        self.assertEqual(len(prefs_payload), 3, "Debe haber exactamente 3 preferencias (límite de equidad).")
        
        # B. Verificar que días están presentes
        # Los días esperados son: 10, 15, 20 (índices relativos al inicio)
        dias_presentes = [p['dia'] for p in prefs_payload]
        
        self.assertNotIn(5, dias_presentes, "La preferencia más vieja (día 5) debió ser recortada.")
        self.assertIn(10, dias_presentes)
        self.assertIn(15, dias_presentes)
        self.assertIn(20, dias_presentes)

    def test_payload_estructura_basica(self):
        """Verifica que el JSON tenga las claves maestras requeridas por la API."""
        inicio = date(2026, 2, 1)
        fin = date(2026, 2, 5)
        
        payload = generar_payload_ag(inicio, fin, Empleado.TipoEspecialidad.MEDICO, self.plantilla.id)
        
        self.assertIn('config', payload)
        self.assertIn('datos_problema', payload)
        self.assertIn('estrategias', payload)
        
        datos = payload['datos_problema']
        self.assertEqual(datos['num_dias'], 5)
        self.assertIsInstance(datos['lista_profesionales'], list)
        self.assertEqual(len(datos['lista_profesionales']), 1) # Nuestro Dr. Test