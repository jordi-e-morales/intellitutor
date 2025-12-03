#!/bin/bash
set -e

echo "========================================"
echo "IntelliTutor - Starting Initialization"
echo "========================================"

# Function to wait for PostgreSQL
wait_for_postgres() {
    echo "[INIT] Waiting for PostgreSQL at $PG_HOST:$PG_PORT..."
    while ! python -c "import psycopg2; psycopg2.connect(host='$PG_HOST', port=$PG_PORT, dbname='$PG_DB', user='$PG_USER', password='$PG_PASSWORD')" 2>/dev/null; do
        echo "[INIT] PostgreSQL is unavailable - sleeping 2s..."
        sleep 2
    done
    echo "[INIT] PostgreSQL is ready!"
}

# Function to wait for Qdrant
wait_for_qdrant() {
    QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"
    echo "[INIT] Waiting for Qdrant at $QDRANT_URL..."
    while ! curl -sf "$QDRANT_URL/health" > /dev/null 2>&1; do
        echo "[INIT] Qdrant is unavailable - sleeping 2s..."
        sleep 2
    done
    echo "[INIT] Qdrant is ready!"
}

# Function to check if Ollama is available (optional, for ingestion)
check_ollama() {
    OLLAMA_URL="${OLLAMA_URL:-http://host.docker.internal:11434}"
    echo "[INIT] Checking Ollama at $OLLAMA_URL..."
    if curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        echo "[INIT] Ollama is available!"
        return 0
    else
        echo "[WARN] Ollama is not available at $OLLAMA_URL"
        echo "[WARN] Document ingestion will be skipped. Run manually later."
        return 1
    fi
}

# Wait for dependencies
wait_for_postgres
wait_for_qdrant

# Initialize database schema (idempotent - uses CREATE IF NOT EXISTS)
echo "[INIT] Initializing database schema..."
python db_schema.py

# Populate demo data (idempotent - uses ON CONFLICT)
echo "[INIT] Populating demo data..."
python populate_db.py

# Ingest documents if Ollama is available (idempotent - checks collection)
if check_ollama; then
    echo "[INIT] Running document ingestion..."
    python ingest_pipeline.py || echo "[WARN] Ingestion failed - you can run it manually later"
else
    echo "[INIT] Skipping document ingestion (Ollama not available)"
fi

echo "========================================"
echo "IntelliTutor - Initialization Complete"
echo "========================================"
echo "[INIT] Starting Flask application..."

# Execute the main command
exec "$@"
