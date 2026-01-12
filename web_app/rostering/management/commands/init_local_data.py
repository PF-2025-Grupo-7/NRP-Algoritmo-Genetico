from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User # <--- Importante
from rostering.models import Empleado, PlantillaDemanda
import os

class Command(BaseCommand):
    help = 'Carga datos iniciales y crea superusuario si no existen (Idempotente)'

    def handle(self, *args, **options):
        self.stdout.write("🕵️  Verificando estado de la Base de Datos...")

        # --- PARTE 1: DATOS DE NEGOCIO (Fixtures) ---
        empleados_count = Empleado.objects.count()
        
        if empleados_count == 0:
            self.stdout.write(self.style.WARNING("⚠️  Datos de negocio vacíos. Cargando semillas..."))
            try:
                call_command('loaddata', 'rostering/fixtures/datos_iniciales.json')
                self.stdout.write(self.style.SUCCESS("✅  Datos cargados exitosamente."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌  Error cargando datos: {e}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✨  Datos de negocio OK ({empleados_count} empleados)."))

        # --- PARTE 2: SUPERUSUARIO (Admin) ---
        # Verificamos independientemente si existe el admin, sin importar si cargamos datos o no
        if not User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING("⚠️  No existe superusuario. Creando 'admin'..."))
            try:
                # Podés cambiar el pass o mail aquí
                User.objects.create_superuser('admin', 'admin@hospital.com', 'admin')
                self.stdout.write(self.style.SUCCESS("👤  Superusuario creado: admin / admin"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌  Error creando admin: {e}"))
        else:
            self.stdout.write(self.style.SUCCESS("👤  El usuario 'admin' ya existe."))