# Smart Box Lock — Hệ thống tủ thông minh

## Mục tiêu
Xây dựng hệ thống quản lý tủ khóa thông minh:
- Admin quản lý N tủ (Locker), mỗi tủ có 6 ngăn (Compartment)
- Người dùng đăng ký tài khoản, đăng nhập để sử dụng hệ thống
- Người dùng quét mã QR dán tại ngăn tủ vật lý để đăng ký gửi đồ
- Người dùng quét QR hoặc truy cập web để mở ngăn tủ của mình

---

## Kiến trúc Django Apps

| App | Vai trò |
|---|---|
| `authentication/` | Đăng ký, đăng nhập, đăng xuất người dùng |
| `customers/` | Hồ sơ người dùng (Profile) |
| `lockers/` | Quản lý tủ (Locker), ngăn (Compartment), QR code |
| `bookings/` | Quản lý lượt đặt/gửi đồ, unlock ngăn |

---

## Models

### `lockers/models.py`
```
Locker
  - name          : tên tủ (VD: "Tủ A - Tầng 1")
  - location      : địa điểm
  - description   : mô tả
  - created_at / updated_at

Compartment
  - locker        : FK → Locker
  - number        : số ngăn (1–6)
  - status        : available | occupied | maintenance
  - uuid_token    : UUID ngẫu nhiên (nhúng vào QR)
  - qr_code       : ImageField (ảnh QR được gen tự động)
  - unique_together: (locker, number)
```

### `bookings/models.py`
```
Booking
  - user          : FK → User
  - compartment   : FK → Compartment
  - status        : pending | active | completed | cancelled
  - unlock_token  : UUID (token riêng để mở cửa)
  - started_at    : thời điểm bắt đầu
  - ended_at      : thời điểm kết thúc (null nếu đang dùng)
  - note          : ghi chú
```

---

## Luồng người dùng

### Đăng ký / Đăng nhập
```
/register/  → Tạo tài khoản mới
/login/     → Đăng nhập
/profile/   → Xem/chỉnh sửa hồ sơ cá nhân
```

### Quét QR tại tủ vật lý
```
User đứng trước tủ → Quét QR dán trên ngăn
  ↓
Truy cập: /lockers/qr/<uuid_token>/
  ↓
Chưa đăng nhập → Redirect /login/?next=...  → Đăng nhập xong quay lại
  ↓
Ngăn trống      → Form đăng ký gửi đồ → Tạo Booking (sinh unlock_token)
Ngăn đang dùng:
  ├─ Đúng chủ   → Nút "Mở cửa" → POST /bookings/unlock/<unlock_token>/
  └─ Người khác → Thông báo "Ngăn đang được sử dụng"
```

### Mở cửa
```
POST /bookings/unlock/<unlock_token>/
  → Xác thực: đúng chủ booking, booking đang active
  → Gọi API / MQTT đến ESP32
  → ESP32 kéo relay → mở khóa ngăn
```

---

## Bảo mật

| Lớp | Cơ chế |
|---|---|
| Tài khoản | Đăng ký + đăng nhập, mật khẩu hash Django |
| QR tại tủ | UUID ngẫu nhiên, phải đứng trước tủ mới quét được |
| Trang web | `@login_required` — chưa đăng nhập thì không vào được |
| Mở cửa | `unlock_token` UUID riêng mỗi booking, chỉ chủ booking thấy |
| Hardware API | Token xác thực, chỉ server gọi được |

---

## QR Code

- Thư viện: `qrcode[pil]`
- URL nhúng vào QR: `https://<domain>/lockers/qr/<uuid>/`
- Tự động gen khi Admin tạo Compartment, lưu vào `media/`
- Admin vào trang admin → tải ảnh QR → in → dán lên ngăn tủ vật lý

---

## API cho phần cứng (ESP32 / Arduino)

```
GET  /api/compartments/<id>/status/   → Trạng thái ngăn
POST /api/compartments/<id>/open/     → Lệnh mở cửa
```

---

## Packages cần cài thêm

```
qrcode[pil]
djangorestframework
```

---

## Thứ tự implement

1. App `lockers`: models (Locker, Compartment) + admin + tự động gen QR
2. App `bookings`: models (Booking) + admin
3. Views: trang QR landing, form đăng ký gửi đồ, trang unlock
4. API endpoint cho hardware (ESP32)
5. Templates: danh sách tủ, trạng thái ngăn, lịch sử booking của user
6. Tích hợp phần cứng (MQTT hoặc HTTP đến ESP32)
