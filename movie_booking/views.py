from django.shortcuts import render, redirect
from .models import *
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import uuid
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_POST
import json
from django.http import JsonResponse
from movie_booking.utils.booking_cleanup import clean_expired_bookings
from .models import Payment
import razorpay
from django.views.decorators.csrf import csrf_exempt
from movie_booking.payment_utils import calculate_booking_amount
from .seat_utils import update_available_seats   
from .constants import MOVIE_SERVICE_CHARGE


def movie_display(request):


    movies = Movie.objects.all().order_by('-release_date')


    languages = sorted(set(
        movies.values_list("language", flat=True)
    ))

    format = sorted(set(
        movies.values_list("format", flat=True)
    ))

    genre = sorted(set(
        movies.values_list("genre", flat=True)
    ))


    context = {
        'movies': movies,
        'languages': list(languages),
        'format': list(format),
        'genre': list(genre),
    }
    return render(request, "movie_booking/movie_display.html", context)




def filter_movies(request):

    data = json.loads(request.body)


    qs = Movie.objects.all().order_by('-release_date')

    # SEARCH
    if data.get("movie"):
        qs = qs.filter(title__icontains=data["movie"])

    if data.get("city"):
        qs = qs.filter(
            shows__screen__theatre__city__icontains=data["city"]
        ).distinct()
        


    if data.get("languages"):
        qs = qs.filter(language__in=data["languages"])

    if data.get("format"):
        qs = qs.filter(format__in=data["format"])

    if data.get("genre"):
        qs = qs.filter(genre=data["genre"])

    sort = data.get("sort")

    if sort == "old_to_new":
        qs = qs.order_by('release_date')
    else:
        qs = qs.order_by('-release_date')


    # UNIQUE FILTER DATA
    languages = sorted(set(
        qs.values_list("language", flat=True)
    ))

    format = sorted(set(
        qs.values_list("format", flat=True)
    ))

    genre = sorted(set(
        qs.values_list("genre", flat=True)
    ))


    # RESPONSE
    movies = [{
        "id": t.id,
        "title": t.title,
        "poster": t.poster.url if t.poster else "",
        "language": t.language,
        
    } for t in qs]

    return JsonResponse({
        "movies": movies,
        
    })




def show_selection(request, movie_id):
    movie = Movie.objects.filter(id=movie_id).first()
    cities = City.objects.all()

    context = {
        'cities': cities,
        'movie': movie,
    }
    return render(request, "movie_booking/movie_show_selection.html", context)


def get_dates(request):
    movie_id = request.GET.get("movie_id")
    city_id = request.GET.get("city_id")

    dates = MovieShow.objects.filter(
        movie_id=movie_id,
        screen__theatre__city_id=city_id
    ).values_list("show_date", flat=True).distinct().order_by("show_date")

    return JsonResponse({"dates": list(dates)})




def get_shows(request):
    movie_id = request.GET.get("movie_id")
    city_id = request.GET.get("city_id")
    date = request.GET.get("date")

    shows = MovieShow.objects.filter(
        movie_id=movie_id,
        screen__theatre__city_id=city_id,
        show_date=date
    ).select_related("screen__theatre__city").order_by("show_time")

    data = {}

    for show in shows:
        theatre_name = show.screen.theatre.name
        address = show.screen.theatre.address
        city = show.screen.theatre.city.name

        if theatre_name not in data:
            data[theatre_name ] = {
            "address": address,
            "city": city,
            "shows": []
        }

        data[theatre_name]["shows"].append({
            "id": show.id,
            "time": show.show_time.strftime("%I:%M %p")
        })

    return JsonResponse({"shows": data})


def seat_selection(request, show_id):
    
    clean_expired_bookings()

    seats = MovieShowSeatAvailability.objects.filter(show_id=show_id, show__is_booking_closed=False).select_related(
            'seat','show__movie', 'show__screen__theatre' 
        ).order_by('seat__row', 'seat__column')
        
    if(seats):

        seat_rows = defaultdict(list)

        for s in seats:
            seat_rows[s.seat.row].append(s)

        context = {
            "seat_rows": dict(seat_rows),
            "show_id": show_id,
        }

        return render(request, "movie_booking/movie_seatlayout.html", context)
    else:
        messages.info(request, "Movie show not found.")
        return redirect('movie_booking:movie_display')
        
    

@require_POST
@login_required
def initiate_booking(request, show_id):     

    if request.method == "POST":

        show = MovieShow.objects.filter(id=show_id, is_booking_closed=False).first()
        
        if show:

            selected_seats = request.POST.get('selected_seats')

            if not selected_seats:
                return redirect("movie_booking:seat_selection", show_id=show_id)
        
            selected_seats_list = selected_seats.split(',')

            if selected_seats_list:

                seats = MovieShowSeatAvailability.objects.filter(
                    show=show,
                    seat__seat_number__in=selected_seats_list,
                    status='available',
                    is_booked=False
                )

                if seats.count() != len(selected_seats_list):
                    messages.error(request, "Some seats already taken.")
                    return redirect("movie_booking:seat_selection", show_id=show_id)
                
                #  Lock them
                seats.update(
                    status='locked',
                    locked_by=request.user,
                    locked_at=timezone.now()
                )

                # store in session
                request.session['selected_seats'] = selected_seats_list
                request.session['show_id'] = show_id
            
                booking = MovieShowBooking.objects.create(
                    user=request.user,
                    show=show,
                    booking_reference=str(uuid.uuid4())[:10].upper(),
                    total_persons=len(selected_seats_list),
                    total_ticket_amount=0,
                    service_charge=0,
                    tax=0,
                    total_amount=0,
                    status='pending',
                    expires_at=timezone.now() + timedelta(minutes=10)

                )

                # store booking id also
                request.session['booking_id'] = booking.id
                request.session['just_created_booking'] = True
                return redirect('movie_booking:booking_details', current_booking_id=booking.id)

        else:
            messages.info(request, "Flight not found.")
            return redirect('movie_booking:movie_display')   
    
        


@login_required
def booking_details(request, current_booking_id):   
        
    if request.session.pop('just_created_booking', False):

        session_booking_id = request.session.get('booking_id')
        show_id = request.session.get('show_id')
        selected_seats_list = request.session.get('selected_seats')

        if not session_booking_id or not show_id or not selected_seats_list:
            return redirect('flight_booking:flights_display')
        
        # ✅ Match session booking with URL booking
        if int(session_booking_id) != int(current_booking_id):
            return redirect('movie_booking:movie_display')

        booking = MovieShowBooking.objects.filter(id=current_booking_id,user=request.user, status='pending').select_related('show').first()
        if not booking:
            return redirect('movie_booking:movie_display')
        
        show = booking.show

        selected_seat = show.seats.filter(seat__seat_number__in=selected_seats_list,is_booked=False).select_related(
            'seat',
            'show__screen__theatre__city'
        )

        if not selected_seat:
            return redirect('movie_booking:movie_display')
        
        booking_seats = []

        for s in selected_seat:
            booking_seats.append(
                MovieShowBookingSeat(
                    booking=booking,
                    seat=s.seat,
                    price=s.seat_price,
                    charges = MOVIE_SERVICE_CHARGE
                )
            )

        MovieShowBookingSeat.objects.bulk_create(booking_seats) 

        total_ticket_price = selected_seat.aggregate(total=Sum('seat_price'))['total'] or 0

        total_viewers = len(selected_seat)


        return render(request, 'movie_booking/booking_details.html', {
            'booking': booking,
            'seat_list': selected_seat,
            'total_ticket_price':total_ticket_price,
            'total_viewers': total_viewers,
            'service_charge': MOVIE_SERVICE_CHARGE,
            'expiry_time': booking.expires_at.timestamp(),
        })

    else:
        # SECOND visit → delete old booking

        booking = MovieShowBooking.objects.filter(
            id=current_booking_id,
            user=request.user,
            status='pending'
        ).first()

        if booking:

            # 🔓 unlock seats
            MovieShowSeatAvailability.objects.filter(
                show=booking.show,
                status='locked',
                is_booked = False,
                locked_by=request.user
            ).update(
                status='available',
                locked_by=None,
                locked_at=None
            )

            # cancel booking (not delete)
            booking.status = 'cancelled'
            booking.cancelled_at = timezone.now()
            booking.save()

            MovieShowBookingSeat.objects.filter(
                booking=booking,
            ).delete()

            # clear session
            for key in ['booking_id', 'show_id', 'selected_seats', 'just_created_booking']:
                request.session.pop(key, None)

            payment = Payment.objects.filter(booking=booking).first()

            if payment:
                
                payment.payment_status = 'cancelled'
                payment.error_description = 'Payment cancelled'
                payment.save()

                messages.warning(request, "Booking and payment cancelled successfully.")
                return JsonResponse({"success": True})

        else:
            messages.warning(request, "Error in cancel booking.")
            return JsonResponse({"success": False})

        messages.warning(request, "Page Refreshed. Booking Cancelled")
        return redirect('movie_booking:seat_selection', show_id=booking.show.id)
    

        





@require_POST
@login_required
def create_payment_order(request, booking_id):

    booking = MovieShowBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending'
    ).first()

    if not booking:
        return JsonResponse({"success": False})

    if booking.show.is_booking_closed==False:

        # 🔥 CALCULATE FINAL AMOUNT
        data = calculate_booking_amount(booking)

        # 🔥 SAVE IN BOOKING
        booking.total_ticket_amount = data["ticket"]
        booking.service_charge = data["charges"]
        booking.tax = data["tax"]
        booking.total_amount = data["total"]
        booking.save()

        # 🔥 CONVERT TO PAISE
        amount = int(booking.total_amount * 100)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        order = client.order.create({
            "amount": amount,
            "currency": "INR",
            "payment_capture": "1"
        })

        Payment.objects.create(
            booking=booking,
            payment_status= "pending",
            amount= amount,
            razorpay_order_id=order['id'],
        )

        return JsonResponse({
            "success": True,
            "order_id": order['id'],
            "amount": amount,
            "key": settings.RAZORPAY_KEY_ID
        })



@csrf_exempt
@login_required
def verify_payment(request):

    data = json.loads(request.body)

    rzp_order_id = data.get("razorpay_order_id")
    rzp_payment_id = data.get("razorpay_payment_id")
    rzp_signature = data.get("razorpay_signature")

    payment = Payment.objects.filter(
        razorpay_order_id=rzp_order_id
    ).select_related("booking").first()

    booking = payment.booking

    if not booking:
        return JsonResponse({"success": False})

    payment = Payment.objects.filter(booking=booking).first()

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": rzp_order_id,
            "razorpay_payment_id": rzp_payment_id,
            "razorpay_signature": rzp_signature,
        })

        # ✅ Fetch full payment details
        payment_data = client.payment.fetch(rzp_payment_id)

    except Exception as e:

        if payment:
            payment.payment_status = 'failed'
            payment.error_description = str(e)
            payment.save()

        return JsonResponse({"success": False})

    # 🔥 SUCCESS

    booking.status = 'confirmed'
    booking.expires_at = None
    booking.booking_date=timezone.now()
    booking.save()

    # 🔒 lock seats permanently
    MovieShowSeatAvailability.objects.filter(
        show=booking.show,
        locked_by=request.user,
        status='locked'
    ).update(
        status='booked',
        is_booked=True,
        locked_by=None,
        locked_at=None,
        booked_at=timezone.now()
    )

    update_available_seats(booking.show)

    # ✅ UPDATE PAYMENT MODEL
    if payment:
        payment.payment_status = 'success'
        payment.transaction_id = rzp_payment_id
        payment.transaction_signature = rzp_signature
        payment.method = payment_data.get("method")
        payment.email = payment_data.get("email")
        payment.contact = payment_data.get("contact")
        payment.bank = payment_data.get("bank")
        payment.wallet = payment_data.get("wallet")
        payment.vpa = payment_data.get("vpa")
        payment.international = payment_data.get("international", False)
        payment.status = payment_data.get("status")
        payment.captured = payment_data.get("captured")
        payment.fee = payment_data.get("fee", 0)
        payment.tax = payment_data.get("tax", 0)
        payment.raw_response = payment_data
        payment.confirmed_at = timezone.now()
        payment.save()

    return JsonResponse({"success": True})




@require_POST
@login_required
def expire_booking(request, booking_id):

    booking = MovieShowBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking and booking.expires_at <= timezone.now():
        MovieShowSeatAvailability.objects.filter(
            show=booking.show,
            status='locked',
            is_booked = False,
            locked_by=request.user
        ).update(
            status='available',
            locked_by=None,
            locked_at=None
        )

        booking.status = 'cancelled'
        booking.cancelled_at = timezone.now()
        booking.save()

        MovieShowBookingSeat.objects.filter(
            booking=booking
        ).delete()

        # clear session
        for key in ['booking_id', 'show_id', 'selected_seats', 'just_created_booking']:
            request.session.pop(key, None)

        messages.warning(request, "Booking cancelled successfully.")
        return JsonResponse({"success": True})
    
    else:
        messages.warning(request, "Error in cancel booking.")
        return JsonResponse({"success": False})




@require_POST
@login_required
def cancel_booking(request, booking_id):

    booking = MovieShowBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking:
        MovieShowSeatAvailability.objects.filter(
            show=booking.show,
            status='locked',
            is_booked = False,
            locked_by=request.user
        ).update(
            status='available',
            locked_by=None,
            locked_at=None
        )

        booking.status = 'cancelled'
        booking.cancelled_at = timezone.now()
        booking.save()

        MovieShowBookingSeat.objects.filter(
            booking=booking
        ).delete()

        # clear session
        for key in ['booking_id', 'show_id', 'selected_seats', 'just_created_booking']:
            request.session.pop(key, None)

        payment = Payment.objects.filter(booking=booking).first()
        if payment:
            
            payment.payment_status = 'cancelled'
            payment.error_description = 'Payment cancelled'
            payment.save()

            messages.warning(request, "Booking and payment cancelled successfully.")
            return JsonResponse({"success": True})

        messages.warning(request, "Booking cancelled successfully.")
        return JsonResponse({"success": True})
    
    else:
        messages.warning(request, "Error in cancel booking.")
        return JsonResponse({"success": False})
    



@login_required
def payment_success(request, booking_id):

    booking = MovieShowBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='confirmed'
    ).select_related('show__movie','show__screen__theatre__city').first()

    if not booking:
        messages.error(request, "Error in booking.")
        return redirect('booking_app:index_page')
    
    booking_seats = MovieShowBookingSeat.objects.filter(
        booking=booking
    ).select_related('seat')

    return render(request, "movie_booking/payment_success.html", {
        "booking": booking,
        'booking_seats': booking_seats,
    })


@login_required
def payment_failed(request, booking_id):

    booking = MovieShowBooking.objects.filter(
        id=booking_id,
        user=request.user
    ).select_related('show__movie','show__screen__theatre__city').first()

    return render(request, "movie_booking/payment_failed.html", {
        "booking": booking
    })