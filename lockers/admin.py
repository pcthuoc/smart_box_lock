from django.contrib import admin
from django.utils.html import format_html
from .models import Locker, Compartment
from .signals import _generate_qr


class CompartmentInline(admin.TabularInline):
    model = Compartment
    extra = 6
    max_num = 6
    fields = ("number", "status")


@admin.register(Locker)
class LockerAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "is_online", "compartment_count", "qr_preview", "created_at")
    list_filter = ("is_online",)
    search_fields = ("name", "location")
    readonly_fields = ("uuid_token", "qr_code", "qr_preview")
    inlines = [CompartmentInline]
    actions = ["action_regenerate_qr"]

    def compartment_count(self, obj):
        return obj.compartments.count()
    compartment_count.short_description = "Số ngăn"

    def qr_preview(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" width="60" height="60" />', obj.qr_code.url)
        return "—"
    qr_preview.short_description = "QR"

    @admin.action(description="🔄 Gen lại QR code (cập nhật SITE_URL mới)")
    def action_regenerate_qr(self, request, queryset):
        count = 0
        for locker in queryset:
            try:
                _generate_qr(locker)
                count += 1
            except Exception as e:
                self.message_user(request, f"Lỗi tủ {locker.name}: {e}", level="error")
        if count:
            self.message_user(request, f"✅ Đã gen lại QR cho {count} tủ với SITE_URL: {__import__('django.conf', fromlist=['settings']).settings.SITE_URL}")


@admin.register(Compartment)
class CompartmentAdmin(admin.ModelAdmin):
    list_display = ("locker", "number", "status")
    list_filter = ("status", "locker")
