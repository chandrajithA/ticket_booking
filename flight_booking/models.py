from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError




class Airport(models.Model):
    name = models.CharField(max_length=150,null=False, blank=False)
    code = models.CharField(max_length=10, unique=True, null=False, blank=False)  # MAA, DEL
    city = models.CharField(max_length=100, null=False, blank=False)
    country = models.CharField(max_length=100, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.city} city"
    

class Terminal(models.Model):
    airport = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='terminals')
    name = models.CharField(max_length=50)   

    def __str__(self):
        return f"{self.airport.name} - {self.name}"
    

def airline_image_upload_path(instance, filename):
    from django.utils.text import slugify
    name = slugify(instance.name)
    id = instance.pk
    return f'User_images/{name}_ID_{id}/{filename}'

    
class Airline(models.Model):
    name = models.CharField(max_length=100, unique=True, null=False, blank=False)
    picture = models.ImageField( null=True, blank=True, upload_to=airline_image_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
        
    def __str__(self):
            return f"{self.name}"



class Flight(models.Model):
    brand = models.ForeignKey(Airline, on_delete=models.CASCADE, related_name='flights', null=False, blank=False)
    flight_name = models.CharField(max_length=100, null=False, blank=False)
    flight_number = models.CharField(max_length=20, unique=True, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.flight_name} ({self.flight_number})"



    

class FlightSeat(models.Model):
    SEAT_CLASS = (
        ('economy', 'Economy'),
        ('business', 'Business'),
        ('first', 'First Class'),
    )

    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='seats', null=False, blank=False)
    seat_number = models.CharField(max_length=10, null=False, blank=False)  # 12A, 1B
    row = models.IntegerField(null=False, blank=False)
    column = models.IntegerField(null=False, blank=False)
    seat_class = models.CharField(max_length=20, choices=SEAT_CLASS, null=False, blank=False)
    is_window = models.BooleanField(default=False, null=False, blank=False)
    is_right_aisle = models.BooleanField(default=False, null=False, blank=False)
    is_left_aisle = models.BooleanField(default=False, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.flight} - {self.seat_number} - {self.seat_class} - is_window:{self.is_window} - right_aisle:{self.is_right_aisle} - left_aisle:{self.is_left_aisle}"

    class Meta:
        unique_together = ['flight', 'seat_number']


class FlightSchedule(models.Model):
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='schedules', null=False, blank=False)
    boarding = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='departures', null=False, blank=False)
    boarding_terminal = models.ForeignKey(Terminal, on_delete=models.SET_NULL, null=True, related_name='boarding_schedules')
    arrival = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='arrivals', null=False, blank=False)
    arrival_terminal = models.ForeignKey(Terminal, on_delete=models.SET_NULL, null=True, related_name='arrival_schedules')
    boarding_time = models.TimeField(null=False, blank=False)
    arrival_time = models.TimeField(null=False, blank=False)
    duration = models.DurationField(null=False, blank=False)
    stops = models.IntegerField(null=False, blank=False, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.flight.flight_number} - {self.boarding} to {self.arrival}"
    
    def clean(self):
        if self.boarding_terminal and self.boarding_terminal.airport != self.boarding:
            raise ValidationError("Boarding terminal must belong to boarding airport")

        if self.arrival_terminal and self.arrival_terminal.airport != self.arrival:
            raise ValidationError("Arrival terminal must belong to arrival airport")
    

class FlightTrip(models.Model):
    schedule = models.ForeignKey(FlightSchedule, on_delete=models.CASCADE, related_name='trips', null=False, blank=False)
    travel_date = models.DateField(null=False, blank=False)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Leave empty when adding. Automatic update the low value")
    available_seats = models.IntegerField(null=True, blank=True, help_text="leave empty when adding. Automatically update flight seat count.")
    is_booking_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.schedule.flight.flight_number} - {self.travel_date}"
    
    class Meta:
        unique_together = ['schedule', 'travel_date']
    


class FlightSeatAvailability(models.Model):
    STATUS = (
        ('available', 'Available'),
        ('locked', 'Locked'),
        ('booked', 'Booked'),
    )
    
    trip = models.ForeignKey(FlightTrip, on_delete=models.CASCADE, related_name='seats', null=False, blank=False)
    seat = models.ForeignKey(FlightSeat, on_delete=models.CASCADE, null=False, blank=False)
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




class FlightBooking(models.Model):
    STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('failed','Failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, blank=False)
    trip = models.ForeignKey(FlightTrip, on_delete=models.CASCADE, null=False, blank=False)
    booking_reference = models.CharField(max_length=20, unique=True, null=False, blank=False)
    total_passengers = models.IntegerField(null=False, blank=False)
    total_ticket_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_luggage_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_food_price = models.DecimalField(max_digits=10, decimal_places=2)
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

    MEAL_TYPE = (
        ('veg', 'Vegetarian Meal'),
        ('non_veg', 'Non-Vegetarian Meal'),
        ('vegan', 'Vegan Meal'),
        ('child', 'Child Meal'),
        ('none', 'No Meal'),
    )

    BAGGAGE_TYPE = (
        ('cabin', 'Cabin Baggage (7kg)'),
        ('checkin', 'Check-in Baggage (15kg)'),
        ('extra_5', 'Extra 5kg'),
        ('extra_10', 'Extra 10kg'),
        ('none', 'No Extra'),
    )

    BABY_CARRIER = (
        ('none', 'None'),
        ('single', 'Baby Carrier Single'),
        ('double', 'Baby Carrier Double'),
    )

    WHEELCHAIR = (
        ('none', 'None'),
        ('door', 'Wheelchair to Aircraft Door'),
        ('seat', 'Wheelchair to Seat'),
        ('lift', 'Wheelchair with Lift'),
    )

    booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE, related_name='passengers', null=False, blank=False)
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
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE, default='none', help_text="Set as No Meals for default")   
    baggage_type = models.CharField(max_length=20, choices=BAGGAGE_TYPE, default='none', help_text="Set as No Extra for default")
    baby_carrier = models.CharField(max_length=20, choices=BABY_CARRIER, default='none', help_text="Set as None for default")
    wheelchair = models.CharField(max_length=20, choices=WHEELCHAIR, default='none', help_text="Set as None for default")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} ({self.booking.booking_reference})"
    
    class Meta:
        unique_together = ['booking', 'passenger_number']
    

class FlightBookingSeat(models.Model):
    seat = models.ForeignKey(FlightSeat, on_delete=models.CASCADE, null=False, blank=False)
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE, null=False, blank=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    luggage_price = models.DecimalField(max_digits=10, decimal_places=2)
    food_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.passenger.booking.trip.schedule.flight.flight_name} - {self.passenger.booking.trip.travel_date} - {self.seat.seat_number} - {self.passenger.first_name} - {self.created_at}"
    
    class Meta:
        unique_together = ['seat', 'passenger']


class Payment(models.Model):

    payment_status = models.CharField(max_length=20, choices=(
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('cancelled','Cancelled'),
    ))

    booking = models.OneToOneField(FlightBooking, on_delete=models.CASCADE, null=False, blank=False)
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
