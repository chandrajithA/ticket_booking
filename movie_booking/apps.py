from django.apps import AppConfig


class MovieBookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'movie_booking'

    def ready(self):
        import movie_booking.signals  