from django.test import TestCase
from rostering.models import PlantillaDemanda, Empleado, ConfiguracionTurnos, TipoTurno, ReglaDemandaSemanal
from rostering.forms import ReglaDemandaSemanalForm
from datetime import time

class TestFormsLimitesReglas(TestCase):
    
    def setUp(self):
        # 1. Configuración Base (2x12)
        self.config = ConfiguracionTurnos.objects.create(
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            esquema='2x12', # Límite esperado: 14
            hora_inicio_base="08:00"
        )
        
        self.plantilla = PlantillaDemanda.objects.create(
            nombre="Plantilla Test",
            especialidad=Empleado.TipoEspecialidad.MEDICO
        )
        
        self.turno = TipoTurno.objects.create(
            nombre="Turno A", abreviatura="TA",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8,0), hora_fin=time(20,0)
        )

    def test_limite_14_reglas_esquema_2x12(self):
        # 1. Llenamos la plantilla con 14 reglas (el límite)
        for i in range(14):
            ReglaDemandaSemanal.objects.create(
                plantilla=self.plantilla,
                turno=self.turno,
                dias=[0], # Dummy
                cantidad_senior=1, cantidad_junior=1
            )
            
        # 2. Intentamos crear la regla #15 a través del FORM
        data = {
            'turno': self.turno.id,
            'cantidad_senior': 1,
            'cantidad_junior': 1,
            'dia_lunes': True # Equivale a dias=[0]
        }
        
        # Pasamos plantilla_id en kwargs como hace la vista
        form = ReglaDemandaSemanalForm(data=data, plantilla_id=self.plantilla.id)
        
        # 3. Verificamos que falle
        self.assertFalse(form.is_valid())
        self.assertIn("Límite alcanzado", form.non_field_errors()[0])
        self.assertIn("14 reglas", form.non_field_errors()[0])

    def test_limite_21_reglas_esquema_3x8(self):
        # 1. Cambiamos esquema a 3x8
        self.config.esquema = '3x8'
        self.config.save()
        
        # 2. Llenamos con 21 reglas
        for i in range(21):
            ReglaDemandaSemanal.objects.create(
                plantilla=self.plantilla,
                turno=self.turno,
                dias=[0],
                cantidad_senior=1, cantidad_junior=1
            )
            
        # 3. Intentamos crear la regla #22
        data = {'turno': self.turno.id, 'cantidad_senior': 1, 'cantidad_junior': 1, 'dia_lunes': True}
        form = ReglaDemandaSemanalForm(data=data, plantilla_id=self.plantilla.id)
        
        self.assertFalse(form.is_valid())
        self.assertIn("21 reglas", form.non_field_errors()[0])

    def test_permitir_edicion_aunque_limite_este_alcanzado(self):
        # 1. Llenamos al límite (14)
        reglas = []
        for i in range(14):
            r = ReglaDemandaSemanal.objects.create(
                plantilla=self.plantilla, turno=self.turno, dias=[0], cantidad_senior=1, cantidad_junior=1
            )
            reglas.append(r)
            
        una_regla_existente = reglas[0]
        
        # 2. Intentamos EDITAR esa regla (pasando instance)
        data = {'turno': self.turno.id, 'cantidad_senior': 5, 'cantidad_junior': 5, 'dia_lunes': True}
        
        form = ReglaDemandaSemanalForm(data=data, instance=una_regla_existente, plantilla_id=self.plantilla.id)
        
        # 3. Debería ser VÁLIDO (porque no estamos agregando, sino modificando)
        self.assertTrue(form.is_valid(), f"Errores: {form.errors}")