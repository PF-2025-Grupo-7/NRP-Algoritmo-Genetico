from django.db import models
from datetime import datetime, date, timedelta
from django.core.exceptions import ValidationError
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

    activo = models.BooleanField(default=True, verbose_name="Activo en planificaciones")

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
        estado = "" if self.activo else "(INACTIVO)"
        return f"{self.nombre_completo} - {self.get_especialidad_display()} {estado}"

class TipoTurno(models.Model):
    nombre = models.CharField(max_length=50) 
    abreviatura = models.CharField(max_length=5) 

    especialidad = models.CharField(
        max_length=20, 
        choices=Empleado.TipoEspecialidad.choices,
        default=Empleado.TipoEspecialidad.MEDICO,
        verbose_name="Especialidad asociada"
    )
    
    es_nocturno = models.BooleanField(
        default=False, 
        verbose_name="Es turno nocturno",
        help_text="Marcar si este turno implica penalización de descanso o secuencias prohibidas específicas."
    )

    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    duracion_horas = models.DecimalField(max_digits=4, decimal_places=2,blank=True, null=True)

    def save(self, *args, **kwargs):

        dummy_date = date(2000, 1, 1)
        dt_inicio = datetime.combine(dummy_date, self.hora_inicio)
        dt_fin = datetime.combine(dummy_date, self.hora_fin)

        if dt_fin < dt_inicio:
            dt_fin += timedelta(days=1)

        diferencia = dt_fin - dt_inicio
        self.duracion_horas = diferencia.total_seconds() / 3600  # Guardar en horas

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({self.get_especialidad_display()})"

class PlantillaDemanda(models.Model):
    nombre = models.CharField(max_length=50, unique=True, help_text="Ej: Demanda Estándar 2025, Demanda Verano")
    
    especialidad = models.CharField(
        max_length=20, 
        choices=Empleado.TipoEspecialidad.choices,
        default=Empleado.TipoEspecialidad.MEDICO
    )
    descripcion = models.TextField(blank=True)
    
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_especialidad_display()})"

class DiaSemana(models.IntegerChoices):
    LUNES = 0, 'Lunes'
    MARTES = 1, 'Martes'
    MIERCOLES = 2, 'Miércoles'
    JUEVES = 3, 'Jueves'
    VIERNES = 4, 'Viernes'
    SABADO = 5, 'Sábado'
    DOMINGO = 6, 'Domingo'

class ReglaDemandaSemanal(models.Model):
    plantilla = models.ForeignKey(PlantillaDemanda, on_delete=models.CASCADE, related_name='reglas')
    dia = models.IntegerField(choices=DiaSemana.choices)
    turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)
    
    cantidad_senior = models.IntegerField(default=1, verbose_name="Min. Senior")
    cantidad_junior = models.IntegerField(default=2, verbose_name="Min. Junior")
    
    class Meta:
        unique_together = ('plantilla', 'dia', 'turno')
        verbose_name = "Regla de Demanda Semanal"
        verbose_name_plural = "Reglas de Demanda Semanal"

    def clean(self):
        super().clean()
        # Validar que el turno sea de la misma especialidad que la plantilla
        if self.plantilla and self.turno:
            if self.plantilla.especialidad != self.turno.especialidad:
                raise ValidationError({
                    'turno': f"El turno '{self.turno}' ({self.turno.get_especialidad_display()}) "
                             f"no corresponde a la especialidad de la plantilla ({self.plantilla.get_especialidad_display()})."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_dia_display()} {self.turno.abreviatura}: S={self.cantidad_senior}/J={self.cantidad_junior}"

class ExcepcionDemanda(models.Model):
    """
    Permite sobreescribir la regla semanal para una fecha específica (Ej: Navidad, Año Nuevo)
    """
    plantilla = models.ForeignKey(PlantillaDemanda, on_delete=models.CASCADE, related_name='excepciones', null=True)
    fecha = models.DateField()
    turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)
    
    cantidad_senior = models.IntegerField(default=0, verbose_name="Req. Senior")
    cantidad_junior = models.IntegerField(default=0, verbose_name="Req. Junior")
    
    motivo = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('plantilla', 'fecha', 'turno')
        verbose_name = "Excepción de Demanda (Feriados/Picos)"
        verbose_name_plural = "Excepciones de Demanda"

    def clean(self):
        super().clean()
        # Validar solo si la excepción está vinculada a una plantilla
        if self.plantilla and self.turno:
            if self.plantilla.especialidad != self.turno.especialidad:
                raise ValidationError({
                    'turno': f"El turno '{self.turno}' ({self.turno.get_especialidad_display()}) "
                             f"no corresponde a la especialidad de la plantilla ({self.plantilla.get_especialidad_display()})."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class NoDisponibilidad(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='no_disponibilidades')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo_turno = models.ForeignKey(
        TipoTurno, on_delete=models.CASCADE, 
        null=True, blank=True, verbose_name="Turno (Dejar vacío para todo el día)"
    )
    motivo = models.CharField(max_length=100)

    def clean(self):
        super().clean()
        # Si especifica un turno puntual (no es día completo), validar especialidad
        if self.empleado and self.tipo_turno:
            if self.empleado.especialidad != self.tipo_turno.especialidad:
                raise ValidationError({
                    'tipo_turno': f"El turno '{self.tipo_turno}' ({self.tipo_turno.get_especialidad_display()}) "
                                  f"no coincide con la especialidad del empleado ({self.empleado.get_especialidad_display()})."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        turno_str = self.tipo_turno.nombre if self.tipo_turno else "TODO EL DÍA"
        return f"{self.empleado.legajo} ({self.fecha_inicio} - {self.fecha_fin}): {turno_str}"

    class Meta:
        verbose_name_plural = "No Disponibilidades"

class Preferencia(models.Model):
    class Deseo(models.TextChoices):
        # CAMBIO 1: Texto amigable para el usuario final
        TRABAJAR = 'TRABAJAR', 'Desea trabajar'
        DESCANSAR = 'DESCANSAR', 'Desea descansar'

    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha = models.DateField()
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE, null=True, blank=True)
    deseo = models.CharField(max_length=20, choices=Deseo.choices)
    
    comentario = models.CharField(max_length=100, blank=True, null=True)

    # CAMBIO 2: Validación de Especialidad
    def clean(self):
        super().clean()
        
        # Solo validamos si hay un turno seleccionado. 
        # Si tipo_turno es None (quiere el día libre completo), no importa la especialidad.
        if self.tipo_turno and self.empleado:
            if self.tipo_turno.especialidad != self.empleado.especialidad:
                raise ValidationError({
                    'tipo_turno': f"El turno '{self.tipo_turno}' ({self.tipo_turno.get_especialidad_display()}) "
                                  f"no coincide con la especialidad del empleado ({self.empleado.get_especialidad_display()})."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        turno_str = self.tipo_turno.nombre if self.tipo_turno else "DÍA COMPLETO"
        return f"{self.empleado}: {self.get_deseo_display()} en {self.fecha} ({turno_str})"

class Cronograma(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        OPTIMIZANDO = 'OPTIMIZANDO', 'En Proceso de Optimización'
        PUBLICADO = 'PUBLICADO', 'Publicado'

    especialidad = models.CharField(max_length=20, choices=Empleado.TipoEspecialidad.choices)
    
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    plantilla_demanda = models.ForeignKey(PlantillaDemanda, on_delete=models.PROTECT, null=True, blank=True)
    
    configuracion_usada = models.ForeignKey('ConfiguracionAlgoritmo', on_delete=models.SET_NULL, null=True, blank=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    fitness = models.FloatField(
        null=True, blank=True, 
        help_text="Puntaje de calidad (Menor/Mayor según tu función, generalmente Mayor es mejor o Menor es penalización)"
    )
    tiempo_ejecucion = models.FloatField(
        null=True, blank=True, 
        verbose_name="Tiempo de Ejecución (s)"
    )
    
    # Aquí guardamos TODO el objeto "explicabilidad" del JSON
    reporte_analisis = models.JSONField(
        null=True, blank=True, 
        verbose_name="Detalle de Explicabilidad (JSON)",
        help_text="Guarda violaciones blandas, métricas de equidad, etc."
    )

    def clean(self):
        super().clean()
        # Validar que la plantilla coincida con la especialidad del cronograma
        if self.plantilla_demanda:
            if self.especialidad != self.plantilla_demanda.especialidad:
                raise ValidationError({
                    'plantilla_demanda': f"La plantilla '{self.plantilla_demanda}' es de {self.plantilla_demanda.get_especialidad_display()}, "
                                         f"pero estás creando un cronograma de {self.get_especialidad_display()}."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Plan {self.get_especialidad_display()} ({self.fecha_inicio} al {self.fecha_fin}) - {self.estado}"

class Asignacion(models.Model):
    cronograma = models.ForeignKey(Cronograma, on_delete=models.CASCADE, related_name='asignaciones')
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha = models.DateField()
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "Asignaciones (Resultado)"
        unique_together = ('cronograma', 'empleado', 'fecha') # Un empleado no puede tener 2 turnos el mismo día en el mismo plan

class ConfiguracionAlgoritmo(models.Model):
    """
    Modelo único para parámetros técnicos del AG y parámetros de negocio (pesos).
    """
    nombre = models.CharField(max_length=50, default="Configuración Estándar")
    activa = models.BooleanField(default=True, help_text="Solo debe haber una activa por defecto")

    # --- SECCIÓN 1: Parámetros Técnicos del Algoritmo Genético ---
    tamano_poblacion = models.IntegerField(
        default=100, 
        verbose_name="Tamaño Población (pop_size)",
        validators=[MinValueValidator(10)]
    )
    generaciones = models.IntegerField(
        default=15, 
        verbose_name="Generaciones",
        validators=[MinValueValidator(10)]
    )
    prob_cruce = models.FloatField(
        default=0.85, 
        verbose_name="Probabilidad de Cruce (pc)",
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    prob_mutacion = models.FloatField(
        default=0.20, 
        verbose_name="Probabilidad de Mutación (pm)",
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    elitismo = models.BooleanField(default=True, verbose_name="Usar Elitismo")
    
    semilla = models.IntegerField(
        null=True, blank=True, 
        verbose_name="Semilla (Seed)",
        help_text="Dejar vacío para aleatorio. Usar número fijo para reproducibilidad."
    )

    class EstrategiaSeleccion(models.TextChoices):
        TORNEO = 'torneo_deterministico', 'Torneo Determinístico'
        RANKING = 'ranking_lineal', 'Ranking Lineal'
        
    estrategia_seleccion = models.CharField(
        max_length=50, 
        choices=EstrategiaSeleccion.choices, 
        default=EstrategiaSeleccion.TORNEO
    )

    class EstrategiaCruce(models.TextChoices):
        BLOQUES_VERTICALES = 'bloques_verticales', 'Bloques Verticales'
        BLOQUES_HORIZONTALES = 'bloques_horizontales', 'Bloques Horizontales'
        DOS_PUNTOS = 'dos_puntos', 'Dos Puntos'

    estrategia_cruce = models.CharField(
        max_length=50,
        choices=EstrategiaCruce.choices,
        default=EstrategiaCruce.BLOQUES_VERTICALES
    )

    class EstrategiaMutacion(models.TextChoices):
        HIBRIDA = 'hibrida_adaptativa', 'Híbrida'
        REASIGNAR = 'reasignar_turno', 'Reasignar Turno'
        INTERCAMBIO = 'intercambio_dia', 'Intercambio de Día'
        FLIP = 'flip_simple', 'Flip Simple'

    estrategia_mutacion = models.CharField(
        max_length=50,
        choices=EstrategiaMutacion.choices,
        default=EstrategiaMutacion.HIBRIDA
    )

    # --- SECCIÓN 2: Pesos y Preferencias de Negocio ---
    peso_equidad_general = models.FloatField(default=1.0, validators=[MinValueValidator(0.0)])
    peso_equidad_dificil = models.FloatField(default=1.5, validators=[MinValueValidator(0.0)])
    peso_preferencia_dias_libres = models.FloatField(default=2.0, validators=[MinValueValidator(0.0)])
    peso_preferencia_turno = models.FloatField(default=0.5, validators=[MinValueValidator(0.0)])
    
    factor_alpha_pte = models.FloatField(
        default=0.5, 
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Penalización parcial si se descansa en vez de trabajar el turno pedido (0-1)"
    )
    
    tolerancia_general = models.IntegerField(default=8, verbose_name="Tolerancia Horas General")
    tolerancia_dificil = models.IntegerField(default=4, verbose_name="Tolerancia Turnos Difíciles")

    class Meta:
        verbose_name = "Configuración Global del Algoritmo"
        verbose_name_plural = "Configuraciones Globales"

    def __str__(self):
        return f"{self.nombre} (Pop:{self.tamano_poblacion}, Gen:{self.generaciones})"

    def save(self, *args, **kwargs):
        if self.activa:
            ConfiguracionAlgoritmo.objects.filter(activa=True).exclude(pk=self.pk).update(activa=False)
        super().save(*args, **kwargs)

class SecuenciaProhibida(models.Model):
    """
    Define pares de turnos incompatibles según la especialidad.
    """
    especialidad = models.CharField(
        max_length=20, 
        choices=Empleado.TipoEspecialidad.choices, 
        default=Empleado.TipoEspecialidad.ENFERMERO
    )
    
    turno_previo = models.ForeignKey(TipoTurno, on_delete=models.CASCADE, related_name='prohibido_origen')
    turno_siguiente = models.ForeignKey(TipoTurno, on_delete=models.CASCADE, related_name='prohibido_destino')
    
    def clean(self):
        """
        Valida que los turnos seleccionados pertenezcan a la especialidad declarada.
        """
        super().clean()
        
        # Validar Turno Previo
        if self.turno_previo_id: # Usamos _id para evitar query extra si no hace falta
            if self.turno_previo.especialidad != self.especialidad:
                raise ValidationError({
                    'turno_previo': f"El turno '{self.turno_previo}' no corresponde a la especialidad {self.get_especialidad_display()}."
                })

        # Validar Turno Siguiente
        if self.turno_siguiente_id:
            if self.turno_siguiente.especialidad != self.especialidad:
                raise ValidationError({
                    'turno_siguiente': f"El turno '{self.turno_siguiente}' no corresponde a la especialidad {self.get_especialidad_display()}."
                })

    def save(self, *args, **kwargs):
        self.full_clean() # Forzar validación antes de guardar
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Secuencia Prohibida"
        verbose_name_plural = "Secuencias Prohibidas"
        unique_together = ('especialidad', 'turno_previo', 'turno_siguiente')

    def __str__(self):
        return f"[{self.get_especialidad_display()}] NO HACER: {self.turno_previo.abreviatura} -> {self.turno_siguiente.abreviatura}"
    
    # ... (otros modelos)

class TrabajoPlanificacion(models.Model):
    """
    Tabla temporal para persistir el contexto de una optimización en curso.
    Reemplaza el uso de sesiones para mayor robustez.
    """
    job_id = models.UUIDField(primary_key=True, editable=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    # Datos necesarios para reconstruir el cronograma al terminar
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    especialidad = models.CharField(max_length=20)
    payload_original = models.JSONField(help_text="Copia del JSON enviado al optimizador")

    def __str__(self):
        return f"Job {self.job_id} ({self.especialidad})"