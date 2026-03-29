from django.db import models
from django.conf import settings
from django.db.models import Min
from django.core.exceptions import ValidationError




class BusStand(models.Model):
    name = models.CharField(max_length=150,null=False, blank=False)
    code = models.CharField(max_length=10, unique=True, null=False, blank=False)  # MAA, DEL
    city = models.CharField(max_length=100, null=False, blank=False)
    country = models.CharField(max_length=100, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.city} city"
    

class Terminal(models.Model):
    busstand = models.ForeignKey(BusStand, on_delete=models.CASCADE, related_name='terminals')
    name = models.CharField(max_length=50)   

    def __str__(self):
        return f"{self.busstand.name} - {self.name}"
    

def travel_image_upload_path(instance, filename):
    from django.utils.text import slugify
    name = slugify(instance.name)
    id = instance.pk
    return f'Travel_images/{name}_ID_{id}/{filename}'

    
class Travel(models.Model):
    name = models.CharField(max_length=100, unique=True, null=False, blank=False)
    picture = models.ImageField( null=True, blank=True, upload_to=travel_image_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
        
    def __str__(self):
        return f"{self.name}"



class Bus(models.Model):
    brand = models.ForeignKey(Travel, on_delete=models.CASCADE, related_name='buses', null=False, blank=False)
    bus_name = models.CharField(max_length=100, null=False, blank=False)
    bus_number = models.CharField(max_length=20, unique=True, null=False, blank=False)
    is_ac = models.BooleanField(default=False, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.bus_name} ({self.bus_number})"



    

class BusSeat(models.Model):
    SEAT_CLASS = (
        ('seater', 'Seater'),
        ('berth', 'Berth'),
    )

    FLOOR_CHOICE = (
        ('lower', 'Lower'),
        ('upper', 'Upper'),
    )

    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='seats', null=False, blank=False)
    seat_number = models.CharField(max_length=10, null=False, blank=False)  # 12A, 1B
    floor_choice = models.CharField(max_length=10, choices=FLOOR_CHOICE, null=False, blank=False)
    row = models.IntegerField(null=False, blank=False)
    column = models.IntegerField(null=False, blank=False)
    seat_class = models.CharField(max_length=20, choices=SEAT_CLASS, null=False, blank=False)
    is_single_one = models.BooleanField(default=False, null=False, blank=False)
    is_right_aisle = models.BooleanField(default=False, null=False, blank=False)
    is_left_aisle = models.BooleanField(default=False, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bus} - {self.seat_number} - {self.seat_class} - right_aisle:{self.is_right_aisle} - left_aisle:{self.is_left_aisle}"

    class Meta:
        unique_together = ['bus', 'seat_number']


class BusSchedule(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='schedules', null=False, blank=False)
    boarding = models.ForeignKey(BusStand, on_delete=models.CASCADE, related_name='departures', null=False, blank=False)
    boarding_terminal = models.ForeignKey(Terminal, on_delete=models.SET_NULL, null=True, related_name='boarding_schedules')
    arrival = models.ForeignKey(BusStand, on_delete=models.CASCADE, related_name='arrivals', null=False, blank=False)
    arrival_terminal = models.ForeignKey(Terminal, on_delete=models.SET_NULL, null=True, related_name='arrival_schedules')
    boarding_time = models.TimeField(null=False, blank=False)
    arrival_time = models.TimeField(null=False, blank=False)
    duration = models.DurationField(null=False, blank=False)
    stops = models.IntegerField(null=False, blank=False, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bus.bus_number} - {self.boarding} to {self.arrival}"
    
    def clean(self):
        if self.boarding_terminal and self.boarding_terminal.busstand != self.boarding:
            raise ValidationError("Boarding terminal must belong to boarding airport")

        if self.arrival_terminal and self.arrival_terminal.busstand != self.arrival:
            raise ValidationError("Arrival terminal must belong to arrival airport")
    

class BusTrip(models.Model):
    schedule = models.ForeignKey(BusSchedule, on_delete=models.CASCADE, related_name='trips', null=False, blank=False)
    travel_date = models.DateField(null=False, blank=False)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Leave empty when adding. Automatic update the low value")
    available_seats = models.IntegerField(null=True, blank=True, help_text="leave empty when adding. Automatically update bus seat count.")
    is_booking_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.schedule.bus.bus_number} - {self.travel_date}"
    
    def save(self, *args, **kwargs):
        if not self.pk:
            self.available_seats = self.schedule.bus.seats.count()
        super().save(*args, **kwargs)
    
    class Meta:
        unique_together = ['schedule', 'travel_date']
    


class BusSeatAvailability(models.Model):
    STATUS = (
        ('available', 'Available'),
        ('locked', 'Locked'),
        ('booked', 'Booked'),
    )
    
    trip = models.ForeignKey(BusTrip, on_delete=models.CASCADE, related_name='seats', null=False, blank=False)
    seat = models.ForeignKey(BusSeat, on_delete=models.CASCADE, null=False, blank=False)
    seat_price = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False)
    status = models.CharField(max_length=10, choices=STATUS, default='available')
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    is_booked = models.BooleanField(default=False)
    booked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['trip', 'seat']

    def __str__(self):
        return f"{self.trip} - {self.seat} - {self.status}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        update_trip_base_price(self.trip)


    def delete(self, *args, **kwargs):
        trip = self.trip
        super().delete(*args, **kwargs)
        update_trip_base_price(trip)


def update_trip_base_price(trip):
    min_price = BusSeatAvailability.objects.filter(
        trip=trip,
        status='available'
    ).aggregate(min_price=Min('seat_price'))['min_price']

    trip.base_price = min_price or 0
    trip.save(update_fields=['base_price'])


class BusBooking(models.Model):
    STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('failed','Failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, blank=False)
    trip = models.ForeignKey(BusTrip, on_delete=models.CASCADE, null=False, blank=False)
    booking_reference = models.CharField(max_length=20, unique=True, null=False, blank=False)
    total_passengers = models.IntegerField(null=False, blank=False)
    total_ticket_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    booking_date = models.DateTimeField(null=True, blank=True)  
    cancelled_at = models.DateTimeField(null=True, blank=True)
     

    def __str__(self):
        return f"{self.booking_reference}"
    

class Passenger(models.Model):
    GENDER = (
        ('male', 'Male'),
        ('female', 'Female'),
    )


    booking = models.ForeignKey(BusBooking, on_delete=models.CASCADE, related_name='passengers', null=False, blank=False)
    passenger_number = models.IntegerField(null=False, blank=False)
    first_name = models.CharField(max_length=50, null=False, blank=False)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER, null=False, blank=False)
    dob = models.DateField(null=False, blank=False)
    nationality = models.CharField(max_length=50, null=False, blank=False)
    phone = models.CharField(max_length=10, null=False, blank=False)
    email = models.EmailField(null=False, blank=False)
    address = models.CharField(max_length=200, null=False, blank=False)
    pincode = models.IntegerField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} ({self.booking.booking_reference})"
    
    class Meta:
        unique_together = ['booking', 'passenger_number']
    

class BusBookingSeat(models.Model):
    seat = models.ForeignKey(BusSeat, on_delete=models.CASCADE, null=False, blank=False)
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE, null=False, blank=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.passenger.booking.trip.schedule.bus.bus_name} - {self.passenger.booking.trip.travel_date} - {self.seat.seat_number} - {self.passenger.first_name} - {self.created_at}"
    
    class Meta:
        unique_together = ['seat', 'passenger']


class Payment(models.Model):

    payment_status = models.CharField(max_length=20, choices=(
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('cancelled','Cancelled'),
    ))

    booking = models.OneToOneField(BusBooking, on_delete=models.CASCADE, null=False, blank=False)
    razorpay_order_id = models.CharField(max_length=255, null=True, blank=True)  
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    transaction_signature = models.CharField(max_length=256, null=False, blank=False)
    method = models.CharField(max_length=30, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    contact = models.CharField(max_length=20, null=True, blank=True)
    bank = models.CharField(max_length=50, null=True, blank=True)
    wallet = models.CharField(max_length=50, null=True, blank=True)
    vpa = models.CharField(max_length=100, null=True, blank=True)
    international = models.BooleanField(default=False)
    amount = models.PositiveIntegerField(default=0,help_text="Amount is in paise", null=False, blank=False)
    currency = models.CharField(max_length=10, default="INR")
    status = models.CharField(max_length=30, null=True, blank=True)
    captured = models.BooleanField(default=False)
    fee = models.PositiveIntegerField(default=0,help_text="Amount is in paise")
    tax = models.PositiveIntegerField(default=0,help_text="Amount is in paise")
    error_code = models.CharField(max_length=100, null=True, blank=True)
    error_description = models.TextField(null=True, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.booking.booking_reference} - {self.payment_status}"
