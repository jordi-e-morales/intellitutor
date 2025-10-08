# No es necesario un Dockerfile personalizado para la base de datos PostgreSQL, se usa la imagen oficial.
# Cuando quieras conteinerizar la app, puedes crear un Dockerfile como este:

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expone Flask por defecto
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
EXPOSE 5000

# Ejecuta la app Flask directamente
CMD ["python", "auth_app.py"]
