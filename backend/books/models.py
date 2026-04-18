"""Database models for the Document Intelligence platform."""
from django.db import models


class Book(models.Model):
    """Stores core metadata and content about a scraped book."""

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True, default='Unknown')
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    reviews_count = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, default='')
    book_url = models.URLField(unique=True)
    cover_image_url = models.URLField(blank=True, default='')
    genre = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Model metadata for Book."""

        ordering = ('-created_at',)

    def __str__(self) -> str:
        """Return a readable string representation."""
        return self.title


class AIInsight(models.Model):
    """Stores LLM-generated insight fields for a single book."""

    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name='ai_insight')
    summary = models.TextField()
    genre_classification = models.CharField(max_length=120)
    sentiment = models.CharField(max_length=32)
    sentiment_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Model metadata for AIInsight."""

        ordering = ('-created_at',)

    def __str__(self) -> str:
        """Return a readable string representation."""
        return f"AIInsight<{self.book.title}>"


class BookChunk(models.Model):
    """Represents a chunk of book content mapped to vector storage."""

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='chunks')
    chunk_text = models.TextField()
    chunk_index = models.PositiveIntegerField()
    chroma_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Model metadata for BookChunk."""

        ordering = ('book_id', 'chunk_index')
        unique_together = ('book', 'chunk_index')

    def __str__(self) -> str:
        """Return a readable string representation."""
        return f"Chunk {self.chunk_index} for {self.book.title}"


class ChatHistory(models.Model):
    """Stores RAG question-answer exchanges and supporting sources."""

    question = models.TextField()
    answer = models.TextField()
    sources = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Model metadata for ChatHistory."""

        ordering = ('-created_at',)

    def __str__(self) -> str:
        """Return a readable string representation."""
        return f"ChatHistory<{self.id}>"
