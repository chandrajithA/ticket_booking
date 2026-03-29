from django.urls import path
from .views import *

app_name = 'booking_app'

urlpatterns = [
    path('', index_page, name='index_page'),   
]