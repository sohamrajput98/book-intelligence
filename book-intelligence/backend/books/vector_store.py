"""ChromaDB vector store integration for book chunk indexing and search."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from django.conf import settings
from sentence_transformers import SentenceTransformer

from .models import BookChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "book_chunks"

_client: chromadb.PersistentClient | None = None
_collection: Collection | None = None
_embedding_model: SentenceTransformer | None = None


@dataclass(slots=True)
class SearchResult:
    """Typed structure for one vector similarity hit."""

    chroma_id: str
    chunk_text: str
    book_id: int
    title: str
    chunk_index: int
    score: float


def _get_chroma_path() -> Path:
    """Return the persistent path used by ChromaDB storage."""
    return Path(settings.BASE_DIR) / "chroma_db"


def _get_client() -> chromadb.PersistentClient:
    """Create or reuse a singleton Chroma persistent client."""
    global _client
    if _client is None:
        path = _get_chroma_path()
        path.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(path))
    return _client


def _get_collection() -> Collection:
    """Create or reuse the configured Chroma collection for book chunks."""
    global _collection
    if _collection is None:
        _collection = _get_client().get_or_create_collection(name=COLLECTION_NAME)
    return _collection


def _get_embedding_model() -> SentenceTransformer:
    """Create or reuse the sentence-transformers embedding model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedding_model


def _embed_text(text: str) -> list[float]:
    """Generate embedding vector for a text input."""
    model = _get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def add_book_chunks(book_id: int, title: str, chunks: list[dict[str, Any]]) -> dict[str, int]:
    """Insert or update book chunks in SQLite and ChromaDB.

    Args:
        book_id: Source book primary key.
        title: Source book title for metadata.
        chunks: List of chunk dictionaries with keys: chroma_id, chunk_index, chunk_text, embedding.

    Returns:
        Count metadata for inserted chunks.
    """
    if not chunks:
        return {"book_id": book_id, "chunks_added": 0}

    collection = _get_collection()

    ids = [str(item["chroma_id"]) for item in chunks]
    documents = [str(item["chunk_text"]) for item in chunks]
    embeddings = [item["embedding"] for item in chunks]
    metadatas = [
        {
            "book_id": int(book_id),
            "title": title,
            "chunk_index": int(item["chunk_index"]),
        }
        for item in chunks
    ]

    collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    BookChunk.objects.filter(book_id=book_id).delete()
    BookChunk.objects.bulk_create(
        [
            BookChunk(
                book_id=book_id,
                chroma_id=str(item["chroma_id"]),
                chunk_index=int(item["chunk_index"]),
                chunk_text=str(item["chunk_text"]),
            )
            for item in chunks
        ],
        batch_size=200,
    )

    return {"book_id": book_id, "chunks_added": len(chunks)}


def similarity_search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Find top similar chunks for a natural-language query string."""
    normalized_top_k = max(1, min(top_k, 20))
    query_embedding = _embed_text(query)
    collection = _get_collection()

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=normalized_top_k,
        include=["metadatas", "documents", "distances"],
    )

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    hits: list[dict[str, Any]] = []
    for idx, chroma_id in enumerate(ids):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        distance = float(distances[idx]) if idx < len(distances) else 1.0
        score = max(0.0, 1.0 - distance)
        hits.append(
            {
                "chroma_id": str(chroma_id),
                "chunk_text": str(documents[idx]) if idx < len(documents) else "",
                "book_id": int(metadata.get("book_id", 0) or 0),
                "title": str(metadata.get("title", "Unknown")),
                "chunk_index": int(metadata.get("chunk_index", 0) or 0),
                "score": score,
            }
        )

    return hits


def delete_book_chunks(book_id: int) -> dict[str, int]:
    """Delete all chunks for a specific book from ChromaDB and SQLite."""
    collection = _get_collection()
    existing_ids = list(BookChunk.objects.filter(book_id=book_id).values_list("chroma_id", flat=True))

    if existing_ids:
        collection.delete(ids=existing_ids)

    deleted_db_count, _ = BookChunk.objects.filter(book_id=book_id).delete()
    return {
        "book_id": book_id,
        "deleted_chroma_ids": len(existing_ids),
        "deleted_db_rows": int(deleted_db_count),
    }
