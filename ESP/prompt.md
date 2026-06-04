Bạn là một chuyên gia lập trình nhúng ESP32 và hệ điều hành thời gian thực FreeRTOS. Hãy thiết kế và viết mã nguồn hoàn chỉnh cho dự án ESP32-CAM (Sơ đồ cấu hình chân AI-Thinker) theo kiến trúc mô-đun hóa (Modular Architecture), phân chia thành 2 file .ino chạy song song trên môi trường Arduino IDE như sau:

### 1. PHÂN CHIA VÀ CẤU TRÚC FILE (.ino)
- **File phụ: CameraWebServer.ino (HTTP Service)**
  + Đây là file mẫu của https://github.com/espressif/esp32-camera/blob/master/examples/CameraWebServer/CameraWebServer.ino. Bạn chỉ chỉnh sửa các hàm setup() và loop() gốc của hãng. Đổi tên hàm khởi tạo hệ thống camera thành: `bool initCameraServer()`. Hàm này mở một Web Server tại cổng 80 để phát luồng Stream trực tuyến dạng MJPEG.
  + Viết hàm `bool checkCameraHardware()` trả về true/false để kiểm tra phần cứng camera có hoạt động hay không.
  + Tận dụng biến trạng thái `extern bool dang_stream;` từ file chính. Khi `dang_stream == true`, Web Server liên tục chụp ảnh (`esp_camera_fb_get()`) để truyền luồng. Khi `dang_stream == false`, tạm dừng luồng để giải phóng RAM cho chip.

- **File chính: ESP.ino (Entry Point / API Gateway)**
  + Chứa hàm `setup()` và `loop()` tổng của toàn hệ thống.
  + Cấu hình kết nối mạng Wi-Fi và giao thức mạng MQTT (Broker: `broker.hivemq.com`, Port: 1883).
  + Đăng ký lắng nghe lệnh chuỗi từ Server Python tại topic: `esp32/lenh`.
  + Khai báo phần cứng theo đúng sơ đồ chân vật lý sau:
    * Cảm biến PIR HC-SR501: Chân OUT kết nối chân đầu vào `GPIO 13`.
    * Còi báo động Active Buzzer 5V: Chân Cực dương (+) kết nối chân đầu ra `GPIO 12`.

### 2. MA TRẬN LOGIC CÒI, CAMERA VÀ PHÂN CẤP QUYỀN ƯU TIÊN (STATE MACHINE)
Khai báo các biến trạng thái hệ thống dạng toàn cục:
`bool coi_khan_cap = false;` (Mặc định ban đầu tắt)
`bool coi_tu_dong = true;`   (Mặc định ban đầu bật)
`bool cam_bien_on = true;`   (Mặc định ban đầu bật)
`bool dang_stream = false;`  (Mặc định ban đầu tắt)
`bool cam_ok = false;`       (Trạng thái kết nối phần cứng camera)
`bool pir_ok = false;`       (Trạng thái kết nối phần cứng PIR)
`bool coi_ok = false;`       (Trạng thái kết nối phần cứng còi)

Hàm `callback()` tiếp nhận dữ liệu từ topic `esp32/lenh` bằng CHUỖI VĂN BẢN THUẦN (Plain Text), đối chiếu chính xác bộ mã lệnh sau:
- `"COIKC_ON"`   -> `coi_khan_cap = true`. (Ép còi hú liên tục ngay lập tức, đè lên mọi chế độ và cảm biến).
- `"COIKC_OFF"`  -> `coi_khan_cap = false`. (Dừng còi khẩn cấp, trả hệ thống về chế độ tự động).
- `"COI_ON"`     -> `coi_tu_dong = true`. (Bật chế độ còi tự động kêu khi có chuyển động).
- `"COI_OFF"`    -> `coi_tu_dong = false`. (Khóa còi tự động hoàn toàn, PIR có báo trộm còi vẫn im lặng. Tuy nhiên lệnh COIKC_ON vẫn có quyền bắt còi kêu).
- `"CAMBIEN_ON"` -> `cam_bien_on = true`. (Kích hoạt chân đọc dữ liệu từ cảm biến PIR).
- `"CAMBIEN_OFF"`-> `cam_bien_on = false`. (Vô hiệu hóa cảm biến PIR).
- `"CAMERA_ON"`  -> `dang_stream = true`. (Kích hoạt luồng Stream Video truyền qua HTTP cổng 80).
- `"CAMERA_OFF"` -> `dang_stream = false`. (Ngắt luồng Stream Video giải phóng bộ nhớ RAM).
- `"RESET"`      -> Thực hiện lệnh hệ thống `ESP.restart();` để khởi động lại mạch phần cứng.
- `"TRANG_THAI"` -> Gom tất cả các biến trạng thái thiết bị và chế độ hoạt động đóng gói thành chuỗi cấu trúc JSON (Sử dụng thư viện `ArduinoJson` và giới hạn vùng nhớ `StaticJsonDocument<256>`), sau đó Publish lên topic `esp32/trangthai` với cấu trúc:
  `{"cam_ok": 0/1, "pir_ok": 0/1, "coi_kc": 0/1, "coi_td": 0/1, "pir_on": 0/1, "stream": 0/1}` lần lượt là trạng thái kết nối phần cứng camera, cảm biến PIR, còi khẩn cấp, còi tự động, chế độ cảm biến PIR, chế độ stream video

### 3. CÁCH THỨC HOẠT ĐỘNG CHÍNH VÀ CẢNH BÁO TỰ ĐỘNG
Khi tất cả các chế độ bảo vệ đều bật (`coi_tu_dong == true` và `cam_bien_on == true`):
- Nếu chân `GPIO 13` (PIR) nhận tín hiệu `HIGH` (Phát hiện chuyển động đột nhập) -> Lập tức kích hoạt chân `GPIO 12` lên mức `HIGH` để báo chuông.
- Đồng thời, con ESP32-CAM sẽ tự động kích hoạt chụp 1 khung hình từ camera (Snapshot) hoặc bật tạm thời một luồng Stream khẩn cấp, đồng thời bắn ngay 1 thông điệp văn bản cảnh báo `"PIR_ALERT"` lên topic `esp32/trangthai` để thông báo cho Server Python biết và xử lý lưu lịch sử.

### 4. PHÂN CHIA TÁC VỤ ĐA NHIỆM BẰNG FreeRTOS (DUAL-CORE)
Trong hàm `setup()` của file chính `ESP.ino`, khởi tạo 2 Task FreeRTOS chạy độc lập trên 2 nhân xử lý của ESP32:
- **Task 1 (Định tuyến chạy trên Core 0):** Chuyên trách duy trì kết nối Wi-Fi, chạy vòng lặp `mqttClient.loop()` liên tục để hóng lệnh không độ trễ, đồng thời liên tục thực hiện quét đọc chân cảm biến PIR, điều phối ma trận logic còi báo động để đảm bảo phản xạ thời gian thực.
- **Task 2 (Định tuyến chạy trên Core 1):** Chỉ duy nhất chịu trách nhiệm vận hành chương trình Web Server HTTP Camera từ file `CameraWebServer.ino` để đẩy luồng stream mượt mà về Server Python khi được yêu cầu, cô lập hoàn toàn tác vụ đồ họa nặng để không gây tràn RAM hay xung đột với luồng mạng MQTT.
