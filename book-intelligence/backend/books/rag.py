"""RAG pipeline for indexing books and answering questions from retrieved chunks."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from typing import Any

from sentence_transformers import SentenceTransformer

from .llm_client import LLMServiceError, LLMServiceTransientError, chat_completion
from .models import AIInsight, Book
from .vector_store import add_book_chunks, delete_book_chunks, similarity_search

logger = logging.getLogger(__name__)

_CHUNK_SIZE_TOKENS = 300
_CHUNK_OVERLAP_TOKENS = 50
_embedding_model: SentenceTransformer | None = None


class RAGError(Exception):
    """Raised when RAG indexing or querying fails."""


@dataclass(slots=True)
class ChunkReference:
    """Represents a retrieved chunk used as a supporting citation."""

    book_id: int
    title: str
    chunk_index: int
    chroma_id: str
    score: float


def _get_embedding_model() -> SentenceTransformer:
    """Create or reuse local sentence-transformer model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedding_model


def generate_embeddings(text: str) -> list[float]:
    """Generate normalized embedding vector from input text."""
    model = _get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def _compose_book_document(book: Book) -> str:
    """Build the canonical text used for chunking and indexing."""
    summary = ""
    insight: AIInsight | None = getattr(book, "ai_insight", None)
    if insight:
        summary = insight.summary

    return (
        f"Title: {book.title}\n"
        f"Author: {book.author}\n"
        f"Description: {book.description or ''}\n"
        f"Summary: {summary}\n"
    )


def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE_TOKENS, overlap: int = _CHUNK_OVERLAP_TOKENS) -> list[str]:
    """Split text into overlapping word-based chunks approximating token windows."""
    words = text.split()
    if not words:
        return []

    step = max(1, chunk_size - overlap)
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words).strip()
        if chunk_text:
            chunks.append(chunk_text)
        if end >= len(words):
            break
        start += step

    return chunks


def index_book(book: Book) -> dict[str, Any]:
    """Index a single book by chunking content and storing vectors in ChromaDB."""
    delete_book_chunks(book_id=book.id)

    content = _compose_book_document(book=book)
    chunk_texts = _chunk_text(content)
    if not chunk_texts:
        return {
            "book_id": book.id,
            "title": book.title,
            "chunks_indexed": 0,
            "message": "No content available to index.",
        }

    payload: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunk_texts):
        payload.append(
            {
                "chroma_id": f"book-{book.id}-chunk-{idx}",
                "chunk_index": idx,
                "chunk_text": chunk,
                "embedding": generate_embeddings(chunk),
            }
        )

    add_result = add_book_chunks(book_id=book.id, title=book.title, chunks=payload)
    return {
        "book_id": book.id,
        "title": book.title,
        "chunks_indexed": add_result["chunks_added"],
    }


def _build_context(hits: list[dict[str, Any]]) -> str:
    """Construct ranked context block from retrieved chunks."""
    parts: list[str] = []
    for idx, hit in enumerate(hits, start=1):
        parts.append(
            f"[{idx}] Title: {hit['title']} | Book ID: {hit['book_id']} | Chunk: {hit['chunk_index']}\n"
            f"{hit['chunk_text']}"
        )
    return "\n\n".join(parts)


def _call_llm_with_context(question: str, context: str) -> str:
    """Call the configured LLM provider for grounded answering."""
    timeout = int(os.getenv("LM_STUDIO_TIMEOUT_SECONDS", "90"))
    try:
        return chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a retrieval-grounded assistant. "
                        "Return only valid JSON with keys: answer, matched_titles."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Use ONLY the provided context. Do not invent books.\n"
                        "If context is insufficient, answer must be exactly "
                        "\"Insufficient indexed data.\" and matched_titles must be [].\n\n"
                        f"Context:\n{context}\n\nQuestion:\n{question}"
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=280,
            timeout_seconds=timeout,
        )
    except (LLMServiceTransientError, LLMServiceError) as exc:
        logger.exception("RAG LLM request failed")
        raise RAGError(f"LLM request failed: {exc}") from exc


def _parse_structured_answer(raw_text: str, allowed_titles: set[str]) -> tuple[str, list[str]]:
    """Parse model JSON answer and enforce title grounding to retrieved books only."""
    candidate = raw_text.strip()
    if "```" in candidate:
        candidate = candidate.replace("```json", "").replace("```", "").strip()
    if "{" in candidate and "}" in candidate:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]

    try:
        parsed = json.loads(candidate)
        answer = str(parsed.get("answer", "")).strip() or "Insufficient indexed data."
        raw_titles = parsed.get("matched_titles", [])
        titles = [str(item).strip() for item in raw_titles if str(item).strip() in allowed_titles]
        return answer, titles
    except (TypeError, ValueError, json.JSONDecodeError):
        fallback = raw_text.strip() or "Insufficient indexed data."
        if len(fallback) > 700:
            fallback = fallback[:700].rstrip() + "..."
        return fallback, []


def rag_query(question: str) -> dict[str, Any]:
    """Run retrieval-augmented generation for a user question."""
    cleaned_question = question.strip()
    if not cleaned_question:
        raise RAGError("Question cannot be empty.")

    hits = similarity_search(query=cleaned_question, top_k=5)
    if not hits:
        return {
            "answer": "No indexed content is available yet. Index books first, then ask again.",
            "sources": [],
            "chunk_references": [],
        }

    context = _build_context(hits=hits)
    raw_answer = _call_llm_with_context(question=cleaned_question, context=context)

    sources: list[str] = []
    seen_titles: set[str] = set()
    chunk_refs: list[dict[str, Any]] = []

    for hit in hits:
        title = hit["title"]
        if title not in seen_titles:
            seen_titles.add(title)
            sources.append(title)
        chunk_refs.append(
            {
                "book_id": hit["book_id"],
                "title": title,
                "chunk_index": hit["chunk_index"],
                "chroma_id": hit["chroma_id"],
                "score": hit["score"],
            }
        )

    answer, matched_titles = _parse_structured_answer(raw_text=raw_answer, allowed_titles=seen_titles)
    if matched_titles:
        sources = matched_titles

    return {
        "answer": answer,
        "sources": sources,
        "chunk_references": chunk_refs,
    }
