from django.test import TestCase # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from datetime import time
from rostering.models import ReglaDemandaSemanal, TipoTurno, Empleado, PlantillaDemanda, DiaSemana

class TestReglaDemandaSemanal(TestCase):

    def setUp(self):
        self.plantilla = PlantillaDemanda.objects.create(
            nombre="Demanda Médicos",
            especialidad=Empleado.TipoEspecialidad.MEDICO
        )

        self.turno = TipoTurno.objects.create(
            nombre="Día",
            abreviatura="D",
            especialidad=Empleado.TipoEspecialidad.MEDICO,
            hora_inicio=time(8, 0),
            hora_fin=time(16, 0)
        )

        self.turno_enfermero = TipoTurno.objects.create(
            nombre="Noche Enfermería",
            abreviatura="NE",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(20, 0),
            hora_fin=time(8, 0)
        )

    def crear_regla_demanda(self, **custom_data):
        # ADAPTADOR: Si el test viejo pasa 'dia', lo convertimos a lista 'dias'
        dia_singular = custom_data.pop('dia', None)
        
        regla_default = {
            "plantilla": self.plantilla,
            "dias": [DiaSemana.LUNES] if dia_singular is None else [dia_singular], # Default Lunes
            "turno": self.turno,
            "cantidad_senior": 1,
            "cantidad_junior": 2,
        }

        # Si custom_data traía 'dias' explícitamente, sobrescribe lo anterior
        regla_default.update(custom_data)

        regla = ReglaDemandaSemanal(**regla_default)
        regla.full_clean()
        regla.save()
        return regla

    def test_cuando_regla_demanda_tiene_datos_validos_deberia_crearse(self):
        dia = DiaSemana.MARTES
        cant_senior = 8

        # Pasamos 'dia' singular, el adaptador lo convierte a lista
        regla_creada = self.crear_regla_demanda(dia=dia, cantidad_senior=cant_senior)

        # Buscamos usando filter porque 'dias' es JSON, no podemos buscar por igualdad simple
        # En JSONField, contains busca si la lista contiene el valor
        regla_en_db = ReglaDemandaSemanal.objects.filter(dias__contains=dia).first()

        self.assertIsNotNone(regla_en_db)
        self.assertEqual(cant_senior, regla_en_db.cantidad_senior)
        self.assertIn(dia, regla_en_db.dias)

    def test_cuando_faltan_campos_obligatorios_deberia_fallar(self):
        regla = ReglaDemandaSemanal()

        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_cuando_no_tiene_datos_deberia_usar_valores_por_defecto(self):
        # Aquí usamos create directo, así que pasamos 'dias' (lista) manualmente
        regla = ReglaDemandaSemanal.objects.create(
            plantilla=self.plantilla,
            dias=[DiaSemana.MARTES],
            turno=self.turno
        )

        self.assertEqual(regla.cantidad_senior, 1)
        self.assertEqual(regla.cantidad_junior, 2)

    def test_cuando_turno_no_corresponde_a_especialidad_deberia_fallar(self):
        turno_enfermero = TipoTurno.objects.create(
            nombre="Día Enfermería",
            abreviatura="DE",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO,
            hora_inicio=time(8, 0),
            hora_fin=time(16, 0)
        )

        with self.assertRaises(ValidationError):
            self.crear_regla_demanda(turno=turno_enfermero)

    def test_cuando_dia_es_invalido_deberia_fallar(self):
        # Probamos con un valor inválido dentro de la lista
        with self.assertRaises(ValidationError):
            self.crear_regla_demanda(dias=[7])

    def test_cuando_cantidad_senior_es_negativa_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_regla_demanda(cantidad_senior=-1)

    def test_cuando_cantidad_junior_es_negativa_deberia_fallar(self):
        with self.assertRaises(ValidationError):
            self.crear_regla_demanda(cantidad_junior=-1)

    def test_cuando_se_edita_regla_demanda_con_datos_validos_deberia_actualizarse(self):
        regla = self.crear_regla_demanda()

        nuevo_dia = DiaSemana.MIERCOLES
        nueva_cantidad_senior = 3
        nueva_cantidad_junior = 6
        plantilla_enfermero = PlantillaDemanda.objects.create(
            nombre="Demanda Enfermeros",
            especialidad=Empleado.TipoEspecialidad.ENFERMERO
        )

        regla.plantilla = plantilla_enfermero
        regla.dias = [nuevo_dia] # Actualizamos la lista
        regla.turno = self.turno_enfermero
        regla.cantidad_senior = nueva_cantidad_senior
        regla.cantidad_junior = nueva_cantidad_junior

        regla.full_clean()
        regla.save()

        regla_actualizada = ReglaDemandaSemanal.objects.get(pk=regla.pk)

        self.assertEqual(plantilla_enfermero, regla_actualizada.plantilla)
        self.assertEqual([nuevo_dia], regla_actualizada.dias)
        self.assertEqual(self.turno_enfermero, regla_actualizada.turno)
        self.assertEqual(nueva_cantidad_senior, regla_actualizada.cantidad_senior)
        self.assertEqual(nueva_cantidad_junior, regla_actualizada.cantidad_junior)

    def test_cuando_se_edita_cantidad_senior_a_valor_negativo_deberia_fallar(self):
        regla = self.crear_regla_demanda()
        regla.cantidad_senior = -1
        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_cuando_se_edita_cantidad_junior_a_valor_negativo_deberia_fallar(self):
        regla = self.crear_regla_demanda()
        regla.cantidad_junior = -1
        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_cuando_se_edita_turno_con_especialidad_distinta_a_plantilla_deberia_fallar(self):
        regla = self.crear_regla_demanda()
        regla.turno = self.turno_enfermero
        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_cuando_se_edita_dia_a_valor_invalido_deberia_fallar(self):
        regla = self.crear_regla_demanda()
        regla.dias = [7] # Valor inválido en lista
        with self.assertRaises(ValidationError):
            regla.full_clean()

    # NOTA: Eliminamos 'test_cuando_plantilla_turno_y_dia_estan_duplicados_deberia_fallar'
    # porque ahora el modelo permite superposición lógica a nivel de modelo (no hay unique_together en 'dias').
    # La validación de unicidad ahora es responsabilidad del Formulario o lógica de negocio superior,
    # no del modelo crudo (salvo que implementemos un validador complejo en clean(), que por ahora no está).
    # Si querés testear eso, tendrías que testear el FORM, no el MODELO.