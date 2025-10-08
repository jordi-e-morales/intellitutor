```mermaid
graph TD
    subgraph UI
        A[Usuario/Estudiante]
        B[Interfaz Web (Chat)]
    end
    subgraph CrewAI Agents
        C[Agente Perfil Estudiante]
        D[Agente Materias]
        E[Agente Tutor (RAG)]
    end
    subgraph Infraestructura
        F[Base de Datos Estudiantes/Materias (en container)]
        G[Qdrant Vector DB]
        H[LLM Local/Remoto]
    end

    A -- Pregunta, interacción --> B
    B -- Solicitud de contexto y consulta --> C
    B -- Solicitud de materias y progreso --> D
    B -- Consulta de conocimiento --> E
    C -- Lee/actualiza perfil --> F
    D -- Lee/actualiza materias --> F
    E -- Recupera chunks relevantes --> G
    E -- Llama a LLM para respuesta --> H
    E -- Devuelve respuesta contextualizada --> B
    C -- Proporciona contexto de perfil --> E
    D -- Proporciona contexto de materias --> E
```

### Descripción de cada agente:

- **Agente Perfil Estudiante**: Consulta y actualiza información del estudiante (nombre, carrera, materias inscritas, nivel, idioma, progreso general). Puede recibir actualizaciones desde la UI y proveer contexto personalizado al Agente Tutor.

- **Agente Materias**: Gestiona la lista de materias inscritas, progreso por materia, y puede registrar avances o dificultades. Se comunica con la base de datos y puede informar al Agente Tutor sobre el estado académico.

- **Agente Tutor (RAG)**: Orquesta la recuperación de información relevante desde Qdrant, consulta el LLM (local o remoto) y genera respuestas personalizadas usando el contexto del perfil y materias. Devuelve respuestas a la UI.

- **Base de Datos (en container)**: Almacena perfiles de estudiantes y materias. Puede ser SQLite, PostgreSQL, etc.

- **Qdrant Vector DB**: Almacena los embeddings de los documentos de conocimiento.

- **LLM Local/Remoto**: Provee la generación de lenguaje natural, usando Ollama, LM Studio o vLLM.
