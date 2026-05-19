from django.core.management.base import BaseCommand
from django.conf import settings
from lockers.models import Locker
from lockers.signals import _generate_qr


class Command(BaseCommand):
    help = "Gen lại QR code cho tất cả (hoặc một số) tủ với SITE_URL hiện tại"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ids",
            nargs="*",
            type=int,
            help="Danh sách ID tủ cần gen lại (bỏ trống = tất cả)",
        )

    def handle(self, *args, **options):
        ids = options.get("ids")
        qs = Locker.objects.filter(pk__in=ids) if ids else Locker.objects.all()

        if not qs.exists():
            self.stdout.write(self.style.WARNING("Không tìm thấy tủ nào."))
            return

        self.stdout.write(f"SITE_URL hiện tại: {settings.SITE_URL}")
        self.stdout.write(f"Bắt đầu gen lại QR cho {qs.count()} tủ...")

        ok, fail = 0, 0
        for locker in qs:
            try:
                url = _generate_qr(locker)
                self.stdout.write(self.style.SUCCESS(f"  ✓ {locker.name} → {url}"))
                ok += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ {locker.name}: {e}"))
                fail += 1

        self.stdout.write(f"\nHoàn tất: {ok} thành công, {fail} lỗi.")
