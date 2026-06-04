#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// Nguyên mẫu các hàm từ CameraWebServer.ino
extern bool initCameraServer();
extern bool checkCameraHardware();

// Cấu hình mạng Wi-Fi
const char *ssid = "daisymusicgroup";
const char *password = "39393939";

// Cấu hình giao thức MQTT Broker
const char *mqtt_broker = "10.162.4.28";
const int mqtt_port = 1883;
const char *mqtt_topic_cmd = "esp32/lenh";
const char *mqtt_topic_status = "esp32/trangthai";

// Khai báo các biến trạng thái hệ thống toàn cục
bool coi_khan_cap = false; // Mặc định ban đầu tắt
bool coi_tu_dong = true;   // Mặc định ban đầu bật
bool cam_bien_on = true;   // Mặc định ban đầu bật
bool dang_stream = false;  // Mặc định ban đầu tắt
bool cam_ok = false;       // Trạng thái kết nối phần cứng camera
bool pir_ok = false;       // Trạng thái kết nối phần cứng PIR
bool coi_ok = false;       // Trạng thái kết nối phần cứng còi

// Biến điều khiển kích hoạt luồng Stream khẩn cấp tạm thời khi phát hiện chuyển động
bool temp_stream = false;
unsigned long temp_stream_start = 0;

// Khai báo các đối tượng mạng
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Task Handles điều phối đa nhiệm FreeRTOS
TaskHandle_t Task1;
TaskHandle_t Task2;

// Các nguyên mẫu hàm cục bộ
void Task1code(void *pvParameters);
void Task2code(void *pvParameters);
void setupWiFi();
void reconnectMQTT();
void callback(char *topic, byte *payload, unsigned int length);
void publishStatus();

void setup() {
  // Khởi động cổng Serial truyền dữ liệu debug
  Serial.begin(115200);
  Serial.println("System starting...");

  // Khai báo cấu hình chân vật lý cảm biến PIR
  pinMode(13, INPUT); // Chân GPIO 13 làm đầu vào nhận tín hiệu từ PIR
  pir_ok = true;      // Ghi nhận cấu hình phần cứng PIR hoàn thành
  
  // Khai báo cấu hình chân vật lý còi báo động Active Buzzer
  pinMode(12, OUTPUT);       // Chân GPIO 12 làm đầu ra xuất mức điện áp điều khiển còi
  digitalWrite(12, LOW);     // Đặt trạng thái ban đầu là tắt còi (LOW)
  coi_ok = true;             // Ghi nhận cấu hình phần cứng còi hoàn thành

  // Khởi tạo Task 1 chạy trên Core 0: Xử lý mạng (Wi-Fi, MQTT), đọc cảm biến và điều phối còi thời gian thực
  xTaskCreatePinnedToCore(
    Task1code,       /* Tên hàm thực thi task */
    "NetworkLogicTask", /* Tên đặt cho task */
    10000,           /* Độ lớn bộ nhớ Stack cấp phát (bytes) */
    NULL,            /* Tham số truyền vào task */
    1,               /* Mức độ ưu tiên của task */
    &Task1,          /* Biến lưu trữ Task Handle */
    0                /* Định tuyến chạy trên Core 0 */
  );
  delay(100);

  // Khởi tạo Task 2 chạy trên Core 1: Chuyên trách vận hành Camera Web Server để stream mượt mà
  xTaskCreatePinnedToCore(
    Task2code,       /* Tên hàm thực thi task */
    "CameraServerTask", /* Tên đặt cho task */
    10000,           /* Độ lớn bộ nhớ Stack cấp phát (bytes) */
    NULL,            /* Tham số truyền vào task */
    1,               /* Mức độ ưu tiên của task */
    &Task2,          /* Biến lưu trữ Task Handle */
    1                /* Định tuyến chạy trên Core 1 */
  );
  delay(100);
}

void loop() {
  // Do dùng kiến trúc FreeRTOS đa nhiệm chạy trên các Core nên loop chính không xử lý logic
  vTaskDelay(10000 / portTICK_PERIOD_MS);
}

// ==========================================
// TÁC VỤ 1 (Core 0): WI-FI, MQTT, LOGIC CÒI BÁO ĐỘNG VÀ CẢM BIẾN PIR
// ==========================================
void Task1code(void *pvParameters) {
  Serial.print("Task 1 running on core ");
  Serial.println(xPortGetCoreID());

  // Kết nối Wi-Fi ban đầu
  setupWiFi();

  // Thiết lập MQTT Broker và Hàm Callback tiếp nhận lệnh
  mqttClient.setServer(mqtt_broker, mqtt_port);
  mqttClient.setCallback(callback);

  for (;;) {
    // Tự động kiểm tra và kết nối lại Wi-Fi nếu bị ngắt
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Wi-Fi connection lost. Reconnecting...");
      WiFi.disconnect();
      WiFi.begin(ssid, password);
      int attempts = 0;
      while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        vTaskDelay(500 / portTICK_PERIOD_MS);
        attempts++;
      }
    }

    // Tự động kiểm tra và kết nối lại MQTT Broker
    if (WiFi.status() == WL_CONNECTED) {
      if (!mqttClient.connected()) {
        reconnectMQTT();
      }
      mqttClient.loop(); // Duy trì lắng nghe thông điệp MQTT
    }

    // --- MA TRẬN LOGIC ĐIỀU PHỐI CÒI VÀ PHÂN CẤP ƯU TIÊN ---
    if (coi_khan_cap) {
      // Ưu tiên 1: Còi khẩn cấp bật -> Bật còi liên tục lập tức, bỏ qua mọi cảm biến
      digitalWrite(12, HIGH);
    } else {
      // Ưu tiên 2: Chế độ tự động hoạt động khi cả coi_tu_dong và cam_bien_on đều bật
      if (cam_bien_on && coi_tu_dong) {
        int pirState = digitalRead(13); // Đọc tín hiệu từ chân GPIO 13 (PIR HC-SR501)
        
        if (pirState == HIGH) {
          digitalWrite(12, HIGH); // Bật còi báo động ngay lập tức khi phát hiện đột nhập
          
          // Kích hoạt tạm thời luồng Stream khẩn cấp trong 15 giây để quan sát
          if (!dang_stream) {
            dang_stream = true;
            temp_stream = true;
            temp_stream_start = millis();
            Serial.println("Motion detected! Temporary stream triggered.");
          }

          // Bắn thông điệp văn bản "PIR_ALERT" lên MQTT (Sử dụng cơ chế chống dội/spam 5 giây)
          static unsigned long last_alert_time = 0;
          if (millis() - last_alert_time > 5000) {
            if (mqttClient.connected()) {
              mqttClient.publish(mqtt_topic_status, "PIR_ALERT");
              Serial.println("Alert 'PIR_ALERT' sent to broker.");
            }
            last_alert_time = millis();
          }
        } else {
          digitalWrite(12, LOW); // Tắt còi khi không còn phát hiện chuyển động
        }
      } else {
        // Nếu một trong hai chế độ bảo vệ bị tắt và còi khẩn cấp không bật -> Đảm bảo còi tắt
        digitalWrite(12, LOW);
      }
    }

    // Quản lý việc dừng luồng stream khẩn cấp tạm thời sau 15 giây
    if (temp_stream && (millis() - temp_stream_start > 15000)) {
      temp_stream = false;
      dang_stream = false;
      Serial.println("Temporary stream ended. Stream closed to free RAM.");
    }

    // Nhường quyền xử lý cho hệ thống (Tránh kích hoạt Watchdog Reset)
    vTaskDelay(50 / portTICK_PERIOD_MS);
  }
}

// ==========================================
// TÁC VỤ 2 (Core 1): VẬN HÀNH WEB SERVER HTTP CAMERA
// ==========================================
void Task2code(void *pvParameters) {
  Serial.print("Task 2 running on core ");
  Serial.println(xPortGetCoreID());

  // Chờ Wi-Fi sẵn sàng trước khi cấu hình Server
  while (WiFi.status() != WL_CONNECTED) {
    vTaskDelay(1000 / portTICK_PERIOD_MS);
  }

  // Khởi tạo camera và Web Server tại cổng 80
  cam_ok = initCameraServer();
  if (cam_ok) {
    cam_ok = checkCameraHardware(); // Kiểm tra phần cứng camera
  }

  if (cam_ok) {
    Serial.println("Camera hardware & Web Server initialized successfully.");
  } else {
    Serial.println("Camera initialization failed! Check pins or power.");
  }

  for (;;) {
    // Vòng lặp duy trì tác vụ, tránh kết thúc Task
    vTaskDelay(10000 / portTICK_PERIOD_MS);
  }
}

// ==========================================
// CÁC HÀM HỖ TRỢ KẾT NỐI MẠNG WI-FI VÀ MQTT
// ==========================================
void setupWiFi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to network: ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  int attempt = 0;
  // Chờ tối đa 15 giây để kết nối Wi-Fi thành công
  while (WiFi.status() != WL_CONNECTED && attempt < 30) {
    delay(500);
    Serial.print(".");
    attempt++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("");
    Serial.println("Wi-Fi connected.");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWi-Fi connection timeout. Retrying in task loop...");
  }
}

void reconnectMQTT() {
  // Lặp lại việc kết nối cho tới khi thành công
  while (!mqttClient.connected()) {
    if (WiFi.status() != WL_CONNECTED) {
      return; // Không thử kết nối MQTT khi chưa có Wi-Fi
    }

    Serial.print("Attempting MQTT connection to: ");
    Serial.println(mqtt_broker);

    // Tạo Client ID ngẫu nhiên để tránh trùng lặp phiên kết nối
    String clientId = "ESP32CAM-Client-";
    clientId += String(random(0xffff), HEX);

    // Kết nối đến broker
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("MQTT connected successfully.");
      
      // Đăng ký nhận dữ liệu từ topic lệnh
      mqttClient.subscribe(mqtt_topic_cmd);
      Serial.print("Subscribed to topic: ");
      Serial.println(mqtt_topic_cmd);

      // Publish trạng thái ban đầu sau khi kết nối lại
      publishStatus();
    } else {
      Serial.print("MQTT connection failed, state: ");
      Serial.print(mqttClient.state());
      Serial.println(" - Retrying in 5 seconds.");
      vTaskDelay(5000 / portTICK_PERIOD_MS);
    }
  }
}

// Xử lý khi có gói tin MQTT gửi tới
void callback(char *topic, byte *payload, unsigned int length) {
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.print("Received message on topic [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(message);

  // So khớp chính xác các mã lệnh plain text từ Server Python
  if (message == "COIKC_ON") {
    coi_khan_cap = true;
    Serial.println("State change: emergency siren ACTIVATED.");
  } else if (message == "COIKC_OFF") {
    coi_khan_cap = false;
    Serial.println("State change: emergency siren DEACTIVATED.");
  } else if (message == "COI_ON") {
    coi_tu_dong = true;
    Serial.println("State change: auto siren mode ENABLED.");
  } else if (message == "COI_OFF") {
    coi_tu_dong = false;
    Serial.println("State change: auto siren mode DISABLED.");
  } else if (message == "CAMBIEN_ON") {
    cam_bien_on = true;
    Serial.println("State change: PIR sensor ENABLED.");
  } else if (message == "CAMBIEN_OFF") {
    cam_bien_on = false;
    Serial.println("State change: PIR sensor DISABLED.");
  } else if (message == "CAMERA_ON") {
    dang_stream = true;
    temp_stream = false; // Tắt cờ stream tạm thời nếu nhận được lệnh bật stream liên tục
    Serial.println("State change: Video streaming ENABLED.");
  } else if (message == "CAMERA_OFF") {
    dang_stream = false;
    temp_stream = false;
    Serial.println("State change: Video streaming DISABLED.");
  } else if (message == "RESET") {
    Serial.println("Restart command received. Restarting ESP32 hardware...");
    delay(500);
    ESP.restart();
  } else if (message == "TRANG_THAI") {
    publishStatus();
  }
}

// Đóng gói JSON và Publish thông tin trạng thái
void publishStatus() {
  StaticJsonDocument<256> doc;
  doc["cam_ok"] = cam_ok ? 1 : 0;
  doc["pir_ok"] = pir_ok ? 1 : 0;
  doc["coi_kc"] = coi_khan_cap ? 1 : 0;
  doc["coi_td"] = coi_tu_dong ? 1 : 0;
  doc["pir_on"] = cam_bien_on ? 1 : 0;
  doc["stream"] = dang_stream ? 1 : 0;

  char buffer[256];
  serializeJson(doc, buffer);

  if (mqttClient.connected()) {
    mqttClient.publish(mqtt_topic_status, buffer);
    Serial.print("Published status: ");
    Serial.println(buffer);
  } else {
    Serial.println("Cannot publish status: MQTT client not connected.");
  }
}
