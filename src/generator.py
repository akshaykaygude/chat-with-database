"""
generator.py
Generates PostgreSQL-compliant SQL queries using Hugging Face LLM models
via huggingface_hub.InferenceClient.
"""

import os
import re
from typing import Optional
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

DEFAULT_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct")

SYSTEM_PROMPT = """You are an expert PostgreSQL Data Engineer.
Given a user question and the relevant PostgreSQL database schemas, write a valid, optimized, read-only PostgreSQL SELECT query to answer the question.

Rules to follow:
1. ONLY return a valid SQL SELECT statement. Never modify, drop, or alter data.
2. Target SQL Dialect: PostgreSQL.
   - For case-insensitive text search, use the infix ILIKE operator: `column_name ILIKE '%pattern%'`.
     IMPORTANT: ILIKE is an infix OPERATOR, NOT a function! NEVER write `ILIKE(column, pattern)`.
   - Use standard PostgreSQL functions: e.g. DATE_TRUNC('month', order_date), EXTRACT(MONTH FROM ...), COALESCE().
   - Use proper JOIN conditions using primary/foreign keys provided in the schema.
   - If grouping is needed, include all non-aggregated select columns in the GROUP BY clause.
3. Use aliases for table readability (e.g. `orders o JOIN customers c ON o.customer_id = c.customer_id`).
4. Output ONLY the SQL code enclosed in a ```sql ... ``` block. Do not provide conversational filler or explanations before or after.
"""

CHAT_SYSTEM_PROMPT = """You are an intelligent AI Data Analyst, Charting Advisor & Operations Assistant (like ChatGPT).
Your job is to assist users by answering their business, database, charting, and operational questions in fluent, engaging, professional English.

Guidelines:
1. Direct Executive Answer: Begin with a direct, clear answer to the user's question.
2. Charting & Column Recommendations:
   - When asked which columns to use for a chart (such as a Pie Chart, Bar Chart, Line Chart):
     - Identify the exact available columns from the user's active table or schema context.
     - For Pie / Donut Chart:
       * Slice / Label (Category): Recommend a categorical column with 2 to 7 unique values (e.g. department, shift, status, plant_name).
       * Size / Value (Metric): Recommend a numeric column to sum/average (e.g. salary, defect_qty, downtime_mins) or a row count (COUNT).
       * Best Practice: Mention that pie charts work best for 2 to 7 categories; if there are more categories, recommend a Bar Chart instead.
       * Caution: Warn against high-cardinality columns (e.g. employee names, IDs, dates).
     - For Bar Chart: Recommend 1 categorical column for X-axis and 1+ numeric column for Y-axis.
     - For Line Chart: Recommend 1 date/time column for X-axis and numeric metric for Y-axis.
3. Key Insights & Metrics: Highlight notable figures, top/bottom performers, percentages, or trends using markdown bullet points and bold text.
4. Actionable Takeaways: If operational issues are present, suggest practical next steps or root-cause checks.
5. Tone: Helpful, analytical, concise, and executive-ready like ChatGPT.
"""

class SQLGenerator:
    def __init__(self, model_name: Optional[str] = None, token: Optional[str] = None):
        """
        Initializes Hugging Face InferenceClient.
        """
        self.model_name = model_name or os.getenv("HF_MODEL", DEFAULT_MODEL)
        self.token = token or os.getenv("HF_TOKEN")
        
        # Initialize client with optional token
        self.client = InferenceClient(model=self.model_name, token=self.token if self.token else None)

    def is_conversational_question(self, user_question: str) -> bool:
        """
        Detects whether a user prompt is a general conversational question, greeting,
        or charting advice question rather than a direct database query request.
        """
        q = user_question.strip().lower()
        greetings = ["hi", "hello", "hey", "who are you", "what can you do", "help", "good morning", "good evening"]
        if q in greetings or len(q.split()) <= 2 and any(g in q for g in greetings):
            return True
        
        # Charting advice questions (e.g., 'which columns use for pie chat', 'how to plot bar chart')
        chart_keywords = [
            "pie chart", "pie chat", "bar chart", "line chart", "donut chart",
            "which column", "which columns", "what column", "what columns",
            "recommend chart", "best chart", "suggest chart", "visualize",
            "visualization", "how to plot", "plot this", "how to graph"
        ]
        if any(k in q for k in chart_keywords):
            return True

        conceptual_keywords = [
            "what is oee", "what does oee mean", "explain oee",
            "how to use", "how does rag work", "what tables exist", "what tables do you have"
        ]
        if any(k in q for k in conceptual_keywords):
            return True

        return False

    def generate_sql(self, user_question: str, schema_context: str) -> str:
        """
        Calls Hugging Face LLM to translate natural language + schema into SQL.
        """
        prompt = (
            f"Database Schema Context:\n"
            f"{schema_context}\n\n"
            f"User Question: {user_question}\n\n"
            f"SQL Query:"
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        try:
            # Hugging Face chat completion
            response = self.client.chat.completions.create(
                messages=messages,
                max_tokens=500,
                temperature=0.1 # Low temperature for deterministic, accurate SQL
            )
            raw_output = response.choices[0].message.content
            return self._clean_sql(raw_output)
        except Exception as e:
            # Helpful error message if token is missing
            if not self.token or self.token == "your_hf_token_here":
                raise ValueError(
                    f"Hugging Face API call failed: {e}\n"
                    "[!] Please set your free Hugging Face token in .env (HF_TOKEN=hf_...)\n"
                    "    Get one for free at: https://huggingface.co/settings/tokens"
                ) from e
            raise e

    def generate_chat_answer(
        self,
        user_question: str,
        schema_context: str = "",
        sql: Optional[str] = None,
        data_summary: Optional[str] = None
    ) -> str:
        """
        Generates a ChatGPT-style conversational assistant response explaining
        the query findings, metrics, and actionable operational insights.
        """
        if sql and data_summary:
            prompt = (
                f"User Question: {user_question}\n\n"
                f"Executed SQL Query:\n{sql}\n\n"
                f"Database Query Results:\n{data_summary}\n\n"
                f"Please provide an executive summary, key findings with bullet points, "
                f"and operational recommendations answering the user question like an expert AI assistant:"
            )
        else:
            prompt = (
                f"Database / Operational Context:\n{schema_context}\n\n"
                f"User Question: {user_question}\n\n"
                f"Please provide a helpful, friendly, and comprehensive answer to assist the user:"
            )

        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                messages=messages,
                max_tokens=600,
                temperature=0.4
            )
            return response.choices[0].message.content.strip()
        except Exception as err:
            # Smart fallback in case of API rate limit or network issue
            return self._generate_fallback_chat_answer(user_question, sql, data_summary, schema_context)

    def _generate_fallback_chat_answer(
        self,
        user_question: str,
        sql: Optional[str] = None,
        data_summary: Optional[str] = None,
        schema_context: str = ""
    ) -> str:
        """
        Generates a clean rule-based analytical and charting summary if LLM completion is unavailable.
        """
        q = user_question.lower()

        # Charting advice: Pie chart
        if any(w in q for w in ["pie chart", "pie chat", "donut", "pie"]):
            cols = re.findall(r"-\s*([a-zA-Z0-9_]+)", schema_context)
            cat_guess = [c for c in cols if any(k in c.lower() for k in ["dept", "shift", "status", "category", "role", "plant", "city", "type"])]
            num_guess = [c for c in cols if any(k in c.lower() for k in ["salary", "qty", "defect", "cost", "hours", "mins", "count", "amount", "total", "capacity"])]
            
            cat_sample = f"`{cat_guess[0]}`" if cat_guess else "`department` or `shift`"
            num_sample = f"`{num_guess[0]}`" if num_guess else "`total_defects` or `salary`"

            return (
                "### 🥧 Recommended Columns for a Pie / Donut Chart\n\n"
                "To create an effective and easy-to-read pie chart, you need **two columns**:\n\n"
                f"1. **Category / Slice Column (Labels)**: {cat_sample}\n"
                "   - *Rule*: Choose a column with **2 to 7 distinct categories** (e.g. departments, shifts, operational statuses).\n"
                "   - *Avoid*: High-cardinality columns (like unique Employee IDs, serial numbers, or full names) because they crowd the slices.\n\n"
                f"2. **Metric / Value Column (Slice Size)**: {num_sample} or **Row Count (`COUNT(*)`)**\n"
                "   - *Rule*: Must be a numeric aggregate (e.g. Total Output, Defect Count, Downtime Minutes, or Total Salary).\n\n"
                "💡 **Pro Tip**: If your category has **more than 7 values**, a **Bar Chart** is strongly recommended instead so labels don't overlap!"
            )

        # Charting advice: Bar chart
        if any(w in q for w in ["bar chart", "bar graph", "bar"]):
            return (
                "### 📊 Recommended Columns for a Bar Chart\n\n"
                "1. **X-Axis (Categories / Groups)**: Categorical column (e.g., `plant_name`, `department`, `shift`, `issue_category`).\n"
                "2. **Y-Axis (Metrics / Measures)**: One or more numeric columns (e.g., `actual_qty`, `defect_qty`, `salary`, `repair_cost`).\n\n"
                "💡 **Pro Tip**: Bar charts are ideal for ranking, comparing performance, and seeing differences across groups!"
            )

        # Charting advice: Line chart
        if any(w in q for w in ["line chart", "trend", "time series"]):
            return (
                "### 📈 Recommended Columns for a Line Chart\n\n"
                "1. **X-Axis (Time / Sequence)**: Date or timestamp column (e.g., `run_date`, `maintenance_date`, `month`).\n"
                "2. **Y-Axis (Trend Metric)**: Numeric continuous metric (e.g., `actual_qty`, `oee_pct`, `downtime_mins`).\n\n"
                "💡 **Pro Tip**: Line charts reveal patterns, seasonal cycles, and trends over time."
            )

        if not data_summary or not sql:
            return (
                "👋 **Hello! I am your AI Data Assistant & Charting Advisor.**\n\n"
                "I can assist you like ChatGPT: ask me which columns to use for charts, "
                "ask me to write and execute SQL queries, or ask conceptual questions about your data!"
            )
        
        return (
            f"### 📋 Executive Summary\n"
            f"Here are the findings based on your query *'{user_question}'*:\n\n"
            f"**Query Results Highlights:**\n"
            f"```\n{data_summary[:500]}\n```\n\n"
            f"- **Data Retrieval**: Successfully retrieved relevant operational records.\n"
            f"- **Recommendation**: Review the visualized charts below for deeper distribution and time-series patterns."
        )

    def _clean_sql(self, text: str) -> str:
        """
        Extracts SQL code from markdown code fences if present,
        and auto-repairs common LLM syntax bugs (such as ILIKE(col, pattern)).
        """
        # Search for ```sql ... ```
        sql_match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if sql_match:
            sql = sql_match.group(1).strip()
        else:
            sql = text.strip()

        # Fix function-style ILIKE / LIKE: ILIKE(col, '%val%') -> col ILIKE '%val%'
        # Handles: ILIKE(e.employee_name, '%akash%') -> e.employee_name ILIKE '%akash%'
        sql = re.sub(
            r"\bNOT\s+ILIKE\s*\(\s*([^,]+?)\s*,\s*('[^']+'|\"[^\"]+\"|[^)]+?)\s*\)",
            r"\1 NOT ILIKE \2",
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r"\bILIKE\s*\(\s*([^,]+?)\s*,\s*('[^']+'|\"[^\"]+\"|[^)]+?)\s*\)",
            r"\1 ILIKE \2",
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r"\bLIKE\s*\(\s*([^,]+?)\s*,\s*('[^']+'|\"[^\"]+\"|[^)]+?)\s*\)",
            r"\1 LIKE \2",
            sql,
            flags=re.IGNORECASE
        )

        # Remove trailing semicolons or commentary
        sql = sql.rstrip(";") + ";"
        return sql

if __name__ == "__main__":
    generator = SQLGenerator()
    test_schema = (
        "Table: regions (region_id, region_name)\n"
        "Table: orders (order_id, customer_id, total_amount, order_date)"
    )
    test_q = "What is the total revenue for all orders?"
    print(f"Testing generator with prompt: '{test_q}'...")
    try:
        sql = generator.generate_sql(test_q, test_schema)
        print("Generated SQL:\n", sql)
    except Exception as err:
        print(f"Error: {err}")
