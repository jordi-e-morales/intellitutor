"""
Aplicación Flask para autenticación de usuarios con interfaz moderna.
Incluye endpoint de chat nativo (sin Gradio) que integra con el Tutor RAG.
"""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask_cors import CORS
import json
from werkzeug.security import check_password_hash
import psycopg2
from psycopg2 import pool
import os
from datetime import datetime, timedelta
from agents_rag import StudentProfileAgent, TutorAgent

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Enable template auto-reload in development
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Enable CORS with secure defaults
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# Configuración de base de datos
PG_CONFIG = {
    'host': os.environ.get('PG_HOST', 'localhost'),
    'port': int(os.environ.get('PG_PORT', 5432)),
    'dbname': os.environ.get('PG_DB', 'tutor_db'),
    'user': os.environ.get('PG_USER', 'tutor_user'),
    'password': os.environ.get('PG_PASSWORD', 'tutor_pass')
}

# Connection pool for better performance (min 1, max 20 connections)
_connection_pool = None

def get_connection_pool():
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            **PG_CONFIG
        )
    return _connection_pool

def get_db_connection():
    """Get a connection from the pool."""
    return get_connection_pool().getconn()

def release_db_connection(conn):
    """Return a connection to the pool."""
    get_connection_pool().putconn(conn)

def load_settings():
    """Fetch app settings (single-row table)."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT llm_backend, llm_model, ollama_url, openai_base_url, qdrant_url, qdrant_collection, logging_enabled FROM app_settings WHERE id=1;")
        row = cur.fetchone()
        cur.close()
        if not row:
            return {
                'llm_backend': 'ollama',
                'llm_model': 'gemma3:4b',
                'ollama_url': 'http://localhost:11434',
                'openai_base_url': 'https://api.openai.com',
                'qdrant_url': 'http://localhost:6333',
                'qdrant_collection': 'tutor_demo',
                'logging_enabled': True,
            }
        keys = ['llm_backend','llm_model','ollama_url','openai_base_url','qdrant_url','qdrant_collection','logging_enabled']
        return dict(zip(keys, row))
    finally:
        release_db_connection(conn)

def is_admin():
    """Simple admin check using ADMIN_EMAILS env (comma-separated)."""
    emails = os.environ.get('ADMIN_EMAILS')
    if not emails:
        return False
    allowed = {e.strip().lower() for e in emails.split(',') if e.strip()}
    return session.get('user_email','').lower() in allowed

def verify_user(email, password):
    """Verifica las credenciales del usuario usando password hashing seguro."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Fetch user by email only, then verify password hash
        cur.execute("""
            SELECT id, name, password, career, grade, language
            FROM students
            WHERE email = %s
        """, (email,))

        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[2], password):
            return {
                'id': user[0],
                'name': user[1],
                'email': email,
                'career': user[3],
                'grade': user[4],
                'language': user[5]
            }
        return None
    finally:
        release_db_connection(conn)

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
    role="Agente tutor inteligente para estudiantes universitarios en México",
    goal="Responder preguntas del estudiante usando RAG y personalización, comunicándose en español mexicano.",
    backstory="Orquesta la recuperación de información y la generación de respuestas educativas personalizadas para el contexto universitario mexicano."
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
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.name, s.id
            FROM subjects s
            JOIN enrollments e ON s.id = e.subject_id
            WHERE e.student_id = %s
        """, (session['user_id'],))
        subjects = cur.fetchall()
        cur.close()
    finally:
        release_db_connection(conn)

    return render_template('dashboard.html',
                         user=session,
                         subjects=subjects)

@app.route('/admin', methods=['GET', 'POST'])
def admin_page():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    if not is_admin():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        data = {
            'llm_backend': request.form.get('llm_backend','ollama'),
            'llm_model': request.form.get('llm_model','gemma3:4b'),
            'ollama_url': request.form.get('ollama_url','http://localhost:11434'),
            'openai_base_url': request.form.get('openai_base_url','https://api.openai.com'),
            'qdrant_url': request.form.get('qdrant_url','http://localhost:6333'),
            'qdrant_collection': request.form.get('qdrant_collection','tutor_demo'),
            'logging_enabled': True if request.form.get('logging_enabled') == 'on' else False,
        }
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE app_settings SET
                  llm_backend=%s,
                  llm_model=%s,
                  ollama_url=%s,
                  openai_base_url=%s,
                  qdrant_url=%s,
                  qdrant_collection=%s,
                  logging_enabled=%s,
                  updated_at=NOW()
                WHERE id=1
                """,
                (data['llm_backend'], data['llm_model'], data['ollama_url'], data['openai_base_url'], data['qdrant_url'], data['qdrant_collection'], data['logging_enabled'])
            )
            conn.commit()
            cur.close()
        finally:
            release_db_connection(conn)

    # Reload settings and metrics
    settings = load_settings()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, user_id, subject_id, backend, model, prompt_tokens, completion_tokens, total_tokens, latency_ms, created_at
            FROM chat_metrics
            ORDER BY created_at DESC
            LIMIT 50
        """)
        metrics = cur.fetchall()
        cur.close()
    finally:
        release_db_connection(conn)
    return render_template('admin.html', settings=settings, metrics=metrics, user=session)

@app.route('/chat/<int:subject_id>')
def chat(subject_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    # Verificar que el usuario esté inscrito en la materia
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.name
            FROM subjects s
            JOIN enrollments e ON s.id = e.subject_id
            WHERE e.student_id = %s AND s.id = %s
        """, (session['user_id'], subject_id))
        subject = cur.fetchone()
        cur.close()
    finally:
        release_db_connection(conn)

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


@app.route('/api/chat/stream', methods=['POST'])
def api_chat_stream():
    """Streaming endpoint de chat usando Server-Sent Events (SSE).
    Espera JSON: { message: str, subject_id: int, chat_history?: [{user,tutor}, ...] }
    Devuelve: text/event-stream con chunks de respuesta
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

    # Construir perfil del estudiante desde la sesión
    student_profile = {
        'id': session.get('user_id'),
        'name': session.get('user_name'),
        'email': session.get('user_email'),
        'career': session.get('user_career'),
        'grade': session.get('user_grade'),
        'language': session.get('user_language'),
    }

    def generate():
        """Generator function for SSE streaming."""
        try:
            for chunk in tutor_agent.stream_answer(
                question=message,
                subject_ids=[int(subject_id)],
                student_profile=student_profile,
                llm_backend="ollama",
                llm_model="gemma3:4b",
                chat_history=chat_history,
            ):
                # Send each chunk as an SSE event
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            # Signal end of stream
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
        }
    )


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
    # threaded=True allows handling multiple requests concurrently
    # This prevents blocking when LLM calls take long to process
    # use_reloader=True enables hot reload for Python file changes
    # extra_files can be used to watch additional files (e.g., config files)
    app.run(
        debug=True,
        port=5000,
        threaded=True,
        use_reloader=True,
        extra_files=['templates/', 'static/']
    )
