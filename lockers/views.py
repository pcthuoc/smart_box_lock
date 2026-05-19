from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Prefetch
from .models import Locker, Compartment

staff_required = user_passes_test(lambda u: u.is_staff, login_url='login')


@login_required(login_url='login')
def qr_landing(request, token):
    """Trang hiện ra khi user quét QR của tủ — chọn ngăn để gửi đồ."""
    from bookings.models import Booking
    locker = get_object_or_404(Locker, uuid_token=token)

    active_bookings_qs = Booking.objects.filter(status='active').select_related('user')
    compartments = list(locker.compartments.prefetch_related(
        Prefetch('bookings', queryset=active_bookings_qs, to_attr='active_bookings')
    ).order_by('number'))

    # Gán my_booking và tổng hợp user_bookings
    user_bookings = []
    for comp in compartments:
        bk = next((b for b in comp.active_bookings if b.user == request.user), None)
        comp.my_booking = bk
        if bk:
            user_bookings.append(bk)

    # Chuẩn bị layout vật lý như manage_lockers
    locker.comp_left   = next((c for c in compartments if c.number == 1), None)
    locker.comp_middle = [c for c in compartments if 2 <= c.number <= 5]
    locker.comp_right  = next((c for c in compartments if c.number == 6), None)
    locker.has_compartments = bool(compartments)

    # Tất cả booking của user (dùng để hiện lịch sử ở bottom của trang)
    all_user_bookings = list(
        request.user.bookings
        .select_related('compartment__locker')
        .order_by('-started_at')[:20]
    )

    context = {
        'locker': locker,
        'compartments': compartments,
        'user_bookings': user_bookings,
        'all_user_bookings': all_user_bookings,
    }
    return render(request, 'lockers/qr_landing.html', context)


@staff_required
def manage_lockers(request):
    """Admin: danh sách tất cả tủ + trạng thái ngăn."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        location = request.POST.get('location', '').strip()
        description = request.POST.get('description', '').strip()
        if name and location:
            Locker.objects.create(name=name, location=location, description=description)
            messages.success(request, f'Đã thêm tủ "{name}" thành công.')
        else:
            messages.error(request, 'Tên tủ và địa điểm không được để trống.')
        return redirect('manage_lockers')

    from bookings.models import Booking
    active_bookings_qs = Booking.objects.filter(status='active').select_related('user')
    compartments_qs = Compartment.objects.order_by('number').prefetch_related(
        Prefetch('bookings', queryset=active_bookings_qs, to_attr='active_bookings')
    )
    lockers = list(Locker.objects.prefetch_related(
        Prefetch('compartments', queryset=compartments_qs)
    ).all())

    # Gom ngăn theo vị trí vật lý: trái(1), giữa(2-5), phải(6)
    for locker in lockers:
        comps = list(locker.compartments.all())
        locker.comp_left   = next((c for c in comps if c.number == 1), None)
        locker.comp_middle = [c for c in comps if 2 <= c.number <= 5]
        locker.comp_right  = next((c for c in comps if c.number == 6), None)
        locker.has_compartments = bool(comps)

    context = {'lockers': lockers, 'segment': 'manage_lockers'}
    return render(request, 'lockers/manage_lockers.html', context)


@staff_required
def toggle_online(request, locker_id):
    """Admin: bật/tắt trạng thái online của tủ."""
    locker = get_object_or_404(Locker, pk=locker_id)
    if request.method == 'POST':
        locker.is_online = not locker.is_online
        locker.save()
        status = 'Online' if locker.is_online else 'Offline'
        messages.success(request, f'{locker.name} đã chuyển sang {status}.')
    return redirect('manage_lockers')


@staff_required
def init_compartments(request, locker_id):
    """Admin: tự động tạo 6 ngăn cho tủ (chỉ tạo những ngăn chưa có)."""
    locker = get_object_or_404(Locker, pk=locker_id)
    if request.method == 'POST':
        created = 0
        for num in range(1, 7):
            _, is_new = Compartment.objects.get_or_create(locker=locker, number=num)
            if is_new:
                created += 1
        if created:
            messages.success(request, f'Đã tạo {created} ngăn mới cho {locker.name}.')
        else:
            messages.info(request, f'{locker.name} đã có đủ 6 ngăn rồi.')
    return redirect('manage_lockers')


@staff_required
def toggle_compartment_status(request, compartment_id):
    """Admin: chuyển trạng thái ngăn (available ↔ maintenance)."""
    compartment = get_object_or_404(Compartment, pk=compartment_id)
    if request.method == 'POST':
        if compartment.status == Compartment.STATUS_MAINTENANCE:
            compartment.status = Compartment.STATUS_AVAILABLE
            msg = f'Ngăn {compartment.number} đã mở lại.'
        elif compartment.status == Compartment.STATUS_AVAILABLE:
            compartment.status = Compartment.STATUS_MAINTENANCE
            msg = f'Ngăn {compartment.number} đã khoá bảo trì.'
        else:
            msg = f'Ngăn {compartment.number} đang có người dùng, không thể thay đổi.'
        compartment.save()
        messages.info(request, msg)
    return redirect('manage_lockers')


@staff_required
def regenerate_qr(request, locker_id):
    """Admin: gen lại QR code cho tủ với SITE_URL hiện tại."""
    locker = get_object_or_404(Locker, pk=locker_id)
    if request.method == 'POST':
        from .signals import _generate_qr
        try:
            url = _generate_qr(locker)
            messages.success(request, f'Đã gen lại QR cho {locker.name} → {url}')
        except Exception as e:
            messages.error(request, f'Lỗi gen QR: {e}')
    return redirect('manage_lockers')
