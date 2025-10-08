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
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Base de datos PostgreSQL inicializada con las tablas: students, subjects, enrollments.")
