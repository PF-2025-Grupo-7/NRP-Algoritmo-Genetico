from django.urls import path
from . import views

app_name = 'rostering'

urlpatterns = [
    # Rutas para cumplir con las interfaces de Figma
    path('', views.index, name='index'),
    path('personal/', views.gestion_personal, name='personal'),
    path('preferencias/', views.gestion_preferencias, name='preferencias'),
    path('planificacion/', views.ver_planificacion, name='ver_planificacion'),
    path('planificar/nueva/', views.nueva_planificacion, name='nueva_planificacion'),
]