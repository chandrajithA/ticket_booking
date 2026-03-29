from django.urls import path
from .views import *

app_name = 'movie_booking'

urlpatterns = [
    path('', movie_display, name='movie_display'),   
    path('search/', filter_movies, name='filter_movies'),
    path('show-selection/<int:movie_id>/', show_selection, name = 'show_selection'),
    path('get-dates/', get_dates, name='get_dates'),
    path('get-shows/', get_shows, name='get_shows'),
    path('seat-selection/<int:show_id>/', seat_selection, name='seat_selection'),
    path('initiate-booking/<int:show_id>/', initiate_booking, name = 'initiate_booking'),
    path('booking-details/<int:current_booking_id>/', booking_details, name = 'booking_details'),
    path('expire-booking/<int:booking_id>/', expire_booking, name='expire_booking'),
    path('cancel-booking/<int:booking_id>/', cancel_booking, name='cancel_booking'),
    path("create-payment/<int:booking_id>/", create_payment_order, name="create_payment_order"),
    path("verify-payment/", verify_payment, name="verify_payment"),
    path("booking-success/<int:booking_id>/", payment_success, name="payment_success"),
    path("booking-failed/<int:booking_id>/", payment_failed, name="payment_failed"),
]