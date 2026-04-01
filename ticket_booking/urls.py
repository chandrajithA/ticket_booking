"""
URL configuration for ticket_booking project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('booking_app.urls')),
    path("trains/", include("train_booking.urls")),
    path("buses/", include("bus_booking.urls")),
    path("flights/", include("flight_booking.urls")),
    path("movies/", include("movie_booking.urls")),
    path("sports/", include("sport_booking.urls")),
    path("events/", include("event_booking.urls")),
    path("activities/", include("activity_booking.urls")),
    path("hotels/", include("hotel_booking.urls")),
    path("users/", include("accounts.urls")), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
