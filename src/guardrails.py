"""
guardrails.py
Validates generated SQL queries to ensure safe, read-only execution.
Blocks data modification statements (DROP, DELETE, UPDATE, INSERT, ALTER, etc.).
"""

import sqlparse
from typing import Tuple

FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", 
    "TRUNCATE", "CREATE", "REPLACE", "GRANT", "REVOKE",
    "EXEC", "EXECUTE", "SHUTDOWN"
}

def validate_sql(sql_query: str) -> Tuple[bool, str]:
    """
    Validates that the provided SQL query is strictly a safe read-only SELECT statement.
    Returns: (is_safe: bool, message: str)
    """
    cleaned = sql_query.strip()
    if not cleaned:
        return False, "Query is empty."

    # Parse query into AST / statements
    parsed = sqlparse.parse(cleaned)
    if not parsed:
        return False, "Could not parse SQL query."

    # Prevent multi-statement injection (e.g. SELECT 1; DROP TABLE orders;)
    if len(parsed) > 1:
        # Check if secondary statements are just comments or empty
        non_empty = [s for s in parsed if str(s).strip().rstrip(";")]
        if len(non_empty) > 1:
            return False, "Multiple SQL statements detected. Only a single SELECT query is permitted."

    stmt = parsed[0]
    stmt_type = stmt.get_type().upper()

    if stmt_type != "SELECT":
        return False, f"Forbidden statement type: '{stmt_type}'. Only SELECT queries are permitted."

    # Inspect all tokens for forbidden commands (e.g. subquery deletes, stored procs)
    for token in stmt.flatten():
        val = token.value.strip().upper()
        if val in FORBIDDEN_KEYWORDS:
            return False, f"Prohibited SQL keyword detected: '{val}'. Only read-only operations are allowed."

    return True, "Valid SELECT query."

if __name__ == "__main__":
    # Test cases
    tests = [
        ("SELECT * FROM orders WHERE total_amount > 1000;", True),
        ("DROP TABLE customers;", False),
        ("SELECT * FROM orders; DELETE FROM customers;", False),
        ("UPDATE products SET unit_price = 0;", False),
    ]

    for q, expected in tests:
        safe, msg = validate_sql(q)
        print(f"Query: {q}\nSafe: {safe} | Reason: {msg}\n")
