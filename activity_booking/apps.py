from django.apps import AppConfig


class ActivityBookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'activity_booking'

    def ready(self):
        import activity_booking.signals    