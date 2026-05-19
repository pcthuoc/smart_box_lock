from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'compartment', 'status', 'started_at', 'ended_at')
    list_filter = ('status', 'compartment__locker')
    search_fields = ('user__username', 'compartment__locker__name')
    readonly_fields = ('unlock_token', 'started_at')
