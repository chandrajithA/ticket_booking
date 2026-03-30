from django.apps import AppConfig


class SportBookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sport_booking'

    def ready(self):
        import sport_booking.signals



    