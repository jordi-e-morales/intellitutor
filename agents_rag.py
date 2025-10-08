import requests
# agents_rag.py
"""
Agentes para demo de Tutor Inteligente con RAG y metadata.
- StudentProfileAgent: consulta materias inscritas en PostgreSQL
- TutorAgent: consulta Qdrant filtrando por metadata y orquesta la respuesta
"""


import psycopg2
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

# Configuración Qdrant
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "tutor_demo"
EMBED_MODEL = "nomic-embed-text"


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
    def call_llm_ollama(self, prompt, model="gemma3:4b"):
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()["response"]

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
        embeddings = OllamaEmbeddings(model=EMBED_MODEL)
        client = QdrantClient(url=QDRANT_URL)
        vectorstore = Qdrant(
            collection_name=QDRANT_COLLECTION,
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
        # Llamada al LLM según backend seleccionado
        llm_response = None
        if llm_backend == "ollama":
            llm_response = self.call_llm_ollama(prompt, model=llm_model)
            print("\n[INFO] Respuesta del LLM (Ollama):\n")
            print(llm_response)
        else:
            print("[WARN] Backend LLM no soportado aún: ", llm_backend)
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
