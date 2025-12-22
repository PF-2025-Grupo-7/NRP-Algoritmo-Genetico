from django.db import models
from datetime import datetime, date, timedelta
from django.core.validators import MinValueValidator, MaxValueValidator

class Empleado(models.Model):
    class TipoEspecialidad(models.TextChoices):
        MEDICO = 'MEDICO', 'Médico'
        ENFERMERO = 'ENFERMERO', 'Enfermero'
        ER = 'ER', 'Experto en Emergencias'
        UCI = 'UCI', 'Unidad de Cuidados Intensivos'

    class TipoExperiencia(models.TextChoices):
        SENIOR = 'SENIOR', 'Senior'
        JUNIOR = 'JUNIOR', 'Junior'

    legajo = models.CharField(max_length=20, unique=True)
    nombre_completo = models.CharField(max_length=255)
    especialidad = models.CharField(max_length=20, choices=TipoEspecialidad.choices)
    experiencia = models.CharField(max_length=20, choices=TipoExperiencia.choices)

    min_horas_mensuales = models.IntegerField(
        default=120, 
        verbose_name="Mínimo Horas/Mes",
        help_text="Límite inferior del contrato (ej. 120 para part-time)"
    )
    max_horas_mensuales = models.IntegerField(
        default=160, 
        verbose_name="Máximo Horas/Mes",
        help_text="Límite superior del contrato antes de contar horas extra o prohibir"
    )
    
    def __str__(self):
        return f"{self.nombre_completo} ({self.legajo})"

class TipoTurno(models.Model):
    nombre = models.CharField(max_length=50) 
    abreviatura = models.CharField(max_length=5) 
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    duracion_horas = models.DecimalField(max_digits=4, decimal_places=2,blank=True, null=True)

    def save(self, *args, **kwargs):
        # 1. Crear fechas dummy para poder restar las horas
        dummy_date = date(2000, 1, 1)
        dt_inicio = datetime.combine(dummy_date, self.hora_inicio)
        dt_fin = datetime.combine(dummy_date, self.hora_fin)

        # 2. Si el fin es menor al inicio, significa que cruza la medianoche (ej: 22:00 a 06:00)
        if dt_fin < dt_inicio:
            dt_fin += timedelta(days=1)

        # 3. Calcular diferencia en horas
        diferencia = dt_fin - dt_inicio
        self.duracion_horas = diferencia.total_seconds() / 3600  # Guardar en horas

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

class PlantillaDemanda(models.Model):
    nombre = models.CharField(max_length=50, unique=True, help_text="Ej: Demanda Estándar 2025, Demanda Verano")
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

class DiaSemana(models.IntegerChoices):
    LUNES = 0, 'Lunes'
    MARTES = 1, 'Martes'
    MIERCOLES = 2, 'Miércoles'
    JUEVES = 3, 'Jueves'
    VIERNES = 4, 'Viernes'
    SABADO = 5, 'Sábado'
    DOMINGO = 6, 'Domingo'

# ... imports ...

class ReglaDemandaSemanal(models.Model):
    """ Define cuántos enfermeros de cada tipo se necesitan """
    plantilla = models.ForeignKey(PlantillaDemanda, on_delete=models.CASCADE, related_name='reglas')
    dia = models.IntegerField(choices=DiaSemana.choices)
    turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)
    
    # CAMBIO: Desdoblamos la cantidad
    cantidad_senior = models.IntegerField(default=1, verbose_name="Min. Senior")
    cantidad_junior = models.IntegerField(default=2, verbose_name="Min. Junior")
    
    class Meta:
        unique_together = ('plantilla', 'dia', 'turno')
        verbose_name = "Regla de Demanda Semanal"
        verbose_name_plural = "Reglas de Demanda Semanal"

    def __str__(self):
        return f"{self.get_dia_display()} {self.turno}: S={self.cantidad_senior}/J={self.cantidad_junior}"

class ExcepcionDemanda(models.Model):
    """
    Permite sobreescribir la regla semanal para una fecha específica
    """
    fecha = models.DateField()
    turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)
    
    # CAMBIO: Aquí también desdoblamos
    cantidad_senior = models.IntegerField(default=0, verbose_name="Req. Senior")
    cantidad_junior = models.IntegerField(default=0, verbose_name="Req. Junior")
    
    motivo = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('fecha', 'turno')
        verbose_name = "Excepción de Demanda"
        verbose_name_plural = "Excepciones de Demanda"


class NoDisponibilidad(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='no_disponibilidades')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    # Si es NULL, significa "Todo el día" (o todos los días del rango).
    # Si tiene valor, afecta solo a ese turno específico.
    tipo_turno = models.ForeignKey(
        TipoTurno, on_delete=models.CASCADE, 
        null=True, blank=True,verbose_name="Turno (Dejar vacío para todo el día)")
    motivo = models.CharField(max_length=255)

    motivo = models.CharField(max_length=100)

    def __str__(self):
        turno_str = self.tipo_turno.nombre if self.tipo_turno else "TODO EL DÍA"
        return f"{self.empleado} ({self.fecha_inicio} al {self.fecha_fin}): {turno_str}"

    class Meta:
        verbose_name_plural = "No Disponibilidades"

class Preferencia(models.Model):
    class Nivel(models.TextChoices):
        TRABAJAR = 'TRABAJAR', 'Desea trabajar'
        DESCANSAR = 'DESCANSAR', 'Desea descansar'

    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha = models.DateField()
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)
    nivel = models.CharField(max_length=20, choices=Nivel.choices)

class Cronograma(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        PUBLICADO = 'PUBLICADO', 'Publicado'

    especialidad = models.CharField(max_length=20, choices=Empleado.TipoEspecialidad.choices)
    mes = models.PositiveIntegerField()
    anio = models.PositiveIntegerField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    plantilla_demanda = models.ForeignKey(PlantillaDemanda, on_delete=models.PROTECT, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Planificación {self.mes}/{self.anio} ({self.estado})"

class Asignacion(models.Model):
    cronograma = models.ForeignKey(Cronograma, on_delete=models.CASCADE, related_name='asignaciones')
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha = models.DateField()
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "Asignaciones"

class ConfiguracionAlgoritmo(models.Model):
    """
    Modelo para gestionar los parámetros dinámicos del Algoritmo Genético.
    Se recomienda usar un patrón Singleton (solo una instancia activa).
    """
    nombre = models.CharField(max_length=50, default="Configuración Principal")
    activa = models.BooleanField(default=True)

    # --- SECCIÓN 1: PESOS DE LA FUNCIÓN DE FITNESS (Soft Constraints) ---
    # Nota: Se eliminó el peso de 'Carga Horaria' ya que ahora es una restricción dura.
    
    peso_equidad_general = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0)],
        verbose_name="Peso Equidad General (eq)",
        help_text="Penalización por varianza en la carga total de guardias entre médicos."
    )

    peso_equidad_dificil = models.FloatField(
        default=1.5,
        validators=[MinValueValidator(0.0)],
        verbose_name="Peso Equidad Difícil (dif)",
        help_text="Penalización por desbalance en guardias de fin de semana o nocturnas."
    )

    peso_preferencia_dias_libres = models.FloatField(
        default=2.0,
        validators=[MinValueValidator(0.0)],
        verbose_name="Peso Días Libres (pdl)",
        help_text="Importancia de respetar los días que el médico pidió NO trabajar."
    )

    peso_preferencia_turno = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0)],
        verbose_name="Peso Turno Específico (pte)",
        help_text="Importancia de asignar exactamente el turno solicitado (Mañana/Tarde/Noche)."
    )

    factor_alpha_pte = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Factor Alpha (α)",
        help_text="Coeficiente de penalización parcial cuando se asigna descanso en lugar del turno pedido (0 < α <= 1)."
    )

    # --- SECCIÓN 2: TOLERANCIAS (Nuevos campos solicitados) ---
    
    tolerancia_general = models.IntegerField(
        default=8,
        validators=[MinValueValidator(0)],
        verbose_name="Tolerancia Equidad General",
        help_text="Diferencia máxima de horas/turnos permitida antes de aplicar penalización severa."
    )

    tolerancia_dificil = models.IntegerField(
        default=4,
        validators=[MinValueValidator(0)],
        verbose_name="Tolerancia Equidad Difícil",
        help_text="Diferencia máxima de guardias difíciles permitida antes de penalizar."
    )

    class Meta:
        verbose_name = "Configuración del Algoritmo"
        verbose_name_plural = "Configuraciones del Algoritmo"

    def __str__(self):
        return f"{self.nombre} ({'Activa' if self.activa else 'Inactiva'})"

class SecuenciaProhibida(models.Model):
    """
    Define pares de turnos incompatibles según la especialidad.
    Ej: Enfermeros no pueden hacer Noche (3) -> Mañana (1).
    """
    class Especialidad(models.TextChoices):
        MEDICO = 'MEDICO', 'Médico'
        ENFERMERO = 'ENFERMERO', 'Enfermero'
        TODOS = 'TODOS', 'Cualquiera'

    especialidad = models.CharField(max_length=20, choices=Especialidad.choices, default=Especialidad.ENFERMERO)
    
    turno_previo = models.ForeignKey(TipoTurno, on_delete=models.CASCADE, related_name='prohibido_origen', verbose_name="Si trabaja en...")
    turno_siguiente = models.ForeignKey(TipoTurno, on_delete=models.CASCADE, related_name='prohibido_destino', verbose_name="No puede trabajar después en...")
    
    class Meta:
        verbose_name = "Secuencia Prohibida"
        verbose_name_plural = "Secuencias Prohibidas (Reglas de Oro)"
        unique_together = ('especialidad', 'turno_previo', 'turno_siguiente')

    def __str__(self):
        return f"[{self.especialidad}] Prohibido: {self.turno_previo.abreviatura} -> {self.turno_siguiente.abreviatura}"