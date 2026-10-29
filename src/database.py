"""
database.py
Handles database connection, schema introspection (reflection), and query execution.
Supports both PostgreSQL (primary) and SQLite (for quick local testing).
"""

import os
import re
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

load_dotenv()

# Manufacturing table descriptions for schema vector search
TABLE_DESCRIPTIONS = {
    "plants": "Manufacturing facilities, factories, plant locations (Detroit, Munich, Tokyo), and daily capacity.",
    "production_lines": "Factory production lines, assembly lines, machining lines, stamping presses, and line operational status.",
    "products": "Manufactured products, parts, hydraulic cylinders, motor rotors, ECUs, component costs, and cycle times.",
    "production_runs": "Daily production work orders, batches, shifts (Morning, Afternoon, Night), planned quantity, actual produced units, defect count, scrap, downtime minutes, and OEE percentage.",
    "machine_maintenance": "Equipment maintenance logs, machine breakdowns, repair costs, downtime hours, and issue categories (Hydraulic Leak, Sensor Fault, Motor Overheating).",
    "noise_canteen_menu": "Cafeteria food menu and meal calories (unrelated to manufacturing).",
    "noise_visitor_logs": "Security gate guest sign-in logs (unrelated to production)."
}

def get_engine(db_name: Optional[str] = None) -> Engine:
    """
    Creates and returns a SQLAlchemy Engine.
    Uses DATABASE_URL if provided, else constructs from POSTGRES_* env vars.
    Supports targeting a specific db_name or falls back to local SQLite.
    """
    # Direct database URL override
    db_url = os.getenv("DATABASE_URL")
    if db_url and not db_name:
        return create_engine(db_url)
    
    target_db = db_name or os.getenv("POSTGRES_DB", "company_db")
    host = os.getenv("POSTGRES_HOST")
    
    # Check PostgreSQL env vars
    if host and os.getenv("POSTGRES_USER"):
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        try:
            pg_engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{target_db}")
            with pg_engine.connect() as conn:
                pass
            return pg_engine
        except Exception:
            # If PostgreSQL connection fails, fall back to SQLite below
            pass
    
    # Fallback to local SQLite
    if db_name and (db_name.endswith(".db") or db_name.endswith(".sqlite")):
        sqlite_path = os.path.join(os.path.dirname(__file__), "..", "data", db_name)
    else:
        sqlite_path = os.path.join(os.path.dirname(__file__), "..", "data", "manufacturing_db.db")
        
    return create_engine(f"sqlite:///{os.path.abspath(sqlite_path)}")

def import_csv_to_db(df: pd.DataFrame, table_name: str, db_name: Optional[str] = None, if_exists: str = "replace") -> Tuple[bool, str]:
    """
    Imports a pandas DataFrame from an uploaded CSV into the chosen database and table.
    Sanitizes table and column names for safe SQL compatibility.
    """
    try:
        clean_tbl = re.sub(r"[^a-zA-Z0-9_]", "_", table_name.strip()).lower().strip("_")
        if not clean_tbl:
            clean_tbl = "uploaded_dataset"

        clean_df = df.copy()
        clean_cols = []
        for i, col in enumerate(clean_df.columns):
            c = re.sub(r"[^a-zA-Z0-9_]", "_", str(col).strip()).lower().strip("_")
            if not c:
                c = f"column_{i+1}"
            clean_cols.append(c)
        clean_df.columns = clean_cols

        engine = get_engine(db_name=db_name)
        clean_df.to_sql(clean_tbl, con=engine, if_exists=if_exists, index=False)
        return True, f"Successfully imported {len(clean_df)} records into table '{clean_tbl}'!"
    except Exception as err:
        return False, str(err)


def extract_schema_metadata(engine: Engine) -> List[Dict[str, Any]]:
    """
    Introspects the database using SQLAlchemy's Inspector.
    Extracts table names, columns, data types, primary keys, foreign keys, 
    and a few sample rows to help the LLM understand value formats.
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    schema_docs = []
    
    with engine.connect() as conn:
        for table_name in table_names:
            columns = inspector.get_columns(table_name)
            pk_constraint = inspector.get_pk_constraint(table_name)
            primary_keys = set(pk_constraint.get("constrained_columns", []))
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            # Map foreign keys for easy lookup: col_name -> target_table.target_col
            fk_map = {}
            for fk in foreign_keys:
                referred_table = fk.get("referred_table")
                for constrained_col, referred_col in zip(fk.get("constrained_columns", []), fk.get("referred_columns", [])):
                    fk_map[constrained_col] = f"{referred_table}.{referred_col}"
            
            # Format column specifications
            col_lines = []
            for col in columns:
                c_name = col["name"]
                c_type = str(col["type"])
                attributes = []
                if c_name in primary_keys:
                    attributes.append("PRIMARY KEY")
                if c_name in fk_map:
                    attributes.append(f"FOREIGN KEY -> {fk_map[c_name]}")
                if not col.get("nullable", True):
                    attributes.append("NOT NULL")
                
                attr_str = f" ({', '.join(attributes)})" if attributes else ""
                col_lines.append(f"  - {c_name}: {c_type}{attr_str}")
            
            # Fetch 2 sample rows to provide context for data formats (dates, codes, text patterns)
            sample_rows_text = ""
            try:
                result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 2;"))
                rows = result.fetchall()
                if rows:
                    col_keys = list(result.keys())
                    sample_lines = [
                        "    " + " | ".join(f"{col}: {val}" for col, val in zip(col_keys, row))
                        for row in rows
                    ]
                    sample_rows_text = "\n  Sample rows:\n" + "\n".join(sample_lines)
            except Exception:
                pass  # In case table is inaccessible or empty
            
            description = TABLE_DESCRIPTIONS.get(table_name, "Business data table.")
            
            # Create a rich document representation of this table
            formatted_doc = (
                f"Table Name: {table_name}\n"
                f"Description: {description}\n"
                f"Columns:\n" + "\n".join(col_lines) +
                sample_rows_text
            )
            
            schema_docs.append({
                "table_name": table_name,
                "description": description,
                "document": formatted_doc,
                "columns": [c["name"] for c in columns],
                "foreign_keys": fk_map
            })
            
    return schema_docs

def execute_query(engine: Engine, query: str) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    """
    Executes a SELECT SQL query and returns (column_names, rows).
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        columns = list(result.keys())
        rows = result.fetchall()
        return columns, rows
