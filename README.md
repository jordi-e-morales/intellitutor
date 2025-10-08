# Tutor Inteligente - Demo Educación

Este proyecto incluye una app Flask con autenticación y un tutor RAG que integra PostgreSQL, Qdrant y Ollama.

## Requisitos
- Python 3.11 (recomendado)
- Docker Desktop
- Ollama instalado (para LLM y embeddings)
- PowerShell (Windows)

## Instalación
1. Crear/activar venv 3.11 (usando uv):
   ```powershell
   uv venv --python 3.11
   .\.venv\Scripts\activate
   ```
2. Instalar dependencias:
   ```powershell
   uv pip install -r .\requirements.txt
   ```

## Servicios requeridos

### PostgreSQL
1. Levantar contenedor (si no existe):
   ```powershell
   docker run -d --name pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15
   ```
2. Bootstrap de base de datos y usuario (opción 1) con script idempotente:
   ```powershell
   ./bootstrap_db.ps1
   ```
   Crea (si no existen):
   - usuario: `tutor_user`
   - base: `tutor_db`
   - otorga privilegios

3. Inicializar esquema y poblar datos demo:
   ```powershell
   python .\db_schema.py
   python .\populate_db.py
   ```

#### Alternativa Linux / macOS (sin PowerShell)

Si no deseas usar `bootstrap_db.ps1`, puedes ejecutar los mismos pasos con `docker exec` y `psql` directamente:

```bash
# 1) Crear contenedor de Postgres (si no existe)
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15

# 2) Crear usuario si no existe (idempotente)
docker exec -i pg psql -U postgres -v ON_ERROR_STOP=1 -c "DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'tutor_user') THEN
    CREATE ROLE tutor_user LOGIN PASSWORD 'tutor_pass';
  END IF;
END$$;"

# 3) Crear base de datos si no existe (idempotente)
docker exec -i pg psql -U postgres -v ON_ERROR_STOP=1 -c "DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'tutor_db') THEN
    CREATE DATABASE tutor_db OWNER tutor_user;
  END IF;
END$$;"

# 4) Conceder privilegios (seguro de repetir)
docker exec -i pg psql -U postgres -v ON_ERROR_STOP=1 -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE \"tutor_db\" TO tutor_user;"

# 5) Inicializar tablas y datos demo desde tu host
python ./db_schema.py
python ./populate_db.py
```

Notas:
- Las credenciales por defecto que usa la app son `host=localhost`, `port=5432`, `db=tutor_db`, `user=tutor_user`, `password=tutor_pass`.
- Asegúrate de que el puerto 5432 no esté ocupado y que el contenedor `pg` esté en ejecución (`docker ps`).

### Qdrant (Vector DB)

Levantar Qdrant:
```powershell
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
```
- URL esperada: `http://localhost:6333`
- Colección esperada: `tutor_demo` (ver `agents_rag.py`)

### Ollama (LLM y embeddings)

1. Instalar y ejecutar Ollama.
2. Descargar modelos requeridos:
```powershell
ollama pull gemma3:4b
ollama pull nomic-embed-text
```
- El servicio escucha en `http://localhost:11434`.

### Ingesta de documentos (RAG)

Con Qdrant y Ollama corriendo y los modelos descargados, ejecutar la ingesta para poblar la colección `tutor_demo` con embeddings:
```powershell
python .\ingest_pipeline.py
```
Esto almacenará los chunks vectorizados en Qdrant con metadata de materias.

## Ejecutar la aplicación

1. Ejecutar Flask (UI + API):
```powershell
python .\run_app.py
```
- URL: http://localhost:5000

2. Iniciar sesión (datos demo desde `populate_db.py`):
- Email: `ana.garcia@email.com`
- Password: `ana123`

## Variables de entorno (opcionales)
- `SECRET_KEY`: clave de sesión Flask (por defecto `your-secret-key-here`).
- Para `db_schema.py` puedes usar:
  ```powershell
  $env:PG_HOST="localhost"
  $env:PG_PORT="5432"
  $env:PG_DB="tutor_db"
  $env:PG_USER="tutor_user"
  $env:PG_PASSWORD="tutor_pass"
  ```

## Notas
- `auth_app.py` usa credenciales de DB internas: `tutor_user`/`tutor_pass` y DB `tutor_db` en `localhost:5432`.
- `agents_rag.py` usa `QDRANT_URL=http://localhost:6333`, `QDRANT_COLLECTION=tutor_demo`, LLM `gemma3:4b` y embeddings `nomic-embed-text` vía Ollama.
- Asegúrate de que Postgres, Qdrant y Ollama estén corriendo antes de usar el chat.
