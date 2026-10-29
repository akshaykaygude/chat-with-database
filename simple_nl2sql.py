"""
==============================================================================
BEGINNER'S GUIDE TO SCHEMA-AWARE RAG (TEXT-TO-SQL)
==============================================================================
This single script teaches you all 5 steps of building a Natural Language to SQL
system using PostgreSQL/SQLite and Hugging Face:

  Step 1: Connect to Database & Create Sample Tables
  Step 2: Read the Database Schema (Columns & Data Types)
  Step 3: RAG Retrieval (Pick ONLY the tables needed for the question)
  Step 4: Hugging Face AI (Translate English Question -> SQL)
  Step 5: Safety Guardrails & Query Execution
==============================================================================
"""

import os
import re
import math
from typing import List, Dict, Tuple
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

# Load secrets (.env file)
load_dotenv()


# ==============================================================================
# STEP 1: DATABASE SETUP
# ==============================================================================
# In a real company, you connect to PostgreSQL.
# For quick local testing, this script automatically falls back to SQLite
# so you can run and learn immediately without setting up a server!
# ==============================================================================

def get_database_engine():
    """
    Creates a connection to the database.
    If PostgreSQL credentials are set in .env, connects to PostgreSQL.
    Otherwise, uses a local file database (SQLite).
    """
    pg_host = os.getenv("POSTGRES_HOST")
    pg_user = os.getenv("POSTGRES_USER")
    
    # Try PostgreSQL first if credentials are configured
    if pg_host and pg_user and pg_user != "postgres_placeholder":
        try:
            pg_password = os.getenv("POSTGRES_PASSWORD", "postgres")
            pg_port = os.getenv("POSTGRES_PORT", "5432")
            pg_db = os.getenv("POSTGRES_DB", "company_db")
            url = f"postgresql+psycopg2://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
            engine = create_engine(url)
            with engine.connect() as conn:
                pass
            print(" Connected to: PostgreSQL Database")
            return engine
        except Exception as e:
            print(" [Notice] Could not connect to PostgreSQL (server not running or psycopg2 not installed).")
            print("          Falling back to local SQLite database so you can test right now!")
    
    # Default beginner fallback: SQLite (zero installation needed)
    db_file = os.path.join(os.path.dirname(__file__), "data", "beginner_demo.db")
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    print(" Using local mock database (SQLite). Easy for learning!")
    return create_engine(f"sqlite:///{os.path.abspath(db_file)}")


def setup_sample_data(engine):
    """
    Creates manufacturing operational tables:
      1. plants (Factory locations, daily capacity)
      2. production_lines (Assembly, Machining, Packaging lines)
      3. production_runs (Daily shifts, planned vs actual units, defect scrap, downtime, OEE)
      
    And 1 UNRELATED table:
      4. noise_canteen_menu (Cafeteria meals - NOISE to test our RAG filter!)
    """
    print("\n--- [Step 1] Creating Manufacturing Sample Tables & Data ---")
    is_sqlite = engine.dialect.name == "sqlite"
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"

    with engine.begin() as conn:
        for tbl in ["production_runs", "production_lines", "plants", "noise_canteen_menu"]:
            conn.execute(text(f"DROP TABLE IF EXISTS {tbl};"))

        # Table 1: plants
        conn.execute(text(f"""
            CREATE TABLE plants (
                plant_id {pk},
                plant_name VARCHAR(100),
                city VARCHAR(100),
                country VARCHAR(100)
            );
        """))

        # Table 2: production_lines
        conn.execute(text(f"""
            CREATE TABLE production_lines (
                line_id {pk},
                plant_id INT,
                line_name VARCHAR(100),
                line_type VARCHAR(50) -- Assembly, Machining, Stamping
            );
        """))

        # Table 3: production_runs
        conn.execute(text(f"""
            CREATE TABLE production_runs (
                run_id {pk},
                plant_id INT,
                line_id INT,
                run_date DATE,
                shift VARCHAR(20),       -- Morning, Afternoon, Night
                actual_qty INT,
                defect_qty INT,
                downtime_mins INT,
                oee_pct NUMERIC(5, 2)
            );
        """))

        # Table 4: noise_canteen_menu (Noise table)
        conn.execute(text(f"""
            CREATE TABLE noise_canteen_menu (
                menu_id {pk},
                dish_name VARCHAR(100),
                calories INT
            );
        """))

        # Insert realistic manufacturing rows
        conn.execute(text("""
            INSERT INTO plants (plant_name, city, country) VALUES
            ('Detroit Heavy Assembly', 'Detroit', 'USA'),
            ('Munich Powertrain Hub', 'Munich', 'Germany'),
            ('Tokyo Micro-Fab & Electronics', 'Yokohama', 'Japan'),
            ('Monterrey Stamping Works', 'Monterrey', 'Mexico');
        """))

        conn.execute(text("""
            INSERT INTO production_lines (plant_id, line_name, line_type) VALUES
            (1, 'Line A - Chassis Welding', 'Assembly'),
            (2, 'Line 1 - Engine CNC', 'Machining'),
            (3, 'Cleanroom Line Alpha', 'Assembly'),
            (4, 'Press Line 500T', 'Stamping');
        """))

        conn.execute(text("""
            INSERT INTO production_runs (plant_id, line_id, run_date, shift, actual_qty, defect_qty, downtime_mins, oee_pct) VALUES
            (1, 1, '2026-09-20', 'Morning',   1150, 24, 35, 87.5),
            (1, 1, '2026-09-20', 'Afternoon', 1100, 38, 55, 81.2),
            (1, 1, '2026-09-20', 'Night',      920, 45, 75, 74.0),
            (2, 2, '2026-09-20', 'Morning',   2480, 12, 10, 94.2),
            (2, 2, '2026-09-20', 'Afternoon', 2410, 22, 25, 89.8),
            (3, 3, '2026-09-20', 'Morning',   4950, 18, 15, 96.0),
            (3, 3, '2026-09-20', 'Afternoon', 4890, 35, 30, 91.5),
            (4, 4, '2026-09-21', 'Morning',   1850, 65, 80, 78.4),
            (4, 4, '2026-09-21', 'Afternoon', 1910, 42, 45, 83.1);
        """))

        conn.execute(text("""
            INSERT INTO noise_canteen_menu (dish_name, calories) VALUES
            ('Grilled Salmon Salad', 450),
            ('Beef Stroganoff', 780);
        """))

    print(" Created manufacturing tables: 'plants', 'production_lines', 'production_runs', 'noise_canteen_menu'")


# ==============================================================================
# STEP 2: SCHEMA INTROSPECTION (READING THE DATABASE STRUCTURE)
# ==============================================================================
# An LLM cannot see your database unless you describe it.
# We inspect the database to extract:
#   - Table name
#   - Column names and their data types (e.g. total_amount is NUMERIC)
# ==============================================================================

def extract_schema_descriptions(engine) -> Dict[str, str]:
    """
    Inspects each table and creates a simple text card describing it.
    Example output for 'orders':
      Table: orders
      Description: Customer sales transactions, order dates, total amounts, and statuses.
      Columns:
        - order_id: INTEGER
        - customer_id: INTEGER
        - total_amount: NUMERIC
        - status: VARCHAR
    """
    print("\n--- [Step 2] Reading Database Schema Automatically ---")
    inspector = inspect(engine)
    
    # Manufacturing descriptions (helps RAG semantic search)
    table_purposes = {
        "plants": "Manufacturing facilities, factories, plant locations (Detroit, Munich, Tokyo), and capacity.",
        "production_lines": "Assembly, Machining, and Stamping production lines and their status.",
        "production_runs": "Daily manufacturing work orders, shifts, actual output, scrap/defect count, downtime minutes, and OEE percentage.",
        "noise_canteen_menu": "Cafeteria food menu and meal calories (unrelated to production)."
    }

    schemas = {}
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        col_list = [f"  - {c['name']} ({c['type']})" for c in columns]
        
        purpose = table_purposes.get(table_name, "Business table")
        schema_text = (
            f"Table: {table_name}\n"
            f"Purpose: {purpose}\n"
            f"Columns:\n" + "\n".join(col_list)
        )
        schemas[table_name] = schema_text

    return schemas


# ==============================================================================
# STEP 3: RAG RETRIEVAL (FINDING RELEVANT TABLES)
# ==============================================================================
# What is RAG here?
# When an analyst asks: "What is the total sales amount?",
# we want to find 'orders' and 'customers', NOT 'system_logs'!
#
# We use Hugging Face 'sentence-transformers' to compute embeddings.
# (An embedding is a list of numbers representing the meaning of a sentence).
# We compare the question's embedding to each table's embedding using Cosine Similarity.
# ==============================================================================

def get_relevant_tables(user_question: str, schemas: Dict[str, str], top_k: int = 2) -> List[str]:
    """
    Finds the top_k most relevant tables for the user's question.
    Uses Hugging Face sentence-transformers (or a smart keyword matcher as fallback).
    """
    print(f"\n--- [Step 3] RAG Retrieval: Finding tables for: '{user_question}' ---")
    
    try:
        from sentence_transformers import SentenceTransformer
        # Free, ultra-fast embedding model by Hugging Face (runs locally)
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        
        # 1. Turn user question into numbers (embedding)
        q_embedding = model.encode(user_question)

        # 2. Score each table by cosine similarity
        scored_tables = []
        for table_name, schema_text in schemas.items():
            t_embedding = model.encode(schema_text)
            
            # Cosine similarity formula: dot_product / (norm(a) * norm(b))
            dot = sum(a * b for a, b in zip(q_embedding, t_embedding))
            norm_q = math.sqrt(sum(a * a for a in q_embedding))
            norm_t = math.sqrt(sum(b * b for b in t_embedding))
            score = dot / (norm_q * norm_t)
            
            scored_tables.append((table_name, score))

        # Sort by highest similarity score first
        scored_tables.sort(key=lambda x: x[1], reverse=True)
        
        print("  Table similarity scores:")
        for tbl, score in scored_tables:
            print(f"    * {tbl}: {score:.4f}")

        selected = [tbl for tbl, score in scored_tables[:top_k]]
        print(f" -> RAG selected {len(selected)} tables: {selected}")
        return selected

    except ImportError:
        # Fallback if sentence-transformers is not yet installed:
        print("  [Notice] sentence-transformers not installed yet. Using keyword matching.")
        scores = {}
        for tbl, text_content in schemas.items():
            words = user_question.lower().split()
            matches = sum(1 for w in words if w in text_content.lower())
            scores[tbl] = matches
        sorted_tables = sorted(scores.keys(), key=lambda t: scores[t], reverse=True)
        return sorted_tables[:top_k]


# ==============================================================================
# STEP 4: HUGGING FACE AI (GENERATING SQL)
# ==============================================================================
# We craft a clear prompt containing:
#   1. Rules: "Write ONLY a PostgreSQL SELECT query."
#   2. Context: The schemas of the tables we found in Step 3.
#   3. Question: The user's question.
#
# Then we call Hugging Face Inference API.
# ==============================================================================

def generate_sql_with_huggingface(user_question: str, schema_context: str) -> str:
    """
    Sends the prompt to Hugging Face LLM (e.g. Qwen2.5-Coder) and gets back SQL.
    """
    print("\n--- [Step 4] Calling Hugging Face AI to Generate SQL ---")
    hf_token = os.getenv("HF_TOKEN")
    
    prompt = f"""You are an expert SQL Data Engineer.
Given the following database schema, write a valid read-only SQL SELECT query to answer the user question.

Schema:
{schema_context}

User Question: {user_question}

Rules:
- Write ONLY the SQL query inside ```sql ... ```
- Do not provide conversational explanations.
- Query must be a SELECT statement.

SQL Query:"""

    # If user provided a free Hugging Face token:
    if hf_token and hf_token.startswith("hf_"):
        from huggingface_hub import InferenceClient
        client = InferenceClient(model="Qwen/Qwen2.5-Coder-32B-Instruct", token=hf_token)
        
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a professional SQL writer. Return only executable SQL."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.1
        )
        raw_text = response.choices[0].message.content
    else:
        # If no token is provided yet, show an educational demo query
        print("  [Tip] No HF_TOKEN found in .env. Showing demo SQL response.")
        print("  (To get real AI responses, add your free token at huggingface.co/settings/tokens)")
        raw_text = """```sql
SELECT p.plant_name, SUM(r.defect_qty) AS total_defects, SUM(r.downtime_mins) AS total_downtime_mins
FROM production_runs r
JOIN plants p ON r.plant_id = p.plant_id
GROUP BY p.plant_name
ORDER BY total_defects DESC;
```"""

    # Extract SQL from ```sql ... ```
    match = re.search(r"```(?:sql)?\s*(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
    sql = match.group(1).strip() if match else raw_text.strip()
    
    print("\nGenerated SQL:")
    print(f"  {sql}\n")
    return sql


# ==============================================================================
# STEP 5: SAFETY GUARDRAIL & EXECUTION
# ==============================================================================
# NEVER run AI-generated SQL blindly!
# We check:
#   1. Does the query start with SELECT?
#   2. Does it contain forbidden words like DROP, DELETE, UPDATE, ALTER?
# If safe, we execute it on the database and show the results!
# ==============================================================================

def validate_and_execute_sql(engine, sql: str):
    """
    Checks if query is safe (read-only), then executes it and prints rows.
    """
    print("--- [Step 5] Safety Guardrail & Execution ---")
    
    # 1. Clean query
    cleaned = sql.strip().rstrip(";")
    
    # 2. Check for dangerous words
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
    for word in forbidden:
        if re.search(rf"\b{word}\b", cleaned, re.IGNORECASE):
            print(f" [BLOCKED] Query contains dangerous keyword: {word}!")
            return

    # 3. Must start with SELECT
    if not cleaned.upper().startswith("SELECT"):
        print(" [BLOCKED] Only SELECT queries are allowed!")
        return

    print(" [PASS] Query is safe (Read-Only SELECT).")
    
    # 4. Execute on database
    print("\nExecuting query on database...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text(cleaned))
            rows = result.fetchall()
            headers = list(result.keys())
            
            print(f"\n Results ({len(rows)} rows):")
            print(" | ".join(headers))
            print("-" * 50)
            for r in rows:
                print(" | ".join(str(val) for val in r))
    except Exception as e:
        print(f" [!] Execution error: {e}")


# ==============================================================================
# MAIN DEMO WALKTHROUGH
# ==============================================================================
def main():
    print("=" * 70)
    print("   BEGINNER-FRIENDLY NATURAL LANGUAGE TO SQL (RAG PIPELINE)   ")
    print("=" * 70)

    # 1. Setup DB
    engine = get_database_engine()
    setup_sample_data(engine)

    # 2. Read Schemas
    schemas = extract_schema_descriptions(engine)

    # 3. Ask a Question in Natural Language
    user_question = "Which manufacturing plant had the highest total defect count?"
    print(f"\nUser Question: \"{user_question}\"")

    # 4. RAG: Pick only relevant tables
    selected_tables = get_relevant_tables(user_question, schemas, top_k=3)
    
    # Build schema context string with only selected tables
    context = "\n\n".join(schemas[tbl] for tbl in selected_tables)

    # 5. AI: Generate SQL
    generated_sql = generate_sql_with_huggingface(user_question, context)

    # 6. Safety & Run
    validate_and_execute_sql(engine, generated_sql)

    print("\n" + "=" * 70)
    print(" Tutorial finished! You just experienced the complete Text-to-SQL flow.")
    print("=" * 70)


if __name__ == "__main__":
    main()
