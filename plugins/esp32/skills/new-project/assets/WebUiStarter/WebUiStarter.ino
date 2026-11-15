/*
  WebUiStarter — стартовий скетч для проєкту на ESP32 з веб-інтерфейсом.

  Що вже працює
  -------------
  - Wi-Fi: власна мережа налаштування, вибір домашньої мережі зі сторінки,
    збереження і автопідключення — усе це робить модуль wifi_portal
    (опис — у wifi_portal.h; файли wifi_portal.* змінювати не треба).
  - Головна сторінка (pages.h) з панеллю Wi-Fi: поки є зв'язок із домашньою
    мережею, панель згорнута в кнопку і місце на сторінці віддане вмісту.

  Що додавати
  -----------
  - Сторінки проєкту — у pages.h, їхні адреси — у setup() через server.on().
  - Логіку проєкту — у loop(), без довгих delay(): веб-сервер і Wi-Fi
    обслуговуються в кожному проході loop().

  Плата:      ESP32 Dev Module (ядро "esp32 by Espressif Systems" 3.x)
  Бібліотеки: лише ті, що входять до ядра ESP32.
*/

#include <WebServer.h>
#include "wifi_portal.h"
#include "pages.h"

WebServer        server(80);
WifiPortalConfig wifiConfig;

// GET / — головна сторінка проєкту (однакова в домашній мережі та в мережі налаштування)
void handleRoot() {
  server.sendHeader("Cache-Control", "no-store");
  server.send_P(200, "text/html; charset=utf-8", HOME_PAGE);
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("=== WebUiStarter ===");

  wifiConfig.deviceName = "WebUiStarter";         // назва на сторінках
  wifiConfig.apSsid     = "WebUiStarter-Setup";   // мережа налаштування
  wifiConfig.hostname   = "webuistarter";         // http://webuistarter.local
  wifiPortalBegin(server, wifiConfig);

  server.on("/", HTTP_GET, handleRoot);
  // server.on("/api/...", HTTP_POST, handleSomething);   // адреси проєкту
  server.begin();
}

void loop() {
  wifiPortalLoop();
  server.handleClient();

  // ... логіка проєкту ...

  delay(2);   // даємо попрацювати фоновим задачам Wi-Fi
}
