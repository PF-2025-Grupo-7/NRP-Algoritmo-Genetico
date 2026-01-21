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

    def test_payload_rellena_huecos_con_ceros(self):
        """
        Prueba crítica: Si la plantilla NO tiene reglas para un día (ej: Domingo),
        el payload debe generar explícitamente {senior:0, junior:0} para ese día,
        en lugar de dejar un objeto vacío {} que rompería al motor.
        """
        # 1. Crear un segundo turno para que sea más realista (Mañana y Noche)
        turno_noche = TipoTurno.objects.create(
            nombre="Noche", abreviatura="N", especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(20,0), hora_fin=time(8,0), es_nocturno=True
        )
        
        # 2. Definir un rango de 3 días: Viernes (4), Sábado (5), Domingo (6)
        # Usamos fechas reales: 2026-02-06 (Viernes) a 2026-02-08 (Domingo)
        inicio = date(2026, 2, 6)
        fin = date(2026, 2, 8)
        
        # 3. Crear Regla SOLO para Viernes (día 4 de la semana)
        # Sábado y Domingo quedan "huecos"
        from rostering.models import ReglaDemandaSemanal
        ReglaDemandaSemanal.objects.create(
            plantilla=self.plantilla,
            turno=self.turno,
            dias=[4], # Solo viernes
            cantidad_senior=1, cantidad_junior=1
        )
        # Regla para el turno noche también solo viernes
        ReglaDemandaSemanal.objects.create(
            plantilla=self.plantilla,
            turno=turno_noche,
            dias=[4], 
            cantidad_senior=1, cantidad_junior=1
        )
        
        # 4. Generar Payload
        payload = generar_payload_ag(inicio, fin, Empleado.TipoEspecialidad.MEDICO, self.plantilla.id)
        reqs = payload['datos_problema']['requerimientos_cobertura_explicita']
        
        self.assertEqual(len(reqs), 3, "Debe haber 3 días en la lista")
        
        # 5. Verificar Viernes (Debe tener demanda > 0)
        viernes = reqs[0]
        self.assertEqual(viernes[str(self.turno.id)]['senior'], 1)
        
        # 6. Verificar Sábado (Debe tener ceros explícitos, NO estar vacío)
        sabado = reqs[1]
        self.assertIn(str(self.turno.id), sabado, "El sábado debe tener la clave del turno día")
        self.assertIn(str(turno_noche.id), sabado, "El sábado debe tener la clave del turno noche")
        self.assertEqual(sabado[str(self.turno.id)]['senior'], 0, "Debe ser 0 explícito")
        self.assertEqual(sabado[str(self.turno.id)]['junior'], 0, "Debe ser 0 explícito")
        
        # 7. Verificar Domingo (Igual)
        domingo = reqs[2]
        self.assertEqual(domingo[str(self.turno.id)]['senior'], 0)