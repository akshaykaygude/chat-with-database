"""
app.py
Interactive CLI orchestrator for Natural Language to SQL RAG system.
Uses:
  - Hugging Face sentence-transformers for schema vector search
  - ChromaDB for vector storage
  - Hugging Face Inference API (Qwen2.5-Coder) for SQL generation
  - PostgreSQL / SQLite for relational data execution
"""

import sys
import os
from tabulate import tabulate
from dotenv import load_dotenv

from src.database import get_engine, execute_query
from src.retriever import SchemaRetriever
from src.generator import SQLGenerator
from src.guardrails import validate_sql

load_dotenv()

def process_question(user_question: str, retriever: SchemaRetriever, generator: SQLGenerator, engine):
    """
    Executes the full Schema-Aware RAG pipeline for a single user question.
    """
    print("\n" + "=" * 70)
    print(f"USER QUESTION: {user_question}")
    print("=" * 70)

    # 1. Retrieve relevant schema chunks via Vector Search
    print("\n[1/4] Retrieving relevant database schemas using Hugging Face embeddings...")
    relevant_tables = retriever.retrieve_relevant_schemas(user_question)
    
    table_names = [t["table_name"] for t in relevant_tables]
    print(f"      Matched Tables: {', '.join(table_names)}")
    for t in relevant_tables:
        print(f"        - {t['table_name']} (vector distance: {t['distance']:.4f})")

    schema_context = retriever.format_schemas_for_prompt(relevant_tables)

    # 2. Generate SQL via Hugging Face LLM
    print("\n[2/4] Generating PostgreSQL query using Hugging Face LLM...")
    try:
        sql = generator.generate_sql(user_question, schema_context)
    except Exception as e:
        print(f"\n[!] Generation failed: {e}")
        return

    print("\n----- GENERATED SQL -----")
    print(sql)
    print("-------------------------")

    # 3. Guardrail validation
    print("\n[3/4] Running safety guardrails...")
    is_safe, reason = validate_sql(sql)
    if not is_safe:
        print(f"[BLOCKED] Security violation: {reason}")
        return
    print("      [PASS] Query is safe (SELECT only).")

    # 4. Execute query on PostgreSQL
    print("\n[4/4] Executing query against database...")
    try:
        columns, rows = execute_query(engine, sql)
        if not rows:
            print("Query executed successfully, but returned 0 rows.")
        else:
            print(f"\nQuery Results ({len(rows)} row(s)):")
            print(tabulate(rows, headers=columns, tablefmt="psql"))
    except Exception as e:
        print(f"\n[!] SQL Execution Error: {e}")

def main():
    print("=" * 70)
    print("   Schema-Aware Natural Language to SQL (PostgreSQL + Hugging Face)   ")
    print("=" * 70)

    # Initialize components
    try:
        engine = get_engine()
        print(f" Connected to database: {engine.url.render_as_string(hide_password=True)}")
    except Exception as e:
        print(f"[!] Database connection error: {e}")
        print("Tip: Run `python data/seed_data.py --sqlite` if you want a local mock database to test.")
        return

    try:
        retriever = SchemaRetriever(top_k=3)
    except Exception as e:
        print(f"[!] Vector retriever error: {e}")
        print("Tip: Run `python -m src.indexer` to index your tables first.")
        return

    generator = SQLGenerator()

    # If question passed via CLI argument
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        process_question(question, retriever, generator, engine)
        return

    # Interactive loop
    print("\nType your question in natural language (or 'exit' / 'quit' to stop):")
    print("Example: 'Show me our top-selling region last month'")
    print("Example: 'List all platinum tier customers and their regions'")
    print("-" * 70)

    while True:
        try:
            user_input = input("\nAsk SQL > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            
            process_question(user_input, retriever, generator, engine)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()
