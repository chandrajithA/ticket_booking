from django.apps import AppConfig


class TrainBookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'train_booking'

    def ready(self):
        import train_booking.signals