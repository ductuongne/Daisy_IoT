Khởi tạo môi trường ảo:
```bash
python -m venv .venv
```


Mẫu cấu hình môi trường `.env` (`Server/.env`):
```env
ESP_IP=""          # IP CỦA ESP32 (Ví dụ: "10.176.71.218")
BROKER=""          # IP CỦA MQTT SERVER (Ví dụ: "10.176.71.27")
PORT=""            # PORT CỦA MQTT SERVER (Ví dụ: 1883)
TELEBOT_TOKEN=""   # TOKEN CỦA TELEGRAM BOT
ADMIN_BOT_ID=[]    # ID CỦA ADMIN BOT (Ví dụ: [5159544554])
```

---

# 📸 Daisy IoT Camera Server & Alert System

Hệ thống giám sát an ninh thông minh tích hợp thiết bị **ESP32-CAM**, **Web Dashboard** thời gian thực và điều khiển tương tác qua **Telegram Bot** bằng MQTT Protocol.

## 🚀 Các Tính Năng Nổi Bật

1. **Bảng Điều Khiển Web Dashboard**:
   * Thiết kế giao diện hiện đại (Bright Slate Theme), Glassmorphism mượt mà.
   * Xem trực tiếp luồng MJPEG Video Stream cổng **81**.
   * Đồng bộ trạng thái và tự động khóa điều khiển (Offline Lockout) kèm biểu ngữ cảnh báo khi ESP32 ngoại tuyến.
   * Danh sách lịch sử phát hiện chuyển động kèm ảnh chụp và video.

2. **Telegram Bot Tương Tác Thông Minh (Inline Keyboard)**:
   * Gửi bảng điều khiển tương tác qua lệnh `/start` hoặc `/control`.
   * Sử dụng bàn phím ảo (Inline Keyboard) để bật/tắt thiết bị: Camera, Còi khẩn cấp, Còi tự động, Cảm biến PIR.
   * Hiển thị popup thông báo (Toast Alert) xác nhận khi người dùng nhấn nút.
   * **Cảnh báo mất kết nối tự động**: Gửi tin nhắn cảnh báo ngay khi thiết bị mất kết nối quá 10 giây hoặc khi thiết bị trực tuyến trở lại.

3. **Cơ Chế Phân Tách Cổng Kết Nối (Port Separation)**:
   * Khắc phục triệt để lỗi nghẽn/timeout trên ESP32-CAM bằng cách chạy song song hai server: cổng **80** (cho APIs chụp ảnh, lấy trạng thái, điều khiển) và cổng **81** (dành riêng cho luồng video trực tiếp).

4. **Ghi Hình & Xử Lý Video PIR 5 Giây**:
   * Chụp ảnh và ghi hình tự động khi cảm biến PIR phát hiện chuyển động.
   * **Đồng bộ khung hình (Frame Interpolation)**: Tự động nhân bản khung hình cuối để đảm bảo thời lượng video luôn chính xác 5 giây kể cả khi luồng stream bị suy giảm FPS.
   * **Mã hóa tương thích trình duyệt**: Chuyển đổi video đã quay sang định dạng H.264 qua `ffmpeg` để xem trực tiếp mượt mà trên cả trình duyệt Web và ứng dụng Telegram.

5. **Đồng Bộ Dòng Dữ Liệu MQTT Phản Ứng (Reactive Sync)**:
   * Mọi cập nhật trạng thái từ ESP32 qua MQTT lập tức đồng bộ đồng thời cho cả giao diện Web Dashboard lẫn nội dung tin nhắn điều khiển trên Telegram Bot.

---

## 🛠 Sơ Đồ Đấu Nối Phần Cứng (ESP32-CAM)

| Linh Kiện | Chân ESP32-CAM | Mô Tả |
| :--- | :--- | :--- |
| **Cảm biến PIR** | `GPIO 13` | Nhận tín hiệu phát hiện chuyển động (HIGH/LOW) |
| **Còi báo (Siren)** | `GPIO 12` | Kích hoạt còi hú |
| **Status LED** | `GPIO 33` | Đèn báo kết nối hệ thống (Tích hợp trên bo mạch) |

---

## 💻 Cài Đặt và Khởi Chạy

### 1. Kích hoạt môi trường ảo và Cài đặt thư viện:
```bash
# Kích hoạt môi trường ảo (Windows)
.venv\Scripts\activate

# Cài đặt thư viện
pip install -r Server/requirements.txt
```

### 2. Yêu cầu cài đặt ffmpeg:
Hệ thống sử dụng phần mềm `ffmpeg` để xử lý và re-encode video ghi hình. Hãy cài đặt `ffmpeg` lên hệ thống của bạn và đảm bảo tệp thực thi `ffmpeg` được thêm vào biến môi trường `PATH` của hệ điều hành.

### 3. Khởi chạy Server:
```bash
cd Server
python app.py
```
Giao diện quản trị web sẽ chạy tại địa chỉ: `http://localhost:5000`

---

## 📡 Sơ Đồ Cấu Trúc MQTT (MQTT API Schema)

### 1. Topic Trạng Thái: `esp32/trangthai` (ESP32 ➔ Server)
* **Status Heartbeat (Định kỳ 4 giây)**: ESP32 gửi định kỳ bản tin JSON chứa trạng thái hoạt động hiện tại:
  ```json
  {
    "coi_kc": 0,    // Trạng thái còi khẩn cấp (0: Tắt, 1: Hú)
    "coi_td": 0,    // Trạng thái còi tự động (0: Tắt, 1: Bật)
    "pir_on": 1,    // Trạng thái cảm biến PIR (0: Tắt, 1: Bật)
    "stream": 1     // Trạng thái Camera stream (0: Tắt, 1: Bật)
  }
  ```
* **Cảnh Báo PIR**: Khi phát hiện chuyển động, ESP32 gửi một chuỗi văn bản không định dạng:
  ```text
  PIR_ALERT
  ```

### 2. Topic Lệnh Điều Khiển: `esp32/lenh` (Server/Telegram ➔ ESP32)
* `CAMERA_ON` / `CAMERA_OFF`: Bật/tắt luồng camera.
* `COIKC_ON` / `COIKC_OFF`: Bật/tắt còi báo khẩn cấp thủ công.
* `COI_ON` / `COI_OFF`: Bật/tắt chế độ tự động hú còi khi PIR phát hiện chuyển động.
* `CAMBIEN_ON` / `CAMBIEN_OFF`: Bật/tắt cảm biến chuyển động PIR.
* `TRANG_THAI`: Yêu cầu ESP32 phản hồi trạng thái hoạt động tức thì.
* `RESET`: Reset khởi động lại bo mạch ESP32.