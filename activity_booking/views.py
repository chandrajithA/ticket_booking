from django.shortcuts import render, redirect
from .models import *
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import uuid
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_POST
import json
from django.http import JsonResponse
from activity_booking.utils.booking_cleanup import clean_expired_bookings
from .models import Payment
import razorpay
from django.views.decorators.csrf import csrf_exempt
from activity_booking.payment_utils import calculate_booking_amount
from django.db.models import Q
from django.db import transaction
from django.db.models.functions import Cast
from django.db.models import IntegerField

@login_required
def activities_display(request):

    clean_expired_bookings()

    events = Event.objects.select_related('city').order_by('event_date')

    # FILTER OPTIONS
    event_types = sorted(set(
        events.values_list("category__name", flat=True)
    ))

    cities = sorted(set(
        events.values_list("city__name", flat=True)
    ))

    prices = events.values_list("seat_price", flat=True)

    context = {
        'events': events,
        'event_types': event_types,
        'cities': cities,
        'min_price': min(prices) if prices else 0,
        'max_price': max(prices) if prices else 100000,
    }

    return render(request, "activity_booking/activities_display.html", context)



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


def filter_activities(request):

    data = json.loads(request.body)

    qs = Event.objects.select_related('category', 'city').all().order_by('event_date')

    # SEARCH (teams)
    if data.get("search"):
        qs = qs.filter(
            Q(title__icontains=data["search"]) 
        )

    if data.get("date"):
        qs = qs.filter(event_date=data["date"])

    # CITY
    if data.get("city"):
        qs = qs.filter(city__name=data["city"])

    # SPORT TYPE
    if data.get("event"):
        qs = qs.filter(category__name=data["event"])

    # PRICE RANGE
    if data.get("min_price") is not None:
        qs = qs.filter(seat_price__gte=data["min_price"])

    if data.get("max_price") is not None:
        qs = qs.filter(seat_price__lte=data["max_price"])


    # RESPONSE
    events = [{
        "id": e.id,
        "title": e.title,
        "poster": e.poster.url if e.poster else "",
        "sport": e.category.name,
        "date": e.event_date.strftime("%B %d, %Y"),
        "time": f'{e.event_start_time.strftime("%I:%M %p")} - {e.event_end_time.strftime("%I:%M %p")}',
        "city": f'{e.address}, {e.city.name}',
        "price": e.seat_price,
    } for e in qs]

    return JsonResponse({"events": events})


        
    

@require_POST
def initiate_booking(request, event_id):     

    if request.method == "POST":

        event = Event.objects.filter(id=event_id, is_booking_closed=False).first()
        
        if event:

            seats = EventSeatAvailability.objects.filter(
                event=event,
                status='available',
                is_booked=False
            )

            if not seats:

                
                messages.error(request, "Some seats already taken.")
                return redirect("activity_booking:activities_display")
        
            

            # store in session
            request.session['event_id'] = event_id
        
            booking = EventBooking.objects.create(
                user=request.user,
                event=event,
                booking_reference=str(uuid.uuid4())[:10].upper(),
                total_ticket_amount=0,
                tax=0,
                total_amount=0,
                status='pending',
                expires_at=timezone.now() + timedelta(minutes=10)

            )

            # store booking id also
            request.session['booking_id'] = booking.id
            request.session['just_created_booking'] = True
            
            return JsonResponse({
                    "success": True,
                    "redirect_url": f"/activities/booking-details/{booking.id}/"
                })

    else:
        messages.info(request, "Events event not found.")
        return redirect('activity_booking:activities_display')   
    
        


@login_required
def booking_details(request, current_booking_id):   
        
    if request.session.pop('just_created_booking', False):

        session_booking_id = request.session.get('booking_id')
        event_id = request.session.get('event_id')

        if not session_booking_id or not event_id:
            return redirect('activity_booking:activities_display')
        
        # ✅ Match session booking with URL booking
        if int(session_booking_id) != int(current_booking_id):
            return redirect('activity_booking:activities_display')

        booking = EventBooking.objects.filter(id=current_booking_id,user=request.user, status='pending').select_related('event').first()
        if not booking:
            return redirect('activity_booking:activities_display')
       

        single_ticket_price = booking.event.seat_price

        return render(request, 'activity_booking/booking_details.html', {
            'booking': booking,
            'single_ticket_price':single_ticket_price,
            'expiry_time': booking.expires_at.timestamp(),
        })

    else:
        # SECOND visit → delete old booking

        booking = EventBooking.objects.filter(
            id=current_booking_id,
            user=request.user,
            status='pending'
        ).first()

        if booking:

            # cancel booking (not delete)
            booking.status = 'cancelled'
            booking.cancelled_at = timezone.now()
            booking.save()

            # clear session
            for key in ['booking_id', 'event_id', 'just_created_booking']:
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
        return redirect('activity_booking:activities_display')
    

        





@require_POST
@login_required
def create_payment_order(request, booking_id):

    booking = EventBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending'
    ).first()

    if not booking:
        return JsonResponse({"success": False})
    
    data = json.loads(request.body)

    ticket_count = int(data.get("ticket_count"))
    
    booking.total_ticket = ticket_count
    booking.save()

    with transaction.atomic(): 

        # 🔒 lock seats permanently
        available_seats = EventSeatAvailability.objects.select_for_update().annotate(
            seat_num_int=Cast('seat_number', IntegerField())
        ).filter(
            event=booking.event,
            status='available',
            is_booked=False,
        ).order_by('seat_num_int')[:ticket_count]

        if available_seats.count() != ticket_count:
            return JsonResponse({
                "success": False,
                "message": "Seat Booking Error. Try again."
            })
        
        for seat in available_seats:
            seat.status='locked'
            seat.locked_by=request.user
            seat.locked_at=timezone.now()
            seat.save()

            EventBookingSeat.objects.create(
                booking=booking,
                seat=seat,
                price=booking.event.seat_price
            )

    if booking.event.is_booking_closed==False:

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
    EventSeatAvailability.objects.filter(
        event=booking.event,
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

    booking = EventBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking and booking.expires_at <= timezone.now():
        EventSeatAvailability.objects.filter(
            event=booking.event,
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

        EventBookingSeat.objects.filter(
            booking=booking
        ).delete()

        # clear session
        for key in ['booking_id', 'event_id', 'just_created_booking']:
            request.session.pop(key, None)

        messages.warning(request, "Booking cancelled successfully.")
        return JsonResponse({"success": True})
    
    else:
        messages.warning(request, "Error in cancel booking.")
        return JsonResponse({"success": False})




@require_POST
@login_required
def cancel_booking(request, booking_id):

    booking = EventBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking:
        EventSeatAvailability.objects.filter(
            event=booking.event,
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

        EventBookingSeat.objects.filter(
            booking=booking
        ).delete()

        # clear session
        for key in ['booking_id', 'event_id', 'just_created_booking']:
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

    booking = EventBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='confirmed'
    ).select_related('event','event__city').first()

    if not booking:
        messages.error(request, "Error in booking.")
        return redirect('booking_app:index_page')
    
    booking_seats = EventBookingSeat.objects.filter(
        booking=booking
    ).select_related('seat')

    return render(request, "activity_booking/payment_success.html", {
        "booking": booking,
        'booking_seats': booking_seats,
    })


@login_required
def payment_failed(request, booking_id):

    booking = EventBooking.objects.filter(
        id=booking_id,
        user=request.user
    ).select_related('event','event__city').first()

    return render(request, "activity_booking/payment_failed.html", {
        "booking": booking
    })