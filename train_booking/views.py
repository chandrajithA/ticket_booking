from django.shortcuts import render, redirect , get_object_or_404
from .models import *
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import uuid
from django.utils import timezone
from datetime import timedelta, datetime
from django.views.decorators.http import require_POST
import json
from django.http import JsonResponse
from train_booking.utils.booking_cleanup import clean_expired_bookings
import razorpay
from django.views.decorators.csrf import csrf_exempt
from train_booking.payment_utils import calculate_booking_amount
from datetime import date
from datetime import timedelta
from django.db.models import Count, Q


MEAL_PRICES = {
    "veg": 300,
    "non_veg": 500,
    "vegan": 400,
    "child": 250,
    "none": 0
}

LUGGAGE_PRICES = {
    "cabin": 0,
    "checkin": 0,
    "extra_5": 800,
    "extra_10": 1500,
    "none": 0
}



def train_display(request):
    

    trips = TrainTrip.objects.filter(is_booking_closed=False).select_related(
        'schedule__train',
        'schedule__boarding',
        'schedule__arrival'
    ).all().order_by('travel_date')


    train_types = sorted(set(
        trips.values_list("schedule__train__train_type", flat=True)
    ))

    COACH_TYPE_DICT = dict(Coach.COACH_TYPE)

    travel_classes = (
        Coach.objects.filter(
            train__schedules__trips__in=trips
        )
        .values_list("coach_type", flat=True)
        .distinct()
    )

    travel_classes = [
        {"value": cls, "label": COACH_TYPE_DICT.get(cls)}
        for cls in travel_classes
    ]

    

    

    context = {
        'trips': trips,
        'train_types': list(train_types),
        'travel_classes': list(travel_classes),
    }


    return render(request, "train_booking/train_display.html", context)


def format_duration_py(duration):
    total_seconds = int(duration.total_seconds())

    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    minutes = (total_seconds % 3600) // 60

    parts = []

    if days > 0:
        parts.append(f"{days}d")

    if hours > 0:
        parts.append(f"{hours}hr")

    if minutes > 0:
        parts.append(f"{minutes}min")

    return " ".join(parts)


def filter_trains(request):

    data = json.loads(request.body)

    qs = TrainTrip.objects.filter(is_booking_closed=False).select_related(
        'schedule__train',
        'schedule__boarding',
        'schedule__arrival'
    ).order_by('travel_date')

    # SEARCH
    if data.get("source"):
        qs = qs.filter(schedule__boarding__city__icontains=data["source"])

    if data.get("destination"):
        qs = qs.filter(schedule__arrival__city__icontains=data["destination"])
        

    if data.get("date"):
        try:
            date_obj = datetime.strptime(data["date"], "%Y-%m-%d").date()
            qs = qs.filter(travel_date=date_obj)
        except:
            pass

     # 🚆 TRAIN TYPE
    if data.get("train_types"):
        qs = qs.filter(schedule__train__train_type__in=data["train_types"])

    # 🪑 TRAVEL CLASS (IMPORTANT)
    if data.get("travel_classes"):
        qs = qs.filter(
            schedule__train__coaches__coach_type__in=data["travel_classes"]
        ).distinct()

    # ⏰ DEPARTURE TIME
    if data.get("departure_slots"):
        dep_q = Q()

        for slot in data["departure_slots"]:
            start, end = map(int, slot.split("-"))
            dep_q |= Q(
                schedule__boarding_time__hour__gte=start,
                schedule__boarding_time__hour__lt=end
            )

        qs = qs.filter(dep_q)

    # ⏰ ARRIVAL TIME
    if data.get("arrival_slots"):
        arr_q = Q()

        for slot in data["arrival_slots"]:
            start, end = map(int, slot.split("-"))
            arr_q |= Q(
                schedule__arrival_time__hour__gte=start,
                schedule__arrival_time__hour__lt=end
            )

        qs = qs.filter(arr_q)

    

    # RESPONSE
    trains = [{
        "id": t.id,
        "train_name": t.schedule.train.train_name,
        "train_number": t.schedule.train.train_number,

        "travel_date": str(t.travel_date),

        "departure": t.schedule.boarding_time.strftime("%I:%M %p"),
        "arrival": t.schedule.arrival_time.strftime("%I:%M %p"),

        "source": t.schedule.boarding.code,
        "destination": t.schedule.arrival.code,

        "source_name": t.schedule.boarding.name,
        "destination_name": t.schedule.arrival.name,

        "duration": format_duration_py(t.schedule.duration),

        "price": t.starting_price,

        "monday": t.schedule.monday,
        "tuesday": t.schedule.tuesday,
        "wednesday": t.schedule.wednesday,
        "thursday": t.schedule.thursday,
        "friday": t.schedule.friday,
        "saturday": t.schedule.saturday,
        "sunday": t.schedule.sunday,
    } for t in qs]

    return JsonResponse({
        "trains": trains,
    
    })


@login_required
def class_selection(request, trip_id):

    clean_expired_bookings()

    trip = TrainTrip.objects.filter(id=trip_id).select_related(
        'schedule__train',
        'schedule__boarding',
        'schedule__arrival'
    ).first()

    schedule = trip.schedule


    # 🔥 CURRENT TRIP SEATS PER CLASS
    class_seats = (
        trip.seats
        .filter(status='available')
        .values('seat__coach__coach_type')
        .annotate(count=Count('id'))
    )

    seat_map = {
        i['seat__coach__coach_type']: i['count']
        for i in class_seats
    }

    coach_types = schedule.train.coaches.values_list(
        'coach_type', flat=True
    ).distinct()

    coach_types = list(coach_types)[::-1]

    COACH_DICT = dict(Coach.COACH_TYPE)

    class_data = []

    

    for c in coach_types:

        price = (
                trip.seats
                .filter(seat__coach__coach_type=c)
                .values_list('seat_price', flat=True)
                .first()
            )
        
        class_data.append({
            "code": c,
            "name": COACH_DICT.get(c),
            "available_seats": seat_map.get(c, 0),
            "price": price,
        })

    context = {
        "trip": trip,
        "class_data": class_data
    }

    return render(request, "train_booking/train_class_selection.html", context)


        
    

@require_POST
def initiate_booking(request, trip_id):     

    if request.method == "POST":

        data = json.loads(request.body)

        coach_type = data.get("coach_type")

        trip = TrainTrip.objects.filter(id=trip_id, is_booking_closed=False).first()
        
        if trip:            
        
            booking = TrainBooking.objects.create(
                user=request.user,
                trip=trip,
                booking_reference=str(uuid.uuid4())[:10].upper(),
                coach_type=coach_type,
                total_ticket_amount=0,
                tax=0,
                total_amount=0,
                status='pending',
                expires_at=timezone.now() + timedelta(minutes=10)
            )

            # store booking id also
            request.session['trip_id'] = trip_id
            request.session['booking_id'] = booking.id
            request.session['just_created_booking'] = True
            return JsonResponse({
                "success": True,
                "redirect_url": f"/trains/passenger-details/{booking.id}/"
            })

        else:
            messages.info(request, "Train not found.")
            return redirect('train_booking:coach_selection', trip_id=trip_id)   
    
        


@login_required
def passenger_details(request, current_booking_id):   
        
    if request.session.pop('just_created_booking', False):

        session_booking_id = request.session.get('booking_id')
        trip_id = request.session.get('trip_id')

        if not session_booking_id or not trip_id:
            return redirect('train_booking:train_display')
        
        # ✅ Match session booking with URL booking
        if int(session_booking_id) != int(current_booking_id):
            return redirect('train_booking:train_display')

        booking = TrainBooking.objects.filter(id=current_booking_id,user=request.user, status='pending').select_related('trip').first()
        if not booking:
            return redirect('train_booking:train_display')
        
        trip = booking.trip

        price = (
                trip.seats
                .filter(seat__coach__coach_type=booking.coach_type)
                .values_list('seat_price', flat=True)
                .first()
            )

        

        return render(request, 'train_booking/passenger_details.html', {
            'booking': booking,
            'price':price,
            'expiry_time': booking.expires_at.timestamp(),
        })

    else:
        # SECOND visit → delete old booking

        booking = TrainBooking.objects.filter(
            id=current_booking_id,
            user=request.user,
            status='pending'
        ).first()

        if booking:

            # cancel booking (not delete)
            booking.status = 'cancelled'
            booking.cancelled_at = timezone.now()
            booking.save()

            TrainBookingSeat.objects.filter(
                passenger__booking=booking
            ).delete()

            # clear session
            for key in ['booking_id', 'trip_id', 'just_created_booking']:
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
        return redirect('train_booking:class_selection', trip_id=booking.trip.id)
    

        


@require_POST
@login_required
def add_passenger(request, booking_id):
    data = json.loads(request.body)

    dob = data.get('dob')


    age = None
    dob_obj = None

    if dob:
        dob_obj = datetime.strptime(dob, "%Y-%m-%d").date()
        today = date.today()
        age = today.year - dob_obj.year - (
            (today.month, today.day) < (dob_obj.month, dob_obj.day)
        )

        if age == 0:
            age_label = "below 1"
        else:
            age_label = str(age)

    booking = TrainBooking.objects.filter(id=booking_id, user=request.user, status='pending').first()
    if not booking:
        return JsonResponse({"success": False, "error": "Invalid booking"})
    

    passenger = Passenger.objects.create(
        booking=booking,
        first_name=data['first_name'],
        last_name=data['last_name'],
        gender=data['gender'],
        dob=dob_obj,
        nationality=data['nationality'],
        phone=data['phone'],
        email=data['email'],
        address=data['address'],
        pincode=data['pincode'],
    )

    price = (
                booking.trip.seats
                .filter(seat__coach__coach_type=booking.coach_type)
                .values_list('seat_price', flat=True)
                .first()
            )

    TrainBookingSeat.objects.create(
        passenger=passenger,
        price=price,
    )

    return JsonResponse({
        "success": True,
        "passenger_id": passenger.id,
        "age_label": age_label,
        "price":price,
    })




@require_POST
@login_required
def delete_passenger(request, passenger_id):
    passenger = Passenger.objects.filter(id=passenger_id, booking__user=request.user).first()
    
    if not passenger:
        return JsonResponse({"success": False, "error": "Passenger not found"})

    seat_obj = TrainBookingSeat.objects.filter(passenger=passenger).first()

    if not seat_obj:
        return JsonResponse({"success": False, "error": "Passenger not found"})


    passenger.delete()

    return JsonResponse({
        "success": True,
    })





@require_POST
@login_required
def create_payment_order(request, booking_id):

    booking = TrainBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending'
    ).first()

    if not booking:
        return JsonResponse({"success": False})
    
    price = (
                booking.trip.seats
                .filter(seat__coach__coach_type=booking.coach_type)
                .values_list('seat_price', flat=True)
                .first()
            )

    if booking.trip.is_booking_closed==False:

        total_passengers = TrainBookingSeat.objects.filter(passenger__booking=booking).count()

        booking.total_passengers = total_passengers

        # 🔥 CALCULATE FINAL AMOUNT
        data = calculate_booking_amount(booking)

        # 🔥 SAVE IN BOOKING
        
        booking.total_ticket_amount = data["ticket"]
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

    seat_count = booking.total_passengers
    
    # 🔒 lock seats permanently
    available_seats = TrainSeatAvailability.objects.filter(
        trip=booking.trip,
        seat__coach__coach_type=booking.coach_type,
        status='available'
    ).order_by('seat__seat_number')[:seat_count]
    
    if not available_seats:
        
        if payment:
            payment.payment_status = 'failed'
            payment.error_description = str(e)
            payment.save()

        return JsonResponse({"success": False})


    booking_seats = TrainBookingSeat.objects.filter(
        passenger__booking=booking,
        seat__isnull=True   # only unassigned
    )
    
    for booking_seat, seat in zip(booking_seats, available_seats):

        seat.status = 'booked'
        seat.is_booked = True
        seat.locked_by = None
        seat.locked_at = None
        seat.booked_at = timezone.now()
        seat.save()

        # 💺 assign seat to passenger
        booking_seat.seat = seat.seat
        booking_seat.save()


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

    booking = TrainBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking and booking.expires_at <= timezone.now():

        booking.status = 'cancelled'
        booking.cancelled_at = timezone.now()
        booking.save()

        TrainBookingSeat.objects.filter(
            passenger__booking=booking
        ).delete()

        Payment.objects.filter(
            booking=booking,
            booking__status='cancelled',
            payment_status='pending',
        ).update(
            payment_status = 'cancelled',
            error_description = 'Payment cancelled',
        )



        # clear session
        for key in ['booking_id', 'trip_id', 'coach_type', 'just_created_booking']:
            request.session.pop(key, None)

        messages.warning(request, "Booking cancelled successfully.")
        return JsonResponse({"success": True})
    
    else:
        messages.warning(request, "Error in cancel booking.")
        return JsonResponse({"success": False})




@require_POST
@login_required
def cancel_booking(request, booking_id):

    booking = TrainBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking:

        booking.status = 'cancelled'
        booking.cancelled_at = timezone.now()
        booking.save()

        TrainBookingSeat.objects.filter(
            passenger__booking=booking
        ).delete()

        # clear session
        for key in ['booking_id', 'trip_id', 'coach_type', 'just_created_booking']:
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

    booking = TrainBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='confirmed'
    ).select_related('trip__schedule__boarding','trip__schedule__arrival').first()

    if not booking:
        messages.error(request, "Error in booking.")
        return redirect('booking_app:index_page')

    return render(request, "train_booking/payment_success.html", {
        "booking": booking
    })


@login_required
def payment_failed(request, booking_id):

    booking = TrainBooking.objects.filter(
        id=booking_id,
        user=request.user
    ).select_related('trip__schedule__boarding','trip__schedule__arrival').first()

    return render(request, "train_booking/payment_failed.html", {
        "booking": booking
    })


