from django.urls import path
from . import views

urlpatterns = [
    # Ruta raíz: Redirige directo al generador
    path('', views.pagina_generador, name='vista_generador'),
    
    # Si quieres mantener la url /generar/ también (opcional)
    path('generar/', views.pagina_generador, name='vista_generador_explicita'),
    path('accounts/register/', views.registrar_usuario, name='register'),

    # NUEVA RUTA: Ver el resultado visual
    path('cronograma/<int:cronograma_id>/', views.ver_cronograma, name='ver_cronograma'),
    path('cronograma/<int:cronograma_id>/diario/', views.ver_cronograma_diario, name='ver_cronograma_diario'),


    # APIs (Endpoints JSON)
    path('api/planificar/iniciar/', views.iniciar_planificacion, name='api_iniciar_planificacion'),
    path('api/planificar/estado/<str:job_id>/', views.verificar_estado_planificacion, name='api_estado_planificacion'),

    # Rutas de Empleados
    path('empleados/', views.EmpleadoListView.as_view(), name='empleado_list'),
    path('empleados/crear/', views.EmpleadoCreateView.as_view(), name='empleado_create'),
    path('empleados/<int:pk>/editar/', views.EmpleadoUpdateView.as_view(), name='empleado_update'),
    path('empleados/<int:pk>/eliminar/', views.EmpleadoDeleteView.as_view(), name='empleado_delete'),
]