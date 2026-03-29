from django.urls import path
from .views import *

app_name = 'accounts'

urlpatterns = [
    path('login/', login_page, name='login_page'),   
    path('signup/', signup_page, name='signup_page'),
    path('user_logout/', user_logout, name='user_logout'),    
]