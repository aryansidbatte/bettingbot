import sqlite3
import sys
import os
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch):
    """Replace the module-level SQLite connection with an in-memory DB for every test."""
    import database

    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    monkeypatch.setattr(database, "conn", conn)
    monkeypatch.setattr(database, "c", c)
    database.setup_db()
    yield conn
    conn.close()
