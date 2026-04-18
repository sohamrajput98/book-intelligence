"""API views for books and Q&A endpoints."""
from __future__ import annotations

import logging

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .ai_insights import AIServiceError, generate_all_book_insights, generate_book_insight
from .models import AIInsight, Book, ChatHistory
from .rag import RAGError, index_book, rag_query
from .scraper import scrape_books
from .serializers import (
    AskQuestionRequestSerializer,
    BookDetailSerializer,
    BookListSerializer,
    ChatHistorySerializer,
    ForceRequestSerializer,
    RecommendationBookSerializer,
    ScrapeRequestSerializer,
)
from .vector_store import similarity_search

logger = logging.getLogger(__name__)


def _ok(data: object, http_status: int = status.HTTP_200_OK) -> Response:
    """Return a standard success envelope."""
    return Response({"success": True, "data": data, "error": None}, status=http_status)


def _fail(message: str, http_status: int) -> Response:
    """Return a standard error envelope."""
    return Response({"success": False, "data": None, "error": message}, status=http_status)


class BookViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Book API endpoints with operational actions for scraping, insights, and indexing."""

    queryset = Book.objects.all().prefetch_related(Prefetch("ai_insight", queryset=AIInsight.objects.all()))

    def get_serializer_class(self):
        """Select serializer by action for list/detail endpoints."""
        if self.action == "retrieve":
            return BookDetailSerializer
        return BookListSerializer

    def list(self, request: Request, *args, **kwargs) -> Response:
        """Return paginated books with nested AI insight data."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        paginated = self.get_paginated_response(serializer.data)
        return _ok(paginated.data, http_status=paginated.status_code)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Return full details for a single book, including chunk count."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return _ok(serializer.data)

    @action(detail=True, methods=["get"], url_path="recommendations")
    def recommendations(self, request: Request, pk: str | None = None) -> Response:
        """Return up to five similar books from vector similarity search."""
        book = self.get_object()
        insight = getattr(book, "ai_insight", None)
        summary = insight.summary if insight else ""
        query = f"{book.title}\n{book.author}\n{book.description}\n{summary}".strip()

        try:
            candidate_ids: list[int] = []
            if query:
                try:
                    hits = similarity_search(query=query, top_k=25)
                    seen: set[int] = set()
                    for hit in hits:
                        book_id = int(hit.get("book_id", 0) or 0)
                        if book_id <= 0 or book_id == book.id or book_id in seen:
                            continue
                        seen.add(book_id)
                        candidate_ids.append(book_id)
                        if len(candidate_ids) == 5:
                            break
                except Exception:
                    logger.exception("Vector recommendation lookup failed for book_id=%s", book.id)

            books = list(Book.objects.filter(id__in=candidate_ids).prefetch_related("ai_insight"))
            books_map = {item.id: item for item in books}
            ordered_books = [books_map[item_id] for item_id in candidate_ids if item_id in books_map]

            if len(ordered_books) < 5:
                # Fallback path when vector retrieval is sparse: same-genre and high-rated books.
                fallback_qs = (
                    Book.objects.exclude(id=book.id)
                    .exclude(id__in=[item.id for item in ordered_books])
                    .order_by("-rating", "-reviews_count", "-created_at")
                )
                if book.genre:
                    genre_books = list(fallback_qs.filter(genre=book.genre)[: 5 - len(ordered_books)])
                    ordered_books.extend(genre_books)
                if len(ordered_books) < 5:
                    generic_books = list(fallback_qs[: 5 - len(ordered_books)])
                    ordered_books.extend(generic_books)

            ordered_books = ordered_books[:5]
            data = RecommendationBookSerializer(ordered_books, many=True).data
            return _ok(data)
        except Exception as exc:
            logger.exception("Failed generating recommendations for book_id=%s", book.id)
            return _fail(f"Failed to generate recommendations: {exc}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["post"], url_path="scrape")
    def scrape(self, request: Request) -> Response:
        """Trigger multi-page scraping with cached URL skipping."""
        serializer = ScrapeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return _fail(str(serializer.errors), status.HTTP_400_BAD_REQUEST)

        try:
            result = scrape_books(pages=serializer.validated_data["pages"])
            return _ok(result)
        except Exception as exc:
            logger.exception("Unhandled scrape endpoint error")
            return _fail(f"Failed to scrape books: {exc}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], url_path="generate-insights")
    def generate_insights(self, request: Request, pk: str | None = None) -> Response:
        """Generate or refresh AI insight for a specific book."""
        force_serializer = ForceRequestSerializer(data=request.data)
        if not force_serializer.is_valid():
            return _fail(str(force_serializer.errors), status.HTTP_400_BAD_REQUEST)

        book = self.get_object()
        force = force_serializer.validated_data.get("force", False)
        try:
            result = generate_book_insight(book=book, force=force)
            return _ok(result)
        except AIServiceError as exc:
            return _fail(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            logger.exception("Unhandled insight generation error for book_id=%s", book.id)
            return _fail(f"Failed to generate insight: {exc}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], url_path="index")
    def index(self, request: Request, pk: str | None = None) -> Response:
        """Index a single book into ChromaDB and BookChunk storage."""
        book = self.get_object()
        try:
            result = index_book(book=book)
            return _ok(result)
        except Exception as exc:
            logger.exception("Unhandled single-book index error for book_id=%s", book.id)
            return _fail(f"Failed to index book: {exc}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["post"], url_path="generate-all-insights")
    def generate_all_insights(self, request: Request) -> Response:
        """Generate AI insights for every book in storage."""
        force_serializer = ForceRequestSerializer(data=request.data)
        if not force_serializer.is_valid():
            return _fail(str(force_serializer.errors), status.HTTP_400_BAD_REQUEST)

        try:
            result = generate_all_book_insights(force=force_serializer.validated_data.get("force", False))
            return _ok(result)
        except Exception as exc:
            logger.exception("Unhandled bulk insight endpoint error")
            return _fail(f"Failed to generate all insights: {exc}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=["post"], url_path="index-all")
    def index_all(self, request: Request) -> Response:
        """Index all books while isolating failures per record."""
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
                logger.exception("Index-all failed for book_id=%s", book.id)
                errors.append({"book_id": str(book.id), "error": str(exc)})

        return _ok(
            {
                "total_books": total,
                "indexed": indexed,
                "failed": failed,
                "errors": errors[:25],
            }
        )


class QAViewSet(viewsets.ViewSet):
    """Q&A API endpoints for asking questions and listing chat history."""

    def ask(self, request: Request) -> Response:
        """Handle a RAG question, return answer, and persist chat history."""
        serializer = AskQuestionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return _fail(str(serializer.errors), status.HTTP_400_BAD_REQUEST)

        question = serializer.validated_data["question"].strip()

        try:
            result = rag_query(question=question)
            history = ChatHistory.objects.create(
                question=question,
                answer=result["answer"],
                sources=result["chunk_references"],
            )
            return _ok(
                {
                    "answer": result["answer"],
                    "sources": result["sources"],
                    "chunk_references": result["chunk_references"],
                    "chat_id": history.id,
                }
            )
        except RAGError as exc:
            return _fail(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            logger.exception("Unhandled QA ask endpoint error")
            return _fail(f"Failed to answer question: {exc}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    def history(self, request: Request) -> Response:
        """Return recent chat history entries in reverse chronological order."""
        limit_raw = request.query_params.get("limit", "50")
        try:
            limit = max(1, min(int(limit_raw), 200))
        except ValueError:
            return _fail("Invalid 'limit' query parameter.", status.HTTP_400_BAD_REQUEST)

        rows = ChatHistory.objects.order_by("-created_at")[:limit]
        data = ChatHistorySerializer(rows, many=True).data
        return _ok(data)

    def clear_history(self, request: Request) -> Response:
        """Delete all chat history records."""
        deleted_count, _ = ChatHistory.objects.all().delete()
        return _ok({"deleted_count": int(deleted_count)})
