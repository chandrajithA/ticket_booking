from django.apps import AppConfig


class BusBookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bus_booking'

    def ready(self):
        import bus_booking.signals
