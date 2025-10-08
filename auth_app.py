"""
Aplicación Flask para autenticación de usuarios con interfaz moderna.
Incluye endpoint de chat nativo (sin Gradio) que integra con el Tutor RAG.
"""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import psycopg2
import hashlib
import os
from datetime import datetime, timedelta
from agents_rag import StudentProfileAgent, TutorAgent

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Configuración de base de datos
PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'tutor_db',
    'user': 'tutor_user',
    'password': 'tutor_pass'
}

def get_db_connection():
    return psycopg2.connect(**PG_CONFIG)

def verify_user(email, password):
    """Verifica las credenciales del usuario"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, name, career, grade, language 
        FROM students 
        WHERE email = %s AND password = %s
    """, (email, password))
    
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'name': user[1],
            'email': email,
            'career': user[2],
            'grade': user[3],
            'language': user[4]
        }
    return None

# =========================
# Agentes RAG (una sola instancia por proceso)
# =========================
profile_agent = StudentProfileAgent(
    name="PerfilEstudiante",
    role="Agente de perfil de estudiante",
    goal="Consultar materias inscritas del estudiante.",
    backstory="Accede a la base de datos para obtener información relevante del estudiante."
)

tutor_agent = TutorAgent(
    name="TutorRAG",
    role="Agente tutor inteligente",
    goal="Responder preguntas del estudiante usando RAG y personalización.",
    backstory="Orquesta la recuperación de información y la generación de respuestas educativas personalizadas."
)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    
    user = verify_user(email, password)
    if user:
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        session['user_career'] = user['career']
        session['user_grade'] = user['grade']
        session['user_language'] = user['language']
        session.permanent = True
        app.permanent_session_lifetime = timedelta(hours=8)
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', error='Credenciales inválidas')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    # Obtener materias del usuario
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.name, s.id
        FROM subjects s
        JOIN enrollments e ON s.id = e.subject_id
        WHERE e.student_id = %s
    """, (session['user_id'],))
    subjects = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', 
                         user=session, 
                         subjects=subjects)

@app.route('/chat/<int:subject_id>')
def chat(subject_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    # Verificar que el usuario esté inscrito en la materia
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.name
        FROM subjects s
        JOIN enrollments e ON s.id = e.subject_id
        WHERE e.student_id = %s AND s.id = %s
    """, (session['user_id'], subject_id))
    subject = cur.fetchone()
    cur.close()
    conn.close()
    
    if not subject:
        return redirect(url_for('dashboard'))
    
    return render_template('chat.html', 
                         subject_name=subject[0],
                         subject_id=subject_id,
                         gradio_port=7860)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Endpoint de chat nativo para el tutor.
    Espera JSON: { message: str, subject_id: int, chat_history?: [{user,tutor}, ...] }
    Devuelve: { reply: str }
    """
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    subject_id = data.get('subject_id')
    chat_history = data.get('chat_history')

    if not message:
        return jsonify({'error': 'Empty message'}), 400
    if not subject_id:
        return jsonify({'error': 'Missing subject_id'}), 400

    # Construir perfil del estudiante (básico) desde la sesión
    student_profile = {
        'id': session.get('user_id'),
        'name': session.get('user_name'),
        'email': session.get('user_email'),
        'career': session.get('user_career'),
        'grade': session.get('user_grade'),
        'language': session.get('user_language'),
    }

    try:
        # Llamar al TutorAgent con el subject_id actual
        reply = tutor_agent.answer_question(
            question=message,
            subject_ids=[int(subject_id)],
            student_profile=student_profile,
            llm_backend="ollama",
            llm_model="gemma3:4b",
            chat_history=chat_history,
        )
    except Exception as e:
        return jsonify({'error': 'Chat processing failed', 'detail': str(e)}), 500

    return jsonify({'reply': reply or ''})

@app.route('/api/user-info')
def api_user_info():
    """API endpoint para que Gradio obtenga información del usuario"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'user_id': session['user_id'],
        'name': session['user_name'],
        'email': session['user_email'],
        'career': session['user_career'],
        'grade': session['user_grade'],
        'language': session['user_language']
    })

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
