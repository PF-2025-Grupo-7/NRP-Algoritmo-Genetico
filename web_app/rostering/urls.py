from django.urls import path
from . import views

urlpatterns = [
    # Ruta raíz: Redirige directo al generador
    path('', views.pagina_generador, name='vista_generador'),
    
    # Si quieres mantener la url /generar/ también (opcional)
    path('generar/', views.pagina_generador, name='vista_generador_explicita'),

    # APIs (Endpoints JSON)
    path('api/planificar/iniciar/', views.iniciar_planificacion, name='api_iniciar_planificacion'),
    path('api/planificar/estado/<str:job_id>/', views.verificar_estado_planificacion, name='api_estado_planificacion'),
]