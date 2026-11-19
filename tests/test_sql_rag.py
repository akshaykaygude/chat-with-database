import unittest
import os
import sys

# Ensure src is importable
sys.path.insert(0, os.path.abspath("."))

from src.guardrails import validate_sql
from src.database import get_engine, extract_schema_metadata, execute_query
from src.generator import SQLGenerator


class TestGuardrails(unittest.TestCase):
    """Tests SQL safety guardrail filtering (Strict SELECT-only)."""

    def test_safe_select_query_passes(self):
        sql = "SELECT plant_name, city, max_daily_capacity FROM plants WHERE max_daily_capacity > 1000;"
        is_safe, reason = validate_sql(sql)
        self.assertTrue(is_safe, f"Safe query was blocked: {reason}")

    def test_drop_table_is_blocked(self):
        sql = "DROP TABLE plants;"
        is_safe, reason = validate_sql(sql)
        self.assertFalse(is_safe)
        self.assertIn("DROP", reason.upper())

    def test_delete_statement_is_blocked(self):
        sql = "DELETE FROM production_runs WHERE run_id = 1;"
        is_safe, reason = validate_sql(sql)
        self.assertFalse(is_safe)

    def test_update_statement_is_blocked(self):
        sql = "UPDATE plants SET max_daily_capacity = 9999;"
        is_safe, reason = validate_sql(sql)
        self.assertFalse(is_safe)


class TestDatabaseReflection(unittest.TestCase):
    """Tests SQLite fallback and schema extraction."""

    def setUp(self):
        self.engine = get_engine("manufacturing_db.db")

    def test_engine_connects_successfully(self):
        self.assertIsNotNone(self.engine)
        self.assertTrue(str(self.engine.url).startswith("sqlite"))

    def test_schema_metadata_extraction(self):
        schemas = extract_schema_metadata(self.engine)
        self.assertIsInstance(schemas, list)
        self.assertGreater(len(schemas), 0)
        table_names = [s["table_name"] for s in schemas]
        self.assertIn("plants", table_names)

    def test_query_execution_returns_columns_and_rows(self):
        cols, rows = execute_query(self.engine, "SELECT plant_name, city FROM plants LIMIT 2;")
        self.assertEqual(cols, ["plant_name", "city"])
        self.assertGreater(len(rows), 0)


class TestConversationalRouter(unittest.TestCase):
    """Tests routing between conversational chatting and SQL generation."""

    def setUp(self):
        self.generator = SQLGenerator(token="mock_test_token")

    def test_charting_question_identified_as_conversational(self):
        self.assertTrue(self.generator.is_conversational_question("Which columns should I use for a pie chart?"))
        self.assertTrue(self.generator.is_conversational_question("What columns work best for a bar chart?"))

    def test_greetings_identified_as_conversational(self):
        self.assertTrue(self.generator.is_conversational_question("Hello!"))
        self.assertTrue(self.generator.is_conversational_question("What can you do?"))

    def test_operational_query_routes_to_sql(self):
        self.assertFalse(self.generator.is_conversational_question("Show total actual production quantity by plant location"))


if __name__ == "__main__":
    unittest.main()
