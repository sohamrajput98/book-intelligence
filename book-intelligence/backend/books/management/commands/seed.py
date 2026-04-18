"""Custom Django management command to seed the full Book Intelligence pipeline."""
from __future__ import annotations

import json
import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from books.ai_insights import generate_all_book_insights
from books.models import Book
from books.rag import index_book
from books.scraper import scrape_books

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Seed command: scrape books, generate insights, and index all content."""

    help = "Run full seed pipeline: scrape books, generate insights, and index all books."

    def add_arguments(self, parser) -> None:
        """Define command-line arguments for seed behavior."""
        parser.add_argument(
            "--pages",
            type=int,
            default=5,
            help="Number of catalogue pages to scrape from books.toscrape.com (default: 5).",
        )
        parser.add_argument(
            "--force-insights",
            action="store_true",
            help="Regenerate insights even when cached insights already exist.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute pipeline stages and print summarized progress."""
        pages = max(1, int(options["pages"]))
        force_insights = bool(options["force_insights"])

        try:
            self.stdout.write(self.style.NOTICE(f"[1/3] Scraping books (pages={pages})..."))
            scrape_result = scrape_books(pages=pages)
            self.stdout.write(self.style.SUCCESS("Scraping complete."))
            self.stdout.write(json.dumps(scrape_result, indent=2))

            self.stdout.write(
                self.style.NOTICE(
                    f"[2/3] Generating AI insights (force={str(force_insights).lower()})..."
                )
            )
            insights_result = generate_all_book_insights(force=force_insights)
            self.stdout.write(self.style.SUCCESS("Insight generation complete."))
            self.stdout.write(json.dumps(insights_result, indent=2))

            self.stdout.write(self.style.NOTICE("[3/3] Indexing all books into vector store..."))
            total = Book.objects.count()
            indexed = 0
            failed = 0
            errors: list[dict[str, str]] = []

            for book in Book.objects.order_by("id"):
                try:
                    index_book(book=book)
                    indexed += 1
                except Exception as exc:
                    failed += 1
                    logger.exception("Seed indexing failed for book_id=%s", book.id)
                    errors.append({"book_id": str(book.id), "error": str(exc)})

            index_result = {
                "total_books": total,
                "indexed": indexed,
                "failed": failed,
                "errors": errors[:25],
            }
            self.stdout.write(self.style.SUCCESS("Indexing complete."))
            self.stdout.write(json.dumps(index_result, indent=2))

            if failed > 0:
                self.stdout.write(self.style.WARNING("Seed pipeline completed with partial indexing failures."))
            else:
                self.stdout.write(self.style.SUCCESS("Seed pipeline completed successfully."))
        except Exception as exc:
            logger.exception("Seed command failed")
            raise CommandError(f"Seed pipeline failed: {exc}") from exc
