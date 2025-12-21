from django.db import models

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

    def __str__(self):
        return f"{self.nombre_completo} ({self.legajo})"

class TipoTurno(models.Model):
    nombre = models.CharField(max_length=50) 
    abreviatura = models.CharField(max_length=5) 
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    duracion_horas = models.DecimalField(max_digits=4, decimal_places=2)

    def __str__(self):
        return self.nombre

class RequerimientoTurno(models.Model):
    class DiaSemana(models.IntegerChoices):
        LUNES = 0, 'Lunes'
        MARTES = 1, 'Martes'
        MIERCOLES = 2, 'Miércoles'
        JUEVES = 3, 'Jueves'
        VIERNES = 4, 'Viernes'
        SABADO = 5, 'Sábado'
        DOMINGO = 6, 'Domingo'

    dia_semana = models.IntegerField(choices=DiaSemana.choices)
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.CASCADE)
    cantidad_minima_senior = models.PositiveIntegerField()
    cantidad_minima_junior = models.PositiveIntegerField()

class NoDisponibilidad(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='no_disponibilidades')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    # Si es NULL, significa "Todo el día" (o todos los días del rango).
    # Si tiene valor, afecta solo a ese turno específico.
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.SET_NULL, null=True, blank=True)
    motivo = models.CharField(max_length=255)

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