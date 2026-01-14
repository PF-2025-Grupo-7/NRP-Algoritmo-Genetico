from django.test import TestCase
from rostering.forms import (
    ConfiguracionTurnosForm, 
    PlantillaDemandaUpdateForm, 
    ReglaDemandaSemanalForm,
    ExcepcionDemandaForm,
    ConfiguracionSimpleForm
)
from rostering.models import (
    PlantillaDemanda, Empleado, TipoTurno, ConfiguracionAlgoritmo, ReglaDemandaSemanal, ConfiguracionTurnos
)
from datetime import time

class TestFormsGeneral(TestCase):

    def setUp(self):
        # Datos base para los tests
        self.plantilla_medico = PlantillaDemanda.objects.create(
            nombre="Plantilla Medico", especialidad=Empleado.TipoEspecialidad.MEDICO
        )
        self.plantilla_uci = PlantillaDemanda.objects.create(
            nombre="Plantilla UCI", especialidad=Empleado.TipoEspecialidad.UCI
        )
        
        self.turno_medico = TipoTurno.objects.create(
            nombre="G", abreviatura="G", especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8,0), hora_fin=time(20,0)
        )
        self.turno_uci = TipoTurno.objects.create(
            nombre="U", abreviatura="U", especialidad=Empleado.TipoEspecialidad.UCI,
            hora_inicio=time(8,0), hora_fin=time(20,0)
        )
        
        # Configuración de Turnos (Necesaria para validaciones de límite en ReglaForm)
        self.config_turnos = ConfiguracionTurnos.objects.create(
            especialidad=Empleado.TipoEspecialidad.MEDICO, esquema='2x12', hora_inicio_base="08:00"
        )

    # ==========================================================================
    # 1. TEST CONFIGURACION TURNOS (Validación Condicional)
    # ==========================================================================
    def test_config_turnos_3x8_requiere_nombre_t3(self):
        """Si el esquema es 3x8, nombre_t3 es obligatorio."""
        data = {
            'esquema': '3x8',
            'hora_inicio_base': '08:00',
            'nombre_t1': 'M', 'abrev_t1': 'M',
            'nombre_t2': 'T', 'abrev_t2': 'T',
            # Falta T3 intencionalmente
        }
        form = ConfiguracionTurnosForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('nombre_t3', form.errors)

    def test_config_turnos_2x12_no_requiere_t3(self):
        """Si el esquema es 2x12, T3 es opcional."""
        data = {
            'esquema': '2x12',
            'hora_inicio_base': '08:00',
            'nombre_t1': 'M', 'abrev_t1': 'M',
            'nombre_t2': 'N', 'abrev_t2': 'N'
        }
        form = ConfiguracionTurnosForm(data=data)
        self.assertTrue(form.is_valid())

    # ==========================================================================
    # 2. TEST PLANTILLA UPDATE (Campo Readonly)
    # ==========================================================================
    def test_plantilla_update_especialidad_disabled(self):
        """Al editar una plantilla, la especialidad debe estar deshabilitada."""
        form = PlantillaDemandaUpdateForm(instance=self.plantilla_medico)
        # Verificamos que el widget tenga el atributo disabled
        self.assertTrue(form.fields['especialidad'].disabled)

    # ==========================================================================
    # 3. TEST REGLA DEMANDA (General + Límites)
    # ==========================================================================
    def test_regla_form_filtra_turnos_por_especialidad(self):
        """El select de turnos solo debe mostrar los de la misma especialidad que la plantilla."""
        form = ReglaDemandaSemanalForm(plantilla_id=self.plantilla_medico.id)
        queryset = form.fields['turno'].queryset
        
        self.assertIn(self.turno_medico, queryset)
        self.assertNotIn(self.turno_uci, queryset)

    def test_regla_form_requiere_al_menos_un_dia(self):
        """Debe fallar si no se marca ningún checkbox de día."""
        data = {
            'turno': self.turno_medico.id,
            'cantidad_senior': 1, 'cantidad_junior': 1,
            # Ningún dia_X = True
        }
        form = ReglaDemandaSemanalForm(data=data, plantilla_id=self.plantilla_medico.id)
        self.assertFalse(form.is_valid())
        self.assertIn("Debe seleccionar al menos un día de la semana.", form.non_field_errors())

    def test_regla_form_convierte_checkboxes_a_lista_dias(self):
        """Verifica que dia_lunes=True y dia_martes=True se guarde como dias=[0, 1]."""
        data = {
            'turno': self.turno_medico.id,
            'cantidad_senior': 1, 'cantidad_junior': 1,
            'dia_lunes': True,   # 0
            'dia_martes': True,  # 1
            'dia_domingo': True  # 6
        }
        form = ReglaDemandaSemanalForm(data=data, plantilla_id=self.plantilla_medico.id)
        self.assertTrue(form.is_valid())
        
        regla = form.save(commit=False)
        regla.plantilla = self.plantilla_medico 
        regla.save()
        self.assertEqual(sorted(regla.dias), [0, 1, 6])

    def test_regla_form_inicializa_checkboxes_al_editar(self):
        """Si edito una regla que tiene dias=[2], dia_miercoles debe estar True."""
        regla = ReglaDemandaSemanal.objects.create(
            plantilla=self.plantilla_medico,
            turno=self.turno_medico,
            dias=[2], 
            cantidad_senior=1, cantidad_junior=1
        )
        
        form = ReglaDemandaSemanalForm(instance=regla, plantilla_id=self.plantilla_medico.id)
        self.assertTrue(form.fields['dia_miercoles'].initial)
        self.assertFalse(form.fields['dia_lunes'].initial)

    # --- TESTS DE LÍMITES DE REGLAS ---
    
    def test_limite_14_reglas_esquema_2x12(self):
        """Bloquea la creación de la regla #15 si el esquema es 2x12."""
        # Llenamos la plantilla con 14 reglas
        for i in range(14):
            ReglaDemandaSemanal.objects.create(
                plantilla=self.plantilla_medico, turno=self.turno_medico,
                dias=[0], cantidad_senior=1, cantidad_junior=1
            )
            
        # Intentamos crear la regla #15
        data = {'turno': self.turno_medico.id, 'cantidad_senior': 1, 'cantidad_junior': 1, 'dia_lunes': True}
        form = ReglaDemandaSemanalForm(data=data, plantilla_id=self.plantilla_medico.id)
        
        self.assertFalse(form.is_valid())
        self.assertIn("Límite alcanzado", form.non_field_errors()[0])
        self.assertIn("14 reglas", form.non_field_errors()[0])

    def test_limite_21_reglas_esquema_3x8(self):
        """Bloquea la creación de la regla #22 si el esquema es 3x8."""
        # Cambiamos esquema
        self.config_turnos.esquema = '3x8'
        self.config_turnos.save()
        
        # Llenamos con 21 reglas
        for i in range(21):
            ReglaDemandaSemanal.objects.create(
                plantilla=self.plantilla_medico, turno=self.turno_medico,
                dias=[0], cantidad_senior=1, cantidad_junior=1
            )
            
        # Intentamos crear la regla #22
        data = {'turno': self.turno_medico.id, 'cantidad_senior': 1, 'cantidad_junior': 1, 'dia_lunes': True}
        form = ReglaDemandaSemanalForm(data=data, plantilla_id=self.plantilla_medico.id)
        
        self.assertFalse(form.is_valid())
        self.assertIn("21 reglas", form.non_field_errors()[0])

    def test_permitir_edicion_aunque_limite_este_alcanzado(self):
        """Permite editar una regla existente incluso si el cupo está lleno."""
        reglas = []
        for i in range(14):
            r = ReglaDemandaSemanal.objects.create(
                plantilla=self.plantilla_medico, turno=self.turno_medico, dias=[0], cantidad_senior=1, cantidad_junior=1
            )
            reglas.append(r)
            
        una_regla = reglas[0]
        data = {'turno': self.turno_medico.id, 'cantidad_senior': 5, 'cantidad_junior': 5, 'dia_lunes': True}
        
        # Al pasar instance, el form sabe que es edición
        form = ReglaDemandaSemanalForm(data=data, instance=una_regla, plantilla_id=self.plantilla_medico.id)
        
        self.assertTrue(form.is_valid())

    # ==========================================================================
    # 4. TEST EXCEPCION DEMANDA (Filtrado)
    # ==========================================================================
    def test_excepcion_form_filtra_turnos(self):
        """Igual que la regla, la excepción debe filtrar el combo de turnos."""
        form = ExcepcionDemandaForm(plantilla_id=self.plantilla_uci.id)
        queryset = form.fields['turno'].queryset
        
        self.assertIn(self.turno_uci, queryset)
        self.assertNotIn(self.turno_medico, queryset)

    # ==========================================================================
    # 5. TEST CONFIGURACION SIMPLE (Patrón Facade/Presets)
    # ==========================================================================
    def test_config_simple_aplica_preset_rapida(self):
        """Seleccionar 'RAPIDA' debe setear valores bajos de población/generaciones."""
        config = ConfiguracionAlgoritmo()
        form = ConfiguracionSimpleForm(data={'modo': 'RAPIDA'})
        
        self.assertTrue(form.is_valid())
        form.save(config)
        
        self.assertEqual(config.nombre, "Configuración Rápida")
        self.assertEqual(config.tamano_poblacion, 100)

    def test_config_simple_aplica_preset_profunda(self):
        """Seleccionar 'PROFUNDA' debe setear valores altos."""
        config = ConfiguracionAlgoritmo()
        form = ConfiguracionSimpleForm(data={'modo': 'PROFUNDA'})
        
        self.assertTrue(form.is_valid())
        form.save(config)
        
        self.assertEqual(config.nombre, "Configuración Profunda")
        self.assertEqual(config.tamano_poblacion, 150)