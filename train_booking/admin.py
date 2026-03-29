from django.contrib import admin
from .models import *

admin.site.register(Station)
admin.site.register(Platform)
admin.site.register(Train)
admin.site.register(Coach)
admin.site.register(TrainSeat)
admin.site.register(TrainSchedule)
admin.site.register(TrainTrip)
admin.site.register(TrainSeatAvailability)
admin.site.register(TrainBooking)
admin.site.register(Passenger)
admin.site.register(TrainBookingSeat)
admin.site.register(Payment)