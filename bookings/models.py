import uuid
from django.db import models
from django.contrib.auth.models import User
from lockers.models import Compartment


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Chờ xác nhận'),
        (STATUS_ACTIVE, 'Đang sử dụng'),
        (STATUS_COMPLETED, 'Đã trả'),
        (STATUS_CANCELLED, 'Đã huỷ'),
    ]

    user = models.ForeignKey(User, related_name='bookings', on_delete=models.CASCADE)
    compartment = models.ForeignKey(Compartment, related_name='bookings', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    unlock_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    note = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} — {self.compartment} [{self.status}]"

    class Meta:
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-started_at']
