"""Migrate articles from Render PostgreSQL to local SQLite.

Run this locally with DATABASE_URL set to the Render connection string:

    DATABASE_URL="postgresql://..." python3 migrate_to_sqlite.py

The SQLite database will be written to articles.db in the project directory
(or to SQLITE_PATH if that env var is set).
"""

import os
import sys
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL.startswith("postgresql"):
    sys.exit("ERROR: Set DATABASE_URL to a postgresql:// connection string before running.")

import psycopg2

SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "articles.db"))

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

print(f"Connecting to PostgreSQL...")
pg_conn = psycopg2.connect(DATABASE_URL)
pg_cur = pg_conn.cursor()
pg_cur.execute(f"SELECT {', '.join(COLUMNS)} FROM articles")
rows = pg_cur.fetchall()
pg_cur.close()
pg_conn.close()
print(f"Fetched {len(rows)} articles from PostgreSQL.")

print(f"Writing to SQLite: {SQLITE_PATH}")
sq_conn = sqlite3.connect(SQLITE_PATH)
sq_conn.execute(CREATE_TABLE_SQL)

col_list = ", ".join(COLUMNS)
placeholders = ", ".join("?" * len(COLUMNS))

for row in rows:
    sq_conn.execute(
        f"""INSERT INTO articles ({col_list})
            VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET author = excluded.author""",
        tuple(v or "" for v in row),
    )

sq_conn.commit()
sq_conn.close()
print(f"Done. {len(rows)} articles written to {SQLITE_PATH}.")
