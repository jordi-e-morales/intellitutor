# Cambios recientes (septiembre 2025)

- Se migró el código a las nuevas librerías langchain-ollama y langchain-qdrant para compatibilidad futura.
- Se añadió qdrant-client como dependencia y se corrigió la inicialización de Qdrant para usar QdrantClient.
- Se corrigió agents_rag.py para cumplir con las restricciones de CrewAI/Pydantic (no atributos arbitrarios).
- Se creó y ejecutó populate_db.py para poblar la base de datos PostgreSQL con estudiantes, materias y matrículas ficticias.
- Se actualizaron los requirements.txt con las nuevas dependencias.
- El flujo de RAG y LLM local (Ollama) funciona de extremo a extremo con datos reales y prompt pedagógico.
# Arquitectura y agentes (actualización septiembre 2025)

## Arquitectura general (ver architecture_diagram.md)

- **UI Web (Chat):** Será una interfaz web (próximamente, con Streamlit o Flask) donde el usuario podrá interactuar con el tutor inteligente, enviar preguntas y recibir respuestas personalizadas.
- **CrewAI Agents:**
    - Agente Perfil Estudiante: Consulta y actualiza información del estudiante en PostgreSQL.
    - Agente Materias: Gestiona materias inscritas y progreso académico.
    - Agente Tutor (RAG): Orquesta la recuperación de información relevante desde Qdrant, consulta el LLM (Ollama/vLLM) y genera respuestas pedagógicas personalizadas.
- **Qdrant:** Vector DB para chunks de documentos y metadatos.
- **PostgreSQL:** Gestión de estudiantes, materias y matrículas.
- **LLM Backend:** Ollama local (por ahora), con opción futura de vLLM remoto.

## Estado actual

- Arquitectura modular y orquestada según el diagrama.
- Agentes CrewAI implementados y funcionales (perfil, materias, tutor/RAG).
- Ingesta de documentos y metadatos en Qdrant.
- Base de datos PostgreSQL poblada con datos ficticios.
- Flujo de pregunta-respuesta pedagógica validado end-to-end.
- Falta: UI web para pruebas integradas.

## Próximos pasos

- [ ] Construir una web UI simple (Streamlit o Flask) para probar la demo de extremo a extremo.
- [ ] Permitir actualización de perfil y materias desde la UI.
- [ ] (Opcional) Seguimiento de progreso y feedback visual.

# Intelligent Tutor Demo: Modular RAG con LLMs Locales y Remotos

## Step-by-Step Plan

### 1. Definir Dominio y Recolectar Conocimiento
- [x] Subjects definidos:
    - Ingenieria Industrial (Industrial Engineering) — Clase: Investigación de Operaciones
    - Derecho Internacional Público (en español) — Derecho
- [x] Recolectar materiales de aprendizaje (PDFs, docs, artículos, etc.) para cada materia
- [x] (Opcional) Agregar metadata (tema, dificultad, perfil de estudiante) a cada documento

### 2. Preparar la Knowledge Base
- [x] Carpetas creadas: Ingenieria_Industrial y Derecho
- [x] ingest_pipeline.py para ingestión y almacenamiento en Qdrant usando LangChain
- [x] requirements.txt con dependencias necesarias
- [x] Implementar document loaders (PDF, Markdown, TXT)
- [x] Chunkear documentos en piezas manejables
- [x] Generar embeddings para cada chunk (usando modelo local o remoto)
- [x] Almacenar embeddings en Qdrant

### 3. Gestión de Perfiles y Materias con Agentes (CrewAI)
- [x] CrewAI integrado para orquestar agentes inteligentes
- [x] Esqueleto de agentes: perfil de estudiante, materias, tutor (RAG)
- [x] Estructura de base de datos definida (db_schema.py)
- [x] db_schema.py adaptado a PostgreSQL (psycopg2)
- [x] docker-compose.yml para levantar PostgreSQL
- [x] Dockerfile.app para conteinerizar la app Python
- [x] INSTRUCCIONES_DB.md para levantar la base de datos
- [ ] Permitir que el pipeline de RAG consulte el perfil del estudiante para personalizar respuestas
- [ ] Permitir que los agentes actualicen el perfil según la interacción

### 4. Modular LLM Backend
- [ ] Abstracción de interfaz LLM para:
    - [ ] LLM local (Ollama, LM Studio)
    - [ ] LLM remoto (vLLM endpoint)
    - [x] Vector DB: Qdrant (instancia local, ver INSTRUCCIONES_QDRANT.md)
- [ ] Implementar configuración para alternar entre backends

### 5. Orquestación del Pipeline (RAG)
- [ ] Orquestación del pipeline con LangChain o LlamaIndex
- [ ] Implementar prompt templates para el tutor
- [ ] Integrar retrieval de Qdrant con backend LLM

### 6. Interfaz de Usuario
- [ ] Construir una web UI simple (Streamlit o Flask)
- [ ] Chat con historial
- [ ] Permitir selección de backend LLM (local/remoto)
- [ ] (Opcional) Subida de archivos para nuevos documentos

### 7. Evaluación y Feedback
- [ ] Implementar evaluación básica (preguntas generadas por LLM, revisión de respuestas)
- [ ] Proveer feedback y explicaciones
- [ ] (Opcional) Seguimiento de progreso del usuario

### 8. Pruebas y Refinamiento
- [ ] Pruebas end-to-end con queries de ejemplo
- [ ] Refinar prompts y configuración de retrieval
- [ ] Recopilar feedback y mejorar iterativamente

---

## Progress Tracking
- [x] Paso 1: Definir Dominio y Recolectar Conocimiento
- [x] Paso 2: Preparar la Knowledge Base
- [x] Paso 3: Gestión de Perfiles y Materias con Agentes (CrewAI)
- [ ] Paso 4: Modular LLM Backend
- [ ] Paso 5: Orquestación del Pipeline
- [ ] Paso 6: Interfaz de Usuario
- [ ] Paso 7: Evaluación y Feedback
- [ ] Paso 8: Pruebas y Refinamiento

---

## Notas
- Todos los componentes deben ser modulares y configurables.
- Soporte para LLMs locales y remotos como prioridad.
- Enfoque en valor educativo, explicabilidad y facilidad de uso.
- Archivos de instrucciones: INSTRUCCIONES_DB.md, INSTRUCCIONES_QDRANT.md
