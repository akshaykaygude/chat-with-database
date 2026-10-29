"""
indexer.py
Indexes PostgreSQL table schemas into ChromaDB using Hugging Face Sentence-Transformers embeddings.
Runs locally on your machine (zero API cost).
"""

import os
from typing import List, Dict, Any
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions

from src.database import get_engine, extract_schema_metadata

load_dotenv()

CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_NAME = "database_schemas"

def get_embedding_function():
    """
    Initializes the Hugging Face sentence-transformers embedding function.
    Default: 'sentence-transformers/all-MiniLM-L6-v2' (lightweight, fast, 384 dimensions).
    Runs completely offline on local CPU/GPU.
    """
    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)

def index_database_schema(force_reindex: bool = True, engine: Any = None) -> int:
    """
    Extracts schema from the database, converts each table to a rich text document,
    and indexes it into ChromaDB.
    
    Returns the count of indexed tables.
    """
    print("\n--- Phase 1: Schema Introspection ---")
    if engine is None:
        engine = get_engine()
    schema_docs = extract_schema_metadata(engine)
    print(f"Discovered {len(schema_docs)} tables in the database.")

    # Initialize ChromaDB client
    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    
    embedding_fn = get_embedding_function()
    
    # Delete existing collection if re-indexing
    if force_reindex:
        try:
            chroma_client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"description": "PostgreSQL schema documents for Text-to-SQL"}
    )

    ids = []
    documents = []
    metadatas = []

    print("\n--- Phase 2: Embedding Schema with Hugging Face ---")
    for doc in schema_docs:
        table_name = doc["table_name"]
        content = doc["document"]
        
        ids.append(table_name)
        documents.append(content)
        metadatas.append({
            "table_name": table_name,
            "column_count": len(doc["columns"]),
            "has_foreign_keys": len(doc["foreign_keys"]) > 0
        })
        print(f" -> Prepared schema card for table: '{table_name}'")

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    print(f"\n[OK] Successfully indexed {len(ids)} tables into ChromaDB at '{CHROMA_PERSIST_DIR}'.")
    return len(ids)

if __name__ == "__main__":
    index_database_schema(force_reindex=True)
