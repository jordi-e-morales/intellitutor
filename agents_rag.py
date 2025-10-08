import requests
# agents_rag.py
"""
Agentes para demo de Tutor Inteligente con RAG y metadata.
- StudentProfileAgent: consulta materias inscritas en PostgreSQL
- TutorAgent: consulta Qdrant filtrando por metadata y orquesta la respuesta
"""


import psycopg2
import time
from typing import Optional
import os
from langchain_qdrant import Qdrant
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from crewai import Agent, Task, Crew

# Configuración PostgreSQL
PG_HOST = "localhost"
PG_PORT = 5432
PG_DB = "tutor_db"
PG_USER = "tutor_user"
PG_PASSWORD = "tutor_pass"

# Configuración Qdrant (valores por defecto; pueden ser sobrescritos por app_settings)
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "tutor_demo"
EMBED_MODEL = "nomic-embed-text"

def load_settings_from_db():
    """Lee la fila de configuración desde app_settings (id=1)."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD,
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT llm_backend, llm_model, ollama_url, qdrant_url, qdrant_collection, logging_enabled
                FROM app_settings WHERE id=1
                """
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return {
                'llm_backend': 'ollama',
                'llm_model': 'gemma3:4b',
                'ollama_url': 'http://localhost:11434',
                'qdrant_url': QDRANT_URL,
                'qdrant_collection': QDRANT_COLLECTION,
                'logging_enabled': True,
            }
        keys = ['llm_backend','llm_model','ollama_url','qdrant_url','qdrant_collection','logging_enabled']
        return dict(zip(keys, row))
    except Exception:
        # En caso de error, usar defaults
        return {
            'llm_backend': 'ollama',
            'llm_model': 'gemma3:4b',
            'ollama_url': 'http://localhost:11434',
            'qdrant_url': QDRANT_URL,
            'qdrant_collection': QDRANT_COLLECTION,
            'logging_enabled': True,
        }

def estimate_tokens(text: str) -> int:
    """Estimación simple de tokens si tiktoken no está disponible."""
    try:
        import tiktoken  # type: ignore
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text or ""))
    except Exception:
        return max(1, len((text or "").split()))


class StudentProfileAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_subject_ids(self, student_id):
        import psycopg2
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT subject_id FROM enrollments WHERE student_id = %s
            """, (student_id,))
            return [row[0] for row in cur.fetchall()]


class TutorAgent(Agent):
    def call_llm(self, backend: str, prompt: str, model: str, base_url: str) -> str:
        """
        Llama al proveedor de LLM según el backend seleccionado.
        - backend == 'ollama': usa /api/generate de Ollama
        - backend == 'openai': usa /v1/chat/completions compatible con OpenAI
        """
        if backend == "ollama":
            url = f"{base_url.rstrip('/')}/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False}
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json().get("response", "")
        elif backend == "openai":
            base = base_url.rstrip('/') or "https://api.openai.com"
            url = f"{base}/v1/chat/completions"
            api_key = os.environ.get("OPENAI_API_KEY")
            headers = {
                "Authorization": f"Bearer {api_key}" if api_key else "",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Eres un tutor educativo útil."},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        else:
            raise ValueError(f"Backend LLM no soportado: {backend}")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_subject_context(self, subject_ids):
        """
        Dado uno o varios subject_ids, retorna el contenido de la descripción de la materia (campo description de subjects)
        """
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD
        )
        cur = conn.cursor()
        format_strings = ','.join(['%s'] * len(subject_ids))
        cur.execute(f"SELECT name, description FROM subjects WHERE id IN ({format_strings})", tuple(subject_ids))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # Devuelve un string con el nombre y la descripción de cada materia
        return '\n\n'.join([f"Materia: {row[0]}\n{row[1]}" for row in rows])

    def answer_question(self, question, subject_ids, student_profile=None, llm_backend="ollama", llm_model="gemma3:4b", chat_history=None):
        settings = load_settings_from_db()
        backend = settings.get('llm_backend', llm_backend)
        model = settings.get('llm_model', llm_model)
        ollama_url = settings.get('ollama_url', 'http://localhost:11434')
        openai_base_url = settings.get('openai_base_url', 'https://api.openai.com')
        qdrant_url = settings.get('qdrant_url', QDRANT_URL)
        collection = settings.get('qdrant_collection', QDRANT_COLLECTION)
        logging_enabled = settings.get('logging_enabled', True)

        embeddings = OllamaEmbeddings(model=EMBED_MODEL)
        client = QdrantClient(url=qdrant_url)
        vectorstore = Qdrant(
            collection_name=collection,
            client=client,
            embeddings=embeddings,
        )
        # Qdrant filter: formato correcto con 'must' y 'match'
        if len(subject_ids) == 1:
            filter = {"must": [{"key": "subject_id", "match": {"value": subject_ids[0]}}]}
        else:
            filter = {"must": [{"key": "subject_id", "match": {"any": subject_ids}}]}
        results = vectorstore.similarity_search(
            question,
            k=5,
            filter=filter
        )
        print("[INFO] Resultados relevantes:")
        for i, doc in enumerate(results, 1):
            print(f"--- Chunk {i} ---")
            print("Texto:", doc.page_content)
            print("Metadata:", doc.metadata)

        # Obtener contexto de la(s) materia(s)
        subject_context = self.get_subject_context(subject_ids)
        print("[DEBUG] subject_context:\n", subject_context)

        # Historial de conversación
        history_prompt = self.build_history_prompt(chat_history)
        print("[DEBUG] history_prompt:\n", history_prompt)

        # Construir el prompt personalizado para el LLM
        context = "\n---\n".join([doc.page_content for doc in results])
        print("[DEBUG] context (chunks relevantes):\n", context)
        print("[DEBUG] student_profile:\n", student_profile)
        print("[DEBUG] question:\n", question)
        prompt = f"""
Eres un tutor inteligente. Tu objetivo es ayudar al estudiante de manera personalizada y contextual, siguiendo estas reglas:

- Explicaciones personalizadas: Adapta el nivel y estilo de explicación según el perfil y la pregunta del estudiante.
- Respuestas contextuales: Limítate a responder solo con base en el contenido relevante del curso proporcionado.
- Generación de pistas: Si el estudiante lo solicita o parece atascado, ofrece pistas antes que respuestas directas.
- Clarificación de conceptos: Si el estudiante pide aclaraciones, desglosa los conceptos y usa ejemplos claros.
- Retroalimentación automática: Si el estudiante responde una pregunta o ejercicio, proporciona feedback constructivo y sugerencias de mejora.
- Si el alumno pide recursos adicionales, sugiere materiales complementarios relacionados con la materia.
- Si el alumno quiere preguntas tipo quiz o examen, genera preguntas con opciones múltiples, espera la respuesta y proporciona feedback.

{history_prompt}Contexto de la materia:
{subject_context}

Material de referencia (fragmentos relevantes):
{context}

Pregunta del estudiante:
{question}

Perfil del estudiante:
{student_profile if student_profile else 'No disponible'}
"""
        print("\n[INFO] Prompt generado para el LLM:\n")
        print(prompt)
        # Llamada al LLM según backend seleccionado (Ollama u OpenAI-compatible)
        llm_response: Optional[str] = None
        start = time.time()
        try:
            base = ollama_url if backend == "ollama" else openai_base_url
            llm_response = self.call_llm(backend=backend, prompt=prompt, model=model, base_url=base)
        except Exception as e:
            print("[WARN] Error al invocar LLM:", e)
            llm_response = ""
        latency_ms = int((time.time() - start) * 1000)

        # Métricas aproximadas de tokens
        prompt_tokens = estimate_tokens(prompt)
        completion_tokens = estimate_tokens(llm_response or "")
        total_tokens = prompt_tokens + completion_tokens

        # Persistir métrica
        if logging_enabled:
            try:
                conn = psycopg2.connect(
                    host=PG_HOST,
                    port=PG_PORT,
                    dbname=PG_DB,
                    user=PG_USER,
                    password=PG_PASSWORD,
                )
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO chat_metrics (user_id, subject_id, backend, model, prompt_tokens, completion_tokens, total_tokens, latency_ms)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            (student_profile or {}).get('id'),
                            subject_ids[0] if subject_ids else None,
                            backend,
                            model,
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                            latency_ms,
                        ),
                    )
                    conn.commit()
                conn.close()
            except Exception as e:
                print("[WARN] No se pudo registrar métrica:", e)

        return llm_response

    def run_crew(self, student_id, question, student_profile=None, llm_backend="ollama", llm_model="gemma3:4b", chat_history=None):
        """
        Orquesta el flujo CrewAI: obtiene subject_ids y responde la pregunta usando los agentes y tareas CrewAI.
        chat_history: lista de dicts [{'user':..., 'tutor':...}]
        """
        # Instanciar agentes CrewAI
        profile_agent = StudentProfileAgent(
            name="PerfilEstudiante",
            role="Agente de perfil de estudiante",
            goal="Consultar y actualizar el perfil y materias inscritas del estudiante.",
            backstory="Accede a la base de datos para obtener información relevante del estudiante."
        )
        tutor_agent = TutorAgent(
            name="TutorRAG",
            role="Agente tutor inteligente",
            goal="Responder preguntas del estudiante usando RAG y personalización.",
            backstory="Orquesta la recuperación de información y la generación de respuestas educativas personalizadas."
        )
        # Definir tareas
        get_subjects_task = Task(
            description="Obtener los subject_ids de las materias inscritas del estudiante.",
            agent=profile_agent,
            expected_output="Lista de subject_ids"
        )
        answer_question_task = Task(
            description="Buscar chunks relevantes en Qdrant y mostrar resultados para la pregunta del estudiante.",
            agent=tutor_agent,
            expected_output="Respuesta del tutor"
        )
        # Orquestar con Crew
        crew = Crew(
            agents=[profile_agent, tutor_agent],
            tasks=[get_subjects_task, answer_question_task]
        )
        # Ejecutar flujo CrewAI (aquí se puede expandir para que las tareas se pasen resultados entre sí)
        subject_ids = profile_agent.get_subject_ids(student_id)
        respuesta = tutor_agent.answer_question(
            question,
            subject_ids,
            student_profile=student_profile,
            llm_backend=llm_backend,
            llm_model=llm_model,
            chat_history=chat_history
        )
        return respuesta

    def build_history_prompt(self, chat_history):
        if not chat_history:
            return ""
        history = ""
        for msg in chat_history[-5:]:  # últimas 5 interacciones
            history += f"Tú: {msg['user']}\nTutor: {msg['tutor']}\n"
        return f"Historial de la conversación:\n{history}\n"
# Ejemplo de uso con CrewAI

if __name__ == "__main__":
    student_id = 1  # Cambia por el id real de un estudiante

    # Instanciar agentes CrewAI con los campos obligatorios
    profile_agent = StudentProfileAgent(
        name="PerfilEstudiante",
        role="Agente de perfil de estudiante",
        goal="Consultar y actualizar el perfil y materias inscritas del estudiante.",
        backstory="Accede a la base de datos para obtener información relevante del estudiante."
    )
    tutor_agent = TutorAgent(
        name="TutorRAG",
        role="Agente tutor inteligente",
        goal="Responder preguntas del estudiante usando RAG y personalización.",
        backstory="Orquesta la recuperación de información y la generación de respuestas educativas personalizadas."
    )

    # Definir tareas CrewAI
    get_subjects_task = Task(
        description="Obtener los subject_ids de las materias inscritas del estudiante.",
        agent=profile_agent,
        expected_output="Lista de subject_ids"
    )

    answer_question_task = Task(
        description="Buscar chunks relevantes en Qdrant y mostrar resultados para la pregunta del estudiante.",
        agent=tutor_agent,
        expected_output="Chunks relevantes y metadata"
    )

    # Orquestar con Crew
    crew = Crew(
         
        tasks=[get_subjects_task, answer_question_task]
    )

    # Ejecutar flujo manualmente (CrewAI puede orquestar tareas, aquí lo hacemos explícito)
    subject_ids = profile_agent.get_subject_ids(student_id)
    print(f"Materias inscritas para estudiante {student_id}: {subject_ids}")
    tutor_agent.answer_question("¿Qué es la programación lineal?", subject_ids)
