# 💬 Chat with Database

> **An AI-Powered Database Assistant & Smart Visual Analytics Dashboard**  
> *Translates natural language questions into safe SQL queries, visualizes results with auto-charts, and gives ChatGPT-style analytical advice using Schema-Aware RAG and Hugging Face LLMs.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B.svg)](https://streamlit.io/)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Inference%20API-yellow.svg)](https://huggingface.co/)
[![ChromaDB](https://img.shields.io/badge/Vector%20Store-ChromaDB-purple.svg)](https://www.trychroma.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLite-336791.svg)](https://www.postgresql.org/)

---

## 🌟 Key Features

- 🤖 **ChatGPT-Style Copilot**: Ask freeform business questions or ask for visualization advice (e.g., *"Which columns should I use for a pie chart?"*).
- 🔍 **Schema-Aware RAG**: Intelligently retrieves only the relevant tables and foreign key relationships into the prompt using **ChromaDB** and local **Hugging Face Sentence-Transformers**.
- 📊 **Smart Auto-Dashboard**: Automatically detects data types and renders the ideal visual:
  - 🥧 **Pie / Donut Charts** for categorical splits (2–8 slices)
  - 📊 **Grouped / Multi-bar Charts** for comparisons
  - 📈 **Line Charts** for time-series trends
  - ⚡ **KPI Cards** for single metric summaries
  - 📋 **Interactive Data Tables** with one-click CSV export
- 🛡️ **Built-in Guardrails**: Strictly validates SQL before execution, blocking destructive commands (`DROP`, `DELETE`, `UPDATE`, `ALTER`, `TRUNCATE`).
- 📤 **CSV Uploader & Auto-Indexer**: Upload any spreadsheet to import it into the database and immediately query it with AI.
- ⚡ **Zero-Configuration Mode**: Automatically connects to local PostgreSQL if available, or falls back to an included SQLite database so anyone can test **instantly with zero database setup required**!

---

## 📁 Project Structure

```text
chat-with-database/
├── data/
│   ├── seed_data.py           # Populates sample PostgreSQL / SQLite tables
│   ├── company_mock.db        # Included demo database (for instant zero-setup testing)
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
└── README.md                  # Project documentation
```

---

## 🚀 3-Minute Quickstart

Setting up this project is quick and simple. Follow these steps:

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
Copy `.env.example` to create your `.env`:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in your settings:
```ini
# Hugging Face API Token (Get a free read token at https://huggingface.co/settings/tokens)
HF_TOKEN=your_huggingface_token_here

# (Optional) PostgreSQL settings. If left unchanged, the app automatically runs on local SQLite!
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=company_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

> **Note**: If you don't have PostgreSQL installed, **no problem!** The application will automatically use the included SQLite database (`data/manufacturing_db.db`), allowing you to test right away without configuring a database server.

---

## 💻 Running the Application

### Option A: Interactive Web UI (Recommended)
Launch the Streamlit web dashboard with the side-by-side AI Copilot:
```bash
streamlit run streamlit_app.py
```
Open your browser at `http://localhost:8501`.

### Option B: Terminal / CLI Mode
If you prefer running queries from the command line:
```bash
python app.py
```

### Option C: Beginner's 5-Step Learning Script
To understand how Schema-Aware Text-to-SQL works step-by-step:
```bash
python simple_nl2sql.py
```

---

## 💡 Example Questions to Ask

Try typing these questions into the AI Copilot:

### 📈 Charting & Visualization Advice
- *"Which columns should I use for a pie chart?"*
- *"What columns are best to plot a bar chart?"*
- *"Suggest the best visualization for production output over time."*

### 🏭 Manufacturing & Operations Intelligence
- *"What is our overall average OEE percentage across all runs?"*
- *"Show total defect quantity grouped by plant location."*
- *"Which production line experienced the highest downtime?"*
- *"List all runs where scrap quantity exceeded 20 units."*

### 👥 Employee & Business Analytics
- *"Show me employee count by department."*
- *"List all employees in the Engineering department."*

---

## 🛡️ Query Safety & Guardrails

To protect against SQL injection or accidental data corruption:
1. Queries are parsed and inspected with `sqlparse`.
2. Only read-only `SELECT` statements are permitted.
3. Any attempt to run `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, or `EXEC` is blocked immediately with a safety alert.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **Frontend UI** | [Streamlit](https://streamlit.io/) + [Plotly](https://plotly.com/python/) |
| **Vector Store** | [ChromaDB](https://www.trychroma.com/) |
| **Embeddings** | [Hugging Face Sentence-Transformers](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (`all-MiniLM-L6-v2`) |
| **LLM Model** | [Qwen 2.5 Coder 32B Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) via Hugging Face Inference API |
| **Database** | PostgreSQL (Primary) / SQLite (Fallback & Offline) with [SQLAlchemy](https://www.sqlalchemy.org/) |
| **SQL Parser** | [sqlparse](https://github.com/andialbrecht/sqlparse) |

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!  
Feel free to open an issue or submit a Pull Request on [GitHub](https://github.com/akshaykaygude/chat-with-database).

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
