# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import path, include  # add this

urlpatterns = [
    path('admin/', admin.site.urls),                          # Django admin route
    path('customers/', include("customers.urls")),             # Profile route
    path('lockers/', include("lockers.urls")),                 # Locker / QR route
    path('bookings/', include("bookings.urls")),               # Booking route
    path("", include("app.urls")),                            # UI Kits Html files
    path("", include("authentication.urls")),                  # Auth routes - login / register
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
