#pragma once
#include <Arduino.h>

// Сторінки проєкту. Зберігаються у флеш-пам'яті (PROGMEM).
// Панель Wi-Fi сюди не входить — вона в модулі wifi_portal; сторінка лише
// відводить їй місце (#wifi-button, #wifi-panel) і підключає /wifi/panel.js.

// ---------------------------------------------------------------------------
//  Головна сторінка — відкривається за адресою пристрою в обох мережах.
//  Це заготовка: заміни <section> на інтерфейс проєкту.
//
//  Wi-Fi: поки є зв'язок із домашньою мережею, панель згорнута в кнопку
//  в шапці й не займає місця; без зв'язку — розгорнута над вмістом.
// ---------------------------------------------------------------------------
const char HOME_PAGE[] PROGMEM = R"HTML(<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title data-wifi="name">Пристрій</title>
<style>
:root{--bg:#eef1f4;--card:#fff;--text:#1b2530;--muted:#66758a;--line:#d9e0e7;--accent:#178a4c;--on-accent:#fff;--danger:#b42323;--danger-bg:#fdecec}
@media (prefers-color-scheme:dark){:root{--bg:#10151b;--card:#1a222b;--text:#e7ecf1;--muted:#93a2b3;--line:#2b3642;--accent:#2fb36a;--on-accent:#06210f;--danger:#ffa0a0;--danger-bg:#3a1d1f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:17px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-text-size-adjust:100%}
main{max-width:460px;margin:0 auto;padding:24px 16px 40px}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:20px}
h1{margin:0;font-size:22px;line-height:1.2;overflow-wrap:anywhere}
h2{margin:0;font-size:18px}
p{margin:12px 0 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}
.note{color:var(--muted);font-size:15px}
</style>
</head>
<body>
<main>
  <header>
    <h1 data-wifi="name">Пристрій</h1>
    <span id="wifi-button"></span>   <!-- кнопка Wi-Fi -->
  </header>
  <div id="wifi-panel"></div>        <!-- тут розгортається панель Wi-Fi -->

  <section class="card">
    <h2>Тут буде інтерфейс проєкту</h2>
    <p class="note">Заміни цей блок на кнопки, показники чи інший вміст.</p>
  </section>
</main>
<script src="/wifi/panel.js"></script>
</body>
</html>
)HTML";
