NRP-Algoritmo-Genetico
======================

Breve guía para poner en marcha el proyecto y ejecutar las estrategias.

Requisitos mínimos
- Python 3.11 (u 3.10+)
- Se recomienda crear un entorno virtual para este proyecto.

Crear y activar un entorno virtual (Windows PowerShell)
```powershell
# Desde la raíz del repositorio
python -m venv .venv311
# Activar el virtualenv (PowerShell)
.\.venv311\Scripts\Activate.ps1
# O (si tu shell usa cmd): .\.venv311\Scripts\activate.bat
```

Instalar dependencias (sugeridas)
```powershell
pip install --upgrade pip
pip install numpy mealpy
# Si quieres fijar dependencias, crea un requirements.txt y luego:
# pip install -r requirements.txt
```

Archivos y comandos principales
- `estrategias/mealpy_ga/ejecutar.py` : Runner que usa la implementación basada en `mealpy` (OriginalGA).
- `estrategias/ga_propio/ejecutar_ga_propio.py` : Runner de la implementación propia del GA (sin dependencia de mealpy).

Ejecutar los scripts (desde la raíz del repo, con el virtualenv activado)
```powershell
# GA propio
.\.venv311\Scripts\python.exe .\estrategias\ga_propio\ejecutar_ga_propio.py

# GA basado en mealpy
.\.venv311\Scripts\python.exe .\estrategias\mealpy_ga\ejecutar.py
```

Nota sobre el entorno virtual y Git
- El directorio del entorno virtual `.venv311/` está incluido en `.gitignore` y NO debe subirse a GitHub.
- Si accidentalmente ya lo añadiste al repositorio, puedes eliminarlo del control de versiones con:
```powershell
git rm -r --cached .venv311
git commit -m "Remove venv from repo and add .gitignore"
```

Notas de mantenimiento
- Las penalizaciones compartidas ahora están en `penalizaciones/` en la raíz del proyecto. Evita duplicarlas en las carpetas de estrategia.
- Si prefieres ejecutar como módulo (python -m), añade `__init__.py` en los paquetes según tu flujo de trabajo.

Contacto
- Proyecto mantenido por el equipo NRP (PF-2025-Grupo-7). Para preguntas abre un issue o contacta al autor del repo.
