"""
streamlit_app.py
Interactive Manufacturing Operations Dashboard with Right-Side ChatGPT-style Copilot.

Layout:
  - Left Side: Visual Analytics Dashboard, Auto-Charts (Pie, Bar, Line, KPI), CSV Importer, Table Explorer.
  - Right Side: Dedicated ChatGPT-style AI Assistant & Charting Advisor.

Features:
  - 🤖 Right-side Chatbot: Answers data, charting (e.g., 'which columns for pie chart'), and business questions.
  - 📤 CSV Uploader: Upload CSV, specify Database & Table, auto-import & re-index schema.
  - 📊 Smart Auto-Dashboard: Dynamic Pie, Bar, Line, and KPI metric visuals.
  - 🔍 Schema-Aware RAG with Qwen2.5-Coder-32B & Hugging Face.
"""

import os
import re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.database import get_engine, execute_query, extract_schema_metadata, import_csv_to_db
from src.retriever import SchemaRetriever
from src.generator import SQLGenerator
from src.guardrails import validate_sql
from src.indexer import index_database_schema

load_dotenv()

# ==============================================================================
# STREAMLIT PAGE CONFIGURATION & STYLING
# ==============================================================================
st.set_page_config(
    page_title="Operations Intelligence & AI Copilot",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .chart-badge {
        display: inline-block;
        background: #e0f2fe;
        color: #0369a1;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .chat-pill {
        display: inline-block;
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        color: #334155;
        border-radius: 16px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 500;
        margin-bottom: 8px;
    }
    .stChatMessage {
        border-radius: 10px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# SESSION STATE INITIALIZATION
# ==============================================================================
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "👋 **Hello! I am your AI Data Assistant & Charting Advisor.**\n\n"
                "I can help you analyze your data like ChatGPT:\n"
                "- 🥧 *'Tell me which columns to use for a pie chart'*\n"
                "- 📊 *'Which columns are best for a bar chart?'*\n"
                "- 🔍 *'Show defect quantity grouped by plant'*\n"
                "- ⚡ *'What is our overall average OEE?'*\n\n"
                "Ask me any question below!"
            )
        }
    ]

if "pending_query" not in st.session_state:
    st.session_state["pending_query"] = None

if "current_db" not in st.session_state:
    st.session_state["current_db"] = os.getenv("POSTGRES_DB", "company_db")

if "active_df" not in st.session_state:
    st.session_state["active_df"] = None

if "active_title" not in st.session_state:
    st.session_state["active_title"] = "Operational Overview"

if "active_table" not in st.session_state:
    st.session_state["active_table"] = None


# ==============================================================================
# DATABASE CONNECTION & SCHEMA RETRIEVAL
# ==============================================================================
active_db = st.session_state.get("current_db", os.getenv("POSTGRES_DB", "company_db"))
try:
    engine = get_engine(db_name=active_db)
    is_pg = "postgresql" in str(engine.url)
    db_type_label = f"PostgreSQL ({active_db})" if is_pg else "SQLite (Local Mock)"
    schemas = extract_schema_metadata(engine)
except Exception as e:
    engine = None
    schemas = []
    db_type_label = f"Offline / Error: {e}"

# Set default active table if not set
if not st.session_state.get("active_table") and schemas:
    non_noise = [s["table_name"] for s in schemas if "noise" not in s["table_name"]]
    st.session_state["active_table"] = non_noise[0] if non_noise else schemas[0]["table_name"]


# ==============================================================================
# VISUALIZATION FUNCTIONS (Left Side Dashboard)
# ==============================================================================
def render_pie_chart(df: pd.DataFrame, cat_col: str, num_col: str):
    try:
        import plotly.express as px
        fig = px.pie(
            df, 
            names=cat_col, 
            values=num_col, 
            hole=0.45,
            title=f"Distribution of {num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.bar_chart(df.set_index(cat_col)[num_col])

def render_bar_chart(df: pd.DataFrame, cat_col: str, num_cols: list):
    try:
        import plotly.express as px
        if len(num_cols) == 1:
            fig = px.bar(
                df, 
                x=cat_col, 
                y=num_cols[0], 
                color=cat_col,
                title=f"{num_cols[0].replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}"
            )
        else:
            fig = px.bar(
                df, 
                x=cat_col, 
                y=num_cols, 
                barmode='group',
                title=f"Comparison across {cat_col.replace('_', ' ').title()}"
            )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.bar_chart(df.set_index(cat_col)[num_cols])

def render_line_chart(df: pd.DataFrame, x_col: str, num_cols: list):
    try:
        import plotly.express as px
        fig = px.line(
            df.sort_values(x_col), 
            x=x_col, 
            y=num_cols, 
            markers=True,
            title=f"Trend over {x_col.replace('_', ' ').title()}"
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.line_chart(df.set_index(x_col)[num_cols])

def cat_col_label(col: str) -> str:
    return str(col).replace("_", " ").title()

def render_smart_dashboard(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("No records to visualize. Execute a query or select a table from the explorer.")
        return

    date_cols = [c for c in df.columns if any(k in str(c).lower() for k in ["date", "time", "day", "month", "year"])]
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = [c for c in df.columns if c not in numeric_cols and c not in date_cols]

    auto_chart_type = "table"
    reason = "Tabular view"

    if len(df) == 1 and len(numeric_cols) == 1 and len(cat_cols) == 0:
        auto_chart_type = "metric"
        reason = "Single KPI metric detected"
    elif date_cols and numeric_cols:
        auto_chart_type = "line"
        reason = f"Time-series trend ({date_cols[0]} vs {numeric_cols[0]})"
    elif cat_cols and len(numeric_cols) == 1 and 2 <= len(df) <= 8:
        auto_chart_type = "pie"
        reason = f"Categorical distribution with {len(df)} slices (Pie/Donut)"
    elif cat_cols and numeric_cols:
        auto_chart_type = "bar"
        reason = f"Comparison across {cat_col_label(cat_cols[0])}"

    tab_auto, tab_bar, tab_pie, tab_line, tab_raw = st.tabs([
        f"✨ Auto Visual ({auto_chart_type.upper()})",
        "📊 Bar Chart",
        "🥧 Pie Chart",
        "📈 Line Chart",
        "📋 Data Table"
    ])

    with tab_auto:
        st.markdown(f'<span class="chart-badge">Auto-Selected: {auto_chart_type.upper()} ({reason})</span>', unsafe_allow_html=True)
        if auto_chart_type == "metric":
            col_name = numeric_cols[0]
            val = df[col_name].iloc[0]
            val_str = f"{val:,.2f}%" if "pct" in col_name.lower() or "oee" in col_name.lower() else f"{val:,.2f}"
            st.metric(label=col_name.replace("_", " ").title(), value=val_str)
        elif auto_chart_type == "pie":
            render_pie_chart(df, cat_cols[0], numeric_cols[0])
        elif auto_chart_type == "bar":
            render_bar_chart(df, cat_cols[0], numeric_cols)
        elif auto_chart_type == "line":
            render_line_chart(df, date_cols[0], numeric_cols)
        else:
            st.dataframe(df, use_container_width=True)

    with tab_bar:
        if cat_cols and numeric_cols:
            render_bar_chart(df, cat_cols[0], numeric_cols)
        else:
            st.info("Bar chart requires categorical and numeric columns.")

    with tab_pie:
        if cat_cols and numeric_cols:
            render_pie_chart(df, cat_cols[0], numeric_cols[0])
        else:
            st.info("Pie chart requires at least 1 category column and 1 numeric column.")

    with tab_line:
        x_axis = date_cols[0] if date_cols else (cat_cols[0] if cat_cols else None)
        if x_axis and numeric_cols:
            render_line_chart(df, x_axis, numeric_cols)
        else:
            st.info("Line chart requires numeric metric and date/category column.")

    with tab_raw:
        st.dataframe(df, use_container_width=True)
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv_data,
            file_name="dataset_export.csv",
            mime="text/csv",
            key=f"dl_csv_btn_{len(df)}"
        )


# ==============================================================================
# MAIN PAGE HEADER
# ==============================================================================
col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🏭 Factory & Operations Intelligence")
    st.caption("Schema-Aware Text-to-SQL • Automated Visual Analytics • Right-Side ChatGPT Assistant")
with col_status:
    st.markdown(f"**Database:** `{db_type_label}`")
    st.caption(f"Discovered **{len(schemas)}** tables in database")

st.markdown("---")


# ==============================================================================
# SPLIT SCREEN LAYOUT: LEFT (DASHBOARD) | RIGHT (CHATBOT)
# ==============================================================================
col_dash, col_chat = st.columns([1.12, 0.88], gap="large")


# ==============================================================================
# LEFT COLUMN: VISUAL DASHBOARD, CSV IMPORTER, TABLE EXPLORER
# ==============================================================================
with col_dash:
    st.subheader("📊 Analytics & Data Management")
    
    dash_tabs = st.tabs([
        "📈 Visual Analytics", 
        "📤 Import CSV into Database", 
        "🔍 Database Tables & Schemas"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: VISUAL ANALYTICS
    # --------------------------------------------------------------------------
    with dash_tabs[0]:
        active_tbl = st.session_state.get("active_table", "Unknown")
        st.markdown(f"#### {st.session_state.get('active_title', 'Operational Overview')}")
        st.caption(f"Context Source: Table `{active_tbl}`")

        # If no active dataframe is cached, load sample data from active table
        if st.session_state.get("active_df") is None and engine and schemas:
            try:
                sample_cols, sample_rows = execute_query(engine, f"SELECT * FROM {active_tbl} LIMIT 50;")
                if sample_rows:
                    st.session_state["active_df"] = pd.DataFrame(sample_rows, columns=sample_cols)
            except Exception:
                pass

        current_df = st.session_state.get("active_df")
        if current_df is not None and not current_df.empty:
            render_smart_dashboard(current_df)
        else:
            st.info("No data currently loaded. Upload a CSV or ask a question in the AI Chatbot on the right!")

    # --------------------------------------------------------------------------
    # TAB 2: CSV UPLOADER & IMPORTER
    # --------------------------------------------------------------------------
    with dash_tabs[1]:
        st.markdown("#### 📤 Upload CSV File into Database")
        st.markdown("Upload any CSV spreadsheet to import it directly into PostgreSQL or SQLite:")
        
        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"], key="csv_file_uploader")
        if uploaded_file is not None:
            try:
                preview_df = pd.read_csv(uploaded_file)
                st.write(f"📊 **Detected:** {len(preview_df):,} rows, {len(preview_df.columns)} columns")
                st.dataframe(preview_df.head(4), use_container_width=True)

                col_in1, col_in2 = st.columns(2)
                default_table_name = re.sub(r'[^a-zA-Z0-9_]', '_', os.path.splitext(uploaded_file.name)[0]).lower().strip('_')
                
                with col_in1:
                    target_db_name = st.text_input("Target Database Name:", value=active_db)
                with col_in2:
                    target_tbl_name = st.text_input("Target Table Name:", value=default_table_name)
                
                import_mode_opt = st.radio(
                    "Import Mode:", 
                    ["Replace existing table", "Append to existing table"],
                    horizontal=True
                )

                if st.button("📥 Import CSV & Re-Index AI Schemas", type="primary", use_container_width=True):
                    with st.spinner("Writing data to database and updating AI embeddings..."):
                        if_exists_flag = "replace" if "Replace" in import_mode_opt else "append"
                        success, msg = import_csv_to_db(
                            preview_df, 
                            table_name=target_tbl_name, 
                            db_name=target_db_name, 
                            if_exists=if_exists_flag
                        )
                        if success:
                            st.session_state["current_db"] = target_db_name
                            st.session_state["active_table"] = target_tbl_name
                            st.session_state["active_df"] = preview_df
                            st.session_state["active_title"] = f"Imported Table: {target_tbl_name}"
                            
                            # Re-index schema vector store
                            try:
                                new_eng = get_engine(db_name=target_db_name)
                                index_database_schema(force_reindex=True, engine=new_eng)
                            except Exception as reindex_err:
                                st.warning(f"Re-indexing notice: {reindex_err}")
                            
                            st.success(f"🎉 {msg}")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ Import failed: {msg}")
            except Exception as read_err:
                st.error(f"Error reading CSV: {read_err}")

    # --------------------------------------------------------------------------
    # TAB 3: DATABASE TABLES & SCHEMA EXPLORER
    # --------------------------------------------------------------------------
    with dash_tabs[2]:
        st.markdown("#### 🔍 Discovered Database Tables")
        if schemas:
            table_list = [s["table_name"] for s in schemas]
            selected_table = st.selectbox("Select a table to inspect:", table_list, index=0)
            
            selected_meta = next((s for s in schemas if s["table_name"] == selected_table), None)
            if selected_meta:
                st.caption(f"**Description:** {selected_meta.get('description', 'Table')}")
                st.markdown("**Columns:** " + ", ".join([f"`{c}`" for c in selected_meta.get('columns', [])]))

                col_load, col_view = st.columns([1, 1])
                with col_load:
                    if st.button(f"📊 Load '{selected_table}' into Dashboard", use_container_width=True):
                        try:
                            cols_exp, rows_exp = execute_query(engine, f"SELECT * FROM {selected_table} LIMIT 100;")
                            st.session_state["active_df"] = pd.DataFrame(rows_exp, columns=cols_exp)
                            st.session_state["active_table"] = selected_table
                            st.session_state["active_title"] = f"Table View: {selected_table}"
                            st.success(f"Loaded {len(rows_exp)} rows into dashboard!")
                            st.rerun()
                        except Exception as load_err:
                            st.error(f"Error loading table: {load_err}")

                # Preview sample rows
                try:
                    c_prev, r_prev = execute_query(engine, f"SELECT * FROM {selected_table} LIMIT 5;")
                    if r_prev:
                        st.dataframe(pd.DataFrame(r_prev, columns=c_prev), use_container_width=True)
                except Exception:
                    pass
        else:
            st.info("No tables discovered in the connected database.")


# ==============================================================================
# RIGHT COLUMN: CHATGPT-STYLE AI CHATBOT & CHARTING ADVISOR
# ==============================================================================
with col_chat:
    active_tbl_name = st.session_state.get("active_table", "Unknown")
    st.subheader("🤖 AI Copilot (ChatGPT)")
    st.markdown(f'<span class="chat-pill">📌 Active Context: <b>{active_tbl_name}</b></span>', unsafe_allow_html=True)
    st.caption("Answers data questions, recommends chart columns, and writes SQL.")

    # --------------------------------------------------------------------------
    # QUICK CHARTING & QUERY PROMPT CHIPS
    # --------------------------------------------------------------------------
    st.markdown("**💡 Quick Questions:**")
    quick_col1, quick_col2 = st.columns(2)
    with quick_col1:
        if st.button("🥧 Which columns for Pie Chart?", use_container_width=True):
            st.session_state["pending_query"] = f"Tell me which columns to use for a pie chart from {active_tbl_name}"
        if st.button("📊 Which columns for Bar Chart?", use_container_width=True):
            st.session_state["pending_query"] = f"Tell me which columns to use for a bar chart from {active_tbl_name}"
    with quick_col2:
        if st.button("⚡ Average OEE across runs", use_container_width=True):
            st.session_state["pending_query"] = "What is our overall average OEE percentage across all runs?"
        if st.button("📈 Output trend by date", use_container_width=True):
            st.session_state["pending_query"] = "Show daily actual production quantity by run date"

    # --------------------------------------------------------------------------
    # CHAT HISTORY CONTAINER
    # --------------------------------------------------------------------------
    chat_container = st.container(height=480)
    with chat_container:
        for m in st.session_state["messages"]:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
                if m.get("sql"):
                    with st.expander("💻 View SQL Query", expanded=False):
                        st.code(m["sql"], language="sql")

    # --------------------------------------------------------------------------
    # CHAT INPUT
    # --------------------------------------------------------------------------
    chat_input_val = st.chat_input("Ask ChatGPT assistant (e.g. which columns for pie chart?)...")

    # Clear chat button
    col_c1, col_c2 = st.columns([1, 1])
    with col_c2:
        if st.button("🧹 Clear Chat", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()

    # Determine query to process
    active_prompt = None
    if chat_input_val:
        active_prompt = chat_input_val
    elif st.session_state.get("pending_query"):
        active_prompt = st.session_state["pending_query"]
        st.session_state["pending_query"] = None

    # --------------------------------------------------------------------------
    # PROCESS QUERY & GENERATE CHATBOT ANSWER
    # --------------------------------------------------------------------------
    if active_prompt:
        # 1. Append user prompt to history
        st.session_state["messages"].append({
            "role": "user",
            "content": active_prompt
        })

        generator = SQLGenerator()
        is_chat_only = generator.is_conversational_question(active_prompt)

        # Context gathering
        table_context = ""
        active_meta = next((s for s in schemas if s["table_name"] == active_tbl_name), None)
        if active_meta:
            table_context = active_meta.get("document", "")
        else:
            table_context = "\n\n".join(s.get("document", "") for s in schemas[:3])

        # Case A: Conversational or Charting Advice question
        # (e.g. "tell me which columns use for pie chat", "what is oee", "help")
        if is_chat_only:
            with st.spinner("AI Copilot is analyzing your question..."):
                reply = generator.generate_chat_answer(
                    user_question=active_prompt,
                    schema_context=table_context
                )
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": reply
                })
                st.rerun()

        # Case B: Operational database query
        else:
            with st.spinner("Drafting SQL and querying database..."):
                # RAG retrieval
                try:
                    retriever = SchemaRetriever(top_k=3)
                    relevant_schemas = retriever.retrieve_relevant_schemas(active_prompt)
                    schema_prompt_ctx = retriever.format_schemas_for_prompt(relevant_schemas)
                except Exception:
                    schema_prompt_ctx = table_context

                # SQL Generation
                try:
                    gen_sql = generator.generate_sql(active_prompt, schema_prompt_ctx)
                except Exception as g_err:
                    gen_sql = None
                    ai_reply = f"I had difficulty generating SQL for this question: {g_err}. Try asking for specific columns or metrics."

                if gen_sql:
                    is_safe, guard_reason = validate_sql(gen_sql)
                    if not is_safe:
                        ai_reply = f"🛡️ Query was blocked by guardrails: {guard_reason}"
                        st.session_state["messages"].append({
                            "role": "assistant",
                            "content": ai_reply,
                            "sql": gen_sql
                        })
                    else:
                        try:
                            q_cols, q_rows = execute_query(engine, gen_sql)
                            if q_rows:
                                res_df = pd.DataFrame(q_rows, columns=q_cols)
                                
                                # Update Left Side Dashboard with new results!
                                st.session_state["active_df"] = res_df
                                st.session_state["active_title"] = f"Query: {active_prompt}"

                                # Executive conversational answer for the Right Side Chatbot
                                summary_text = res_df.head(10).to_markdown(index=False)
                                ai_reply = generator.generate_chat_answer(
                                    user_question=active_prompt,
                                    schema_context=schema_prompt_ctx,
                                    sql=gen_sql,
                                    data_summary=summary_text
                                )
                                st.session_state["messages"].append({
                                    "role": "assistant",
                                    "content": ai_reply,
                                    "sql": gen_sql
                                })
                            else:
                                ai_reply = f"I ran the query successfully, but it returned **0 records** from the database."
                                st.session_state["messages"].append({
                                    "role": "assistant",
                                    "content": ai_reply,
                                    "sql": gen_sql
                                })
                        except Exception as q_err:
                            ai_reply = f"❌ SQL execution failed: {q_err}"
                            st.session_state["messages"].append({
                                "role": "assistant",
                                "content": ai_reply,
                                "sql": gen_sql
                            })
                else:
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": ai_reply
                    })

                st.rerun()
