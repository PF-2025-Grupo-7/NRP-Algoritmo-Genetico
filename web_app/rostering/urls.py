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

    # Cronogramas
    path('cronogramas/', views.CronogramaListView.as_view(), name='cronograma_list'),
    path('cronogramas/<int:pk>/eliminar/', views.CronogramaDeleteView.as_view(), name='cronograma_delete'),

    # Tipos de Turno
    path('config/turnos/', views.TipoTurnoListView.as_view(), name='tipoturno_list'),
    path('config/turnos/crear/', views.TipoTurnoCreateView.as_view(), name='tipoturno_create'),
    path('config/turnos/<int:pk>/editar/', views.TipoTurnoUpdateView.as_view(), name='tipoturno_update'),
    path('config/turnos/<int:pk>/eliminar/', views.TipoTurnoDeleteView.as_view(), name='tipoturno_delete'),

    # Ausencias / No Disponibilidad
    path('ausencias/', views.NoDisponibilidadListView.as_view(), name='nodisponibilidad_list'),
    path('ausencias/crear/', views.NoDisponibilidadCreateView.as_view(), name='nodisponibilidad_create'),
    path('ausencias/<int:pk>/editar/', views.NoDisponibilidadUpdateView.as_view(), name='nodisponibilidad_update'),
    path('ausencias/<int:pk>/eliminar/', views.NoDisponibilidadDeleteView.as_view(), name='nodisponibilidad_delete'),

    # Preferencias
    path('preferencias/', views.PreferenciaListView.as_view(), name='preferencia_list'),
    path('preferencias/crear/', views.PreferenciaCreateView.as_view(), name='preferencia_create'),
    path('preferencias/<int:pk>/editar/', views.PreferenciaUpdateView.as_view(), name='preferencia_update'),
    path('preferencias/<int:pk>/eliminar/', views.PreferenciaDeleteView.as_view(), name='preferencia_delete'),
]
