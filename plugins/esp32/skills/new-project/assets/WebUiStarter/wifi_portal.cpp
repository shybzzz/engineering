// Реалізація модуля Wi-Fi. Опис і спосіб використання — у wifi_portal.h.

#include "wifi_portal.h"

#include <WiFi.h>
#include <DNSServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>

#include "json_tools.h"
#include "state_socket.h"
#include "web_pages.h"     // сторінки з теки web/, стиснуті gzip (tools/pack-web.js)

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

// Номери замовлень зі сторінки: за ними вона впізнає "свій" результат у каналі стану
uint32_t attemptId  = 0;       // останнє підключення, замовлене зі сторінки
uint32_t scanId     = 0;       // останній пошук мереж
bool     scanWanted = false;   // сторінка чекає на результат пошуку
uint32_t scanTryMs  = 0;

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

  Serial.printf("Мережа налаштування \"%s\" працює. Сторінка: http://%s/\n",
                cfg.apSsid, WiFi.softAPIP().toString().c_str());
}

// ============================== Пошук мереж ===============================

// Стан пошуку для сторінок — тема "wifi-networks" каналу стану.
void publishNetworks(bool scanning) {
  String json = "{\"scan\":" + String(scanId) + ",\"scanning\":";
  json += scanning ? "true" : "false";
  json += ",\"networks\":[";
  int16_t count = scanning ? 0 : WiFi.scanComplete();   // від'ємне — результату немає
  bool first = true;
  for (int i = 0; i < count; i++) {
    String ssid = WiFi.SSID(i);
    if (ssid.length() == 0) continue;             // приховані мережі пропускаємо
    if (!first) json += ',';
    first = false;
    json += "{\"ssid\":\"" + jsonEscape(ssid) + "\",\"rssi\":" + String(WiFi.RSSI(i));
    json += ",\"open\":";
    json += (WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "true" : "false";
    json += '}';
  }
  json += "]}";
  statePublish("wifi-networks", json);
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

// Чекає на результат пошуку, який замовила сторінка, і повідомляє його.
void updateScan() {
  if (!scanWanted) return;

  int16_t count = WiFi.scanComplete();
  if (count == WIFI_SCAN_RUNNING) return;
  if (count == WIFI_SCAN_FAILED) {                // пошук не почався або зірвався — пробуємо знову
    if (millis() - scanTryMs >= 1000) {
      scanTryMs = millis();
      startScan();
    }
    return;
  }
  scanWanted = false;
  publishNetworks(false);
}

// ============================== Підключення ===============================

// Починає підключення і одразу повертається; результат відстежує updateConnection().
void beginConnect(const String& ssid, const String& pass, bool byUser) {
  attemptSsid   = ssid;
  attemptPass   = pass;
  attemptByUser = byUser;
  attemptError  = "";

  WiFi.scanDelete();
  if (scanWanted) {         // мережу вже вибрано — результат пошуку більше не потрібен
    scanWanted = false;
    publishNetworks(false);
  }
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

// GET /wifi — окрема сторінка Wi-Fi (та сама панель, завжди розгорнута)
void handlePage() {
  webSend(*server, WEB_WIFI_HTML);          // web/wifi.html
}

// GET /wifi/panel.js — панель Wi-Fi, яку підключають сторінки проєкту
void handleScript() {
  webSend(*server, WEB_WIFI_PANEL_JS);      // web/wifi-panel.js
}

// Стан Wi-Fi — тема "wifi" каналу стану і відповідь GET /api/wifi
String wifiStateJson() {
  const char* state = "idle";
  if (isOnline())                                          state = "connected";
  else if (connState == CONN_CONNECTING && attemptByUser)  state = "connecting";
  else if (connState == CONN_FAILED)                       state = "failed";

  String json = "{\"state\":\"";
  json += state;
  json += "\",\"ssid\":\"" + jsonEscape(attemptSsid);
  json += "\",\"ip\":\"";
  if (isOnline()) json += WiFi.localIP().toString();
  json += "\",\"host\":\"" + jsonEscape(cfg.hostname);
  json += "\",\"ap\":\"" + jsonEscape(cfg.apSsid);
  json += "\",\"apIp\":\"" + WiFi.softAPIP().toString();
  json += "\",\"name\":\"" + jsonEscape(cfg.deviceName);
  json += "\",\"error\":\"";
  if (connState == CONN_FAILED) json += attemptError;
  json += "\",\"attempt\":" + String(attemptId);
  json += '}';
  return json;
}

// Повідомляє сторінкам стан Wi-Fi. Канал сам відкидає повтори, тож сторінки
// отримують повідомлення лише тоді, коли щось справді змінилося.
void publishWifiState() {
  static uint32_t lastMs = 0;
  if (millis() - lastMs < 200) return;
  lastMs = millis();
  statePublish("wifi", wifiStateJson());
}

void sendError(int code, const char* text) {
  sendJson(code, String("{\"error\":\"") + text + "\"}");
}

// GET /api/wifi — стан Wi-Fi (для перевірки з комп'ютера; сторінки слухають канал стану)
void handleWifiGet() {
  sendJson(200, wifiStateJson());
}

// POST /api/wifi/scans — почати пошук мереж; результат прийде каналом стану
void handleScanCreate() {
  if (!wifiPortalFromSetupNetwork()) { sendError(403, "setup network only"); return; }

  scanId++;
  scanWanted = true;
  scanTryMs  = millis();
  startScan();
  publishNetworks(true);
  sendJson(202, "{\"scan\":" + String(scanId) + "}");
}

// PUT /api/wifi/network {"ssid":"…","password":"…"} — підключитися до вибраної мережі;
// що вийшло, сторінка побачить у каналі стану
void handleNetworkPut() {
  if (!wifiPortalFromSetupNetwork()) { sendError(403, "setup network only"); return; }

  String body = server->arg("plain");
  String ssid;
  String pass;
  if (!jsonGetString(body, "ssid", ssid) || ssid.length() == 0 || ssid.length() > 32) {
    sendError(400, "ssid: text, 1-32 bytes");
    return;
  }
  jsonGetString(body, "password", pass);    // поля немає — мережа відкрита
  if (pass.length() > 64) {
    sendError(400, "password: up to 64 bytes");
    return;
  }

  attemptId++;
  sendJson(202, "{\"attempt\":" + String(attemptId) + "}");   // спершу відповідь, бо під час підключення зв'язок може "моргнути"
  beginConnect(ssid, pass, true);
}

void handleNotFound() {
  if (server->uri() == "/") { handlePage(); return; }   // проєкт не має головної сторінки
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
  stateSocketBegin(*server);

  loadCredentials();
  if (savedSsid.length() > 0) {
    beginConnect(savedSsid, savedPass, false);    // мережа вже відома — підключаємось
  } else {
    Serial.println("Збереженої мережі немає — чекаю налаштування.");
  }

  server->on("/wifi", HTTP_GET, handlePage);
  server->on("/wifi/panel.js", HTTP_GET, handleScript);
  server->on("/api/wifi", HTTP_GET, handleWifiGet);
  server->on("/api/wifi/network", HTTP_PUT, handleNetworkPut);
  server->on("/api/wifi/scans", HTTP_POST, handleScanCreate);
  server->onNotFound(handleNotFound);

  // Початковий стан обох тем — щоб сторінка отримала його, щойно підключиться
  publishNetworks(false);
  statePublish("wifi", wifiStateJson());
}

void wifiPortalLoop() {
  dnsServer.processNextRequest();
  updateConnection();
  watchConnection();
  updateAutoRetry();
  updateScan();
  publishWifiState();
  stateSocketLoop();
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
  if (server->uri() == "/") return false;    // головної сторінки немає — нема куди перенаправляти

  // Планшет перевіряє, чи є інтернет, звертаючись до різних сайтів.
  // Перенаправляємо все на головну сторінку пристрою — і вона відкривається сама.
  server->sendHeader("Location", "http://" + WiFi.softAPIP().toString() + "/", true);
  server->send(302, "text/plain", "");
  return true;
}
