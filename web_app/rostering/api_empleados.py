from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Empleado

@login_required
def api_empleados_legajos(request):
    """
    Devuelve un listado de legajos, nombre y especialidad de todos los empleados activos.
    Permite filtrar por legajo (parcial) usando ?q=123
    """
    q = request.GET.get('q', '').strip()
    empleados = Empleado.objects.filter(activo=True)
    if q:
        from django.db.models import Q
        empleados = empleados.filter(
            Q(legajo__icontains=q) |
            Q(nombre_completo__icontains=q) |
            Q(especialidad__icontains=q)
        )
    data = [
        {
            'id': emp.pk,
            'legajo': emp.legajo,
            'nombre': emp.nombre_completo,
            'especialidad': emp.get_especialidad_display(),
            'especialidad_codigo': emp.especialidad,
        }
        for emp in empleados.order_by('legajo')
    ]
    return JsonResponse({'empleados': data})
