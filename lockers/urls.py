from django.urls import path
from . import views

urlpatterns = [
    path('qr/<uuid:token>/', views.qr_landing, name='locker_qr'),
    path('manage/', views.manage_lockers, name='manage_lockers'),
    path('manage/<int:locker_id>/toggle-online/', views.toggle_online, name='toggle_online'),
    path('manage/<int:locker_id>/init-compartments/', views.init_compartments, name='init_compartments'),
    path('manage/compartment/<int:compartment_id>/toggle/', views.toggle_compartment_status, name='toggle_compartment'),
    path('manage/<int:locker_id>/regenerate-qr/', views.regenerate_qr, name='regenerate_qr'),
]
