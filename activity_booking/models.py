from django.db import models
from django.conf import settings



class City(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return f"{self.name}"
      

class Category(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return f"{self.name}"
    

def activity_poster_image_upload_path(instance, filename):
    from django.utils.text import slugify
    name = slugify(instance.title)
    id = instance.pk
    return f'activity_pester_images/{name}_ID_{id}/{filename}'


    
    


class Event(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null="False", blank="False")
    address = models.TextField(null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="act_stadiums", null="False", blank="False")
    title=models.CharField(max_length=100, null=False, blank=False)
    poster = models.ImageField(upload_to=activity_poster_image_upload_path, null=False, blank=False)
    seat_price = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False)
    event_date = models.DateField(null=True, blank=True)
    event_start_time = models.TimeField(null=True, blank=True)
    event_end_time = models.TimeField(null=True, blank=True)
    seats_count = models.IntegerField(null=True, blank=True)
    is_booking_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    

    def __str__(self):
        return f"{self.category} {self.title} | {self.event_date} {self.event_start_time} {self.event_end_time}"
    


class EventSeatAvailability(models.Model):

    STATUS = (
        ('available', 'Available'),
        ('locked', 'Locked'),
        ('booked', 'Booked'),
    )

    event = models.ForeignKey(Event, on_delete=models.CASCADE,  related_name='act_seats', null=True, blank=True)
    seat_number = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='available')
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='act_seat_locks', on_delete=models.CASCADE, null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    is_booked = models.BooleanField(default=False)
    booked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event} - {self.seat_number} [{self.status}]"



class EventBooking(models.Model):
    STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('failed','Failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='act_bookings', on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True)
    booking_reference = models.CharField(max_length=20, unique=True, null=False, blank=False)
    total_ticket = models.IntegerField(null=True, blank=True)
    total_ticket_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    booking_date = models.DateTimeField(null=True, blank=True)  
    cancelled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.booking_reference} | {self.user} | {self.event.category} | {self.status}"


class EventBookingSeat(models.Model):
    booking = models.ForeignKey(EventBooking, on_delete=models.CASCADE, null=False, blank=False)
    seat = models.ForeignKey(EventSeatAvailability, on_delete=models.CASCADE, null=False, blank=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)



class Payment(models.Model):

    payment_status = models.CharField(max_length=20, choices=(
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('cancelled','Cancelled'),
    ))

    booking = models.OneToOneField(EventBooking, on_delete=models.CASCADE, null=False, blank=False)
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
