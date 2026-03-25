"""Database layer for Earth Law Tracker.

Uses SQLite by default (articles.db in the project directory).
Falls back to PostgreSQL if DATABASE_URL is set to a postgresql:// URL.
"""

import os
import sqlite3

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(DATA_DIR, "articles.db"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")

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


def _use_postgres():
    return DATABASE_URL.startswith("postgresql")


def _get_pg_conn():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def _get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if _use_postgres():
        conn = _get_pg_conn()
        cur = conn.cursor()
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = _get_sqlite_conn()
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
        conn.close()


def load_articles():
    if _use_postgres():
        conn = _get_pg_conn()
        cur = conn.cursor()
        cur.execute(f"SELECT {', '.join(COLUMNS)} FROM articles")
        articles = [dict(zip(COLUMNS, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
    else:
        conn = _get_sqlite_conn()
        cur = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM articles")
        articles = [dict(row) for row in cur.fetchall()]
        conn.close()
    return articles


def save_articles(articles):
    placeholders = ", ".join("?" * len(COLUMNS))
    col_list = ", ".join(COLUMNS)

    if _use_postgres():
        pg_placeholders = ", ".join(f"%s" for _ in COLUMNS)
        conn = _get_pg_conn()
        cur = conn.cursor()
        for a in articles:
            cur.execute(
                f"""INSERT INTO articles ({col_list})
                    VALUES ({pg_placeholders})
                    ON CONFLICT (id) DO UPDATE SET author = EXCLUDED.author""",
                tuple(a.get(c) or "" for c in COLUMNS),
            )
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = _get_sqlite_conn()
        for a in articles:
            conn.execute(
                f"""INSERT INTO articles ({col_list})
                    VALUES ({placeholders})
                    ON CONFLICT(id) DO UPDATE SET author = excluded.author""",
                tuple(a.get(c) or "" for c in COLUMNS),
            )
        conn.commit()
        conn.close()


def get_existing_urls():
    if _use_postgres():
        conn = _get_pg_conn()
        cur = conn.cursor()
        cur.execute("SELECT url, real_url FROM articles")
        rows = cur.fetchall()
        cur.close()
        conn.close()
    else:
        conn = _get_sqlite_conn()
        rows = conn.execute("SELECT url, real_url FROM articles").fetchall()
        conn.close()
    urls = {r[0] for r in rows}
    real_urls = {r[1] for r in rows if r[1]}
    return urls, real_urls


def delete_old_articles(cutoff_date_str):
    if _use_postgres():
        conn = _get_pg_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM articles WHERE date < %s", (cutoff_date_str,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = _get_sqlite_conn()
        cur = conn.execute("DELETE FROM articles WHERE date < ?", (cutoff_date_str,))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
    return deleted
