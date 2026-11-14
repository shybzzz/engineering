#pragma once
#include <Arduino.h>

// Сторінки проєкту. Зберігаються у флеш-пам'яті (PROGMEM).
// Сторінка налаштування Wi-Fi сюди не входить — вона в модулі wifi_portal.

// ---------------------------------------------------------------------------
//  Головна сторінка — відкривається за адресою пристрою в домашній мережі.
//  Це заготовка: заміни вміст <section> на інтерфейс проєкту.
// ---------------------------------------------------------------------------
const char HOME_PAGE[] PROGMEM = R"HTML(<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Пристрій</title>
<style>
:root{--bg:#eef1f4;--card:#fff;--text:#1b2530;--muted:#66758a;--line:#d9e0e7;--accent:#178a4c}
@media (prefers-color-scheme:dark){:root{--bg:#10151b;--card:#1a222b;--text:#e7ecf1;--muted:#93a2b3;--line:#2b3642;--accent:#2fb36a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:17px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-text-size-adjust:100%}
main{max-width:460px;margin:0 auto;padding:24px 16px 40px}
header{margin-bottom:20px}
h1{margin:0;font-size:22px;line-height:1.2;overflow-wrap:anywhere}
header p{margin:2px 0 0;color:var(--muted);font-size:15px}
h2{margin:0;font-size:18px}
p{margin:12px 0 0}
b{overflow-wrap:anywhere}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}
.note{color:var(--muted);font-size:15px}
</style>
</head>
<body>
<main>
  <header>
    <h1 id="device">Пристрій</h1>
    <p>На зв'язку</p>
  </header>
  <section class="card">
    <h2>Wi-Fi підключено</h2>
    <p>Мережа: <b id="ssid">…</b><br>Адреса: <b id="ip">…</b></p>
    <p class="note">Тут буде інтерфейс проєкту.</p>
    <p class="note">Щоб вибрати іншу мережу Wi-Fi, підключись до мережі «<span id="ap">…</span>».</p>
  </section>
</main>
<script>
fetch('/wifi/status').then(r => r.json()).then(s => {
  document.title = s.name;
  document.getElementById('device').textContent = s.name;
  document.getElementById('ssid').textContent = s.ssid;
  document.getElementById('ip').textContent = s.ip;
  document.getElementById('ap').textContent = s.ap;
});
</script>
</body>
</html>
)HTML";
