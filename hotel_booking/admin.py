from django.contrib import admin
from .models import *

admin.site.register(City)
admin.site.register(Category)
admin.site.register(Hotel)
admin.site.register(HotelRoomAvailability)
admin.site.register(HotelBooking)
admin.site.register(HotelBookingRoom)
admin.site.register(Payment)

