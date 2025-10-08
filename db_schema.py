# db_schema.py
"""
Definición de la estructura de la base de datos para estudiantes y materias.
Utiliza PostgreSQL (en contenedor Docker) para robustez y escalabilidad.
"""

import psycopg2
import os

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "tutor_db")
PG_USER = os.getenv("PG_USER", "tutor_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "tutor_pass")

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    password TEXT,
    career TEXT,
    grade TEXT,
    language TEXT DEFAULT 'es',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subjects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    language TEXT DEFAULT 'es'
);

CREATE TABLE IF NOT EXISTS enrollments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id),
    subject_id INTEGER REFERENCES subjects(id),
    progress REAL DEFAULT 0.0,
    last_interaction TIMESTAMP
);

-- Settings table (single row) for runtime configuration of the app/agents
CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    llm_backend TEXT DEFAULT 'ollama',
    llm_model TEXT DEFAULT 'gemma3:4b',
    ollama_url TEXT DEFAULT 'http://localhost:11434',
    openai_base_url TEXT DEFAULT 'https://api.openai.com',
    qdrant_url TEXT DEFAULT 'http://localhost:6333',
    qdrant_collection TEXT DEFAULT 'tutor_demo',
    logging_enabled BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Observability: metrics per chat call
CREATE TABLE IF NOT EXISTS chat_metrics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    subject_id INTEGER,
    backend TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def init_db():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute(SCHEMA)
    # --- Lightweight migrations for existing installations ---
    # Ensure new column exists even if table was created before
    cur.execute("ALTER TABLE app_settings ADD COLUMN IF NOT EXISTS openai_base_url TEXT;")
    cur.execute("ALTER TABLE app_settings ALTER COLUMN openai_base_url SET DEFAULT 'https://api.openai.com';")
    # Ensure single default row in app_settings
    cur.execute("SELECT COUNT(*) FROM app_settings;")
    count = cur.fetchone()[0]
    if count == 0:
        cur.execute(
            """
            INSERT INTO app_settings (id, llm_backend, llm_model, ollama_url, openai_base_url, qdrant_url, qdrant_collection, logging_enabled)
            VALUES (1, 'ollama', 'gemma3:4b', 'http://localhost:11434', 'https://api.openai.com', 'http://localhost:6333', 'tutor_demo', TRUE)
            ON CONFLICT (id) DO NOTHING;
            """
        )
    else:
        # Backfill null value for existing row
        cur.execute("UPDATE app_settings SET openai_base_url = COALESCE(openai_base_url, 'https://api.openai.com') WHERE id=1;")
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Base de datos PostgreSQL inicializada con las tablas: students, subjects, enrollments.")
