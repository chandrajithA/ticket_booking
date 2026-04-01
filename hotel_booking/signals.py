from .models import HotelRoomAvailability, HotelBookingRoom, Hotel
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Hotel)
def create_room_for_hotel(sender, instance, created, **kwargs):
    if created:
        if instance.room_count and not HotelRoomAvailability.objects.filter(hotel=instance).exists():
            create_hotel_room(instance)



def create_hotel_room(hotel):

    total_rooms = hotel.room_count

    room_objects = []

    for i in range(1, total_rooms + 1):
        room_objects.append(
            HotelRoomAvailability(
                hotel=hotel,
                room_number=i,   # ✅ store directly here
            )
        )

    HotelRoomAvailability.objects.bulk_create(room_objects)




def get_booked_room_ids(hotel, check_in, check_out):

    return HotelBookingRoom.objects.filter(
        booking__hotel=hotel,
        booking__status__in=['confirmed']
    ).filter(
        Q(booking__check_in__lt=check_out) &
        Q(booking__check_out__gt=check_in)
    ).values_list('room_id', flat=True)




def get_available_rooms(hotel, check_in, check_out):

    booked_room_ids = get_booked_room_ids(hotel, check_in, check_out)

    return HotelRoomAvailability.objects.filter(
        hotel=hotel
    ).exclude(id__in=booked_room_ids)