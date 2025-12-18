# Usamos una imagen base oficial de Python ligera
FROM python:3.12-slim

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos primero los requerimientos para aprovechar la caché de Docker
COPY requirements.txt .

# Instalamos las dependencias
# --no-cache-dir mantiene la imagen ligera
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código fuente al contenedor
COPY . .

# Exponemos el puerto 8000
EXPOSE 8000

# Comando por defecto para producción (sin reload). 
# NOTA: Usamos host 0.0.0.0 para que sea accesible desde fuera del contenedor
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]