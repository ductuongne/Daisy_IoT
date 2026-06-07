#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

extern bool initCameraServer();
extern bool checkCameraHardware();

// ==========================================
// CẤU HÌNH
// ==========================================
const char *ssid         = "daisymusicgroup";
const char *password     = "39393939";
const char *mqtt_broker  = "10.176.71.27";
const int   mqtt_port    = 1883;
const char *TOPIC_CMD    = "esp32/lenh";
const char *TOPIC_STATUS = "esp32/trangthai";

#define PIN_PIR    13
#define PIN_BUZZER 12

// ==========================================
// TRẠNG THÁI HỆ THỐNG (do server điều khiển)
// ==========================================
bool coi_khan_cap = false; // Server gửi COIKC_ON/OFF
bool coi_tu_dong  = false;  // Server gửi COI_ON/OFF
bool cam_bien_on  = true;  // Server gửi CAMBIEN_ON/OFF
bool dang_stream  = true; // Server gửi CAMERA_ON/OFF → CameraWebServer đọc biến này
bool cam_ok       = false;

// ==========================================
// BIẾN NỘI BỘ
// ==========================================
bool pir_prev              = false;
bool buzzer_auto_active    = false;
unsigned long buzzer_auto_start = 0;
unsigned long last_alert_time   = 0;

WiFiClient   espClient;
PubSubClient mqttClient(espClient);
TaskHandle_t Task1, Task2;

void Task1code(void *pvParameters);
void Task2code(void *pvParameters);
void setupWiFi();
void reconnectMQTT();
void callback(char *topic, byte *payload, unsigned int length);
void publishStatus();

// ==========================================
// SETUP
// ==========================================
void setup() {
  Serial.begin(115200);
  Serial.println("System starting...");

  pinMode(PIN_PIR,    INPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  xTaskCreatePinnedToCore(Task1code, "NetworkLogicTask", 10000, NULL, 1, &Task1, 0);
  delay(100);
  xTaskCreatePinnedToCore(Task2code, "CameraServerTask", 10000, NULL, 1, &Task2, 1);
  delay(100);
}

void loop() {
  vTaskDelay(10000 / portTICK_PERIOD_MS);
}

// ==========================================
// TASK 1 (Core 0): MẠNG + PIR + CÒI
// ==========================================
void Task1code(void *pvParameters) {
  Serial.printf("Task1 on core %d\n", xPortGetCoreID());

  setupWiFi();
  mqttClient.setServer(mqtt_broker, mqtt_port);
  mqttClient.setCallback(callback);

  for (;;) {

    // --- DUY TRÌ KẾT NỐI ---
    if (WiFi.status() != WL_CONNECTED) {
      WiFi.disconnect();
      WiFi.begin(ssid, password);
      for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++)
        vTaskDelay(500 / portTICK_PERIOD_MS);
    }

    if (WiFi.status() == WL_CONNECTED) {
      if (!mqttClient.connected()) reconnectMQTT();
      mqttClient.loop();

      // Publish status periodically every 4 seconds so the server knows the ESP32 is online
      static unsigned long last_status_pub = 0;
      if (mqttClient.connected() && (millis() - last_status_pub > 4000)) {
        publishStatus();
        last_status_pub = millis();
      }
    }

    // --- ĐỌC PIR (chỉ xử lý cạnh lên LOW→HIGH) ---
    bool pir_now         = (digitalRead(PIN_PIR) == HIGH);
   // Serial.println(pir_now ? "pir true" : "pir_false");
    bool pir_rising_edge = (pir_now && !pir_prev);

    if (pir_rising_edge && cam_bien_on) {
      Serial.println("PIR: Motion detected.");

      // Gửi cảnh báo lên server (chống spam 5 giây)
      if (millis() - last_alert_time > 5000 && mqttClient.connected()) {
        mqttClient.publish(TOPIC_STATUS, "PIR_ALERT");
        last_alert_time = millis();
        Serial.println("PIR_ALERT sent.");
      }

      // Kích hoạt còi tự động nếu server đã bật chế độ này
      if (coi_tu_dong && !buzzer_auto_active && !coi_khan_cap) {
        buzzer_auto_active = true;
        buzzer_auto_start  = millis();
        Serial.println("Auto buzzer started.");
      }
    }

    pir_prev = pir_now;

    // --- ĐIỀU KHIỂN CÒI ---
    if (coi_khan_cap) {
      // Ưu tiên 1: Còi khẩn cấp bật liên tục theo lệnh server
      digitalWrite(PIN_BUZZER, HIGH);
      buzzer_auto_active = false;

    } else if (buzzer_auto_active) {
      // Ưu tiên 2: Còi tự động hú 5 giây rồi tắt
      if (millis() - buzzer_auto_start < 5000) {
        digitalWrite(PIN_BUZZER, HIGH);
      } else {
        digitalWrite(PIN_BUZZER, LOW);
        buzzer_auto_active = false;
        Serial.println("Auto buzzer finished.");
      }

    } else {
      digitalWrite(PIN_BUZZER, LOW);
    }

    vTaskDelay(50 / portTICK_PERIOD_MS);
  }
}

// ==========================================
// TASK 2 (Core 1): CAMERA WEB SERVER
// ==========================================
void Task2code(void *pvParameters) {
  Serial.printf("Task2 on core %d\n", xPortGetCoreID());

  while (WiFi.status() != WL_CONNECTED)
    vTaskDelay(1000 / portTICK_PERIOD_MS);

  cam_ok = initCameraServer();
  if (cam_ok) cam_ok = checkCameraHardware();

  Serial.println(cam_ok ? "Camera OK." : "Camera FAILED!");

  for (;;) vTaskDelay(10000 / portTICK_PERIOD_MS);
}

// ==========================================
// HÀM HỖ TRỢ
// ==========================================
void setupWiFi() {
  Serial.printf("Connecting to %s ", ssid);
  WiFi.begin(ssid, password);
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("\nWi-Fi connected. IP: %s\n", WiFi.localIP().toString().c_str());
  else
    Serial.println("\nWi-Fi timeout. Will retry in task loop.");
}

void reconnectMQTT() {
  if (WiFi.status() != WL_CONNECTED) return;

  String clientId = "ESP32CAM-" + String(random(0xffff), HEX);
  Serial.printf("Connecting MQTT to %s...\n", mqtt_broker);

  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("MQTT connected.");
    mqttClient.subscribe(TOPIC_CMD);
    publishStatus();
  } else {
    Serial.printf("MQTT failed (state=%d). Retry in 5s.\n", mqttClient.state());
    vTaskDelay(5000 / portTICK_PERIOD_MS);
  }
}

void callback(char *topic, byte *payload, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.printf("MQTT [%s]: %s\n", topic, msg.c_str());

  if      (msg == "COIKC_ON")    { coi_khan_cap = true;  Serial.println("Emergency siren ON."); }
  else if (msg == "COIKC_OFF")   { coi_khan_cap = false; Serial.println("Emergency siren OFF."); }
  else if (msg == "COI_ON")      { coi_tu_dong  = true;  Serial.println("Auto siren mode ON."); }
  else if (msg == "COI_OFF")     { coi_tu_dong  = false; Serial.println("Auto siren mode OFF."); }
  else if (msg == "CAMBIEN_ON")  { cam_bien_on  = true;  Serial.println("PIR sensor ON."); }
  else if (msg == "CAMBIEN_OFF") { cam_bien_on  = false; Serial.println("PIR sensor OFF."); }
  else if (msg == "CAMERA_ON")   { dang_stream  = true;  Serial.println("Stream ON."); }
  else if (msg == "CAMERA_OFF")  { dang_stream  = false; Serial.println("Stream OFF."); }
  else if (msg == "RESET")       { delay(500); ESP.restart(); }
  else if (msg == "TRANG_THAI")  publishStatus();
}

void publishStatus() {
  if (!mqttClient.connected()) return;

  StaticJsonDocument<256> doc;
  doc["coi_kc"] = coi_khan_cap ? 1 : 0;
  doc["coi_td"] = coi_tu_dong  ? 1 : 0;
  doc["pir_on"] = cam_bien_on  ? 1 : 0;
  doc["stream"] = dang_stream  ? 1 : 0;

  char buf[256];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_STATUS, buf);
  Serial.printf("Status published: %s\n", buf);
}