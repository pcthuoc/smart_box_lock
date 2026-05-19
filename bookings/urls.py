from django.urls import path
from . import views

urlpatterns = [
    path('book/<int:compartment_id>/', views.book_compartment, name='book_compartment'),
    path('unlock/<uuid:unlock_token>/', views.unlock_compartment, name='unlock_compartment'),
    path('return/<uuid:unlock_token>/', views.return_compartment, name='return_compartment'),
    path('my/', views.my_bookings, name='my_bookings'),
]
