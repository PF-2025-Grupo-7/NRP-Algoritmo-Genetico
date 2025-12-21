from django.shortcuts import render
from .models import Empleado, Cronograma, Asignacion

def index(request):
    return render(request, 'rostering/index.html')

def gestion_personal(request):
    empleados = Empleado.objects.all()
    return render(request, 'rostering/personal.html', {'empleados': empleados})

def gestion_preferencias(request):
    # Lógica para cargar/editar preferencias de los empleados
    return render(request, 'rostering/preferencias.html')

def ver_planificacion(request):
    cronogramas = Cronograma.objects.all().order_by('-anio', '-mes')
    return render(request, 'rostering/calendario.html', {'cronogramas': cronogramas})

def nueva_planificacion(request):
    # Aquí es donde en el futuro llamaremos al motor de AG
    return render(request, 'rostering/nueva_planificacion.html')