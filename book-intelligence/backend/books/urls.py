"""URL declarations for books app endpoints."""
from django.urls import path

from .views import BookViewSet, QAViewSet

book_list = BookViewSet.as_view({"get": "list"})
book_detail = BookViewSet.as_view({"get": "retrieve"})
book_recommendations = BookViewSet.as_view({"get": "recommendations"})
books_scrape = BookViewSet.as_view({"post": "scrape"})
book_generate_insights = BookViewSet.as_view({"post": "generate_insights"})
book_index = BookViewSet.as_view({"post": "index"})
books_generate_all_insights = BookViewSet.as_view({"post": "generate_all_insights"})
books_index_all = BookViewSet.as_view({"post": "index_all"})
qa_ask = QAViewSet.as_view({"post": "ask"})
qa_history = QAViewSet.as_view({"get": "history", "delete": "clear_history"})

urlpatterns = [
    path("books/", book_list, name="books-list"),
    path("books/<int:pk>/", book_detail, name="books-detail"),
    path("books/<int:pk>/recommendations/", book_recommendations, name="books-recommendations"),
    path("books/scrape/", books_scrape, name="books-scrape"),
    path("books/<int:pk>/generate-insights/", book_generate_insights, name="books-generate-insights"),
    path("books/<int:pk>/index/", book_index, name="books-index"),
    path("books/generate-all-insights/", books_generate_all_insights, name="books-generate-all-insights"),
    path("books/index-all/", books_index_all, name="books-index-all"),
    path("qa/ask/", qa_ask, name="qa-ask"),
    path("qa/history/", qa_history, name="qa-history"),
]
