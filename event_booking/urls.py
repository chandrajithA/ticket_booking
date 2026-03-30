from django.urls import path
from .views import *

app_name = 'event_booking'

urlpatterns = [
    path('', events_display, name='events_display'),   
    path('search/', filter_events, name='filter_events'),
    path('initiate-booking/<int:event_id>/', initiate_booking, name = 'initiate_booking'),
    path('booking-details/<int:current_booking_id>/', booking_details, name = 'booking_details'),
    path('expire-booking/<int:booking_id>/', expire_booking, name='expire_booking'),
    path('cancel-booking/<int:booking_id>/', cancel_booking, name='cancel_booking'),
    path("create-payment/<int:booking_id>/", create_payment_order, name="create_payment_order"),
    path("verify-payment/", verify_payment, name="verify_payment"),
    path("booking-success/<int:booking_id>/", payment_success, name="payment_success"),
    path("booking-failed/<int:booking_id>/", payment_failed, name="payment_failed"),
]