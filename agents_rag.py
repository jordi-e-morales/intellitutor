import requests
# agents_rag.py
"""
Agentes para demo de Tutor Inteligente con RAG y metadata.
- StudentProfileAgent: consulta materias inscritas en PostgreSQL
- TutorAgent: consulta Qdrant filtrando por metadata y orquesta la respuesta
"""


import psycopg2
from psycopg2 import pool
import time
from functools import lru_cache
import threading
from typing import Optional
import os
from langchain_qdrant import QdrantVectorStore
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from crewai import Agent, Task, Crew

# Configuración PostgreSQL
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", 5432))
PG_DB = os.environ.get("PG_DB", "tutor_db")
PG_USER = os.environ.get("PG_USER", "tutor_user")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "tutor_pass")

# Configuración Qdrant (valores por defecto; pueden ser sobrescritos por app_settings)
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "tutor_demo"
EMBED_MODEL = "nomic-embed-text"

# =========================
# Connection Pool Singleton
# =========================
_connection_pool = None
_pool_lock = threading.Lock()

def get_connection_pool():
    """Thread-safe connection pool singleton."""
    global _connection_pool
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=20,
                    host=PG_HOST,
                    port=PG_PORT,
                    dbname=PG_DB,
                    user=PG_USER,
                    password=PG_PASSWORD,
                )
    return _connection_pool

def get_db_connection():
    """Get a connection from the pool."""
    return get_connection_pool().getconn()

def release_db_connection(conn):
    """Return a connection to the pool."""
    get_connection_pool().putconn(conn)

# =========================
# Singleton for Embeddings
# =========================
_embeddings_instance = None
_embeddings_lock = threading.Lock()

def get_embeddings(model: str = EMBED_MODEL, base_url: str = None):
    """Thread-safe singleton for OllamaEmbeddings to avoid recreating on each request."""
    global _embeddings_instance
    if _embeddings_instance is None:
        with _embeddings_lock:
            if _embeddings_instance is None:
                _embeddings_instance = OllamaEmbeddings(
                    model=model,
                    base_url=base_url or "http://localhost:11434"
                )
    return _embeddings_instance

# =========================
# Singleton for Qdrant Client
# =========================
_qdrant_clients = {}
_qdrant_lock = threading.Lock()

def get_qdrant_client(url: str = QDRANT_URL):
    """Thread-safe singleton for QdrantClient per URL."""
    global _qdrant_clients
    if url not in _qdrant_clients:
        with _qdrant_lock:
            if url not in _qdrant_clients:
                _qdrant_clients[url] = QdrantClient(url=url)
    return _qdrant_clients[url]

# =========================
# Settings Cache with TTL
# =========================
_settings_cache = {'data': None, 'timestamp': 0}
_settings_cache_ttl = 60  # seconds

def load_settings_from_db():
    """Lee la fila de configuración desde app_settings (id=1) with caching."""
    global _settings_cache
    now = time.time()

    # Return cached settings if still valid
    if _settings_cache['data'] and (now - _settings_cache['timestamp']) < _settings_cache_ttl:
        return _settings_cache['data']

    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT llm_backend, llm_model, ollama_url, qdrant_url, qdrant_collection, logging_enabled
                    FROM app_settings WHERE id=1
                    """
                )
                row = cur.fetchone()
        finally:
            release_db_connection(conn)

        if not row:
            settings = {
                'llm_backend': 'ollama',
                'llm_model': 'gemma3:4b',
                'ollama_url': 'http://localhost:11434',
                'qdrant_url': QDRANT_URL,
                'qdrant_collection': QDRANT_COLLECTION,
                'logging_enabled': True,
            }
        else:
            keys = ['llm_backend','llm_model','ollama_url','qdrant_url','qdrant_collection','logging_enabled']
            settings = dict(zip(keys, row))

        # Update cache
        _settings_cache['data'] = settings
        _settings_cache['timestamp'] = now
        return settings
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
        """Get enrolled subject IDs using connection pool."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT subject_id FROM enrollments WHERE student_id = %s
                """, (student_id,))
                return [row[0] for row in cur.fetchall()]
        finally:
            release_db_connection(conn)


class TutorAgent(Agent):
    def build_messages(self, system_prompt: str, user_message: str, chat_history: list = None) -> list:
        """
        Construye la lista de mensajes para la API de chat con roles apropiados.
        """
        messages = [{"role": "system", "content": system_prompt}]

        # Agregar historial de conversación con roles apropiados
        if chat_history:
            for msg in chat_history[-10:]:  # Últimas 10 interacciones
                if msg.get('user'):
                    messages.append({"role": "user", "content": msg['user']})
                if msg.get('tutor'):
                    messages.append({"role": "assistant", "content": msg['tutor']})

        # Agregar el mensaje actual del usuario
        messages.append({"role": "user", "content": user_message})

        return messages

    def call_llm(self, backend: str, messages: list, model: str, base_url: str) -> str:
        """
        Llama al proveedor de LLM usando la API de chat con mensajes estructurados.
        - backend == 'ollama': usa /api/chat de Ollama
        - backend == 'openai': usa /v1/chat/completions compatible con OpenAI
        """
        if backend == "ollama":
            url = f"{base_url.rstrip('/')}/api/chat"
            payload = {
                "model": model,
                "messages": messages,
                "stream": False
            }
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "")
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
                "messages": messages,
                "stream": False,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        else:
            raise ValueError(f"Backend LLM no soportado: {backend}")

    def stream_llm(self, backend: str, messages: list, model: str, base_url: str):
        """
        Generator that streams LLM response chunks using chat API.
        Yields text chunks as they arrive from the LLM.
        """
        import json

        if backend == "ollama":
            url = f"{base_url.rstrip('/')}/api/chat"
            payload = {
                "model": model,
                "messages": messages,
                "stream": True
            }
            with requests.post(url, json=payload, timeout=120, stream=True) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if "message" in chunk and "content" in chunk["message"]:
                                yield chunk["message"]["content"]
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

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
                "messages": messages,
                "stream": True,
            }
            with requests.post(url, headers=headers, json=payload, timeout=120, stream=True) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                            except json.JSONDecodeError:
                                continue
        else:
            raise ValueError(f"Backend LLM no soportado: {backend}")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_subject_context(self, subject_ids):
        """
        Dado uno o varios subject_ids, retorna el contenido de la descripción de la materia (campo description de subjects)
        Uses connection pooling for better performance.
        """
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            format_strings = ','.join(['%s'] * len(subject_ids))
            cur.execute(f"SELECT name, description FROM subjects WHERE id IN ({format_strings})", tuple(subject_ids))
            rows = cur.fetchall()
            cur.close()
            # Devuelve un string con el nombre y la descripción de cada materia
            return '\n\n'.join([f"Materia: {row[0]}\n{row[1]}" for row in rows])
        finally:
            release_db_connection(conn)

    def get_system_prompt(self, subject_context: str, rag_context: str, student_profile) -> str:
        """
        Construye el prompt del sistema con contexto de materia, RAG y perfil del estudiante.
        """
        return f"""Eres un tutor inteligente para estudiantes universitarios en México. Tu objetivo es ayudar al estudiante de manera personalizada y contextual, siguiendo estas reglas:

- Comunicación: Utiliza español mexicano natural y accesible. Usa "tú" en lugar de "usted" para crear un ambiente de confianza. Evita modismos que no sean comunes en México.
- Explicaciones personalizadas: Adapta el nivel y estilo de explicación según el perfil y la pregunta del estudiante. Cuando sea útil, incluye ejemplos relacionados con el contexto mexicano (empresas, instituciones, cultura o situaciones locales).
- Respuestas contextuales: Limítate a responder solo con base en el contenido relevante del curso proporcionado.
- Generación de pistas: Si el estudiante lo solicita o parece atorado, ofrece pistas antes que respuestas directas.
- Clarificación de conceptos: Si el estudiante pide aclaraciones, desglosa los conceptos y usa ejemplos claros.
- Retroalimentación automática: Si el estudiante responde una pregunta o ejercicio, proporciona retroalimentación constructiva y sugerencias de mejora.
- Si el alumno pide recursos adicionales, sugiere materiales complementarios relacionados con la materia.
- Si el alumno quiere preguntas tipo quiz o examen, genera preguntas con opciones múltiples, espera la respuesta y proporciona retroalimentación.
- Diagramas y visualizaciones: Cuando necesites crear diagramas, flujos, gráficos o cualquier visualización, usa SIEMPRE el formato Mermaid dentro de un bloque de código con el lenguaje "mermaid". Tipos soportados: flowchart, sequenceDiagram, classDiagram, stateDiagram, erDiagram, gantt, pie.
  REGLAS CRÍTICAS DE SINTAXIS MERMAID (para evitar errores):
  - Usa flowchart TD o flowchart LR (no "graph")
  - Los IDs de nodos deben ser alfanuméricos simples sin espacios ni caracteres especiales (A, B1, nodo1)
  - SIEMPRE encierra el texto de los nodos entre comillas dobles si contiene caracteres especiales: A["Texto con (paréntesis)"]
  - Para nodos rectangulares: A["texto"]
  - Para nodos redondeados: A("texto")
  - Para nodos tipo rombo (decisión): A{{"texto"}}
  - Flechas válidas: -->, --->, -.->; (punteada), ==> (gruesa)
  - Para texto en flechas: A -->|"texto"| B o A -- "texto" --> B
  - En subgraph, usa: subgraph nombre["Título con espacios"]
  - NUNCA uses caracteres especiales sin comillas: ( ) [ ] {{ }} | < > & en textos de nodos
  - Evita saltos de línea dentro de un nodo; usa <br> si necesitas múltiples líneas
  - Ejemplo correcto:
    ```mermaid
    flowchart TD
      A["Inicio del proceso"] --> B{{"¿Es válido?"}}
      B -->|"Sí"| C["Continuar"]
      B -->|"No"| D["Revisar"]
    ```
- Fórmulas matemáticas: SIEMPRE usa notación LaTeX para cualquier expresión matemática, nunca uses formato markdown. Usa $...$ para fórmulas en línea (ejemplo: $x^2 + y^2 = r^2$) y $$...$$ para fórmulas en bloque centradas. Ejemplos de notación LaTeX:
  - Fracciones: $\\frac{{a}}{{b}}$
  - Raíces: $\\sqrt{{x}}$, $\\sqrt[n]{{x}}$
  - Exponentes y subíndices: $x^2$, $x_i$, $x_i^2$
  - Sumatorias: $\\sum_{{i=1}}^{{n}} x_i$
  - Integrales: $\\int_{{a}}^{{b}} f(x) dx$
  - Límites: $\\lim_{{x \\to \\infty}} f(x)$
  - Matrices: usa entornos como \\begin{{pmatrix}}...\\end{{pmatrix}}
  - Letras griegas: $\\alpha$, $\\beta$, $\\gamma$, $\\theta$, $\\pi$
  - Operadores: $\\times$, $\\div$, $\\pm$, $\\neq$, $\\leq$, $\\geq$, $\\approx$

Contexto de la materia:
{subject_context}

Material de referencia (fragmentos relevantes del curso):
{rag_context}

Perfil del estudiante:
{student_profile if student_profile else 'No disponible'}

Recuerda: Mantén el contexto de la conversación y haz referencia a mensajes anteriores cuando sea relevante."""

    def answer_question(self, question, subject_ids, student_profile=None, llm_backend="ollama", llm_model="gemma3:4b", chat_history=None):
        settings = load_settings_from_db()  # Uses cached settings (60s TTL)
        backend = settings.get('llm_backend', llm_backend)
        model = settings.get('llm_model', llm_model)
        ollama_url = settings.get('ollama_url', 'http://localhost:11434')
        openai_base_url = settings.get('openai_base_url', 'https://api.openai.com')
        qdrant_url = settings.get('qdrant_url', QDRANT_URL)
        collection = settings.get('qdrant_collection', QDRANT_COLLECTION)
        logging_enabled = settings.get('logging_enabled', True)

        # Use singleton instances for better performance
        embeddings = get_embeddings(model=EMBED_MODEL, base_url=ollama_url)
        client = get_qdrant_client(url=qdrant_url)
        vectorstore = QdrantVectorStore(
            collection_name=collection,
            client=client,
            embedding=embeddings,
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

        # Construir contexto RAG
        rag_context = "\n---\n".join([doc.page_content for doc in results])
        print("[DEBUG] rag_context (chunks relevantes):\n", rag_context)
        print("[DEBUG] student_profile:\n", student_profile)
        print("[DEBUG] question:\n", question)
        print("[DEBUG] chat_history length:", len(chat_history) if chat_history else 0)

        # Construir el prompt del sistema
        system_prompt = self.get_system_prompt(subject_context, rag_context, student_profile)

        # Construir mensajes con historial de conversación
        messages = self.build_messages(system_prompt, question, chat_history)
        print(f"\n[INFO] Total de mensajes para el LLM: {len(messages)}")
        for i, msg in enumerate(messages):
            print(f"  [{i}] {msg['role']}: {msg['content'][:100]}...")

        # Llamada al LLM con mensajes estructurados
        llm_response: Optional[str] = None
        start = time.time()
        try:
            base = ollama_url if backend == "ollama" else openai_base_url
            llm_response = self.call_llm(backend=backend, messages=messages, model=model, base_url=base)
        except Exception as e:
            print("[WARN] Error al invocar LLM:", e)
            llm_response = ""
        latency_ms = int((time.time() - start) * 1000)

        # Métricas aproximadas de tokens (estimación basada en todos los mensajes)
        total_prompt_text = " ".join([msg['content'] for msg in messages])
        prompt_tokens = estimate_tokens(total_prompt_text)
        completion_tokens = estimate_tokens(llm_response or "")
        total_tokens = prompt_tokens + completion_tokens

        # Persistir métrica using connection pool
        if logging_enabled:
            try:
                conn = get_db_connection()
                try:
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
                finally:
                    release_db_connection(conn)
            except Exception as e:
                print("[WARN] No se pudo registrar métrica:", e)

        return llm_response

    def stream_answer(self, question, subject_ids, student_profile=None, llm_backend="ollama", llm_model="gemma3:4b", chat_history=None):
        """
        Generator version of answer_question that streams the response.
        Yields text chunks as they arrive from the LLM.
        """
        settings = load_settings_from_db()
        backend = settings.get('llm_backend', llm_backend)
        model = settings.get('llm_model', llm_model)
        ollama_url = settings.get('ollama_url', 'http://localhost:11434')
        openai_base_url = settings.get('openai_base_url', 'https://api.openai.com')
        qdrant_url = settings.get('qdrant_url', QDRANT_URL)
        collection = settings.get('qdrant_collection', QDRANT_COLLECTION)
        logging_enabled = settings.get('logging_enabled', True)

        # Use singleton instances for better performance
        embeddings = get_embeddings(model=EMBED_MODEL, base_url=ollama_url)
        client = get_qdrant_client(url=qdrant_url)
        vectorstore = QdrantVectorStore(
            collection_name=collection,
            client=client,
            embedding=embeddings,
        )

        # Qdrant filter
        if len(subject_ids) == 1:
            filter = {"must": [{"key": "subject_id", "match": {"value": subject_ids[0]}}]}
        else:
            filter = {"must": [{"key": "subject_id", "match": {"any": subject_ids}}]}

        results = vectorstore.similarity_search(question, k=5, filter=filter)

        # Get context
        subject_context = self.get_subject_context(subject_ids)
        rag_context = "\n---\n".join([doc.page_content for doc in results])

        # Build system prompt and messages with proper roles
        system_prompt = self.get_system_prompt(subject_context, rag_context, student_profile)
        messages = self.build_messages(system_prompt, question, chat_history)

        print(f"\n[INFO] Streaming con {len(messages)} mensajes")

        # Stream the response
        base = ollama_url if backend == "ollama" else openai_base_url
        full_response = []
        start = time.time()

        try:
            for chunk in self.stream_llm(backend=backend, messages=messages, model=model, base_url=base):
                full_response.append(chunk)
                yield chunk
        except Exception as e:
            print(f"[WARN] Error al invocar LLM en streaming: {e}")
            yield f"\n[Error: {str(e)}]"

        latency_ms = int((time.time() - start) * 1000)

        # Log metrics after streaming completes
        if logging_enabled:
            try:
                complete_response = "".join(full_response)
                total_prompt_text = " ".join([msg['content'] for msg in messages])
                prompt_tokens = estimate_tokens(total_prompt_text)
                completion_tokens = estimate_tokens(complete_response)
                total_tokens = prompt_tokens + completion_tokens

                conn = get_db_connection()
                try:
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
                finally:
                    release_db_connection(conn)
            except Exception as e:
                print("[WARN] No se pudo registrar métrica:", e)

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
