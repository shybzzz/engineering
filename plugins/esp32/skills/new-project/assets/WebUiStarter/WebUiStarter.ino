/*
  WebUiStarter — стартовий скетч для проєкту на ESP32 з веб-інтерфейсом.

  Що вже працює
  -------------
  - Wi-Fi: власна мережа налаштування, вибір домашньої мережі зі сторінки,
    збереження і автопідключення — усе це робить модуль wifi_portal
    (опис — у wifi_portal.h).
  - Канал стану (WebSocket): пристрій сам повідомляє сторінкам, що в нього
    змінилося; стан Wi-Fi вже йде цим каналом (опис — у state_socket.h).
  - Головна сторінка (web/index.html) з панеллю Wi-Fi: поки є зв'язок із
    домашньою мережею, панель згорнута в кнопку і місце на сторінці віддане
    вмісту.
  Файли wifi_portal.*, state_socket.*, json_tools.h, web/wifi.html,
  web/wifi-panel.js, web/state.js і tools/pack-web.js змінювати не треба.

  Сторінки і gzip
  ---------------
  Сторінки — звичайні файли в теці web/. У прошивку вони потрапляють
  стиснутими gzip, через web_pages.h, який створює скрипт:

      node tools/pack-web.js

  Запускай його після кожної зміни у web/, перед збиранням. Пристрій віддає
  стиснуте як є (webSend() додає заголовок Content-Encoding: gzip), розпаковує
  браузер. web_pages.h руками не редагуй.

  Що додавати
  -----------
  - Сторінки проєкту — файли в web/ (потім "node tools/pack-web.js"), їхні
    адреси — у setup(): server.on("/about", HTTP_GET, [] { webSend(server, WEB_ABOUT_HTML); });
    Назва — з назви файлу: web/about.html -> WEB_ABOUT_HTML.
  - Стан, який сторінка показує безперервно, — лише каналом стану:
    statePublish("тема", json) у setup() і після кожної зміни. Сторінка
    пристрій не опитує.
  - Дії користувача — REST API: адреса називає річ (/api/lamp, /api/leds/3),
    метод — що з нею зробити (PUT, PATCH, POST, DELETE), тіло і відповідь —
    JSON, код відповіді каже, що вийшло. Приклад — нижче, у коментарях.
  - Логіку проєкту — у loop(), без довгих delay(): веб-сервер, Wi-Fi і канал
    стану обслуговуються в кожному проході loop().

  Плата:      ESP32 Dev Module (ядро "esp32 by Espressif Systems" 3.x)
  Бібліотеки: лише ті, що входять до ядра ESP32.
*/

#include <WebServer.h>
#include "wifi_portal.h"
#include "state_socket.h"
#include "json_tools.h"
#include "web_pages.h"     // тека web/, стиснута gzip (tools/pack-web.js)

WebServer        server(80);
WifiPortalConfig wifiConfig;

// GET / — головна сторінка проєкту (однакова в домашній мережі та в мережі налаштування)
void handleRoot() {
  webSend(server, WEB_INDEX_HTML);          // web/index.html
}

/*
  Приклад: лампа, якою керують зі сторінки.

  bool lampOn = false;

  String lampJson() {
    return String("{\"on\":") + (lampOn ? "true" : "false") + "}";
  }

  // PUT /api/lamp {"on":true} — дія користувача
  void handleLampPut() {
    bool on;
    if (!jsonGetBool(server.arg("plain"), "on", on)) {
      server.send(400, "application/json", "{\"error\":\"body must be {\\\"on\\\":true|false}\"}");
      return;
    }
    lampOn = on;
    digitalWrite(LAMP_PIN, on ? HIGH : LOW);
    statePublish("lamp", lampJson());            // новий стан — усім відкритим сторінкам
    server.send(200, "application/json", lampJson());
  }

  У setup():  statePublish("lamp", lampJson());                  // початковий стан
              server.on("/api/lamp", HTTP_PUT, handleLampPut);
  На сторінці (web/index.html), перед /wifi/panel.js:

    <script src="/state.js"></script>
    <script>
      const button = document.getElementById('lamp');
      let on = false;
      // Стан: пристрій повідомляє сам — щойно сторінка відкрилась і після кожної зміни.
      deviceState.on('lamp', data => { on = data.on; button.classList.toggle('on', on); });
      // Зв'язок із пристроєм є / зник.
      deviceState.onLink(connected => { button.disabled = !connected; });
      // Дія користувача: запит до REST API. Що вийшло — прийде каналом стану.
      button.addEventListener('click', () => fetch('/api/lamp', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ on: !on })
      }));
    </script>

  Адреса з номером: #include <uri/UriBraces.h>, server.on(UriBraces("/api/leds/{}"), HTTP_PUT, ...),
  номер — server.pathArg(0); немає такого — відповідь 404.
*/

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("=== WebUiStarter ===");

  wifiConfig.deviceName = "WebUiStarter";         // назва на сторінках
  wifiConfig.apSsid     = "WebUiStarter-Setup";   // мережа налаштування
  wifiConfig.hostname   = "webuistarter";         // http://webuistarter.local
  wifiPortalBegin(server, wifiConfig);            // Wi-Fi і канал стану

  server.on("/", HTTP_GET, handleRoot);
  // statePublish("lamp", lampJson());                    // початковий стан тем проєкту
  // server.on("/api/lamp", HTTP_PUT, handleLampPut);     // дії користувача — REST API
  server.begin();
}

void loop() {
  wifiPortalLoop();          // Wi-Fi і канал стану
  server.handleClient();     // сторінки і REST API

  // ... логіка проєкту; змінився стан — statePublish(...) ...

  delay(2);   // даємо попрацювати фоновим задачам Wi-Fi
}
