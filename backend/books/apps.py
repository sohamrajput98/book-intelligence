"""Django app configuration for books."""
from django.apps import AppConfig


class BooksConfig(AppConfig):
    """Configuration for books app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'books'
