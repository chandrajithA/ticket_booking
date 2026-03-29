from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

COACH_SEAT_CONFIG = {
    'SL': 64,
    '3A': 56,
    '2A': 42,
    '1A': 18,
    'CC': 78,
    'EE': 52,
}

BERTH_PATTERN = [
    'LB', 'MB', 'UB', 'LB', 'MB', 'UB', 'SL', 'SU'
]


class Station(models.Model):
    name = models.CharField(max_length=150, unique=True, null=False, blank=False)
    code = models.CharField(max_length=10, unique=True, null=False, blank=False)  # MAS, NDLS
    city = models.CharField(max_length=100, null=False, blank=False)
    state = models.CharField(max_length=100, null=False, blank=False)

    def __str__(self):
        return f"{self.name} ({self.code})"
    

class Platform(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='terminals', null=False, blank=False)
    name = models.CharField(max_length=50, null=False, blank=False)   

    def __str__(self):
        return f"{self.station.name} - {self.name}"
    

class Train(models.Model):

    TRAIN_TYPE = (
        ('express', 'Express'),
        ('passenger', 'Passenger'),
        ('superfast', 'Superfast'),
    )

    train_name = models.CharField(max_length=150, unique=True, null=False, blank=False)
    train_number = models.CharField(max_length=20, unique=True, null=False, blank=False)
    train_type = models.CharField(
        max_length=10,
        choices=TRAIN_TYPE,
        null=False, blank=False
    )

    def __str__(self):
        return f"{self.train_name} ({self.train_number})"
    

    


class Coach(models.Model):
    COACH_TYPE = (
        ('SL', 'Sleeper'),
        ('3A', 'AC 3 Tier'),
        ('2A', 'AC 2 Tier'),
        ('1A', 'AC First Class'),
        ('CC', 'Chair Car'),
        ('EC', 'Executive Chair Car'),
    )

    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name='coaches', null=False, blank=False)
    coach_type = models.CharField(max_length=10, choices=COACH_TYPE, null=False, blank=False)
    coach_number = models.CharField(max_length=10, null=False, blank=False)
    total_seats = models.IntegerField(default=0, help_text="Leave Empty it will calculate automatically")

    def save(self, *args, **kwargs):
        is_new = self.pk is None  # ✅ check if new coach

        # set total seats automatically
        self.total_seats = COACH_SEAT_CONFIG.get(self.coach_type, 0)

        super().save(*args, **kwargs)

        # ✅ create seats ONLY when new coach created
        if is_new:
            self.create_seats()

    def create_seats(self):
        seats = []

        for i in range(self.total_seats):
            berth = BERTH_PATTERN[i % len(BERTH_PATTERN)]

            seats.append(
                TrainSeat(
                    coach=self,
                    seat_number=i + 1,
                    berth_type=berth
                )
            )

        TrainSeat.objects.bulk_create(seats)  # ⚡ fast

    def __str__(self):
        return f"{self.train} - {self.coach_number} ({self.total_seats})"
    
    class Meta:
        unique_together = ['train', 'coach_number']
    

    

class TrainSeat(models.Model):
    BERTH_TYPE = (
        ('LB', 'Lower'),
        ('MB', 'Middle'),
        ('UB', 'Upper'),
        ('SL', 'Side Lower'),
        ('SU', 'Side Upper'),
    )

    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name='seats')
    seat_number = models.IntegerField()
    berth_type = models.CharField(max_length=5, choices=BERTH_TYPE)

    def __str__(self):
        return f"{self.coach.coach_number} - {self.seat_number} ({self.berth_type})"

    class Meta:
        unique_together = ['coach', 'seat_number']



class TrainSchedule(models.Model):

    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name='schedules', null=False, blank=False)
    boarding = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='departures', null=False, blank=False)
    boarding_time = models.TimeField(null=False, blank=False)
    boarding_terminal = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, related_name='boarding_schedules')
    arrival = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='arrivals', null=False, blank=False)
    arrival_time = models.TimeField(null=False, blank=False)
    arrival_terminal = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, related_name='arrival_schedules')
    duration = models.DurationField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    monday = models.BooleanField(default=False)
    tuesday = models.BooleanField(default=False)
    wednesday = models.BooleanField(default=False)
    thursday = models.BooleanField(default=False)
    friday = models.BooleanField(default=False)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.train} - {self.boarding} to {self.arrival}"
    

    def clean(self):
        if self.boarding_terminal and self.boarding_terminal.station != self.boarding:
            raise ValidationError("Boarding platform must belong to boarding station")

        if self.arrival_terminal and self.arrival_terminal.station != self.arrival:
            raise ValidationError("Arrival platform must belong to arrival station")
    

class TrainTrip(models.Model):

    schedule = models.ForeignKey(TrainSchedule, on_delete=models.CASCADE, related_name='trips', null=False, blank=False)
    travel_date = models.DateField(null=False, blank=False)
    is_booking_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    starting_price = models.DecimalField(max_digits=10, decimal_places=2)

    
    def __str__(self):
        return f"{self.schedule.train.train_number} - {self.travel_date}"

    class Meta:
        unique_together = ['schedule', 'travel_date']

        


class TrainSeatAvailability(models.Model):
    STATUS = (
        ('available', 'Available'),
        ('locked', 'Locked'),
        ('booked', 'Booked'),
    )

    trip = models.ForeignKey(TrainTrip, on_delete=models.CASCADE, related_name='seats', null=False, blank=False)
    seat = models.ForeignKey(TrainSeat, on_delete=models.CASCADE, null=False, blank=False)
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
    

class TrainBooking(models.Model):
    STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('waiting', 'Waiting List'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=False, blank=False)
    trip = models.ForeignKey(TrainTrip, on_delete=models.CASCADE, null=False, blank=False)
    booking_reference = models.CharField(max_length=20, unique=True, null=False, blank=False)
    coach_type = models.CharField(max_length=10, null=False, blank=False)
    total_passengers = models.IntegerField(null=True, blank=True)
    total_ticket_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    booking_date = models.DateTimeField(null=True, blank=True)  
    cancelled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.booking_reference
    

class Passenger(models.Model):
    GENDER = (
        ('male', 'Male'),
        ('female', 'Female'),
    )

    booking = models.ForeignKey(TrainBooking, on_delete=models.CASCADE, related_name='passengers', null=False, blank=False)
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



class TrainBookingSeat(models.Model):
    seat = models.ForeignKey(TrainSeat, on_delete=models.CASCADE, null=True, blank=True)
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE, null=False, blank=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.passenger.first_name} - {self.seat}"
    
    class Meta:
        unique_together = ['seat', 'passenger']



class Payment(models.Model):

    payment_status = models.CharField(max_length=20, choices=(
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('cancelled','Cancelled'),
    ))

    booking = models.OneToOneField(TrainBooking, on_delete=models.CASCADE, null=False, blank=False)
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
