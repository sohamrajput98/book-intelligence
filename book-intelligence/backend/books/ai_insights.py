"""AI insight generation services backed by LM Studio-compatible chat APIs."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from typing import Any

from django.db import transaction
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .llm_client import LLMServiceError, LLMServiceTransientError, chat_completion
from .models import AIInsight, Book

logger = logging.getLogger(__name__)

LM_STUDIO_MAX_RETRIES = max(1, int(os.getenv("LM_STUDIO_MAX_RETRIES", "2")))
LM_STUDIO_MAX_TOKENS = max(120, int(os.getenv("LM_STUDIO_MAX_TOKENS", "220")))

class AIServiceError(Exception):
    """Base exception for AI insight generation failures."""


class AIServiceTransientError(AIServiceError):
    """Transient AI service error that should be retried."""


@dataclass(slots=True)
class InsightPayload:
    """Represents generated insight fields for one book."""

    summary: str
    genre_classification: str
    sentiment: str
    sentiment_score: float


class LMStudioInsightClient:
    """Client for generating insights through an OpenAI-compatible LM Studio API."""

    def __init__(self) -> None:
        """Initialize API endpoint settings and reusable HTTP session."""
        self.timeout = int(os.getenv("LM_STUDIO_TIMEOUT_SECONDS", "45"))

    @retry(
        stop=stop_after_attempt(LM_STUDIO_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        retry=retry_if_exception_type((AIServiceTransientError,)),
        reraise=True,
    )
    def generate_insight_payload(self, book: Book) -> InsightPayload:
        """Generate insight fields for a given book with retry on transient failures."""
        prompt = self._build_prompt(book=book)
        try:
            content = chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise analyst. Return only valid JSON with keys: "
                            "summary, genre_classification, sentiment, sentiment_score."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=LM_STUDIO_MAX_TOKENS,
                timeout_seconds=self.timeout,
            )
        except LLMServiceTransientError as exc:
            raise AIServiceTransientError(str(exc)) from exc
        except LLMServiceError as exc:
            raise AIServiceError(str(exc)) from exc

        parsed = self._parse_json_content(content=content)
        if parsed is None:
            repaired_content = self._repair_to_json(raw_content=content)
            parsed = self._parse_json_content(content=repaired_content)
        if parsed is None:
            raise AIServiceError("AI response was not valid JSON.")
        return InsightPayload(
            summary=parsed["summary"],
            genre_classification=parsed["genre_classification"],
            sentiment=parsed["sentiment"],
            sentiment_score=parsed["sentiment_score"],
        )

    def _build_prompt(self, book: Book) -> str:
        """Build a constrained prompt for summary, genre, and sentiment extraction."""
        description = (book.description or "").strip()
        if not description:
            description = "No description provided. Infer only from title and minimal context."

        return (
            "Analyze the following book metadata and produce JSON output.\n"
            "Rules:\n"
            "1) summary: exactly 3 concise sentences.\n"
            "2) genre_classification: one primary genre label.\n"
            "3) sentiment: one of Positive, Neutral, Negative.\n"
            "4) sentiment_score: numeric between -1 and 1.\n"
            f"Title: {book.title}\n"
            f"Author: {book.author}\n"
            f"Description: {description[:1800]}\\n"
        )

    def _parse_json_content(self, content: str) -> dict[str, Any] | None:
        """Parse and validate JSON content returned by the language model."""
        candidate = content.strip()
        if "```" in candidate:
            candidate = candidate.replace("```json", "").replace("```", "").strip()

        if "{" in candidate and "}" in candidate:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start >= 0 and end > start:
                candidate = candidate[start : end + 1]

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        required = ["summary", "genre_classification", "sentiment", "sentiment_score"]
        for key in required:
            if key not in parsed:
                raise AIServiceError(f"Missing key in AI response: {key}")

        raw_summary = parsed["summary"]
        if isinstance(raw_summary, list):
            summary = " ".join(str(item).strip() for item in raw_summary if str(item).strip())
        elif isinstance(raw_summary, dict):
            summary = " ".join(str(value).strip() for value in raw_summary.values() if str(value).strip())
        else:
            summary = str(raw_summary).strip()
        genre = str(parsed["genre_classification"]).strip()
        sentiment = str(parsed["sentiment"]).strip().title()

        if sentiment not in {"Positive", "Neutral", "Negative"}:
            sentiment = "Neutral"

        try:
            score = float(parsed["sentiment_score"])
        except (TypeError, ValueError) as exc:
            raise AIServiceError("Invalid sentiment_score returned by AI.") from exc

        score = max(-1.0, min(1.0, score))

        return {
            "summary": summary,
            "genre_classification": genre,
            "sentiment": sentiment,
            "sentiment_score": score,
        }

    def _repair_to_json(self, raw_content: str) -> str:
        """Request a strict JSON-only rewrite when the model returns malformed output."""
        try:
            return chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "Convert text into valid JSON only. No extra words.",
                    },
                    {
                        "role": "user",
                        "content": (
                            "Return ONLY valid JSON with keys: summary, genre_classification, "
                            "sentiment, sentiment_score.\n\nText:\n" + raw_content[:2200]
                        ),
                    },
                ],
                temperature=0.0,
                max_tokens=180,
                timeout_seconds=self.timeout,
            )
        except Exception as exc:
            raise AIServiceError(f"Failed to repair AI JSON response: {exc}") from exc


def generate_book_insight(book: Book, force: bool = False) -> dict[str, Any]:
    """Generate and persist insight for one book, honoring cache unless forced."""
    existing = AIInsight.objects.filter(book=book).first()
    if existing and not force:
        return {
            "status": "skipped",
            "reason": "Insight already exists.",
            "book_id": book.id,
            "insight_id": existing.id,
        }

    client = LMStudioInsightClient()
    payload = client.generate_insight_payload(book=book)

    with transaction.atomic():
        insight, created = AIInsight.objects.update_or_create(
            book=book,
            defaults={
                "summary": payload.summary,
                "genre_classification": payload.genre_classification,
                "sentiment": payload.sentiment,
                "sentiment_score": payload.sentiment_score,
            },
        )
        if book.genre != payload.genre_classification:
            book.genre = payload.genre_classification
            book.save(update_fields=["genre"])

    return {
        "status": "created" if created else "updated",
        "book_id": book.id,
        "insight_id": insight.id,
        "summary": insight.summary,
        "genre_classification": insight.genre_classification,
        "sentiment": insight.sentiment,
        "sentiment_score": insight.sentiment_score,
    }


def generate_all_book_insights(force: bool = False) -> dict[str, Any]:
    """Generate insights for all books and return aggregated progress information."""
    total = Book.objects.count()
    processed = 0
    created_or_updated = 0
    skipped = 0
    failed = 0
    errors: list[dict[str, str]] = []

    for book in Book.objects.order_by("id"):
        processed += 1
        try:
            result = generate_book_insight(book=book, force=force)
            if result["status"] == "skipped":
                skipped += 1
            else:
                created_or_updated += 1
        except AIServiceError as exc:
            failed += 1
            logger.exception("Bulk insight generation failed for book_id=%s", book.id)
            errors.append({"book_id": str(book.id), "error": str(exc)})

    return {
        "total_books": total,
        "processed": processed,
        "created_or_updated": created_or_updated,
        "skipped": skipped,
        "failed": failed,
        "errors": errors[:25],
    }

