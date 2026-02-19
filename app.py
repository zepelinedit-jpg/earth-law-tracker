#!/usr/bin/env python3
"""Flask web app to browse Earth law articles."""

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from flask import Flask, render_template, abort, request
from newspaper import Article as NewsArticle
from deep_translator import GoogleTranslator

from db import load_articles, save_articles, init_db

app = Flask(__name__)

SEARCH_TERMS = [
    '"Rights of Nature"',
    '"environmental personhood"',
    '"ecosystem rights"',
    '"ecological personhood"',
    '"nonhuman rights legal"',
    '"river rights"',
    '"rights of rivers"',
    '"Earth law"',
    '"Earth jurisprudence"',
    '"legal guardianship of nature"',
    '"environmental guardianship"',
    '"Indigenous environmental rights"',
    '"Indigenous land rights"',
    '"free prior informed consent"',
    '"Indigenous environmental justice"',
    '"biocultural rights"',
    '"ecocide"',
    '"rights of future generations"',
    '"right to a healthy environment"',
    '"Green Amendments"',
    '"bioregionalism"',
]


def format_date(date_str):
    try:
        return parsedate_to_datetime(date_str).strftime("%b %d, %Y")
    except Exception:
        return date_str


app.jinja_env.filters["format_date"] = format_date


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


# Maps non-canonical search terms to the canonical term they display under.
# Search terms and DB records are unchanged; this only affects tile grouping.
TAG_CONSOLIDATION = {
    # Rights of Nature tile
    '"environmental personhood"':         '"Rights of Nature"',
    '"ecosystem rights"':                 '"Rights of Nature"',
    '"ecological personhood"':            '"Rights of Nature"',
    '"nonhuman rights legal"':            '"Rights of Nature"',
    # River rights tile
    '"rights of rivers"':                 '"river rights"',
    # Earth law tile
    '"Earth jurisprudence"':              '"Earth law"',
    '"legal guardianship of nature"':     '"Earth law"',
    '"environmental guardianship"':       '"Earth law"',
    # Indigenous environmental rights tile
    '"Indigenous land rights"':           '"Indigenous environmental rights"',
    '"free prior informed consent"':      '"Indigenous environmental rights"',
    '"Indigenous environmental justice"': '"Indigenous environmental rights"',
    '"biocultural rights"':               '"Indigenous environmental rights"',
    # Right to a healthy environment tile
    '"Green Amendments"':                 '"right to a healthy environment"',
}


def canonical_tag(search_term):
    """Return the canonical search term this term consolidates into."""
    return TAG_CONSOLIDATION.get(search_term, search_term)


def tag_display_name(search_term):
    name = search_term.strip('"').strip("'")
    return name[0].upper() + name[1:] if name else name


def tag_slug(search_term):
    name = tag_display_name(search_term).lower()
    slug = re.sub(r"[^\w\s-]", "", name)
    return re.sub(r"[\s_]+", "-", slug).strip("-")


def build_tag_tiles(articles):
    by_tag = defaultdict(list)
    for a in articles:
        by_tag[canonical_tag(a["search_term"])].append(a)

    # Ensure every canonical term gets a tile, even if no articles yet
    canonical_terms = set(SEARCH_TERMS) - set(TAG_CONSOLIDATION.keys())
    for term in canonical_terms:
        by_tag.setdefault(term, [])

    tiles = []
    for term, arts in by_tag.items():
        arts_sorted = sorted(arts, key=lambda a: parse_date(a.get("date", "")), reverse=True)
        tiles.append({
            "search_term": term,
            "name": tag_display_name(term),
            "slug": tag_slug(term),
            "count": len(arts_sorted),
            "articles": arts_sorted,
        })
    # Tiles with articles sort by most-recent; empty tiles go to the end
    _epoch = parse_date("Thu, 01 Jan 1970 00:00:00 +0000")
    tiles.sort(key=lambda t: parse_date(t["articles"][0].get("date", "")) if t["articles"] else _epoch, reverse=True)
    return tiles


def _safe_json(obj):
    """Serialize to JSON and escape </script> sequences for safe embedding in HTML."""
    return json.dumps(obj, ensure_ascii=False).replace("</", r"<\/")


@app.route("/")
def index():
    articles = load_articles()
    tiles = build_tag_tiles(articles)

    search_data = _safe_json([
        {
            "title": a.get("title_en") or a.get("title"),
            "outlet": a.get("outlet_en") or a.get("outlet"),
            "date": a.get("date", ""),
            "tag_name": tag_display_name(canonical_tag(a.get("search_term", ""))),
            "tag_slug": tag_slug(canonical_tag(a.get("search_term", ""))),
            "url": a.get("real_url") or a.get("url"),
            "language": a.get("language", "en"),
            "article_id": a.get("id"),
        }
        for a in articles
    ])

    tile_data = _safe_json({
        t["slug"]: {
            "name": t["name"],
            "articles": [
                {
                    "title": a.get("title_en") or a.get("title"),
                    "outlet": a.get("outlet_en") or a.get("outlet"),
                    "date": a.get("date", ""),
                    "url": a.get("real_url") or a.get("url"),
                    "language": a.get("language", "en"),
                    "article_id": a.get("id"),
                }
                for a in t["articles"]
            ],
        }
        for t in tiles
    })

    return render_template("index.html", tiles=tiles, search_data=search_data, tile_data=tile_data)


@app.route("/all")
def all_articles():
    articles = load_articles()
    q = request.args.get("q", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 50

    articles.sort(key=lambda a: parse_date(a.get("date", "")), reverse=True)

    if q:
        q_lower = q.lower()
        articles = [
            a for a in articles
            if q_lower in (a.get("title_en") or a.get("title") or "").lower()
            or q_lower in (a.get("outlet_en") or a.get("outlet") or "").lower()
            or q_lower in tag_display_name(a.get("search_term", "")).lower()
        ]

    total = len(articles)
    total_pages = max(1, -(-total // per_page))
    page = min(page, total_pages)
    start = (page - 1) * per_page
    # Note: dicts are fresh from load_articles() each request, safe to mutate
    page_articles = articles[start:start + per_page]
    for a in page_articles:
        a["_tag_name"] = tag_display_name(canonical_tag(a.get("search_term", "")))
        a["_tag_slug"] = tag_slug(canonical_tag(a.get("search_term", "")))

    return render_template("all.html", articles=page_articles, total=total,
                           page=page, total_pages=total_pages, q=q)


@app.route("/tag/<slug>")
def tag_view(slug):
    articles = load_articles()

    # Only canonical tags have valid pages; resolve slug → canonical term
    matched_term = None
    for a in articles:
        ct = canonical_tag(a.get("search_term", ""))
        if tag_slug(ct) == slug and ct == canonical_tag(ct):
            matched_term = ct
            break

    if matched_term is None:
        for term in SEARCH_TERMS:
            ct = canonical_tag(term)
            if tag_slug(ct) == slug and ct == term:
                matched_term = term
                break

    if matched_term is None:
        abort(404)

    # Include articles from all terms that consolidate into this canonical term
    tag_articles = [a for a in articles if canonical_tag(a.get("search_term", "")) == matched_term]
    tag_articles.sort(key=lambda a: parse_date(a.get("date", "")), reverse=True)

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 50
    total = len(tag_articles)
    total_pages = max(1, -(-total // per_page))
    page = min(page, total_pages)
    start = (page - 1) * per_page
    page_articles = tag_articles[start:start + per_page]

    return render_template("tag.html", articles=page_articles,
                           tag_name=tag_display_name(matched_term),
                           tag_slug=slug, total=total,
                           page=page, total_pages=total_pages)


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
