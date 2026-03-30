from django.contrib import admin
from .models import *

admin.site.register(City)
admin.site.register(Category)
admin.site.register(Event)
admin.site.register(EventSeatAvailability)
admin.site.register(EventBooking)
admin.site.register(EventBookingSeat)
admin.site.register(Payment)

