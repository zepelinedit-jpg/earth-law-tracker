#!/usr/bin/env python3 -u
"""Fetches Earth law articles from Google News RSS feeds."""

import sys
sys.stdout.reconfigure(line_buffering=True)

import hashlib
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import feedparser
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
from googlenewsdecoder import new_decoderv1
from newspaper import Article as NewsArticle

from db import load_articles, save_articles, get_existing_urls, init_db

SEARCH_TERMS = [
    # Rights of Nature
    '"Rights of Nature"',
    '"environmental personhood"',
    '"ecosystem rights"',
    '"ecological personhood"',
    '"nonhuman rights legal"',
    '"derechos de la naturaleza"',
    '"personería ambiental"',
    '"derechos de los ecosistemas"',
    '"personalidad jurídica de la naturaleza"',
    '"derechos de los seres no humanos"',
    '"derechos para la naturaleza"',
    '"personería jurídica de la naturaleza"',
    '"guardianía ambiental"',
    # River rights
    '"river rights"',
    '"rights of rivers"',
    '"derechos de los ríos"',
    '"ríos con derechos"',
    # Earth law
    '"Earth Law Center"',
    '"Earth jurisprudence"',
    '"legal guardianship of nature"',
    '"environmental guardianship"',
    '"derecho de la Tierra"',
    '"jurisprudencia de la Tierra"',
    '"tutela legal de la naturaleza"',
    '"guardianes legales de la naturaleza"',
    # Indigenous environmental rights
    '"Indigenous environmental rights"',
    '"Indigenous land rights"',
    '"free prior informed consent"',
    '"Indigenous environmental justice"',
    '"biocultural rights"',
    '"derechos ambientales indígenas"',
    '"derechos territoriales indígenas"',
    '"consentimiento libre previo e informado"',
    '"justicia ambiental indígena"',
    '"derechos bioculturales"',
    # Ecocide
    '"ecocide"',
    '"ecocidio"',
    # Rights of future generations
    '"rights of future generations"',
    '"derechos de las generaciones futuras"',
    # Right to a healthy environment
    '"right to a healthy environment"',
    '"Green Amendments"',
    '"derecho a un medio ambiente sano"',
    # Bioregionalism
    '"bioregionalism"',
    '"bioregionalismo"',
    '"regionalismo ecológico"',
    '"eco-regionalismo"',
]

GOOGLE_NEWS_RSS_EN = "https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
GOOGLE_NEWS_RSS_ES = "https://news.google.com/rss/search?q={query}&hl=es&gl=ES&ceid=ES:es"


def make_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]


def detect_language(text):
    try:
        lang = detect(text)
        return lang
    except LangDetectException:
        return "en"


def translate_text(text, source_lang):
    if source_lang == "en" or not text.strip():
        return text
    try:
        translated = GoogleTranslator(source=source_lang, target="en").translate(text)
        return translated or text
    except Exception:
        return text


def resolve_google_news_url(google_url):
    """Decode a Google News RSS redirect URL to the real article URL."""
    try:
        result = new_decoderv1(google_url)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception:
        pass
    return google_url


def is_real_author(name):
    """Filter out CSS/HTML junk that newspaper3k sometimes picks up as authors."""
    name = name.strip()
    if not name or len(name) < 2:
        return False
    junk_indicators = [
        '.wp-block', 'display', 'flex', 'margin', 'font-size',
        'border-box', 'padding', 'vertical-align', 'inline',
        'line-height', 'sourceurl', 'style.min.css', 'wp-includes',
        'height auto', 'max-width', '.is-layout', '.alignleft',
        'box-sizing', 'flex-wrap', 'flex-grow', 'flex-basis',
    ]
    lower = name.lower()
    if any(junk in lower for junk in junk_indicators):
        return False
    if len(name) > 60:
        return False
    return True


def extract_author(url):
    """Download article and extract author name(s)."""
    try:
        article = NewsArticle(url)
        article.download()
        article.parse()
        if article.authors:
            clean = [a for a in article.authors if is_real_author(a)]
            if clean:
                return ", ".join(clean[:3])
    except Exception:
        pass
    return ""


def is_spanish_term(term):
    """Return True if the term contains Spanish-specific characters."""
    return any(c in term for c in "áéíóúüñ¿¡ÁÉÍÓÚÜÑ")


def fetch_for_term(term):
    template = GOOGLE_NEWS_RSS_ES if is_spanish_term(term) else GOOGLE_NEWS_RSS_EN
    url = template.format(query=quote(term))
    feed = feedparser.parse(url)
    results = []

    for entry in feed.entries:
        title = entry.get("title", "")
        link = entry.get("link", "")
        published = entry.get("published", "")
        source = entry.get("source", {})
        outlet = source.get("title", "") if isinstance(source, dict) else ""

        if not title or not link:
            continue

        if not outlet and " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0].strip()
            outlet = parts[1].strip()

        results.append({
            "title": title,
            "url": link,
            "outlet": outlet,
            "date": published,
            "search_term": term,
        })

    return results


def main():
    init_db()
    print(f"[{datetime.now().isoformat()}] Fetching Earth law articles...")

    existing_urls, existing_real_urls = get_existing_urls()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=180)

    new_articles = []

    for term in SEARCH_TERMS:
        print(f"  Searching: {term}")
        results = fetch_for_term(term)
        print(f"    Found {len(results)} results")

        for article in results:
            if article["url"] in existing_urls:
                continue

            try:
                pub_date = parsedate_to_datetime(article.get("date", ""))
                if pub_date < cutoff:
                    continue
            except Exception:
                pass

            existing_urls.add(article["url"])

            real_url = resolve_google_news_url(article["url"])
            if real_url in existing_real_urls:
                continue
            existing_real_urls.add(real_url)
            article["real_url"] = real_url

            article["author"] = extract_author(real_url)

            lang = detect_language(article["title"])
            article["id"] = make_id(article["url"])
            article["language"] = lang
            article["fetched_date"] = datetime.now().isoformat()

            if lang != "en":
                article["title_en"] = translate_text(article["title"], lang)
                article["outlet_en"] = translate_text(article["outlet"], lang)
            else:
                article["title_en"] = article["title"]
                article["outlet_en"] = article["outlet"]

            new_articles.append(article)
            if article["author"]:
                print(f"    + {article['title_en'][:60]} — by {article['author']}")
            else:
                print(f"    + {article['title_en'][:60]}")

        time.sleep(1)

    if new_articles:
        save_articles(new_articles)
        print(f"  Added {len(new_articles)} new articles")
    else:
        print("  No new articles found.")

    print("Done.")


if __name__ == "__main__":
    main()
