#include <WiFi.h>
#include <HTTPClient.h>

// ESP32 DevKit V1 telemetry client for the IoT Honeypot Monitoring Platform.
// Update these values before uploading from Arduino IDE.
const char* WIFI_SSID = "25";
const char* WIFI_PASSWORD = "chinna24";
const char* SERVER_BASE_URL = "http://10.74.110.189:5000";
const char* DEVICE_NAME = "ESP32_DEVKIT";

const int STATUS_LED_PIN = 2;
const unsigned long HEARTBEAT_INTERVAL_MS = 30000;
unsigned long lastHeartbeatMs = 0;

void connectWiFi();
void registerDevice();
void sendBootEvent();
void sendHeartbeat();
int postJson(const String& endpoint, const String& jsonBody);
String ipAddressText();

void setup() {
  Serial.begin(115200);
  delay(1000);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

  Serial.println();
  Serial.println("IoT Honeypot ESP32 client starting");
  connectWiFi();
  registerDevice();
  sendBootEvent();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    digitalWrite(STATUS_LED_PIN, LOW);
    connectWiFi();
  }

  if (millis() - lastHeartbeatMs >= HEARTBEAT_INTERVAL_MS) {
    sendHeartbeat();
    lastHeartbeatMs = millis();
  }

  delay(500);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED_PIN, HIGH);
    Serial.println();
    Serial.print("Connected. ESP32 IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("WiFi connection failed. Retrying from loop.");
  }
}

void registerDevice() {
  String body = "{";
  body += "\"device_name\":\"" + String(DEVICE_NAME) + "\",";
  body += "\"device_ip\":\"" + ipAddressText() + "\",";
  body += "\"status\":\"online\"";
  body += "}";

  int status = postJson("/api/device", body);
  Serial.print("Device registration HTTP status: ");
  Serial.println(status);
}

void sendBootEvent() {
  String body = "{";
  body += "\"device_name\":\"" + String(DEVICE_NAME) + "\",";
  body += "\"event_type\":\"boot\",";
  body += "\"severity\":\"info\",";
  body += "\"payload\":\"device started\",";
  body += "\"source_ip\":\"" + ipAddressText() + "\"";
  body += "}";

  int status = postJson("/api/log", body);
  Serial.print("Boot event HTTP status: ");
  Serial.println(status);
}

void sendHeartbeat() {
  int rawTemperature = analogRead(34);
  float temperature = (rawTemperature * 3.3 / 4095.0) * 100.0;
  int humidity = 70; // Replace with a real sensor reading when available.

  String body = "{";
  body += "\"device_name\":\"" + String(DEVICE_NAME) + "\",";
  body += "\"event_type\":\"heartbeat\",";
  body += "\"temperature\":" + String(temperature, 1) + ",";
  body += "\"humidity\":" + String(humidity) + ",";
  body += "\"source_ip\":\"" + ipAddressText() + "\"";
  body += "}";

  int status = postJson("/api/log", body);
  Serial.print("Heartbeat HTTP status: ");
  Serial.println(status);
}

int postJson(const String& endpoint, const String& jsonBody) {
  if (WiFi.status() != WL_CONNECTED) {
    return -1;
  }

  HTTPClient http;
  String url = String(SERVER_BASE_URL) + endpoint;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  Serial.print("POST ");
  Serial.print(url);
  Serial.print(" ");
  Serial.println(jsonBody);

  int status = http.POST(jsonBody);
  if (status > 0) {
    Serial.println(http.getString());
  }
  http.end();
  return status;
}

String ipAddressText() {
  IPAddress ip = WiFi.localIP();
  return String(ip[0]) + "." + String(ip[1]) + "." + String(ip[2]) + "." + String(ip[3]);
}
