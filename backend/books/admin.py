"""Admin registrations for books app models."""
from django.contrib import admin
from .models import AIInsight, Book, BookChunk, ChatHistory


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    """Admin configuration for Book model."""

    list_display = ('id', 'title', 'author', 'rating', 'reviews_count', 'created_at')
    search_fields = ('title', 'author', 'book_url')
    list_filter = ('created_at',)


@admin.register(AIInsight)
class AIInsightAdmin(admin.ModelAdmin):
    """Admin configuration for AIInsight model."""

    list_display = ('id', 'book', 'genre_classification', 'sentiment', 'sentiment_score', 'created_at')
    search_fields = ('book__title', 'genre_classification', 'sentiment')
    list_filter = ('sentiment', 'created_at')


@admin.register(BookChunk)
class BookChunkAdmin(admin.ModelAdmin):
    """Admin configuration for BookChunk model."""

    list_display = ('id', 'book', 'chunk_index', 'chroma_id', 'created_at')
    search_fields = ('book__title', 'chroma_id')
    list_filter = ('created_at',)


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    """Admin configuration for ChatHistory model."""

    list_display = ('id', 'question', 'created_at')
    search_fields = ('question', 'answer')
    list_filter = ('created_at',)
