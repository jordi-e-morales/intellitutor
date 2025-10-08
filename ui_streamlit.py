import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agents_rag import StudentProfileAgent, TutorAgent
st.set_page_config(page_title="Tutor Inteligente", page_icon="🎓")
st.title("🎓 Tutor Inteligente Demo")
import psycopg2

PG_HOST = "localhost"
PG_PORT = 5432
PG_DB = "tutor_db"
PG_USER = "tutor_user"
PG_PASSWORD = "tutor_pass"

def get_students():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM students ORDER BY id")
    students = cur.fetchall()
    cur.close()
    conn.close()
    return students

def authenticate_user(email, password):
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM students WHERE email = %s AND password = %s", (email, password))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

def get_student_profile(student_id):
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT name, email, career, grade, language FROM students WHERE id = %s", (student_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {
            "name": row[0],
            "email": row[1],
            "career": row[2],
            "grade": row[3],
            "language": row[4],
        }
    return None

def get_student_subjects(student_id):
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT s.name, s.description
        FROM enrollments e
        JOIN subjects s ON e.subject_id = s.id
        WHERE e.student_id = %s
    """, (student_id,))
    subjects = cur.fetchall()
    cur.close()
    conn.close()
    return subjects

# --- Control de página: login o app principal ---
if "page" not in st.session_state:
    st.session_state["page"] = "login"

if st.session_state["page"] == "login":
    st.header("Inicia sesión para acceder al tutor")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        login_btn = st.form_submit_button("Iniciar sesión")
    if login_btn:
        user = authenticate_user(email, password)
        if user:
            st.session_state["user"] = user
            st.session_state["page"] = "app"
            st.success(f"Bienvenido/a, {user[1]}!")
            st.rerun()
        else:
            st.error("Credenciales incorrectas. Intenta de nuevo.")

if st.session_state.get("page") == "app" and "user" in st.session_state:
    user = st.session_state["user"]
    st.success(f"Bienvenido/a, {user[1]}!")
    # Paso 2: Mostrar perfil y materias reales
    st.header("Tu perfil y materias inscritas")
    profile = get_student_profile(user[0])
    if profile:
        st.markdown(f"**Nombre:** {profile['name']}")
        st.markdown(f"**Email:** {profile['email']}")
        st.markdown(f"**Carrera:** {profile['career']}")
        st.markdown(f"**Grado:** {profile['grade']}")
        st.markdown(f"**Idioma:** {profile['language']}")
    subjects = get_student_subjects(user[0])
    st.markdown("**Materias inscritas:**")
    if subjects:
        for subj in subjects:
            st.markdown(f"- {subj[0]}")
        # Mostrar solo el nombre de la materia, no el contenido completo aquí
    else:
        st.info("No tienes materias inscritas.")

    # Paso 3: Chat tipo ChatGPT
    st.header("Chat con el tutor")
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    chat_container = st.container()
    with chat_container:
        for msg in st.session_state["chat_history"]:
            st.markdown(f"<div style='background-color:#e6f7ff;padding:8px 12px;border-radius:8px;margin-bottom:4px;'><b>Tú:</b> {msg['user']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='background-color:#f6f6f6;padding:8px 12px;border-radius:8px;margin-bottom:12px;'><b>Tutor:</b> {msg['tutor']}</div>", unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        question = st.text_input("Escribe tu pregunta al tutor", key="chat_input", placeholder="Escribe tu mensaje y presiona Enter...")
        send_btn = st.form_submit_button("Enviar")
    if send_btn and question:
        if "profile_agent" not in st.session_state:
            st.session_state["profile_agent"] = StudentProfileAgent(
                name="PerfilEstudiante",
                role="Agente de perfil de estudiante",
                goal="Consultar y actualizar el perfil y materias inscritas del estudiante.",
                backstory="Accede a la base de datos para obtener información relevante del estudiante."
            )
        if "tutor_agent" not in st.session_state:
            st.session_state["tutor_agent"] = TutorAgent(
                name="TutorRAG",
                role="Agente tutor inteligente",
                goal="Responder preguntas del estudiante usando RAG y personalización.",
                backstory="Orquesta la recuperación de información y la generación de respuestas educativas personalizadas."
            )
        profile_agent = st.session_state["profile_agent"]
        tutor_agent = st.session_state["tutor_agent"]
        student_profile = get_student_profile(user[0])
        with st.spinner("Consultando al tutor..."):
            respuesta = tutor_agent.run_crew(
                user[0],
                question,
                student_profile=student_profile,
                llm_backend="ollama",
                llm_model="gemma3:4b",
                chat_history=st.session_state["chat_history"]
            )
        st.session_state["chat_history"].append({"user": question, "tutor": respuesta})
        st.rerun()

    if st.button("Cerrar sesión"):
        for k in ["user", "profile_agent", "tutor_agent", "chat_history"]:
            if k in st.session_state:
                del st.session_state[k]
        st.session_state["page"] = "login"
        st.rerun()
