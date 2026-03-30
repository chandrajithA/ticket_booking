from django.apps import AppConfig


class EventBookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'event_booking'

    def ready(self):
        import event_booking.signals



    