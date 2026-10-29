"""
retriever.py
Performs vector search in ChromaDB using Hugging Face embeddings
to retrieve the most relevant database table schemas for any user query.
"""

import os
from typing import List, Dict, Any
from dotenv import load_dotenv
import chromadb

from src.indexer import CHROMA_PERSIST_DIR, COLLECTION_NAME, get_embedding_function

load_dotenv()

class SchemaRetriever:
    def __init__(self, top_k: int = 4):
        """
        Initializes connection to the ChromaDB vector store.
        top_k: Number of relevant tables to retrieve.
        """
        self.top_k = top_k
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self.embedding_fn = get_embedding_function()
        
        try:
            self.collection = self.chroma_client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_fn
            )
        except Exception as e:
            raise RuntimeError(
                f"Collection '{COLLECTION_NAME}' not found in ChromaDB. "
                "Please run `python -m src.indexer` first to index your database."
            ) from e

    def retrieve_relevant_schemas(self, query: str) -> List[Dict[str, Any]]:
        """
        Takes a natural language query (e.g. 'top selling region last month'),
        embeds it via Hugging Face, and retrieves the most semantically relevant tables.
        
        Returns a list of dicts with keys: 'table_name', 'document', 'distance'.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=self.top_k,
            include=["documents", "metadatas", "distances"]
        )

        retrieved_tables = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0] if "distances" in results else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, dists):
                retrieved_tables.append({
                    "table_name": meta.get("table_name", "unknown"),
                    "document": doc,
                    "distance": dist
                })

        return retrieved_tables

    def format_schemas_for_prompt(self, relevant_tables: List[Dict[str, Any]]) -> str:
        """
        Combines retrieved table documents into a clean context block for the LLM prompt.
        """
        blocks = []
        for item in relevant_tables:
            blocks.append(f"### Table: {item['table_name']}\n{item['document']}")
        return "\n\n".join(blocks)

if __name__ == "__main__":
    retriever = SchemaRetriever(top_k=3)
    test_query = "Show me our top-selling region last month"
    print(f"Testing retrieval for query: '{test_query}'\n")
    matches = retriever.retrieve_relevant_schemas(test_query)
    for m in matches:
        print(f"Found Table: {m['table_name']} (Distance: {m['distance']:.4f})")
