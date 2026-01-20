from django.urls import path

from . import views
from . import api_empleados

urlpatterns = [
    # API para autocompletar legajos de empleados
    path('api/empleados/legajos/', api_empleados.api_empleados_legajos, name='api_empleados_legajos'),
    # ==========================================================================
    # LANDING Y DASHBOARD
    # ==========================================================================
    path('', views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('accounts/register/', views.registrar_usuario, name='register'),

    # ==========================================================================
    # MOTOR DE PLANIFICACIÓN (WIZARD & API)
    # ==========================================================================
    # Mantenemos ambos nombres para 'generar/' por compatibilidad con templates viejos
    path('generar/', views.pagina_generador, name='vista_generador'),
    path('generar/', views.pagina_generador, name='generar_cronograma'),

    # Endpoints JSON para el Frontend
    path('api/plantillas/', views.api_get_plantillas, name='api_get_plantillas'),
    path('api/planificar/iniciar/', views.iniciar_planificacion, name='api_iniciar_planificacion'),
    path('api/planificar/estado/<str:job_id>/', views.verificar_estado_planificacion, name='api_estado_planificacion'),

    # ==========================================================================
    # GESTIÓN DE CRONOGRAMAS (VISUALIZACIÓN)
    # ==========================================================================
    path('cronogramas/', views.CronogramaListView.as_view(), name='cronograma_list'),
    
    # Vistas detalladas (usan cronograma_id según tu views.py)
    path('cronograma/<int:cronograma_id>/', views.ver_cronograma, name='ver_cronograma'),
    path('cronograma/<int:cronograma_id>/diario/', views.ver_cronograma_diario, name='ver_cronograma_diario'),
    
    # Acciones y Análisis (usan pk estándar de CBVs)
    path('cronograma/<int:pk>/analisis/', views.CronogramaAnalisisView.as_view(), name='cronograma_analisis'),
    path('cronograma/<int:pk>/publicar/', views.publicar_cronograma, name='cronograma_publish'),
    path('cronograma/<int:pk>/despublicar/', views.despublicar_cronograma, name='cronograma_unpublish'),
    path('cronogramas/<int:pk>/eliminar/', views.CronogramaDeleteView.as_view(), name='cronograma_delete'),

    # Exportar como PDF
    path('cronograma/<int:cronograma_id>/exportar/pdf/', views.exportar_cronograma_pdf, name='exportar_pdf'),
    # Exportar a Excel
    path('cronograma/<int:cronograma_id>/exportar/excel/', views.exportar_cronograma_excel, name='exportar_excel'),

    # ==========================================================================
    # GESTIÓN DE EMPLEADOS
    # ==========================================================================
    path('empleados/', views.EmpleadoListView.as_view(), name='empleado_list'),
    path('empleados/crear/', views.EmpleadoCreateView.as_view(), name='empleado_create'),
    path('empleados/<int:pk>/editar/', views.EmpleadoUpdateView.as_view(), name='empleado_update'),
    path('empleados/<int:pk>/eliminar/', views.EmpleadoDeleteView.as_view(), name='empleado_delete'),

    # ==========================================================================
    # GESTIÓN DE AUSENCIAS Y PREFERENCIAS
    # ==========================================================================
    # Ausencias
    path('ausencias/', views.NoDisponibilidadListView.as_view(), name='nodisponibilidad_list'),
    path('ausencias/crear/', views.NoDisponibilidadCreateView.as_view(), name='nodisponibilidad_create'),
    path('ausencias/<int:pk>/editar/', views.NoDisponibilidadUpdateView.as_view(), name='nodisponibilidad_update'),
    path('ausencias/<int:pk>/eliminar/', views.NoDisponibilidadDeleteView.as_view(), name='nodisponibilidad_delete'),

    # Preferencias
    path('preferencias/', views.PreferenciaListView.as_view(), name='preferencia_list'),
    path('preferencias/crear/', views.PreferenciaCreateView.as_view(), name='preferencia_create'),
    path('preferencias/<int:pk>/editar/', views.PreferenciaUpdateView.as_view(), name='preferencia_update'),
    path('preferencias/<int:pk>/eliminar/', views.PreferenciaDeleteView.as_view(), name='preferencia_delete'),

    # ==========================================================================
    # CONFIGURACIÓN DEL SISTEMA (Reglas, Turnos, Plantillas)
    # ==========================================================================
    
    # Tipos de Turno
    path('config/turnos/', views.ConfiguracionTurnosListView.as_view(), name='tipoturno_list'),
    path('config/turnos/<str:especialidad>/editar/', views.config_turnos_edit, name='tipoturno_edit'),

    # Plantillas de Demanda (Maestro)
    path('config/plantillas/', views.PlantillaListView.as_view(), name='plantilla_list'),
    path('config/plantillas/crear/', views.PlantillaCreateView.as_view(), name='plantilla_create'),
    path('config/plantillas/<int:pk>/editar/', views.PlantillaUpdateView.as_view(), name='plantilla_update'), # actualizar
    path('config/plantillas/<int:pk>/', views.PlantillaDetailView.as_view(), name='plantilla_detail'),
    path('config/plantillas/<int:pk>/eliminar/', views.PlantillaDeleteView.as_view(), name='plantilla_delete'),
    path('config/plantillas/<int:pk>/duplicar/', views.duplicar_plantilla, name='plantilla_duplicate'), # duplicar

    # Reglas y Excepciones (Detalle - Hijos de Plantilla)
    path('config/plantillas/<int:plantilla_id>/regla/nueva/', views.ReglaCreateView.as_view(), name='regla_create'),
    path('config/regla/<int:pk>/editar/', views.ReglaUpdateView.as_view(), name='regla_update'),
    path('config/regla/<int:pk>/eliminar/', views.ReglaDeleteView.as_view(), name='regla_delete'),
    
    # APIs AJAX para edición inline
    path('api/plantillas/<int:plantilla_id>/regla/crear/', views.api_crear_regla, name='api_crear_regla'),
    path('api/regla/<int:regla_id>/actualizar/', views.api_actualizar_regla, name='api_actualizar_regla'),
    path('api/regla/<int:regla_id>/eliminar/', views.api_eliminar_regla, name='api_eliminar_regla'),
    
    path('config/plantillas/<int:plantilla_id>/excepcion/nueva/', views.ExcepcionCreateView.as_view(), name='excepcion_create'),
    path('config/excepcion/<int:pk>/eliminar/', views.ExcepcionDeleteView.as_view(), name='excepcion_delete'),

    # Panel Admin del Algoritmo
    path('admin-panel/', views.ConfiguracionDashboardView.as_view(), name='config_dashboard'),
    path('admin-panel/simple/', views.ConfiguracionSimpleView.as_view(), name='config_simple'),
    path('admin-panel/avanzada/', views.ConfiguracionAvanzadaView.as_view(), name='config_avanzada'),
]