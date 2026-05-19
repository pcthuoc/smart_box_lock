import io
import qrcode
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.files.base import ContentFile
from django.conf import settings
from .models import Locker


def _generate_qr(instance):
    """Tạo QR code cho locker, luôn dùng SITE_URL hiện tại."""
    qr_url = f"{settings.SITE_URL}/lockers/qr/{instance.uuid_token}/"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # Xoá ảnh cũ nếu có
    if instance.qr_code:
        try:
            instance.qr_code.delete(save=False)
        except Exception:
            pass

    filename = f"locker_{instance.pk}_{instance.uuid_token}.png"
    instance.qr_code.save(filename, ContentFile(buffer.read()), save=True)
    return qr_url


@receiver(post_save, sender=Locker)
def generate_qr_code(sender, instance, created, **kwargs):
    """Tự động gen QR code khi tạo Locker mới."""
    if created and not instance.qr_code:
        _generate_qr(instance)
