from .signals import get_available_rooms
from django.db import transaction
from .models import *
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import uuid
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_POST
import json
from hotel_booking.utils.booking_cleanup import clean_expired_bookings
from .models import Payment
import razorpay
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from .constants import HOTEL_TAX_PERCENT
from datetime import datetime




@login_required
def hotels_display(request):

    clean_expired_bookings()

    hotels = Hotel.objects.select_related('city')

    # FILTER OPTIONS
    hotel_types = sorted(set(
        hotels.values_list("category__name", flat=True)
    ))

    cities = sorted(set(
        hotels.values_list("city__name", flat=True)
    ))

    prices = hotels.values_list("room_price", flat=True)

    context = {
        'hotels': hotels,
        'hotel_types': hotel_types,
        'cities': cities,
        'min_price': min(prices) if prices else 0,
        'max_price': max(prices) if prices else 100000,
    }

    return render(request, "hotel_booking/hotels_display.html", context)



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


def filter_hotels(request):

    data = json.loads(request.body)

    qs = Hotel.objects.select_related('category', 'city').all()

    # SEARCH (teams)
    if data.get("search"):
        qs = qs.filter(
            Q(title__icontains=data["search"]) 
        )
    

    # CITY
    if data.get("city"):
        qs = qs.filter(city__name=data["city"])

    # SPORT TYPE
    if data.get("hotel"):
        qs = qs.filter(category__name=data["hotel"])

    # PRICE RANGE
    if data.get("min_price") is not None:
        qs = qs.filter(room_price__gte=data["min_price"])

    if data.get("max_price") is not None:
        qs = qs.filter(room_price__lte=data["max_price"])


    # ✅ DATE AVAILABILITY FILTER
    checkin = data.get("checkin_date")
    checkout = data.get("checkout_date")

    filtered_hotels = []

    for h in qs:

        if checkin and checkout:
            available_rooms = get_available_rooms(h, checkin, checkout)

            if available_rooms.count() == 0:
                continue  # ❌ skip hotel if no rooms

        # ✅ Amenities list
        amenities = []

        if h.is_wifi:
            amenities.append("WiFi")
        if h.is_pool:
            amenities.append("Pool")
        if h.is_spa:
            amenities.append("Spa")
        if h.is_restaurant:
            amenities.append("Restaurant")
        if h.is_gym:
            amenities.append("Gym")
        if h.is_parking:
            amenities.append("Parking")

        filtered_hotels.append({
            "id": h.id,
            "title": h.title,
            "poster": h.poster.url if h.poster else "",
            "category": h.category.name,
            "title": h.title,
            "city": f"{h.address}, {h.city.name}",
            "price": h.room_price,
            "amenities": " | ".join(amenities)  # 🔥 IMPORTANT
        })

    return JsonResponse({"hotels": filtered_hotels})




@require_POST
def initiate_booking(request, hotel_id):     

    if request.method == "POST":

        hotel = Hotel.objects.filter(id=hotel_id, is_booking_closed=False).first()
        
        if hotel:

            rooms = HotelRoomAvailability.objects.filter(
                hotel=hotel,
            )

            if not rooms:

                
                messages.error(request, "Hotel Rooms not available")
                return redirect("hotel_booking:hotels_display")
        
            

            # store in session
            request.session['hotel_id'] = hotel_id
        
            booking = HotelBooking.objects.create(
                user=request.user,
                hotel=hotel,
                booking_reference=str(uuid.uuid4())[:10].upper(),
                total_room_amount=0,
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
                    "redirect_url": f"/hotels/booking-details/{booking.id}/"
                })

    else:
        messages.info(request, "Hotel not found")
        return redirect('hotel_booking:hotels_display')   
    
        


@login_required
def booking_details(request, current_booking_id):   
        
    if request.session.pop('just_created_booking', False):

        session_booking_id = request.session.get('booking_id')
        hotel_id = request.session.get('hotel_id')

        if not session_booking_id or not hotel_id:
            return redirect('hotel_booking:hotels_display')
        
        # ✅ Match session booking with URL booking
        if int(session_booking_id) != int(current_booking_id):
            return redirect('hotel_booking:hotels_display')

        booking = HotelBooking.objects.filter(id=current_booking_id,user=request.user, status='pending').select_related('hotel').first()
        if not booking:
            return redirect('hotel_booking:hotels_display')
       

        single_room_price = booking.hotel.room_price

        return render(request, 'hotel_booking/booking_details.html', {
            'booking': booking,
            'single_room_price':single_room_price,
            'expiry_time': booking.expires_at.timestamp(),
        })

    else:
        # SECOND visit → delete old booking

        booking = HotelBooking.objects.filter(
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
        return redirect('hotel_booking:hotels_display')
    





@require_POST
@login_required
def create_payment_order(request, booking_id):

    booking = HotelBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending'
    ).first()

    if not booking:
        return JsonResponse({"success": False})
    
    data = json.loads(request.body)

    room_count = int(data.get("room_count"))
    checkin = data.get("checkin")
    checkout = data.get("checkout")
    
    booking.check_in=datetime.strptime(checkin, "%Y-%m-%d")
    booking.check_out=datetime.strptime(checkout, "%Y-%m-%d")
    booking.total_room = room_count
    booking.save()

    with transaction.atomic(): 

        available_rooms = get_available_rooms(booking.hotel, checkin, checkout)

        if available_rooms.count() < room_count:
            return JsonResponse({
                "success": False,
                "message": "Not enough rooms available"
            })

        # 🔥 Step 2: Pick required rooms
        selected_rooms = available_rooms[:room_count]

        # 🔥 Step 3: Calculate price
        

        check_in_date = booking.check_in
        check_out_date = booking.check_out

        nights = (check_out_date - check_in_date).days
        total_room_amount = nights * room_count * float(booking.hotel.room_price)
        tax = total_room_amount * HOTEL_TAX_PERCENT / 100
        total_amount = total_room_amount + tax

        booking.total_room_amount = total_room_amount
        booking.tax = tax
        booking.total_amount = total_amount
        booking.save()

        # 🔥 Step 5: Assign rooms
        for room in selected_rooms:
            HotelBookingRoom.objects.create(
                booking=booking,
                room=room,
                price=booking.hotel.room_price
            )


    if booking.hotel.is_booking_closed==False:
 
        

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

    booking = HotelBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking and booking.expires_at <= timezone.now():

        booking.status = 'cancelled'
        booking.cancelled_at = timezone.now()
        booking.save()

        HotelBookingRoom.objects.filter(
            booking=booking
        ).delete()

        # clear session
        for key in ['booking_id', 'hotel_id', 'just_created_booking']:
            request.session.pop(key, None)

        messages.warning(request, "Booking cancelled successfully.")
        return JsonResponse({"success": True})
    
    else:
        messages.warning(request, "Error in cancel booking.")
        return JsonResponse({"success": False})




@require_POST
@login_required
def cancel_booking(request, booking_id):

    booking = HotelBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='pending',
    ).first()

    
    # 🔓 Unlock seats
    if booking:
        

        booking.status = 'cancelled'
        booking.cancelled_at = timezone.now()
        booking.save()

        HotelBookingRoom.objects.filter(
            booking=booking
        ).delete()

        # clear session
        for key in ['booking_id', 'hotel_id', 'just_created_booking']:
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

    booking = HotelBooking.objects.filter(
        id=booking_id,
        user=request.user,
        status='confirmed'
    ).select_related('hotel__city').first()

    if not booking:
        messages.error(request, "Error in booking.")
        return redirect('booking_app:index_page')
    
    booking_rooms = HotelBookingRoom.objects.filter(
        booking=booking
    ).select_related('room')

    return render(request, "hotel_booking/payment_success.html", {
        "booking": booking,
        'booking_rooms': booking_rooms,
    })


@login_required
def payment_failed(request, booking_id):

    booking = HotelBooking.objects.filter(
        id=booking_id,
        user=request.user
    ).select_related('hotel','hotel__city').first()

    return render(request, "hotel_booking/payment_failed.html", {
        "booking": booking
    })



