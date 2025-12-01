
import os
import sys
from langchain_community.document_loaders import TextLoader, PDFPlumberLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Qdrant
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

# Configuración general (supports environment variables for Docker)
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "tutor_demo")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Relación carpeta <-> metadata de materia (ajusta según tu base de datos real)
SUBJECTS = {
    "Ingenieria_Industrial": {"subject_id": 1, "subject_name": "Investigación de Operaciones", "language": "es"},
    "Derecho": {"subject_id": 2, "subject_name": "Derecho Internacional Público", "language": "es"}
}


def check_collection_exists():
    """Check if collection already has documents (idempotency check)."""
    try:
        client = QdrantClient(url=QDRANT_URL)
        collection_info = client.get_collection(QDRANT_COLLECTION)
        points_count = collection_info.points_count
        if points_count > 0:
            print(f"[INFO] Collection '{QDRANT_COLLECTION}' already has {points_count} documents.")
            return True
        return False
    except UnexpectedResponse as e:
        if "404" in str(e) or "not found" in str(e).lower():
            print(f"[INFO] Collection '{QDRANT_COLLECTION}' does not exist yet.")
            return False
        raise
    except Exception as e:
        print(f"[WARN] Could not check collection: {e}")
        return False

def load_documents():
    docs = []
    print("[INFO] Iniciando carga de documentos...")
    for data_dir in SUBJECTS.keys():
        print(f"[INFO] Procesando carpeta: {data_dir}")
        for fname in os.listdir(data_dir):
            fpath = os.path.join(data_dir, fname)
            print(f"  [INFO] Archivo encontrado: {fname}")
            if fname.endswith(".md") or fname.endswith(".txt"):
                print(f"    [INFO] Cargando como texto: {fpath}")
                loaded = TextLoader(fpath).load()
            elif fname.endswith(".pdf"):
                print(f"    [INFO] Cargando como PDF: {fpath}")
                loaded = PDFPlumberLoader(fpath).load()
            else:
                print(f"    [WARN] Tipo de archivo no soportado: {fname}")
                continue
            # Agregar metadata de materia a cada documento
            for doc in loaded:
                doc.metadata.update(SUBJECTS[data_dir])
            docs.extend(loaded)
    print(f"[INFO] Total de documentos cargados: {len(docs)}")
    return docs


def chunk_documents(docs):
    print("[INFO] Iniciando fragmentación de documentos (chunking)...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    print(f"[INFO] Total de chunks generados: {len(chunks)}")
    return chunks


def embed_and_store(chunks):
    print("[INFO] Generando embeddings y almacenando en Qdrant...")
    print(f"[INFO] Using Ollama at: {OLLAMA_URL}")
    embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_URL)
    db = Qdrant.from_documents(
        chunks,
        embeddings,
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION
    )
    print(f"[INFO] Stored {len(chunks)} chunks in Qdrant con metadata de materia.")


def main():
    print("[INFO] === PIPELINE DE INGESTIÓN INICIADO ===")
    print(f"[INFO] Qdrant URL: {QDRANT_URL}")
    print(f"[INFO] Collection: {QDRANT_COLLECTION}")

    # Check if already ingested (idempotency)
    force = "--force" in sys.argv
    if not force and check_collection_exists():
        print("[INFO] Documents already ingested. Use --force to re-ingest.")
        print("[INFO] === PIPELINE DE INGESTIÓN OMITIDO (ya existe) ===")
        return

    docs = load_documents()
    chunks = chunk_documents(docs)
    embed_and_store(chunks)
    print("[INFO] === PIPELINE DE INGESTIÓN FINALIZADO ===")


if __name__ == "__main__":
    main()
