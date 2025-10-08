# agents.py
"""
Esqueleto de agentes CrewAI para la demo de Tutor Inteligente.
"""

from crewai import Agent, Task
import psycopg2
import os

# Configuración de conexión PostgreSQL
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "tutor_db")
PG_USER = os.getenv("PG_USER", "tutor_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "tutor_pass")

def get_pg_conn():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )

# --- Agente Perfil Estudiante ---
class StudentProfileAgent(Agent):
    def __init__(self):
        pass

    def get_profile(self, student_id):
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, email, career, grade, language FROM students WHERE id=%s", (student_id,))
                return cur.fetchone()

    def update_profile(self, student_id, updates):
        # updates: dict con los campos a actualizar
        set_clause = ", ".join([f"{k}=%s" for k in updates.keys()])
        values = list(updates.values()) + [student_id]
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE students SET {set_clause} WHERE id=%s", values)
                conn.commit()

# --- Agente Materias ---
class SubjectAgent(Agent):
    def __init__(self):
        pass

    def get_subjects(self, student_id):
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT s.id, s.name, s.description, e.progress
                    FROM subjects s
                    JOIN enrollments e ON s.id = e.subject_id
                    WHERE e.student_id = %s
                """, (student_id,))
                return cur.fetchall()

    def update_progress(self, student_id, subject_id, progress):
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE enrollments SET progress=%s, last_interaction=NOW() WHERE student_id=%s AND subject_id=%s",
                    (progress, student_id, subject_id)
                )
                conn.commit()

# --- Agente Tutor (RAG) ---
class TutorAgent(Agent):
    def __init__(self, qdrant_client, llm_client, profile_agent, subject_agent):
        self.qdrant = qdrant_client
        self.llm = llm_client
        self.profile_agent = profile_agent
        self.subject_agent = subject_agent

    def answer_question(self, student_id, question):
        # 1. Obtener perfil y materias
        profile = self.profile_agent.get_profile(student_id)
        subjects = self.subject_agent.get_subjects(student_id)
        # 2. Recuperar chunks relevantes de Qdrant
        # 3. Llamar al LLM con contexto
        # 4. Devolver respuesta
        pass

# --- Ejemplo de inicialización (no funcional, solo referencia) ---
if __name__ == "__main__":
    qdrant_client = None  # Cliente real de Qdrant
    llm_client = None  # Cliente real del LLM

    profile_agent = StudentProfileAgent()
    subject_agent = SubjectAgent()
    tutor_agent = TutorAgent(qdrant_client, llm_client, profile_agent, subject_agent)

    # Ejemplo de uso:
    # tutor_agent.answer_question(student_id=1, question="¿Qué es la programación lineal?")
