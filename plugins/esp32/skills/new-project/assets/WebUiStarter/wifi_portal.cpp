// Реалізація модуля Wi-Fi. Опис і спосіб використання — у wifi_portal.h.

#include "wifi_portal.h"

#include <WiFi.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>

#include "wifi_portal_page.h"

namespace {

// ============================== Налаштування ==============================

const uint32_t CONNECT_TIMEOUT_MS = 15000;    // скільки чекаємо на підключення
const uint32_t AUTO_RETRY_MS      = 30000;    // як часто пробуємо збережену мережу, коли її не видно
const uint32_t LOST_GRACE_MS      = 10000;    // скільки чекаємо, що зв'язок повернеться сам
const uint32_t RESET_HOLD_MS      = 3000;     // скільки тримати кнопку, щоб забути Wi-Fi

// ================================== Стан ==================================

WebServer*       server = nullptr;
WifiPortalConfig cfg;
DNSServer        dnsServer;
Preferences      prefs;

// Мережа, збережена в пам'яті пристрою
String savedSsid;
String savedPass;

// Поточна спроба підключення
enum ConnState : uint8_t { CONN_IDLE, CONN_CONNECTING, CONN_CONNECTED, CONN_FAILED };
ConnState   connState      = CONN_IDLE;
String      attemptSsid;
String      attemptPass;
bool        attemptByUser  = false;    // true — зі сторінки налаштування, false — автоматично
uint32_t    attemptStartMs = 0;
uint32_t    attemptEndMs   = 0;
const char* attemptError   = "";       // "password" | "notfound" | "other"

// Це змінюється в обробнику подій Wi-Fi (він працює в окремій задачі)
volatile bool    gotIp          = false;
volatile uint8_t failCount      = 0;
volatile uint8_t lastFailReason = 0;

bool mdnsStarted = false;

// ======================= Збережена мережа (Preferences) ===================

void loadCredentials() {
  prefs.begin("wifi", false);
  if (prefs.isKey("ssid")) {
    savedSsid = prefs.getString("ssid", "");
    savedPass = prefs.getString("pass", "");
  }
  prefs.end();
}

void saveCredentials(const String& ssid, const String& pass) {
  prefs.begin("wifi", false);
  prefs.putString("ssid", ssid);
  prefs.putString("pass", pass);
  prefs.end();
  savedSsid = ssid;
  savedPass = pass;
}

void clearCredentials() {
  prefs.begin("wifi", false);
  prefs.clear();
  prefs.end();
  savedSsid = "";
  savedPass = "";
}

// ============================= Події Wi-Fi ================================

// Тут лише запам'ятовуємо, що сталося; рішення приймає wifiPortalLoop().
void onWiFiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  if (event == ARDUINO_EVENT_WIFI_STA_GOT_IP) {
    gotIp = true;
  } else if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
    gotIp = false;
    uint8_t reason = info.wifi_sta_disconnected.reason;
    if (reason != WIFI_REASON_ASSOC_LEAVE) {    // ASSOC_LEAVE — це ми самі розірвали з'єднання
      lastFailReason = reason;
      failCount = failCount + 1;
    }
  }
}

// Перетворює код причини від Wi-Fi на зрозумілу для сторінки помилку.
const char* failReasonToError(uint8_t reason) {
  switch (reason) {
    case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:
    case WIFI_REASON_HANDSHAKE_TIMEOUT:
    case WIFI_REASON_AUTH_FAIL:
    case WIFI_REASON_MIC_FAILURE:
      return "password";
    case WIFI_REASON_NO_AP_FOUND:
      return "notfound";
    default:
      return "other";
  }
}

// ========================== Мережа налаштування ===========================

// Власна мережа пристрою працює завжди — поруч із підключенням до домашнього Wi-Fi.
void startSetupNetwork() {
  WiFi.mode(WIFI_AP_STA);   // точка доступу + клієнт одночасно
  WiFi.softAP(cfg.apSsid, strlen(cfg.apPassword) >= 8 ? cfg.apPassword : nullptr);

  // Відповідаємо на всі DNS-запити власною адресою — завдяки цьому планшет
  // сам відкриває сторінку налаштування одразу після підключення.
  dnsServer.setErrorReplyCode(DNSReplyCode::NoError);
  dnsServer.start(53, "*", WiFi.softAPIP());

  Serial.printf("Мережа налаштування \"%s\" працює. Сторінка: http://%s/wifi\n",
                cfg.apSsid, WiFi.softAPIP().toString().c_str());
}

// ============================== Підключення ===============================

// Починає підключення і одразу повертається; результат відстежує updateConnection().
void beginConnect(const String& ssid, const String& pass, bool byUser) {
  attemptSsid   = ssid;
  attemptPass   = pass;
  attemptByUser = byUser;
  attemptError  = "";

  WiFi.scanDelete();
  WiFi.disconnect();
  gotIp          = false;
  failCount      = 0;
  lastFailReason = 0;

  WiFi.setSleep(false);   // без режиму сну сторінки відкриваються швидше
  WiFi.begin(ssid.c_str(), pass.length() > 0 ? pass.c_str() : nullptr);

  attemptStartMs = millis();
  connState      = CONN_CONNECTING;
  Serial.printf("Підключаюсь до \"%s\"...\n", ssid.c_str());
}

void updateConnection() {
  if (connState != CONN_CONNECTING) return;

  if (gotIp && WiFi.status() == WL_CONNECTED) {
    connState = CONN_CONNECTED;

    if (attemptSsid != savedSsid || attemptPass != savedPass) {
      saveCredentials(attemptSsid, attemptPass);
    }
    if (!mdnsStarted && MDNS.begin(cfg.hostname)) {
      MDNS.addService("http", "tcp", 80);
      mdnsStarted = true;
    }
    Serial.printf("Підключено до \"%s\". Адреса: http://%s/ або http://%s.local/\n",
                  attemptSsid.c_str(), WiFi.localIP().toString().c_str(), cfg.hostname);
    return;
  }

  // Дві невдачі поспіль (ядро ESP32 саме пробує вдруге) або вийшов час
  bool timedOut = millis() - attemptStartMs >= CONNECT_TIMEOUT_MS;
  if (failCount >= 2 || timedOut) {
    uint8_t reason = lastFailReason;
    WiFi.disconnect();    // зупиняємо подальші спроби, інакше не працюватиме пошук мереж

    attemptError = failReasonToError(reason);
    attemptEndMs = millis();
    connState    = attemptByUser ? CONN_FAILED : CONN_IDLE;
    Serial.printf("Не вдалося підключитися до \"%s\" (%s, код причини %u).\n",
                  attemptSsid.c_str(), attemptError, reason);
  }
}

bool isOnline() {
  return connState == CONN_CONNECTED && WiFi.status() == WL_CONNECTED;
}

// Зв'язок із роутером зник уже під час роботи.
void watchConnection() {
  static bool     lost        = false;
  static uint32_t lostSinceMs = 0;

  if (connState != CONN_CONNECTED || WiFi.status() == WL_CONNECTED) {
    lost = false;
    return;
  }
  if (!lost) {
    lost        = true;
    lostSinceMs = millis();
    Serial.println("Зв'язок із домашнім Wi-Fi втрачено.");
    return;
  }
  if (millis() - lostSinceMs >= LOST_GRACE_MS) {
    // Перші секунди ядро ESP32 пробувало повернути зв'язок саме. Не вийшло —
    // зупиняємо його безперервні спроби (вони заважають нашій власній мережі)
    // і далі пробуємо рідше, див. updateAutoRetry().
    WiFi.disconnect();
    lost         = false;
    connState    = CONN_IDLE;
    attemptEndMs = millis() - AUTO_RETRY_MS;    // перша спроба — без очікування
  }
}

// Немає зв'язку, але є збережена мережа — час від часу пробуємо її знову:
// можливо, роутер просто вмикався довше за нас або ненадовго зникав.
void updateAutoRetry() {
  bool waiting = (connState == CONN_IDLE || connState == CONN_FAILED);
  if (!waiting || savedSsid.length() == 0) return;

  // Кожна спроба на кілька секунд "глушить" нашу власну мережу, тому не
  // пробуємо, поки до неї хтось підключений або поки триває пошук мереж.
  if (WiFi.softAPgetStationNum() > 0) return;
  if (WiFi.scanComplete() == WIFI_SCAN_RUNNING) return;

  if (millis() - attemptEndMs >= AUTO_RETRY_MS) {
    beginConnect(savedSsid, savedPass, false);
  }
}

// ============================== Веб-сервер ================================

void sendJson(int code, const String& json) {
  server->sendHeader("Cache-Control", "no-store");
  server->send(code, "application/json", json);
}

// GET /wifi — сторінка налаштування (лише через мережу налаштування)
void handlePage() {
  if (!wifiPortalFromSetupNetwork()) {
    server->sendHeader("Location", "/", true);
    server->send(302, "text/plain", "");
    return;
  }
  server->sendHeader("Cache-Control", "no-store");
  server->send_P(200, "text/html; charset=utf-8", WIFI_PORTAL_PAGE);
}

void startScan() {
  if (WiFi.scanComplete() == WIFI_SCAN_RUNNING) return;

  if (connState == CONN_CONNECTING) {
    if (attemptByUser) return;    // користувач саме підключається — не заважаємо
    WiFi.disconnect();            // автоматичну спробу перериваємо: пошук важливіший
    attemptEndMs = millis();
    connState    = CONN_IDLE;
  }
  WiFi.scanDelete();
  WiFi.scanNetworks(true);        // true — шукати у фоні, не зупиняючи програму
}

// GET /wifi/scan[?start=1] — список мереж довкола
void handleScan() {
  if (!wifiPortalFromSetupNetwork()) { sendJson(403, "{\"status\":\"forbidden\"}"); return; }

  if (server->hasArg("start")) startScan();

  int16_t count = WiFi.scanComplete();
  if (count < 0) {
    if (count == WIFI_SCAN_FAILED) startScan();   // пошук ще не починався або зірвався
    sendJson(200, "{\"status\":\"scanning\"}");
    return;
  }

  String json = "{\"status\":\"done\",\"networks\":[";
  bool first = true;
  for (int i = 0; i < count; i++) {
    String ssid = WiFi.SSID(i);
    if (ssid.length() == 0) continue;             // приховані мережі пропускаємо
    if (!first) json += ',';
    first = false;
    json += "{\"ssid\":\"" + wifiPortalJsonEscape(ssid) + "\",\"rssi\":" + String(WiFi.RSSI(i));
    json += ",\"open\":";
    json += (WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "true" : "false";
    json += '}';
  }
  json += "]}";
  sendJson(200, json);
}

// POST /wifi/connect (ssid, pass) — підключитися до вибраної мережі
void handleConnect() {
  if (!wifiPortalFromSetupNetwork()) { sendJson(403, "{\"ok\":false}"); return; }

  String ssid = server->arg("ssid");
  String pass = server->arg("pass");
  if (ssid.length() == 0 || ssid.length() > 32 || pass.length() > 64) {
    sendJson(400, "{\"ok\":false}");
    return;
  }

  sendJson(200, "{\"ok\":true}");   // спершу відповідь, бо під час підключення зв'язок може "моргнути"
  beginConnect(ssid, pass, true);
}

// GET /wifi/status — що зараз відбувається
void handleStatus() {
  const char* state = "idle";
  if (isOnline())                                          state = "connected";
  else if (connState == CONN_CONNECTING && attemptByUser)  state = "connecting";
  else if (connState == CONN_FAILED)                       state = "failed";

  String json = "{\"state\":\"";
  json += state;
  json += "\",\"ssid\":\"" + wifiPortalJsonEscape(attemptSsid);
  json += "\",\"ip\":\"";
  if (isOnline()) json += WiFi.localIP().toString();
  json += "\",\"host\":\"" + wifiPortalJsonEscape(cfg.hostname);
  json += "\",\"ap\":\"" + wifiPortalJsonEscape(cfg.apSsid);
  json += "\",\"name\":\"" + wifiPortalJsonEscape(cfg.deviceName);
  json += "\",\"error\":\"";
  if (connState == CONN_FAILED) json += attemptError;
  json += "\"}";
  sendJson(200, json);
}

void handleNotFound() {
  if (wifiPortalHandleCaptive()) return;
  server->send(404, "text/plain; charset=utf-8", "Сторінку не знайдено");
}

// ======================== Світлодіод стану і кнопка =======================

void updateStatusLed() {
  if (cfg.statusLedPin < 0) return;

  bool on;
  if (connState == CONN_CONNECTING) on = (millis() / 100) % 2 == 0;    // швидко блимає
  else if (isOnline())              on = true;                         // світиться
  else                              on = (millis() / 1000) % 2 == 0;   // повільно блимає
  digitalWrite(cfg.statusLedPin, on ? HIGH : LOW);
}

void checkResetButton() {
  static bool     pressed   = false;
  static uint32_t pressedMs = 0;

  if (cfg.resetButtonPin < 0) return;

  if (digitalRead(cfg.resetButtonPin) == HIGH) {    // кнопку відпущено
    pressed = false;
    return;
  }
  if (!pressed) {
    pressed   = true;
    pressedMs = millis();
  } else if (millis() - pressedMs >= RESET_HOLD_MS) {
    Serial.println("Забуваю збережений Wi-Fi і перезапускаюсь...");
    clearCredentials();
    delay(200);
    ESP.restart();
  }
}

}  // namespace

// ============================ Зовнішній інтерфейс =========================

void wifiPortalBegin(WebServer& webServer, const WifiPortalConfig& config) {
  server = &webServer;
  cfg    = config;

  if (cfg.statusLedPin >= 0)   pinMode(cfg.statusLedPin, OUTPUT);
  if (cfg.resetButtonPin >= 0) pinMode(cfg.resetButtonPin, INPUT_PULLUP);

  WiFi.persistent(false);       // назву й пароль мережі зберігаємо самі, у Preferences
  WiFi.setHostname(cfg.hostname);
  WiFi.onEvent(onWiFiEvent);

  startSetupNetwork();

  loadCredentials();
  if (savedSsid.length() > 0) {
    beginConnect(savedSsid, savedPass, false);    // мережа вже відома — підключаємось
  } else {
    Serial.println("Збереженої мережі немає — чекаю налаштування.");
  }

  server->on("/wifi", HTTP_GET, handlePage);
  server->on("/wifi/scan", HTTP_GET, handleScan);
  server->on("/wifi/connect", HTTP_POST, handleConnect);
  server->on("/wifi/status", HTTP_GET, handleStatus);
  server->onNotFound(handleNotFound);
}

void wifiPortalLoop() {
  dnsServer.processNextRequest();
  updateConnection();
  watchConnection();
  updateAutoRetry();
  updateStatusLed();
  checkResetButton();
}

bool wifiPortalOnline() {
  return isOnline();
}

bool wifiPortalFromSetupNetwork() {
  return server != nullptr && server->client().localIP() == WiFi.softAPIP();
}

bool wifiPortalHandleCaptive() {
  if (!wifiPortalFromSetupNetwork()) return false;

  // Планшет перевіряє, чи є інтернет, звертаючись до різних сайтів.
  // Перенаправляємо все на сторінку налаштування — і вона відкривається сама.
  server->sendHeader("Location", "http://" + WiFi.softAPIP().toString() + "/wifi", true);
  server->send(302, "text/plain", "");
  return true;
}

String wifiPortalJsonEscape(const String& text) {
  String out;
  out.reserve(text.length() + 8);
  for (size_t i = 0; i < text.length(); i++) {
    char c = text[i];
    if (c == '"' || c == '\\') {
      out += '\\';
      out += c;
    } else if ((uint8_t)c < 0x20) {
      char buf[8];
      snprintf(buf, sizeof(buf), "\\u%04x", (unsigned)c);
      out += buf;
    } else {
      out += c;
    }
  }
  return out;
}
