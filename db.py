"""Database layer for Earth Law Tracker.

Uses PostgreSQL when DATABASE_URL is set (production on Render),
falls back to a local JSON file for development.
"""

import json
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
ARTICLES_FILE = os.path.join(DATA_DIR, "articles.json")
DATABASE_URL = os.environ.get("DATABASE_URL")


def _get_pg_conn():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Create the articles table if using PostgreSQL."""
    if not DATABASE_URL:
        return
    conn = _get_pg_conn()
    cur = conn.cursor()
    cur.execute("""
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
    """)
    conn.commit()
    cur.close()
    conn.close()


def load_articles():
    if DATABASE_URL:
        conn = _get_pg_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, url, real_url, title, title_en, outlet, outlet_en, author, date, language, search_term, fetched_date FROM articles")
        columns = ["id", "url", "real_url", "title", "title_en", "outlet", "outlet_en", "author", "date", "language", "search_term", "fetched_date"]
        articles = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return articles
    else:
        if os.path.exists(ARTICLES_FILE):
            with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []


def save_articles(articles):
    if DATABASE_URL:
        conn = _get_pg_conn()
        cur = conn.cursor()
        for a in articles:
            cur.execute("""
                INSERT INTO articles (id, url, real_url, title, title_en, outlet, outlet_en, author, date, language, search_term, fetched_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET author = EXCLUDED.author
            """, (
                a.get("id"), a.get("url"), a.get("real_url"),
                a.get("title"), a.get("title_en"),
                a.get("outlet"), a.get("outlet_en"),
                a.get("author", ""), a.get("date"),
                a.get("language", "en"), a.get("search_term"),
                a.get("fetched_date"),
            ))
        conn.commit()
        cur.close()
        conn.close()
    else:
        with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)


def get_existing_urls():
    if DATABASE_URL:
        conn = _get_pg_conn()
        cur = conn.cursor()
        cur.execute("SELECT url, real_url FROM articles")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        urls = {r[0] for r in rows}
        real_urls = {r[1] for r in rows if r[1]}
        return urls, real_urls
    else:
        articles = load_articles()
        urls = {a["url"] for a in articles}
        real_urls = {a.get("real_url", "") for a in articles if a.get("real_url")}
        return urls, real_urls


def delete_old_articles(cutoff_date_str):
    """Remove articles older than cutoff. For PostgreSQL, delete directly."""
    if DATABASE_URL:
        # For PG, we handle this in the save/cleanup step
        conn = _get_pg_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM articles WHERE date < %s", (cutoff_date_str,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return deleted
    return 0
