#!/usr/bin/env python3
"""Flask web app to browse Earth law articles."""

import os
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from flask import Flask, render_template, abort
from newspaper import Article as NewsArticle
from deep_translator import GoogleTranslator

from db import load_articles, save_articles, init_db

app = Flask(__name__)


def parse_date(date_str):
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return datetime.min


def translate_text(text, source_lang):
    if source_lang == "en" or not text.strip():
        return text
    try:
        chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
        translated_chunks = []
        for chunk in chunks:
            result = GoogleTranslator(source=source_lang, target="en").translate(chunk)
            translated_chunks.append(result or chunk)
        return "".join(translated_chunks)
    except Exception as e:
        return f"[Translation failed: {e}]\n\n{text}"


def fetch_and_parse_article(url):
    """Download article and extract text and authors."""
    news = NewsArticle(url)
    news.download()
    news.parse()
    return news.text, news.authors


def parse_fetched_date(fetched_str):
    try:
        return datetime.fromisoformat(fetched_str)
    except Exception:
        return datetime.min


@app.route("/")
def index():
    articles = load_articles()
    cutoff = datetime.now(tz=parse_date(articles[0]["date"]).tzinfo if articles else None) - timedelta(days=365)
    articles = [a for a in articles if parse_date(a.get("date", "")) > cutoff]
    articles.sort(key=lambda a: parse_date(a.get("date", "")), reverse=True)

    groups = {}
    for a in articles:
        pd = parse_date(a.get("date", ""))
        label = pd.strftime("%B %Y") if pd != datetime.min else "Unknown"
        groups.setdefault(label, []).append(a)

    grouped_articles = list(groups.items())
    return render_template("index.html", grouped_articles=grouped_articles, total=len(articles))


@app.route("/read/<article_id>")
def read_article(article_id):
    """Fetch article, extract author (cache it), and show full text or translate."""
    articles = load_articles()
    article = next((a for a in articles if a.get("id") == article_id), None)

    if not article:
        abort(404)

    article_url = article.get("real_url") or article["url"]
    try:
        original_text, authors = fetch_and_parse_article(article_url)
    except Exception as e:
        original_text = f"Could not fetch article text: {e}"
        authors = []

    # Cache the author if we found one and it wasn't already saved
    if authors and not article.get("author"):
        article["author"] = ", ".join(authors)
        save_articles(articles)

    lang = article.get("language", "en")

    if lang != "en" and original_text and not original_text.startswith("Could not"):
        translated_text = translate_text(original_text, lang)
    else:
        translated_text = original_text

    return render_template(
        "article.html",
        article=article,
        original_text=original_text,
        translated_text=translated_text,
    )


# Initialize database on startup
with app.app_context():
    init_db()


if __name__ == "__main__":
    print("Starting Earth Law Tracker at http://localhost:5001")
    app.run(host="127.0.0.1", port=5001, debug=False)
