# 💬 Chat with Database (Schema-Aware Text-to-SQL Copilot)

> **An AI-Powered Database Assistant & Smart Visual Analytics Dashboard**  
> *Translates natural language questions into safe SQL queries, visualizes results with auto-charts, and provides ChatGPT-style analytical advice using Schema-Aware RAG and Hugging Face LLMs.*

[![CI Pipeline](https://github.com/akshaykaygude/chat-with-database/actions/workflows/ci.yml/badge.svg)](https://github.com/akshaykaygude/chat-with-database/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Inference%20API-yellow.svg)](https://huggingface.co/)
[![ChromaDB](https://img.shields.io/badge/Vector%20Store-ChromaDB-purple.svg)](https://www.trychroma.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLite-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 Current Capabilities: What Already Works

The following components are fully implemented and verified in this codebase:

- [x] **ChatGPT-Style Copilot (`src/generator.py`)**:
  - Answers open-ended conversational questions and provides charting advice (e.g., *"Which columns should I use for a pie chart?"*).
  - Translates operational queries into optimized PostgreSQL/SQLite SELECT queries using `Qwen/Qwen2.5-Coder-32B-Instruct`.
- [x] **Schema-Aware RAG Retrieval (`src/retriever.py`, `src/indexer.py`)**:
  - Encodes table definitions, column types, and foreign key relationships into embeddings using local `sentence-transformers/all-MiniLM-L6-v2`.
  - Performs semantic vector search in ChromaDB to retrieve only the relevant table schemas into the prompt, preventing LLM context window overflow.
- [x] **Smart Auto-Dashboard (`streamlit_app.py`)**:
  - Evaluates query result sets and automatically chooses the best visual format:
    - 🥧 **Pie / Donut Charts** for categorical splits (2–8 slices).
    - 📊 **Grouped Bar Charts** for comparisons across dimensions.
    - 📈 **Line Charts** for time-series trends.
    - ⚡ **KPI Metric Cards** for single aggregated metrics.
    - 📋 **Interactive Data Tables** with one-click CSV export.
- [x] **Strict SQL Safety Guardrails (`src/guardrails.py`)**:
  - Parses SQL statements using `sqlparse`.
  - Blocks all destructive statements (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `EXEC`) with immediate user warnings.
- [x] **CSV Uploader & Auto-Indexer (`streamlit_app.py`, `src/database.py`)**:
  - Allows uploading arbitrary CSV files, creates sanitized tables, and automatically re-indexes schema embeddings.
- [x] **Dual Database Support (`src/database.py`)**:
  - Zero-configuration local SQLite fallback (`data/manufacturing_db.db`) allows instant testing without setting up a database server.
  - Production PostgreSQL connection when configured in `.env`.
- [x] **Automated Test Suite & CI (`tests/test_sql_rag.py`, `.github/workflows/ci.yml`)**:
  - Unit tests covering guardrails, schema introspection, query execution, and intent classification running on GitHub Actions.

---

## ⚠️ Known Limitations & Real-World Edge Cases

1. **Hugging Face Inference Free-Tier Limits**:
   - The cloud Inference API provides generous free tier access, but high-frequency requests may experience temporary rate-limit cooldowns. Setting a personal `HF_TOKEN` in `.env` raises throughput.
2. **Deeply Nested Subqueries Across 4+ Tables**:
   - Schema-aware retrieval retrieves the top-K tables (default: 3). Queries requiring complex joins across 5 or more distant tables may require manual table selection or increasing `top_k`.
3. **Dialect Differences (PostgreSQL vs. SQLite)**:
   - While date functions (`strftime` vs `DATE_TRUNC`) are handled by prompt guidelines, advanced PostgreSQL window functions may not execute if falling back to local SQLite.

---

## 🗺️ Development Roadmap & Next Milestones

- [x] **v1.0 (Core Engine)**: Schema vector indexing with ChromaDB and CLI interface.
- [x] **v1.1 (Interactive UI)**: Split-screen Streamlit application with visual analytics and side-by-side chatbot.
- [x] **v1.2 (Data Ingestion)**: Dynamic CSV uploader with automated schema vector re-indexing.
- [x] **v1.3 (Quality & CI)**: Automated unit testing suite and GitHub Actions testing pipeline.
- [ ] **v2.0 (Local Offline LLM)**: Support for local Ollama / vLLM execution (Qwen-2.5-Coder / Llama 3.1) for zero cloud API dependency.
- [ ] **v2.1 (Multi-Database Switcher)**: Live UI connection manager for MySQL, Snowflake, and BigQuery.

---

## 📁 Repository Structure

```text
chat-with-database/
├── .github/workflows/
│   └── ci.yml                 # GitHub Actions automated test pipeline
├── tests/
│   └── test_sql_rag.py        # Automated test suite (guardrails, reflection, router)
├── data/
│   ├── seed_data.py           # Populates sample PostgreSQL / SQLite tables
│   ├── company_mock.db        # Included demo database
│   ├── manufacturing_db.db    # Manufacturing plant & operations dataset
│   └── chroma_db/             # Local vector store containing table schema embeddings
├── src/
│   ├── database.py            # DB connections, schema reflection & query executor
│   ├── indexer.py             # Converts table schemas to vector embeddings in ChromaDB
│   ├── retriever.py           # Semantic vector search to retrieve relevant schemas
│   ├── generator.py           # Hugging Face LLM integration for SQL & ChatGPT advice
│   └── guardrails.py          # SQL safety validation (SELECT-only guardrails)
├── streamlit_app.py           # 🌟 Interactive Web Dashboard & AI Copilot (Main App)
├── app.py                     # Interactive CLI runner
├── simple_nl2sql.py           # 5-step beginner learning script
├── requirements.txt           # Python dependencies
├── .env.example               # Configuration template
├── .gitignore                 # Excludes secrets, venvs, and logs
├── LICENSE                    # MIT Open-Source License
└── README.md                  # Project documentation
```

---

## 🚀 3-Minute Quickstart

### 1. Clone the Repository
```bash
git clone https://github.com/akshaykaygude/chat-with-database.git
cd chat-with-database
```

### 2. Create and Activate a Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Your Environment File (`.env`)
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and configure your free Hugging Face token:
```ini
HF_TOKEN=your_huggingface_token_here
```
*(Get a free read token at https://huggingface.co/settings/tokens. Database credentials are optional; local SQLite is used by default!)*

---

## 💻 Running the Application

### Option A: Interactive Web UI (Recommended)
```bash
streamlit run streamlit_app.py
```
Open your browser at `http://localhost:8501`.

### Option B: Terminal CLI Mode
```bash
python app.py
```

### Option C: Run Test Suite
```bash
python -m unittest tests/test_sql_rag.py
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
