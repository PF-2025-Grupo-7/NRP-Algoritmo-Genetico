from datetime import datetime, date, timedelta
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q

# ==============================================================================
# HELPERS / UTILIDADES
# ==============================================================================

def validar_consistencia_especialidad(obj_padre, obj_hijo, campo_error):
    """
    Valida que dos objetos compartan la misma especialidad.
    Útil para asegurar que no asignamos un turno de Enfermería a un Médico, etc.
    """
    if obj_padre and obj_hijo:
        # Asumimos que ambos objetos tienen un atributo 'especialidad'
        esp_padre = getattr(obj_padre, 'especialidad', None)
        esp_hijo = getattr(obj_hijo, 'especialidad', None)
        
        if esp_padre and esp_hijo and esp_padre != esp_hijo:
            # Intentamos obtener el nombre legible si existe el método
            nombre_padre = getattr(obj_padre, 'get_especialidad_display', lambda: esp_padre)()
            nombre_hijo = getattr(obj_hijo, 'get_especialidad_display', lambda: esp_hijo)()
            
            raise ValidationError({
                campo_error: f"Inconsistencia de especialidad: El objeto seleccionado es '{nombre_hijo}' "
                             f"pero el contexto requiere '{nombre_padre}'."
            })

# ==============================================================================
# CATÁLOGOS BASE (Empleados, Turnos)
# ==============================================================================

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

    min_turnos_mensuales = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(31)],
        verbose_name="Mínimo de turnos/mes",
        help_text="Cantidad mínima de turnos a asignar en el periodo."
    )
    max_turnos_mensuales = models.IntegerField(
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(31)],
        verbose_name="Máximo de turnos/mes",
        help_text="Límite máximo de turnos a asignar en el periodo."
    )
    
    def save(self, *args, **kwargs):
        """
        Sobrescribimos save para mantener la integridad referencial lógica.
        Si cambia la especialidad, borramos preferencias incompatibles.
        """
        if self.pk:
            try:
                old_instance = Empleado.objects.get(pk=self.pk)
                if old_instance.especialidad != self.especialidad:
                    
                    # 1. Limpiar Preferencias (Turnos específicos incompatibles)
                    # Las preferencias con tipo_turno=None (Franco completo) se conservan.
                    deleted_prefs, _ = self.preferencia_set.filter(
                        tipo_turno__especialidad=old_instance.especialidad
                    ).delete()
                    
                    # 2. Limpiar NoDisponibilidades (Turnos específicos incompatibles)
                    deleted_nd, _ = self.no_disponibilidades.filter(
                        tipo_turno__especialidad=old_instance.especialidad
                    ).delete()

                      
            except Empleado.DoesNotExist:
                pass 

        super().save(*args, **kwargs)

    def __str__(self):
        estado = "" if self.activo else "(INACTIVO)"
        return f"{self.nombre_completo} - {self.get_especialidad_display()} {estado}"

class ConfiguracionTurnos(models.Model):
    """
    Define el esquema maestro para una especialidad.
    Actúa como 'Factory' para generar los TipoTurno automáticamente.
    """
    class TipoEsquema(models.TextChoices):
        TURNO_12_HS = '2x12', '2 Turnos de 12 Horas (Total 24hs)'
        TURNO_08_HS = '3x8',  '3 Turnos de 8 Horas (Total 24hs)'

    especialidad = models.CharField(
        max_length=20, 
        choices=Empleado.TipoEspecialidad.choices,
        unique=True, # Solo una configuración por especialidad
        verbose_name="Especialidad"
    )
    
    esquema = models.CharField(max_length=10, choices=TipoEsquema.choices, default=TipoEsquema.TURNO_12_HS)
    hora_inicio_base = models.TimeField(verbose_name="Hora de Inicio (Primer Turno)", help_text="Ej: 08:00. El resto se calcula automáticamente.")

    # Metadatos para persistir los nombres elegidos (JSON para flexibilidad)
    # Estructura: {"t1": {"nombre": "Mañana", "abrev": "M", "es_nocturno": false}, ...}
    nombres_turnos = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Esquema {self.get_esquema_display()} - {self.get_especialidad_display()}"

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
    duracion_horas = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Calcular duración automáticamente al guardar
        dummy_date = date(2000, 1, 1)
        dt_inicio = datetime.combine(dummy_date, self.hora_inicio)
        dt_fin = datetime.combine(dummy_date, self.hora_fin)

        if dt_fin < dt_inicio:
            dt_fin += timedelta(days=1)

        diferencia = dt_fin - dt_inicio
        self.duracion_horas = diferencia.total_seconds() / 3600 
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.hora_inicio and self.hora_fin:
            if (self.hora_fin < self.hora_inicio and not self.es_nocturno):
                raise ValidationError({
                    "es_nocturno": "El turno cambia de día (cruza medianoche), debe marcarse como nocturno."
                })

    def __str__(self):
        return f"{self.nombre} ({self.get_especialidad_display()})"


class SecuenciaProhibida(models.Model):
    """Define pares de turnos incompatibles según la especialidad (Ej: Noche -> Mañana)."""
    especialidad = models.CharField(
        max_length=20, 
        choices=Empleado.TipoEspecialidad.choices, 
        default=Empleado.TipoEspecialidad.ENFERMERO
    )
    turno_previo = models.ForeignKey(TipoTurno, on_delete=models.CASCADE, related_name='prohibido_origen')
    turno_siguiente = models.ForeignKey(TipoTurno, on_delete=models.CASCADE, related_name='prohibido_destino')
    
    def clean(self):
        super().clean()
        # Validamos que ambos turnos sean de la especialidad declarada
        if self.turno_previo_id:
            validar_consistencia_especialidad(self, self.turno_previo, 'turno_previo')
        if self.turno_siguiente_id:
            validar_consistencia_especialidad(self, self.turno_siguiente, 'turno_siguiente')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Secuencia Prohibida"
        verbose_name_plural = "Secuencias Prohibidas"
        unique_together = ('especialidad', 'turno_previo', 'turno_siguiente')

    def __str__(self):
        return f"[{self.get_especialidad_display()}] PROHIBIDO: {self.turno_previo.abreviatura} -> {self.turno_siguiente.abreviatura}"


# ==============================================================================
# GESTIÓN DE DEMANDA (Plantillas y Reglas)
# ==============================================================================

class PlantillaDemanda(models.Model):
    nombre = models.CharField(max_length=50, unique=True, help_text="Ej: Demanda Estándar 2025")
    especialidad = models.CharField(
        max_length=20,
        choices=Empleado.TipoEspecialidad.choices,
        default=Empleado.TipoEspecialidad.MEDICO
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")

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
    dias = models.JSONField(default=list, verbose_name="Días aplicables", 
                           help_text="Lista de días (0=Lunes, 1=Martes, ..., 6=Domingo)")
    turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)
    
    cantidad_senior = models.IntegerField(default=1, verbose_name="Min. Senior", validators=[MinValueValidator(0)])
    cantidad_junior = models.IntegerField(default=2, verbose_name="Min. Junior", validators=[MinValueValidator(0)])
    es_excepcion = models.BooleanField(default=False, verbose_name="Es una excepción")
    
    class Meta:
        verbose_name = "Regla de Demanda Semanal"
        verbose_name_plural = "Reglas de Demanda Semanal"

    def clean(self):
        super().clean()
        if self.plantilla_id and self.turno_id:
            validar_consistencia_especialidad(self.plantilla, self.turno, 'turno')
        
        # Validar que dias sea una lista
        if not isinstance(self.dias, list):
            raise ValidationError({'dias': 'El campo días debe ser una lista.'})
        
        # Validar que los días estén en el rango correcto
        if any(d < 0 or d > 6 for d in self.dias):
            raise ValidationError({'dias': 'Los días deben estar entre 0 (Lunes) y 6 (Domingo).'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_dias_display(self):
        """Retorna los nombres de los días seleccionados."""
        nombres = []
        for dia in sorted(self.dias):
            nombres.append(DiaSemana(dia).label)
        return ", ".join(nombres) if nombres else "Ningún día"

    def __str__(self):
        dias_str = self.get_dias_display()
        return f"{self.turno.abreviatura} [{dias_str}]: S={self.cantidad_senior}/J={self.cantidad_junior}"

class ExcepcionDemanda(models.Model):
    """Permite sobreescribir la regla semanal para una fecha específica (Ej: Navidad)."""
    plantilla = models.ForeignKey(PlantillaDemanda, on_delete=models.CASCADE, related_name='excepciones', null=True, blank=True)
    fecha = models.DateField()
    turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)
    
    cantidad_senior = models.IntegerField(default=0, verbose_name="Req. Senior", validators=[MinValueValidator(0)])
    cantidad_junior = models.IntegerField(default=0, verbose_name="Req. Junior", validators=[MinValueValidator(0)])
    
    # --- NUEVO CAMPO ---
    es_turno_dificil = models.BooleanField(
        default=False, 
        verbose_name="Es Turno Difícil", 
        help_text="Marcar si trabajar este día debe contar doble para la equidad (Ej: Navidad, Año Nuevo)."
    )
    # -------------------

    motivo = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('plantilla', 'fecha', 'turno')
        verbose_name = "Excepción de Demanda (Feriados/Picos)"
        verbose_name_plural = "Excepciones de Demanda"

    def clean(self):
        super().clean()
        if self.plantilla_id and self.turno_id:
            validar_consistencia_especialidad(self.plantilla, self.turno, 'turno')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

# ==============================================================================
# NOVEDADES Y PREFERENCIAS (Inputs del Empleado)
# ==============================================================================

class NoDisponibilidad(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='no_disponibilidades')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo_turno = models.ForeignKey(
        TipoTurno, on_delete=models.CASCADE, 
        null=True, blank=True, verbose_name="Turno (Dejar vacío para todo el día)"
    )
    motivo = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        verbose_name_plural = "No Disponibilidades"

    def clean(self):
        super().clean()
        
        # 1. Validación de Fechas básica
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({'fecha_fin': 'La fecha de fin no puede ser anterior a la fecha de inicio.'})

        # 2. Validación de Especialidad
        if self.empleado_id and self.tipo_turno_id:
            validar_consistencia_especialidad(self.empleado, self.tipo_turno, 'tipo_turno')

        # 3. Validación de Conflicto con Preferencias de "TRABAJAR"
        # Si digo que NO estoy disponible, no debería tener un pedido explícito de "QUIERO TRABAJAR" en ese lapso.
        if self.empleado_id and self.fecha_inicio and self.fecha_fin:
            # Buscamos preferencias de TRABAJAR en el rango
            prefs_conflictivas = Preferencia.objects.filter(
                empleado=self.empleado,
                deseo=Preferencia.Deseo.TRABAJAR,
                fecha__range=[self.fecha_inicio, self.fecha_fin]
            )

            for p in prefs_conflictivas:
                # Chequeamos superposición de turno (Scope)
                # Hay conflicto si:
                # A. La ausencia es todo el día (self.tipo_turno is None)
                # B. La preferencia es todo el día (p.tipo_turno is None)
                # C. Ambos son el mismo turno específico
                hay_superposicion = (
                    self.tipo_turno is None or 
                    p.tipo_turno is None or 
                    self.tipo_turno_id == p.tipo_turno_id
                )
                
                if hay_superposicion:
                    turno_msg = self.tipo_turno.nombre if self.tipo_turno else "Todo el día"
                    raise ValidationError(
                        f"Contradicción: El empleado pidió 'TRABAJAR' el día {p.fecha} ({p.tipo_turno or 'Día completo'}), "
                        f"no se puede cargar una ausencia para '{turno_msg}'."
                    )

        # 4. Validación: evitar duplicados exactos (mismo empleado, rango que se superpone y mismo turno)
        # Solo consideramos duplicado si el turno es el mismo (incluye ambos None -> 'Todo el día')
        if self.empleado_id and self.fecha_inicio and self.fecha_fin:
            dup_q = Q()
            if self.tipo_turno_id is None:
                dup_q = Q(tipo_turno__isnull=True)
            else:
                dup_q = Q(tipo_turno_id=self.tipo_turno_id)

            qs_dup = NoDisponibilidad.objects.filter(
                empleado_id=self.empleado_id,
                fecha_fin__gte=self.fecha_inicio,
                fecha_inicio__lte=self.fecha_fin,
            ).filter(dup_q)

            if self.pk:
                qs_dup = qs_dup.exclude(pk=self.pk)

            if qs_dup.exists():
                raise ValidationError('Ya existe una ausencia para este empleado en este período y turno.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        turno_str = self.tipo_turno.nombre if self.tipo_turno else "TODO EL DÍA"
        return f"{self.empleado.legajo} ({self.fecha_inicio} - {self.fecha_fin}): {turno_str}"


class Preferencia(models.Model):
    class Deseo(models.TextChoices):
        TRABAJAR = 'TRABAJAR', 'Desea trabajar'
        DESCANSAR = 'DESCANSAR', 'Desea descansar'

    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha = models.DateField()
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE, null=True, blank=True)
    deseo = models.CharField(max_length=20, choices=Deseo.choices)
    comentario = models.CharField(max_length=100, blank=True, null=True)

    def clean(self):
        super().clean()
        
        # 1. Validación de Especialidad
        if self.tipo_turno_id and self.empleado_id:
            validar_consistencia_especialidad(self.empleado, self.tipo_turno, 'tipo_turno')

        if self.empleado_id and self.fecha:
            
            # 2. Validación: "El caso Thiago Messi" (Contradicción Trabajo vs Descanso)
            # Buscamos otras preferencias del mismo día para el mismo empleado
            otras_prefs = Preferencia.objects.filter(
                empleado=self.empleado,
                fecha=self.fecha
            ).exclude(pk=self.pk) # Excluímos la propia si estamos editando

            for p in otras_prefs:
                # Solo nos importa si los deseos son OPUESTOS (Trabajar vs Descansar)
                if self.deseo != p.deseo:
                    # Verificamos si los turnos se pisan
                    hay_superposicion = (
                        self.tipo_turno is None or      # Yo pido para todo el día
                        p.tipo_turno is None or         # El otro es para todo el día
                        self.tipo_turno_id == p.tipo_turno_id  # Mismo turno
                    )
                    
                    if hay_superposicion:
                        raise ValidationError({
                            'deseo': f"Contradicción: Ya existe una preferencia opuesta ('{p.get_deseo_display()}') para este día/turno."
                        })

            # 3. Validación: No pedir "TRABAJAR" si estoy Ausente (NoDisponibilidad)
            if self.deseo == self.Deseo.TRABAJAR:
                # Buscamos si hay alguna ausencia que cubra esta fecha
                ausencias = NoDisponibilidad.objects.filter(
                    empleado=self.empleado,
                    fecha_inicio__lte=self.fecha,
                    fecha_fin__gte=self.fecha
                )
                
                for aus in ausencias:
                    # Chequeamos superposición de turno
                    hay_superposicion = (
                        aus.tipo_turno is None or   # Ausencia total
                        self.tipo_turno is None or  # Quiero trabajar todo el día (y hay ausencia parcial o total)
                        aus.tipo_turno_id == self.tipo_turno_id
                    )
                    
                    if hay_superposicion:
                        raise ValidationError(
                            f"Imposible solicitar 'TRABAJAR': El empleado tiene una ausencia registrada para esta fecha ({aus.motivo})."
                        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        turno_str = self.tipo_turno.nombre if self.tipo_turno else "DÍA COMPLETO"
        return f"{self.empleado}: {self.get_deseo_display()} en {self.fecha} ({turno_str})"

# ==============================================================================
# CONFIGURACIÓN DEL ALGORITMO
# ==============================================================================

class ConfiguracionAlgoritmo(models.Model):
    """Modelo único para parámetros técnicos y de negocio (Singleton por bandera 'activa')."""
    nombre = models.CharField(max_length=50, default="Configuración Estándar")
    activa = models.BooleanField(default=True, help_text="Solo debe haber una activa por defecto")

    # Parámetros Técnicos
    tamano_poblacion = models.IntegerField(
        default=100,
        verbose_name="Población",
        validators=[MinValueValidator(10), MaxValueValidator(10000)],
        help_text="Tamaño de la población (entre 10 y 10000)."
    )
    generaciones = models.IntegerField(
        default=15,
        verbose_name="Generaciones",
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="Cantidad de generaciones (entre 1 y 10000)."
    )
    prob_cruce = models.FloatField(default=0.85, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    prob_mutacion = models.FloatField(default=0.20, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    elitismo = models.BooleanField(default=True)
    semilla = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Fijar para reproducibilidad (entero no negativo)."
    )

    # Estrategias
    class EstrategiaSeleccion(models.TextChoices):
        TORNEO = 'torneo_deterministico', 'Torneo Determinístico'
        RANKING = 'ranking_lineal', 'Ranking Lineal'
    estrategia_seleccion = models.CharField(max_length=50, choices=EstrategiaSeleccion.choices, default=EstrategiaSeleccion.TORNEO)

    class EstrategiaCruce(models.TextChoices):
        BLOQUES_VERTICALES = 'bloques_verticales', 'Bloques Verticales'
        BLOQUES_HORIZONTALES = 'bloques_horizontales', 'Bloques Horizontales'
        DOS_PUNTOS = 'dos_puntos', 'Dos Puntos'
    estrategia_cruce = models.CharField(max_length=50, choices=EstrategiaCruce.choices, default=EstrategiaCruce.BLOQUES_VERTICALES)

    class EstrategiaMutacion(models.TextChoices):
        HIBRIDA = 'hibrida_adaptativa', 'Híbrida'
        REASIGNAR = 'reasignar_turno', 'Reasignar Turno'
        INTERCAMBIO = 'intercambio_dia', 'Intercambio de Día'
        FLIP = 'flip_simple', 'Flip Simple'
    estrategia_mutacion = models.CharField(max_length=50, choices=EstrategiaMutacion.choices, default=EstrategiaMutacion.HIBRIDA)

    # Pesos de Negocio
    peso_equidad_general = models.FloatField(default=1.0, validators=[MinValueValidator(0.0)])
    peso_equidad_dificil = models.FloatField(default=1.5, validators=[MinValueValidator(0.0)])
    peso_preferencia_dias_libres = models.FloatField(default=2.0, validators=[MinValueValidator(0.0)])
    peso_preferencia_turno = models.FloatField(default=0.5, validators=[MinValueValidator(0.0)])
    factor_alpha_pte = models.FloatField(default=0.5, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    tolerancia_general = models.IntegerField(
        default=8,
        verbose_name="Tolerancia Horas General",
        validators=[MinValueValidator(0), MaxValueValidator(168)],
        help_text="Horas de tolerancia general (0-168)."
    )
    tolerancia_dificil = models.IntegerField(
        default=4,
        verbose_name="Tolerancia Turnos Difíciles",
        validators=[MinValueValidator(0), MaxValueValidator(168)],
        help_text="Tolerancia para turnos difíciles (0-168)."
    )

    class Meta:
        verbose_name = "Configuración del Algoritmo"
        verbose_name_plural = "Configuraciones"

    def save(self, *args, **kwargs):
        # Forzamos validación de campo/modelo antes de persistir
        self.full_clean()
        if self.activa:
            ConfiguracionAlgoritmo.objects.filter(activa=True).exclude(pk=self.pk).update(activa=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} (Pop:{self.tamano_poblacion}, Gen:{self.generaciones})"


# ==============================================================================
# RESULTADOS Y EJECUCIÓN
# ==============================================================================

class Cronograma(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        OPTIMIZANDO = 'OPTIMIZANDO', 'En Proceso'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        FALLIDO = 'FALLIDO', 'Fallido por Cobertura'

    especialidad = models.CharField(max_length=20, choices=Empleado.TipoEspecialidad.choices)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    
    plantilla_demanda = models.ForeignKey(PlantillaDemanda, on_delete=models.SET_NULL, null=True, blank=True)
    configuracion_usada = models.ForeignKey(ConfiguracionAlgoritmo, on_delete=models.SET_NULL, null=True, blank=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fitness = models.FloatField(null=True, blank=True, help_text="Puntaje de calidad (Mayor es mejor)")
    tiempo_ejecucion = models.FloatField(null=True, blank=True, verbose_name="Tiempo (s)")
    reporte_analisis = models.JSONField(null=True, blank=True, verbose_name="Explicabilidad (JSON)")

    def clean(self):
        super().clean()
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({'fecha_fin': 'La fecha de fin no puede ser anterior a la fecha de inicio.'})

        if self.plantilla_demanda and self.especialidad != self.plantilla_demanda.especialidad:
            validar_consistencia_especialidad(self, self.plantilla_demanda, 'plantilla_demanda')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Plan {self.get_especialidad_display()} ({self.fecha_inicio} al {self.fecha_fin}) - {self.estado}"


class Asignacion(models.Model):
    """Tabla de rompimiento: Resultado final de quién trabaja cuándo y qué."""
    cronograma = models.ForeignKey(Cronograma, on_delete=models.CASCADE, related_name='asignaciones')
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    fecha = models.DateField()
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)

    def clean(self):
        super().clean()

        especialidades = []

        if self.cronograma_id:
            especialidades.append(self.cronograma.especialidad)

        if self.empleado_id:
            especialidades.append(self.empleado.especialidad)

        if self.tipo_turno_id:
            especialidades.append(self.tipo_turno.especialidad)

        if len(set(especialidades)) > 1:
            raise ValidationError(
                "La asignación debe pertenecer a una única especialidad consistente "
                "(cronograma, empleado y tipo de turno)."
            )

    class Meta:
        verbose_name_plural = "Asignaciones (Resultado)"
        unique_together = ('cronograma', 'empleado', 'fecha') 


class TrabajoPlanificacion(models.Model):
    """
    Persistencia temporal del contexto de optimización mientras la API procesa.
    """
    job_id = models.UUIDField(primary_key=True, editable=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    especialidad = models.CharField(max_length=20)
    payload_original = models.JSONField()
    
    plantilla_demanda = models.ForeignKey(PlantillaDemanda, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Job {self.job_id} ({self.especialidad})"