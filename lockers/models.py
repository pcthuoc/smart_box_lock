import uuid
from django.db import models


class Locker(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    is_online = models.BooleanField(default=True)
    uuid_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qr_code = models.ImageField(upload_to='lockers/qrcodes/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.location})"

    class Meta:
        verbose_name = 'Locker'
        verbose_name_plural = 'Lockers'


class Compartment(models.Model):
    STATUS_AVAILABLE = 'available'
    STATUS_OCCUPIED = 'occupied'
    STATUS_MAINTENANCE = 'maintenance'
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Trống'),
        (STATUS_OCCUPIED, 'Đang dùng'),
        (STATUS_MAINTENANCE, 'Bảo trì'),
    ]

    locker = models.ForeignKey(Locker, related_name='compartments', on_delete=models.CASCADE)
    number = models.PositiveSmallIntegerField()  # 1-6
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)

    def __str__(self):
        return f"{self.locker.name} — Ngăn {self.number}"

    class Meta:
        verbose_name = 'Compartment'
        verbose_name_plural = 'Compartments'
        unique_together = ('locker', 'number')
        ordering = ['locker', 'number']
