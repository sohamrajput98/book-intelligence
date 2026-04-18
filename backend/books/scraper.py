"""Scraping utilities for importing books from books.toscrape.com."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from django.db import IntegrityError
from requests import Response, Session
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

from .models import Book

logger = logging.getLogger(__name__)

BASE_SITE_URL = "https://books.toscrape.com/"
CATALOG_PAGE_URL = "https://books.toscrape.com/catalogue/page-{page}.html"
OPENLIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"

RATING_MAP = {
    "One": Decimal("1.00"),
    "Two": Decimal("2.00"),
    "Three": Decimal("3.00"),
    "Four": Decimal("4.00"),
    "Five": Decimal("5.00"),
}

_MOJIBAKE_MARKERS = ("â€", "â€™", "â€œ", "â€", "Ã", "�")


@dataclass(slots=True)
class ScrapeStats:
    """Structured counters returned to API consumers after scraping."""

    pages_requested: int
    pages_processed: int = 0
    books_found: int = 0
    books_created: int = 0
    books_updated: int = 0
    books_skipped_cached: int = 0
    books_failed: int = 0
    failed_pages: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert counters into a serializable dictionary."""
        return {
            "pages_requested": self.pages_requested,
            "pages_processed": self.pages_processed,
            "books_found": self.books_found,
            "books_created": self.books_created,
            "books_updated": self.books_updated,
            "books_skipped_cached": self.books_skipped_cached,
            "books_failed": self.books_failed,
            "failed_pages": self.failed_pages,
        }


def _build_session() -> Session:
    """Create an HTTP session with retry behavior for transient network issues."""
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "book-intelligence-scraper/1.0"})
    return session


def _fetch_page(session: Session, url: str, timeout: int = 20) -> Response:
    """Fetch a web page and raise if the response is not successful."""
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    # books.toscrape is utf-8; enforce to avoid mojibake artifacts.
    response.encoding = "utf-8"
    return response


def _extract_rating_from_tag(article_tag: Any) -> Decimal | None:
    """Extract normalized rating from a product card tag."""
    class_names = article_tag.select_one("p.star-rating")
    if not class_names:
        return None
    for class_name in class_names.get("class", []):
        if class_name in RATING_MAP:
            return RATING_MAP[class_name]
    return None


def _safe_int(raw_value: str) -> int:
    """Parse first positive integer in a string and default to zero."""
    match = re.search(r"\d+", raw_value or "")
    return int(match.group(0)) if match else 0


def _contains_mojibake(text: str) -> bool:
    """Detect common mojibake markers in text payloads."""
    return any(marker in (text or "") for marker in _MOJIBAKE_MARKERS)


def _repair_mojibake(text: str) -> str:
    """Attempt lightweight mojibake repair for latin1-decoded utf-8 text."""
    value = (text or "").strip()
    if not value:
        return ""
    if not _contains_mojibake(value):
        return value

    try:
        repaired = value.encode("latin1", errors="ignore").decode("utf-8", errors="ignore").strip()
        if repaired:
            value = repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        logger.debug("Mojibake repair fallback used")

    return value


def _clean_text(text: str) -> str:
    """Normalize whitespace and attempt character encoding repair."""
    cleaned = _repair_mojibake(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _lookup_author_by_title(session: Session, title: str, cache: dict[str, str | None]) -> str | None:
    """Try resolving author via Open Library using the book title."""
    normalized = title.strip().lower()
    if not normalized:
        return None

    if normalized in cache:
        return cache[normalized]

    try:
        response = session.get(
            OPENLIBRARY_SEARCH_URL,
            params={"title": title, "limit": 1, "fields": "author_name"},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        docs = payload.get("docs", []) if isinstance(payload, dict) else []
        if docs and isinstance(docs[0], dict):
            author_names = docs[0].get("author_name", [])
            if isinstance(author_names, list) and author_names:
                author = _clean_text(str(author_names[0]))
                if author:
                    cache[normalized] = author
                    return author
    except Exception as exc:
        logger.debug("OpenLibrary author lookup failed for title='%s': %s", title, exc)

    cache[normalized] = None
    return None


def _parse_detail_page(html: str) -> tuple[str, int, str]:
    """Parse detail page HTML and return description, review count, and author if present."""
    soup = BeautifulSoup(html, "html.parser")

    description = ""
    description_anchor = soup.select_one("#product_description")
    if description_anchor:
        description_paragraph = description_anchor.find_next("p")
        if description_paragraph:
            description = _clean_text(description_paragraph.get_text(" ", strip=True))

    reviews_count = 0
    author = ""
    for row in soup.select("table.table.table-striped tr"):
        heading = row.select_one("th")
        value = row.select_one("td")
        if not heading or not value:
            continue

        key = heading.get_text(strip=True).lower()
        raw_value = value.get_text(" ", strip=True)

        if key == "number of reviews":
            reviews_count = _safe_int(raw_value)
        elif key == "author":
            author = _clean_text(raw_value)

    return description, reviews_count, author


def _needs_cached_refresh(book: Book) -> bool:
    """Determine whether a cached book should be refreshed."""
    author = (book.author or "").strip().lower()
    author_missing = author in {"", "unknown", "author unavailable"}
    bad_description = _contains_mojibake(book.description or "")
    return author_missing or bad_description


def scrape_books(pages: int = 5) -> dict[str, Any]:
    """Scrape books from books.toscrape.com with cache-aware inserts and safe refreshes.

    Args:
        pages: Number of catalogue pages to scan.

    Returns:
        Dictionary with progress counters and selected errors.
    """
    pages_to_scrape = max(1, min(pages, 100))
    stats = ScrapeStats(pages_requested=pages_to_scrape)
    errors: list[dict[str, str]] = []

    existing_books = {book.book_url: book for book in Book.objects.all()}
    author_cache: dict[str, str | None] = {}

    session = _build_session()

    try:
        for page_number in range(1, pages_to_scrape + 1):
            page_url = CATALOG_PAGE_URL.format(page=page_number)
            try:
                page_response = _fetch_page(session=session, url=page_url)
            except RequestException as exc:
                stats.failed_pages += 1
                logger.exception("Failed to fetch catalogue page %s", page_url)
                errors.append({"page": page_url, "error": str(exc)})
                continue

            stats.pages_processed += 1
            page_soup = BeautifulSoup(page_response.text, "html.parser")
            book_cards = page_soup.select("article.product_pod")

            for book_card in book_cards:
                stats.books_found += 1
                link = book_card.select_one("h3 a")
                image = book_card.select_one("img")

                if not link:
                    stats.books_failed += 1
                    logger.warning("Book card missing link on page %s", page_url)
                    continue

                detail_url = urljoin(page_url, link.get("href", ""))
                title = _clean_text(link.get("title", "").strip() or link.get_text(" ", strip=True))
                rating = _extract_rating_from_tag(book_card)
                cover_image_url = ""
                if image and image.get("src"):
                    cover_image_url = urljoin(page_url, image.get("src"))

                existing_book = existing_books.get(detail_url)
                if existing_book and not _needs_cached_refresh(existing_book):
                    stats.books_skipped_cached += 1
                    continue

                try:
                    detail_response = _fetch_page(session=session, url=detail_url)
                    description, reviews_count, author_from_detail = _parse_detail_page(detail_response.text)
                    resolved_author = author_from_detail or _lookup_author_by_title(session, title, author_cache) or "Author unavailable"

                    if existing_book:
                        fields_to_update: list[str] = []

                        if title and existing_book.title != title:
                            existing_book.title = title
                            fields_to_update.append("title")
                        if existing_book.author != resolved_author:
                            existing_book.author = resolved_author
                            fields_to_update.append("author")
                        if existing_book.rating != rating:
                            existing_book.rating = rating
                            fields_to_update.append("rating")
                        if existing_book.reviews_count != reviews_count:
                            existing_book.reviews_count = reviews_count
                            fields_to_update.append("reviews_count")
                        if description and existing_book.description != description:
                            existing_book.description = description
                            fields_to_update.append("description")
                        if cover_image_url and existing_book.cover_image_url != cover_image_url:
                            existing_book.cover_image_url = cover_image_url
                            fields_to_update.append("cover_image_url")

                        if fields_to_update:
                            existing_book.save(update_fields=fields_to_update)
                            stats.books_updated += 1
                        else:
                            stats.books_skipped_cached += 1
                        continue

                    book = Book.objects.create(
                        title=title,
                        author=resolved_author,
                        rating=rating,
                        reviews_count=reviews_count,
                        description=description,
                        book_url=detail_url,
                        cover_image_url=cover_image_url,
                    )
                    existing_books[detail_url] = book
                    stats.books_created += 1
                except (RequestException, IntegrityError) as exc:
                    stats.books_failed += 1
                    logger.exception("Failed to scrape or store book detail %s", detail_url)
                    errors.append({"book": detail_url, "error": str(exc)})
                    continue
                except Exception as exc:
                    stats.books_failed += 1
                    logger.exception("Unexpected scrape processing error for %s", detail_url)
                    errors.append({"book": detail_url, "error": str(exc)})
                    continue
    finally:
        session.close()

    return {
        "message": "Scraping finished.",
        "stats": stats.to_dict(),
        "errors": errors[:25],
    }
