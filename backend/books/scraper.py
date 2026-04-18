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

RATING_MAP = {
    "One": Decimal("1.00"),
    "Two": Decimal("2.00"),
    "Three": Decimal("3.00"),
    "Four": Decimal("4.00"),
    "Five": Decimal("5.00"),
}


@dataclass(slots=True)
class ScrapeStats:
    """Structured counters returned to API consumers after scraping."""

    pages_requested: int
    pages_processed: int = 0
    books_found: int = 0
    books_created: int = 0
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


def _parse_detail_page(html: str) -> tuple[str, int]:
    """Parse detail page HTML and return description plus review count if present."""
    soup = BeautifulSoup(html, "html.parser")

    description = ""
    description_anchor = soup.select_one("#product_description")
    if description_anchor:
        description_paragraph = description_anchor.find_next("p")
        if description_paragraph:
            description = description_paragraph.get_text(strip=True)

    reviews_count = 0
    for row in soup.select("table.table.table-striped tr"):
        heading = row.select_one("th")
        value = row.select_one("td")
        if not heading or not value:
            continue
        if heading.get_text(strip=True).lower() == "number of reviews":
            reviews_count = _safe_int(value.get_text(strip=True))
            break

    return description, reviews_count


def _safe_int(raw_value: str) -> int:
    """Parse first positive integer in a string and default to zero."""
    match = re.search(r"\d+", raw_value or "")
    return int(match.group(0)) if match else 0


def scrape_books(pages: int = 5) -> dict[str, Any]:
    """Scrape books from books.toscrape.com with cache-aware inserts.

    Args:
        pages: Number of catalogue pages to scan.

    Returns:
        Dictionary with progress counters and selected errors.
    """
    pages_to_scrape = max(1, min(pages, 100))
    stats = ScrapeStats(pages_requested=pages_to_scrape)
    errors: list[dict[str, str]] = []
    existing_urls = set(Book.objects.values_list("book_url", flat=True))

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
                if detail_url in existing_urls:
                    stats.books_skipped_cached += 1
                    continue

                title = link.get("title", "").strip() or link.get_text(strip=True)
                rating = _extract_rating_from_tag(book_card)
                cover_image_url = ""
                if image and image.get("src"):
                    cover_image_url = urljoin(page_url, image.get("src"))

                try:
                    detail_response = _fetch_page(session=session, url=detail_url)
                    description, reviews_count = _parse_detail_page(detail_response.text)

                    Book.objects.create(
                        title=title,
                        author="Unknown",
                        rating=rating,
                        reviews_count=reviews_count,
                        description=description,
                        book_url=detail_url,
                        cover_image_url=cover_image_url,
                    )
                    existing_urls.add(detail_url)
                    stats.books_created += 1
                except (RequestException, IntegrityError) as exc:
                    stats.books_failed += 1
                    logger.exception("Failed to scrape or store book detail %s", detail_url)
                    errors.append({"book": detail_url, "error": str(exc)})
                    continue
    finally:
        session.close()

    return {
        "message": "Scraping finished.",
        "stats": stats.to_dict(),
        "errors": errors[:25],
    }
