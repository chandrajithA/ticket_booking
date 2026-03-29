from django.shortcuts import render


def index_page(request):
    return render(request, 'booking_app/index_page.html')