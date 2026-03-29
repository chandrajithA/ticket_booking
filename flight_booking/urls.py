from django.urls import path
from .views import *

app_name = 'flight_booking'

urlpatterns = [
    path('', flights_display, name='flights_display'),   
    path('search/', filter_flights, name='filter_flights'),
    path('seat-selection/<int:trip_id>/', seat_selection, name = 'seat_selection'),
    path('initiate-booking/<int:trip_id>/', initiate_booking, name = 'initiate_booking'),
    path('passenger-details/<int:current_booking_id>/', passenger_details, name = 'passenger_details'),
    path('add-passenger/<int:booking_id>/', add_passenger, name = 'add_passenger'),
    path('delete-passenger/<int:passenger_id>/', delete_passenger, name = 'delete_passenger'),
    path('expire-booking/<int:booking_id>/', expire_booking, name='expire_booking'),
    path('cancel-booking/<int:booking_id>/', cancel_booking, name='cancel_booking'),
    path("create-payment/<int:booking_id>/", create_payment_order, name="create_payment_order"),
    path("verify-payment/", verify_payment, name="verify_payment"),
    path("booking-success/<int:booking_id>/", payment_success, name="payment_success"),
    path("booking-failed/<int:booking_id>/", payment_failed, name="payment_failed"),
]