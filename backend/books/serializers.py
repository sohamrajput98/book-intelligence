"""Serializers for books, insights, chunk metadata, and Q&A payloads."""
from __future__ import annotations

from rest_framework import serializers

from .models import AIInsight, Book, ChatHistory


class AIInsightSerializer(serializers.ModelSerializer):
    """Serialize AI-generated insights for a single book."""

    class Meta:
        """Serializer metadata."""

        model = AIInsight
        fields = (
            "id",
            "summary",
            "genre_classification",
            "sentiment",
            "sentiment_score",
            "created_at",
        )


class BookListSerializer(serializers.ModelSerializer):
    """Serialize paginated book list payload with nested insight."""

    ai_insight = AIInsightSerializer(read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Book
        fields = (
            "id",
            "title",
            "author",
            "rating",
            "reviews_count",
            "cover_image_url",
            "genre",
            "created_at",
            "ai_insight",
        )


class BookDetailSerializer(serializers.ModelSerializer):
    """Serialize detailed book payload including chunk count."""

    ai_insight = AIInsightSerializer(read_only=True)
    chunks_count = serializers.SerializerMethodField()

    class Meta:
        """Serializer metadata."""

        model = Book
        fields = (
            "id",
            "title",
            "author",
            "rating",
            "reviews_count",
            "description",
            "book_url",
            "cover_image_url",
            "genre",
            "created_at",
            "ai_insight",
            "chunks_count",
        )

    def get_chunks_count(self, obj: Book) -> int:
        """Return number of indexed chunks attached to the book."""
        return obj.chunks.count()


class RecommendationBookSerializer(serializers.ModelSerializer):
    """Serialize recommendation card payload."""

    ai_insight = AIInsightSerializer(read_only=True)

    class Meta:
        """Serializer metadata."""

        model = Book
        fields = ("id", "title", "author", "rating", "cover_image_url", "genre", "ai_insight")


class ScrapeRequestSerializer(serializers.Serializer):
    """Validate scrape trigger input payload."""

    pages = serializers.IntegerField(required=False, min_value=1, default=5)


class ForceRequestSerializer(serializers.Serializer):
    """Validate optional force-toggle input payload."""

    force = serializers.BooleanField(required=False, default=False)


class AskQuestionRequestSerializer(serializers.Serializer):
    """Validate Q&A query payload."""

    question = serializers.CharField(required=True, allow_blank=False, max_length=4000)


class ChatHistorySerializer(serializers.ModelSerializer):
    """Serialize Q&A history records."""

    class Meta:
        """Serializer metadata."""

        model = ChatHistory
        fields = ("id", "question", "answer", "sources", "created_at")
