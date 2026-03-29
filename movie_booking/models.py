from django.db import models
from django.conf import settings



class City(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return f"{self.name}"
      

class Theatre(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    address = models.TextField(null=False, blank=False)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="theatres", null="True", blank="True")
    created_at = models.DateTimeField(auto_now_add=True)
    

    def __str__(self):
        return f"{self.name} ({self.city})"



class Screen(models.Model):
    theatre = models.ForeignKey(Theatre, on_delete=models.CASCADE, related_name='screens')
    name = models.CharField(max_length=50, null=False, blank=False)  # Screen 1, Screen 2
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.theatre.name} - {self.name}"
    

def movie_poster_image_upload_path(instance, filename):
    from django.utils.text import slugify
    name = slugify(instance.title)
    id = instance.pk
    return f'Movie_pester_images/{name}_ID_{id}/{filename}'




class Movie(models.Model):
    FORMAT = (
        ('2D', '2D'),
        ('3D', '3D'),
    )
    title = models.CharField(max_length=100, null=False, blank=False)
    language = models.CharField(max_length=30, null=False, blank=False)
    genre = models.CharField(max_length=100, null=False, blank=False)
    format = models.CharField(max_length=10, choices=FORMAT)
    duration = models.DurationField(null=False, blank=False)
    poster = models.ImageField(upload_to=movie_poster_image_upload_path, null=False, blank=False)
    release_date = models.DateField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.language})"
    

    
    


class ShowSeat(models.Model):
    SEAT_CLASS = (
        ('first', 'First Class'),
        ('second', 'Second Class'),
        ('third', 'Third Class'),
    )
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, null=False, blank=False)
    seat_number = models.CharField(max_length=10, null=False, blank=False)  # 12A, 1B
    row = models.IntegerField(null=False, blank=False)
    column = models.IntegerField(null=False, blank=False)
    seat_class = models.CharField(max_length=20, choices=SEAT_CLASS, null=False, blank=False)
    is_right_aisle = models.BooleanField(default=False, null=False, blank=False)
    is_left_aisle = models.BooleanField(default=False, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.screen} - Seat {self.seat_number}"
    
    class Meta:
        unique_together = ['screen', 'seat_number']

    


class MovieShow(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="shows", null=False, blank=False)
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE, null=False, blank=False)
    show_date = models.DateField(null=False, blank=False)
    show_time = models.TimeField(null=False, blank=False)
    available_seats = models.IntegerField(null=True, blank=True, help_text="leave empty when adding. Automatically update flight seat count.")
    is_booking_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    

    def __str__(self):
        return f"{self.movie.title} | {self.screen.theatre.name} | {self.show_date} {self.show_time}"
    


class MovieShowSeatAvailability(models.Model):

    STATUS = (
        ('available', 'Available'),
        ('locked', 'Locked'),
        ('booked', 'Booked'),
    )

    show = models.ForeignKey(MovieShow, on_delete=models.CASCADE,  related_name='seats', null=False, blank=False)
    seat = models.ForeignKey(ShowSeat, on_delete=models.CASCADE, null=False, blank=False)
    seat_price = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False)
    status = models.CharField(max_length=10, choices=STATUS, default='available')
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    is_booked = models.BooleanField(default=False)
    booked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.show} - {self.seat.seat_number} [{self.status}]"



class MovieShowBooking(models.Model):
    STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('failed','Failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    show = models.ForeignKey(MovieShow, on_delete=models.CASCADE)
    booking_reference = models.CharField(max_length=20, unique=True, null=False, blank=False)
    total_persons = models.IntegerField(null=False, blank=False)
    total_ticket_amount = models.DecimalField(max_digits=10, decimal_places=2)
    service_charge = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    booking_date = models.DateTimeField(null=True, blank=True)  
    cancelled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.booking_reference} | {self.user} | {self.show.movie.title} | {self.status}"


class MovieShowBookingSeat(models.Model):
    booking = models.ForeignKey(MovieShowBooking, on_delete=models.CASCADE, null=False, blank=False)
    seat = models.ForeignKey(ShowSeat, on_delete=models.CASCADE, null=False, blank=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    charges = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)



class Payment(models.Model):

    payment_status = models.CharField(max_length=20, choices=(
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('cancelled','Cancelled'),
    ))

    booking = models.OneToOneField(MovieShowBooking, on_delete=models.CASCADE, null=False, blank=False)
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
