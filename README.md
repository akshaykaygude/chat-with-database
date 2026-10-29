# Schema-Aware Natural Language to SQL (PostgreSQL + Hugging Face)

A RAG system that stores database schemas, table relationships, and metadata. When an analyst asks a natural language question (e.g., *"Show me our top-selling region last month"*), the system:
1. Performs semantic search over database table schemas using local **Hugging Face Sentence-Transformers**.
2. Retrieves only the relevant tables and their foreign key relationships from **ChromaDB**.
3. Prompts a **Hugging Face LLM** (e.g. `Qwen/Qwen2.5-Coder-32B-Instruct`) to generate a PostgreSQL-compliant `SELECT` query.
4. Validates the query with safety guardrails (blocking `DROP`, `DELETE`, `UPDATE`).
5. Executes the query on **PostgreSQL** and returns clean tabular results.

---

## 📁 Project Structure

```text
nl2sql-rag/
├── data/
│   ├── seed_data.py          # Creates sample sales tables and populates sample data
│   └── chroma_db/            # Local vector store storing table schema embeddings
├── src/
│   ├── __init__.py
│   ├── database.py           # DB connection, automatic schema introspection & execution
│   ├── indexer.py            # Converts schemas to embeddings via Hugging Face & saves to ChromaDB
│   ├── retriever.py          # Finds relevant tables for a user question
│   ├── generator.py          # Prompts Hugging Face LLM to write PostgreSQL queries
│   └── guardrails.py         # Validates that SQL is strictly SELECT (safe)
├── app.py                    # Interactive CLI runner
├── requirements.txt          # Python dependencies
├── .env.example              # Configuration template
└── .env                      # Your local environment variables
```

---

## 🚀 Quickstart Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Edit `.env` with your settings:
```ini
# PostgreSQL credentials
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=company_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Hugging Face Settings (Get a free token at https://huggingface.co/settings/tokens)
HF_TOKEN=your_huggingface_token_here
HF_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### 3. Seed Sample Database
Populate sample sales, orders, customers, and regions into PostgreSQL:
```bash
python data/seed_data.py
```
*(If you want to test right away without PostgreSQL running, use: `python data/seed_data.py --sqlite`)*

### 4. Index Database Schema into ChromaDB
Extract table metadata and compute Hugging Face embeddings:
```bash
python -m src.indexer
```

### 5. Run the Interactive Translator
```bash
python app.py
```

Try asking:
- *"Show me the top 3 selling regions by total sales."*
- *"List all Platinum tier customers and who manages their region."*
- *"What is our total revenue from completed orders?"*
