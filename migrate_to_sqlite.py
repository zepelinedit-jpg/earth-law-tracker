"""Migrate articles from articles.json to local SQLite.

Run from the project directory:

    python3 migrate_to_sqlite.py

The SQLite database will be written to articles.db in the project directory
(or to SQLITE_PATH if that env var is set).
"""

import json
import os
import sqlite3

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(DATA_DIR, "articles.db"))
JSON_PATH = os.path.join(DATA_DIR, "articles.json")

COLUMNS = [
    "id", "url", "real_url", "title", "title_en",
    "outlet", "outlet_en", "author", "date", "language",
    "search_term", "fetched_date",
]

CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS articles (
        id TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        real_url TEXT,
        title TEXT,
        title_en TEXT,
        outlet TEXT,
        outlet_en TEXT,
        author TEXT DEFAULT '',
        date TEXT,
        language TEXT DEFAULT 'en',
        search_term TEXT,
        fetched_date TEXT
    )
"""

print(f"Reading {JSON_PATH}...")
with open(JSON_PATH) as f:
    articles = json.load(f)
print(f"Loaded {len(articles)} articles from JSON.")

print(f"Writing to SQLite: {SQLITE_PATH}")
sq_conn = sqlite3.connect(SQLITE_PATH)
sq_conn.execute(CREATE_TABLE_SQL)

col_list = ", ".join(COLUMNS)
placeholders = ", ".join("?" * len(COLUMNS))

for a in articles:
    sq_conn.execute(
        f"""INSERT INTO articles ({col_list})
            VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET author = excluded.author""",
        tuple(a.get(c) or "" for c in COLUMNS),
    )

sq_conn.commit()
sq_conn.close()
print(f"Done. {len(articles)} articles written to {SQLITE_PATH}.")
