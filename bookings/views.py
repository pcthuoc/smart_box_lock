import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Booking
from lockers.models import Compartment

logger = logging.getLogger(__name__)


def _send_unlock_command(compartment):
    """
    Gửi lệnh MỞ KHÓA đến phần cứng (ESP32) qua MQTT.
    Tủ mặc định luôn khóa — server chỉ gửi lệnh mở, KHÔNG gửi lệnh khóa.
    Phần cứng tự khóa lại sau khi cửa đóng (server không can thiệp).

    Topic publish: smart_box/unlock/<compartment_id>
    Payload: {"compartment": <number>, "ts": <epoch>}
    """
    try:
        import time, json
        import paho.mqtt.publish as publish
        from django.conf import settings

        topic   = f'smart_box/locker/{compartment.locker.pk}'
        payload = json.dumps({
            'compartment': compartment.number,
            'ts': int(time.time()),
        })
        auth = None
        username = getattr(settings, 'MQTT_USERNAME', None)
        if username:
            auth = {'username': username, 'password': getattr(settings, 'MQTT_PASSWORD', '')}

        publish.single(
            topic,
            payload,
            qos=1,
            hostname=getattr(settings, 'MQTT_BROKER', 'localhost'),
            port=getattr(settings, 'MQTT_PORT', 1883),
            auth=auth,
        )
        logger.info(f'[MQTT] Unlock sent → {topic}')
    except Exception as e:
        # Không crash view nếu MQTT không available
        logger.warning(f'[MQTT] Could not send unlock command: {e}')


@login_required(login_url='login')
def book_compartment(request, compartment_id):
    """Đăng ký gửi đồ vào ngăn trống (POST từ trang QR landing)."""
    compartment = get_object_or_404(Compartment, pk=compartment_id)

    if compartment.status != Compartment.STATUS_AVAILABLE:
        messages.error(request, 'Ngăn này hiện không khả dụng.')
        return redirect('locker_qr', token=compartment.locker.uuid_token)

    if request.method == 'POST':
        note = request.POST.get('note', '')
        Booking.objects.create(
            user=request.user,
            compartment=compartment,
            note=note,
            status=Booking.STATUS_ACTIVE,
        )
        compartment.status = Compartment.STATUS_OCCUPIED
        compartment.save()
        messages.success(request, f'Đăng ký thành công! Ngăn {compartment.number} đã được đặt. Bạn có thể mở cửa ngay!')
        return redirect('locker_qr', token=compartment.locker.uuid_token)

    return redirect('locker_qr', token=compartment.locker.uuid_token)


@login_required(login_url='login')
def unlock_compartment(request, unlock_token):
    """Mở cửa ngăn tủ bằng unlock_token."""
    booking = get_object_or_404(Booking, unlock_token=unlock_token)

    if booking.user != request.user:
        messages.error(request, 'Bạn không có quyền mở ngăn này.')
        return redirect('my_bookings')

    if booking.status != Booking.STATUS_ACTIVE:
        messages.error(request, 'Booking này không còn hiệu lực.')
        return redirect('my_bookings')

    # Gửi lệnh mở khóa đến phần cứng — tủ tự khóa lại, không cần lệnh khóa
    _send_unlock_command(booking.compartment)
    messages.success(request, f'✅ Đã mở ngăn {booking.compartment.number} — {booking.compartment.locker.name}. Đến lấy đồ nhé!')
    return redirect('locker_qr', token=booking.compartment.locker.uuid_token)


@login_required(login_url='login')
def return_compartment(request, unlock_token):
    """Trả ngăn — kết thúc booking."""
    booking = get_object_or_404(Booking, unlock_token=unlock_token)

    if booking.user != request.user:
        messages.error(request, 'Bạn không có quyền thao tác booking này.')
        return redirect('my_bookings')

    if request.method == 'POST':
        booking.status = Booking.STATUS_COMPLETED
        booking.ended_at = timezone.now()
        booking.save()
        booking.compartment.status = Compartment.STATUS_AVAILABLE
        booking.compartment.save()
        messages.success(request, 'Đã trả ngăn thành công.')
        return redirect('locker_qr', token=booking.compartment.locker.uuid_token)

    return redirect('locker_qr', token=booking.compartment.locker.uuid_token)


@login_required(login_url='login')
def my_bookings(request):
    """Danh sách booking của user hiện tại.
    Nếu user đang có 1 active booking → redirect thẳng về trang tủ đó.
    Nếu nhiều tủ khác nhau hoặc không có active → render danh sách.
    """
    bookings = request.user.bookings.select_related('compartment__locker').all()
    active = [b for b in bookings if b.status == 'active']
    if active:
        # Redirect về tủ có active booking gần nhất
        locker = active[0].compartment.locker
        return redirect('locker_qr', token=locker.uuid_token)
    return render(request, 'bookings/my_bookings.html', {'bookings': bookings})
