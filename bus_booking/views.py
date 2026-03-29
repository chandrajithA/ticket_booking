from django.shortcuts import render, redirect
from .models import *
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import uuid
from django.db.models import Sum, Max
from django.utils import timezone
from datetime import timedelta, datetime
from django.views.decorators.http import require_POST
import json
from django.http import JsonResponse
from bus_booking.utils.booking_cleanup import clean_expired_bookings
from .models import Payment
import razorpay
from django.views.decorators.csrf import csrf_exempt
from bus_booking.payment_utils import calculate_booking_amount
from datetime import date
from django.db.models import Q



def bus_display(request):
    

    trips = BusTrip.objects.filter(is_booking_closed=False).select_related(
        'schedule__bus',
        'schedule__boarding',
        'schedule__arrival'
    ).all().order_by('travel_date')


    travels = sorted(set(
        trips.values_list("schedule__bus__brand__name", flat=True)
    ))

    stops = sorted(set(
        trips.values_list("schedule__stops", flat=True)
    ))

    # ✅ MAX PRICE
    max_price = trips.aggregate(Max("base_price"))["base_price__max"] or 10000

    

    context = {
        'min_price':  0,
        'max_price':  max_price,
        'trips': trips,
        'travels': list(travels),
        'stops': list(stops),
    }
    return render(request, "bus_booking/bus_display.html", context)


def format_duration_py(duration):
    total_seconds = int(duration.total_seconds())

    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    minutes = (total_seconds % 3600) // 60

    parts = []

    if days > 0:
        parts.append(f"{days}d")

    if hours > 0:
        parts.append(f"{hours}h")

    if minutes > 0:
        parts.append(f"{minutes}m")

    return " ".join(parts)


def filter_bus(request):

    data = json.loads(request.body)

    qs = BusTrip.objects.filter(is_booking_closed=False).select_related(
        'schedule__bus__brand',
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

    if data.get("departure_slots"):
        dep_q = Q()

        for slot in data["departure_slots"]:
            start, end = map(int, slot.split("-"))

            dep_q |= Q(
                schedule__boarding_time__hour__gte=start,
                schedule__boarding_time__hour__lt=end
            )

        qs = qs.filter(dep_q)

    if data.get("arrival_slots"):
        arr_q = Q()

        for slot in data["arrival_slots"]:
            start, end = map(int, slot.split("-"))

            arr_q |= Q(
                schedule__arrival_time__hour__gte=start,
                schedule__arrival_time__hour__lt=end
            )

        qs = qs.filter(arr_q)

    # PRICE
    min_price = data.get("min_price", 0)
    max_price = data.get("max_price", 10000)

    qs = qs.filter(base_price__gte=min_price, base_price__lte=max_price)

    # AIRLINE
    if data.get("travels"):
        qs = qs.filter(schedule__bus__brand__name__in=data["travels"])

    # STOPS
    if data.get("stops"):
        qs = qs.filter(schedule__stops__in=data["stops"])

    # UNIQUE FILTER DATA
    travels = qs.values_list(
        "schedule__bus__brand__name", flat=True
    ).distinct()

    max_price = qs.aggregate(Max("base_price"))["base_price__max"] or 0

    stops = qs.values_list("schedule__stops", flat=True).distinct()

    # RESPONSE
    buses = [{
        "id": t.id,
        "bus_name": t.schedule.bus.bus_name,
        "bus_number": t.schedule.bus.bus_number,
        "bus_is_ac": t.schedule.bus.is_ac,
        "logo": t.schedule.bus.brand.picture.url if t.schedule.bus.brand.picture else "",
        "price": t.base_price,
        "stops": t.schedule.stops,

        "departure": t.schedule.boarding_time.strftime("%I:%M %p"),
        "arrival": t.schedule.arrival_time.strftime("%I:%M %p"),
        "travel_date": t.travel_date,

        "source": t.schedule.boarding.city,
        "destination": t.schedule.arrival.city,

        "source_name": t.schedule.boarding.name,
        "destination_name": t.schedule.arrival.name,

        "duration": format_duration_py(t.schedule.duration),  # or format it

        "available_seats": t.available_seats,
    } for t in qs]

    return JsonResponse({
        "buses": buses,
        
    })



def seat_selection(request, trip_id):
    
    clean_expired_bookings()

    seats = BusSeatAvailability.objects.filter(trip_id=trip_id, trip__is_booking_closed=False).select_related(
            'seat','trip__schedule__bus', 'trip__schedule__boarding', 'trip__schedule__arrival' 
        ).order_by('seat__row', 'seat__column')
        
    if(seats):

        lower_seats = seats.filter(seat__floor_choice='lower')
        upper_seats = seats.filter(seat__floor_choice='upper')

        def group_by_row(seats):
            seat_rows = defaultdict(list)
            for s in seats:
                seat_rows[s.seat.row].append(s)

            for row in seat_rows:
                seat_rows[row] = sorted(seat_rows[row], key=lambda x: x.seat.column)

            return dict(seat_rows)


        context = {
            "lower_seat_rows": group_by_row(lower_seats),
            "upper_seat_rows": group_by_row(upper_seats),
            "trip_id": trip_id,
        }

        return render(request, "bus_booking/bus_seatlayout.html", context)
    else:
        messages.info(request, "Bus not found.")
        return redirect('bus_booking:bus_display')
        
    

@require_POST
@login_required
def initiate_booking(request, trip_id):     

    if request.method == "POST":

        trip = BusTrip.objects.filter(id=trip_id, is_booking_closed=False).first()
        
        if trip:

            selected_seats = request.POST.get('selected_seats')

            if not selected_seats:
                return redirect("bus_booking:seat_selection", trip_id=trip_id)
        
            selected_seats_list = selected_seats.split(',')

            if selected_seats_list:

                seats = BusSeatAvailability.objects.filter(
                    trip=trip,
                    seat__seat_number__in=selected_seats_list,
                    status='available',
                    is_booked=False
                )

                if seats.count() != len(selected_seats_list):
                    messages.error(request, "Some seats already taken.")
                    return redirect("bus_booking:seat_selection", trip_id=trip_id)
                
                #  Lock them
                seats.update(
                    status='locked',
                    locked_by=request.user,
                    locked_at=timezone.now()
                )

                # store in session
                request.session['selected_seats'] = selected_seats_list
                request.session['trip_id'] = trip_id
            
                booking = BusBooking.objects.create(
                    user=request.user,
                    trip=trip,
                    booking_reference=str(uuid.uuid4())[:10].upper(),
                    total_passengers=len(selected_seats_list),
                    total_ticket_amount=0,
                    tax=0,
                    total_amount=0,
                    status='pending',
                    expires_at=timezone.now() + timedelta(minutes=10)

                )

                # store booking id also
                request.session['booking_id'] = booking.id
                request.session['just_created_booking'] = True
                return redirect('bus_booking:passenger_details', current_booking_id=booking.id)

        else:
            messages.info(request, "Bus not found.")
            return redirect('bus_booking:bus_display')   
    
        


@login_required
def passenger_details(request, current_booking_id):   
        
    if request.session.pop('just_created_booking', False):

        session_booking_id = request.session.get('booking_id')
        trip_id = request.session.get('trip_id')
        selected_seats_list = request.session.get('selected_seats')

        if not session_booking_id or not trip_id or not selected_seats_list:
            return redirect('bus_booking:bus_display')
        
        # ✅ Match session booking with URL booking
        if int(session_booking_id) != int(current_booking_id):
            return redirect('bus_booking:bus_display')

        booking = BusBooking.objects.filter(id=current_booking_id,user=request.user, status='pending').select_related('trip').first()
        if not booking:
            return redirect('bus_booking:bus_display')
        
        trip = booking.trip

        selected_seat = trip.seats.filter(seat__seat_number__in=selected_seats_list).select_related(
            'seat',
            'trip__schedule__bus__brand'
        )

        total_ticket_price = selected_seat.aggregate(total=Sum('seat_price'))['total'] or 0

        passenger_count = len(selected_seat)
        passenger_range = range(1, passenger_count + 1)

        return render(request, 'bus_booking/passenger_details.html', {
            'booking': booking,
            'seat_list': selected_seat,
            'passenger_count':passenger_range,
            'total_ticket_price':total_ticket_price,
            'expiry_time': booking.expires_at.timestamp(),
        })

    else:
        # SECOND visit → delete old booking

        booking = BusBooking.objects.filter(
            id=current_booking_id,
            user=request.user,
            status='pending'
        ).first()

        if booking:

            # 🔓 unlock seats
            BusSeatAvailability.objects.filter(
                trip=booking.trip,
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

            BusBookingSeat.objects.filter(
                passenger__booking=booking
            ).delete()

            # clear session
            for key in ['booking_id', 'trip_id', 'selected_seats', 'just_created_booking']:
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
        return redirect('bus_booking:seat_selection', trip_id=booking.trip.id)
    

        


@require_POST
@login_required
def add_passenger(request, booking_id):
    data = json.loads(request.body)

    dob = data.get('dob')

    age = None
    dob_obj = None
    age_label = None

    if dob and dob.strip():
        dob_obj = datetime.strptime(dob, "%Y-%m-%d").date()
        today = date.today()
        age = today.year - dob_obj.year - (
            (today.month, today.day) < (dob_obj.month, dob_obj.day)
        )

        if age == 0:
            age_label = "below 1"
        else:
            age_label = str(age)

    booking = BusBooking.objects.filter(id=booking_id, user=request.user, status='pending').first()
    if not booking:
        return JsonResponse({"success": False, "error": "Invalid booking"})

    seat_obj = BusSeatAvailability.objects.select_related('seat').filter(
            seat__id=data['seat_id'],
            trip=booking.trip,
            status='locked',
            locked_by=request.user
        ).first()
    
    if not seat_obj:
        return JsonResponse({"success": False, "error": "Seat not available. Kindly Cancel and Rebook."})

    passenger = Passenger.objects.create(
        booking=booking,
        passenger_number=data['passenger_number'],
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

    BusBookingSeat.objects.create(
        seat=seat_obj.seat,
        passenger=passenger,
        price=seat_obj.seat_price,
    )

    return JsonResponse({
        "success": True,
        "passenger_id": passenger.id,
        "seat_number": seat_obj.seat.seat_number,
        "seat_class": seat_obj.seat.seat_class,
        "seat_floor": seat_obj.seat.floor_choice,
        "age_label": age_label,
    })




@require_POST
@login_required
def delete_passenger(request, passenger_id):
    passenger = Passenger.objects.filter(id=passenger_id, booking__user=request.user).first()
    
    if not passenger:
        return JsonResponse({"success": False, "error": "Passenger not found"})

    seat_obj = BusBookingSeat.objects.filter(passenger=passenger).first()

    if not seat_obj:
        return JsonResponse({"success": False, "error": "Seat mapping missing"})
    
    seat = seat_obj.seat

    seat_availability = BusSeatAvailability.objects.filter(
        seat=seat,
        trip=passenger.booking.trip,
        locked_by=request.user   # 🔥 ensure same user
    ).first()

    if not seat_availability:
        return JsonResponse({
            "success": False,
            "error": "Unauthorized action or seat lock expired"
        })

    passenger.delete()

    return JsonResponse({
        "success": True,
        "seat_number": seat.seat_number,
        "seat_class": seat.seat_class,
        "seat_floor": seat.floor_choice,
    })





@require_POST
@login_required
def create_payment_order(request, booking_id):

    booking = BusBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending'
    ).first()

    if not booking:
        return JsonResponse({"success": False})

    if booking.trip.is_booking_closed==False:

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

    # 🔒 lock seats permanently
    BusSeatAvailability.objects.filter(
        trip=booking.trip,
        locked_by=request.user,
        status='locked'
    ).update(
        status='booked',
        is_booked=True,
        locked_by=None,
        locked_at=None,
        booked_at=timezone.now()
    )

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

    booking = BusBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking and booking.expires_at <= timezone.now():
        BusSeatAvailability.objects.filter(
            trip=booking.trip,
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

        BusBookingSeat.objects.filter(
            passenger__booking=booking
        ).delete()

        # clear session
        for key in ['booking_id', 'trip_id', 'selected_seats', 'just_created_booking']:
            request.session.pop(key, None)

        messages.warning(request, "Booking cancelled successfully.")
        return JsonResponse({"success": True})
    
    else:
        messages.warning(request, "Error in cancel booking.")
        return JsonResponse({"success": False})




@require_POST
@login_required
def cancel_booking(request, booking_id):

    booking = BusBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking:
        BusSeatAvailability.objects.filter(
            trip=booking.trip,
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

        BusBookingSeat.objects.filter(
            passenger__booking=booking
        ).delete()

        # clear session
        for key in ['booking_id', 'trip_id', 'selected_seats', 'just_created_booking']:
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

    booking = BusBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='confirmed'
    ).select_related('trip__schedule__boarding','trip__schedule__arrival').first()

    if not booking:
        messages.error(request, "Error in booking.")
        return redirect('booking_app:index_page')

    return render(request, "bus_booking/payment_success.html", {
        "booking": booking
    })


@login_required
def payment_failed(request, booking_id):

    booking = BusBooking.objects.filter(
        id=booking_id,
        user=request.user
    ).select_related('trip__schedule__boarding','trip__schedule__arrival').first()

    return render(request, "bus_booking/payment_failed.html", {
        "booking": booking
    })


