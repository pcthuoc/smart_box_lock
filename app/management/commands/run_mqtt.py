"""
Django management command để chạy MQTT service.
Cách dùng:
    python manage.py run_mqtt
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Khởi động MQTT service xử lý lệnh mở/đóng tủ khóa thông minh'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('[run_mqtt] Starting MQTT service...'))
        from services.mqtt_service import start_scheduler
        start_scheduler()
