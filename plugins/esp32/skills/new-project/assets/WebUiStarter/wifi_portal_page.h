#pragma once
#include <Arduino.h>

// Сторінка налаштування Wi-Fi (GET /wifi). Частина модуля wifi_portal —
// відкривається через власну мережу пристрою. Зберігається у флеш-пам'яті.
const char WIFI_PORTAL_PAGE[] PROGMEM = R"HTML(<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wi-Fi</title>
<style>
:root{--bg:#eef1f4;--card:#fff;--text:#1b2530;--muted:#66758a;--line:#d9e0e7;--accent:#178a4c;--on-accent:#fff;--danger:#b42323;--danger-bg:#fdecec}
@media (prefers-color-scheme:dark){:root{--bg:#10151b;--card:#1a222b;--text:#e7ecf1;--muted:#93a2b3;--line:#2b3642;--accent:#2fb36a;--on-accent:#06210f;--danger:#ffa0a0;--danger-bg:#3a1d1f}}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--text);font:17px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-text-size-adjust:100%}
main{max-width:460px;margin:0 auto;padding:24px 16px 40px}
header{margin-bottom:20px}
h1{margin:0;font-size:22px;line-height:1.2;overflow-wrap:anywhere}
header p{margin:2px 0 0;color:var(--muted);font-size:15px}
h2{margin:0;font-size:18px;line-height:1.3;overflow-wrap:anywhere}
p{margin:12px 0 0}
a{color:var(--accent)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}
.center{text-align:center}
.row{display:flex;align-items:center;justify-content:space-between;gap:12px}
.note{color:var(--muted);font-size:15px}
button{font:inherit;color:inherit;cursor:pointer}
.ghost{background:none;border:1px solid var(--line);border-radius:10px;padding:8px 14px;min-height:40px}
.ghost:disabled{opacity:.5}
.back{margin-bottom:14px}
.change{margin-top:18px}
.primary{width:100%;margin-top:16px;min-height:52px;border:0;border-radius:12px;background:var(--accent);color:var(--on-accent);font-weight:600;font-size:18px}
ul{list-style:none;margin:12px 0 0;padding:0}
.net{display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;min-height:54px;padding:10px 4px;background:none;border:0;border-top:1px solid var(--line);text-align:left}
.net .name{overflow-wrap:anywhere}
.net .meta{display:flex;align-items:center;gap:8px;flex:none;color:var(--muted)}
.bars{display:inline-flex;align-items:flex-end;gap:2px;height:16px}
.bars b{width:4px;border-radius:1px;background:var(--line)}
.bars b.on{background:var(--text)}
.bars b:nth-child(1){height:25%}
.bars b:nth-child(2){height:50%}
.bars b:nth-child(3){height:75%}
.bars b:nth-child(4){height:100%}
label{display:block;margin:16px 0 6px;font-size:15px;color:var(--muted)}
.pass{position:relative}
.pass input{width:100%;height:52px;padding:0 56px 0 14px;font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:12px}
.pass input:focus{outline:2px solid var(--accent);outline-offset:1px}
#eye{position:absolute;top:0;right:0;width:52px;height:52px;display:flex;align-items:center;justify-content:center;background:none;border:0;color:var(--muted)}
#eye.shown .slash{display:none}
.error{padding:10px 12px;border-radius:10px;background:var(--danger-bg);color:var(--danger);font-size:15px}
.spinner{width:44px;height:44px;margin:8px auto 16px;border:4px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.ok{width:56px;height:56px;margin:4px auto 12px;border-radius:50%;background:var(--accent);color:var(--on-accent);font-size:32px;line-height:56px}
.addr{font-size:22px;font-weight:600;overflow-wrap:anywhere}
</style>
</head>
<body>
<main>
  <header>
    <h1 id="device">Пристрій</h1>
    <p>Підключення до Wi-Fi</p>
  </header>

  <!-- Крок 1: список мереж -->
  <section class="card" id="view-list">
    <div class="row">
      <h2>Вибери свою мережу</h2>
      <button type="button" class="ghost" id="rescan">Оновити</button>
    </div>
    <p class="note" id="scan-msg">Шукаю мережі…</p>
    <ul id="nets"></ul>
    <p class="note">Пристрій бачить лише мережі 2,4 ГГц.</p>
  </section>

  <!-- Крок 2: пароль -->
  <section class="card" id="view-pass" hidden>
    <form id="form" autocomplete="off">
      <button type="button" class="ghost back" id="back">← Інша мережа</button>
      <h2>Мережа «<span id="pass-ssid"></span>»</h2>
      <div id="pass-row">
        <label for="pass">Пароль</label>
        <div class="pass">
          <input id="pass" type="password" maxlength="64" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false">
          <button type="button" id="eye" aria-label="Показати пароль" aria-pressed="false">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
              <line class="slash" x1="3" y1="3" x2="21" y2="21"/>
            </svg>
          </button>
        </div>
      </div>
      <p class="note" id="open-note" hidden>Це відкрита мережа — пароль не потрібен.</p>
      <p class="error" id="error" role="alert" hidden></p>
      <button type="submit" class="primary">Підключити</button>
    </form>
  </section>

  <!-- Крок 3: очікування -->
  <section class="card center" id="view-progress" hidden>
    <div class="spinner"></div>
    <h2>Підключаюсь до «<span id="prog-ssid"></span>»…</h2>
    <p class="note">Це триває до пів хвилини. Якщо сторінка перестане відповідати — підключись до цієї мережі та відкрий <b>http://<span class="host">пристрій.local</span></b></p>
  </section>

  <!-- Крок 4: підключено (цей самий екран бачать, коли заходять пізніше) -->
  <section class="card center" id="view-done" hidden>
    <div class="ok" aria-hidden="true">✓</div>
    <h2>Wi-Fi підключено</h2>
    <p>Пристрій у мережі «<span id="done-ssid"></span>».</p>
    <p>Щоб відкрити його сторінку, підключись до цієї ж мережі та відкрий:</p>
    <p><a class="addr" id="done-ip"></a></p>
    <p class="note">або <a id="done-host"></a></p>
    <button type="button" class="ghost change" id="change">Вибрати іншу мережу</button>
  </section>
</main>

<script>
const $ = id => document.getElementById(id);
const VIEWS = ['list', 'pass', 'progress', 'done'];
const ERRORS = {
  password: 'Схоже, пароль неправильний. Перевір його (натисни на око) і спробуй ще раз.',
  notfound: 'Не бачу цю мережу. Можливо, роутер задалеко або вимкнений.',
  other: 'Не вдалося підключитися. Перевір пароль і спробуй ще раз.',
  lost: 'Пристрій не відповідає. Перевір, чи ти досі підключений до його мережі.'
};
const LOCK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="Потрібен пароль"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';

let selected = null;   // вибрана мережа: {ssid, open}

function show(name) {
  VIEWS.forEach(v => { $('view-' + v).hidden = (v !== name); });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Запит до пристрою з обмеженням часу: його мережа може ненадовго зникати.
function getJSON(url, options) {
  return Promise.race([
    fetch(url, options).then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }),
    new Promise((resolve, reject) => setTimeout(() => reject(new Error('timeout')), 5000))
  ]);
}

// ---------- Список мереж ----------

async function scan() {
  show('list');
  $('nets').innerHTML = '';
  $('scan-msg').textContent = 'Шукаю мережі…';
  $('scan-msg').hidden = false;
  $('rescan').disabled = true;

  let url = '/wifi/scan?start=1';
  for (;;) {
    let data = null;
    try { data = await getJSON(url); } catch (e) { /* спробуємо ще раз */ }
    if (data) url = '/wifi/scan';
    if (data && data.status === 'done') { renderNets(data.networks); break; }
    await sleep(1000);
  }
  $('rescan').disabled = false;
}

function bars(rssi) {
  const level = rssi >= -55 ? 4 : rssi >= -67 ? 3 : rssi >= -78 ? 2 : 1;
  let html = '<span class="bars" role="img" aria-label="Сигнал ' + level + ' з 4">';
  for (let i = 1; i <= 4; i++) html += '<b' + (i <= level ? ' class="on"' : '') + '></b>';
  return html + '</span>';
}

function renderNets(list) {
  // Найсильніші зверху; одна назва — один рядок (у роутера може бути кілька антен).
  const seen = new Set();
  const nets = list.slice().sort((a, b) => b.rssi - a.rssi).filter(n => {
    if (seen.has(n.ssid)) return false;
    seen.add(n.ssid);
    return true;
  });

  const ul = $('nets');
  ul.innerHTML = '';
  nets.forEach(n => {
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = n.ssid;          // textContent — назва мережі не може зламати сторінку

    const meta = document.createElement('span');
    meta.className = 'meta';
    meta.innerHTML = (n.open ? '' : LOCK) + bars(n.rssi);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'net';
    btn.appendChild(name);
    btn.appendChild(meta);
    btn.addEventListener('click', () => choose(n));

    const li = document.createElement('li');
    li.appendChild(btn);
    ul.appendChild(li);
  });

  $('scan-msg').textContent = 'Мереж не знайдено. Підійди ближче до роутера й натисни «Оновити».';
  $('scan-msg').hidden = nets.length > 0;
}

// ---------- Пароль ----------

function setPasswordShown(shown) {
  $('pass').type = shown ? 'text' : 'password';
  $('eye').classList.toggle('shown', shown);
  $('eye').setAttribute('aria-label', shown ? 'Сховати пароль' : 'Показати пароль');
  $('eye').setAttribute('aria-pressed', shown ? 'true' : 'false');
}

function showError(text) {
  $('error').textContent = text;
  $('error').hidden = !text;
}

function prepare(net) {
  selected = net;
  $('pass-ssid').textContent = net.ssid;
  $('pass-row').hidden = net.open;
  $('open-note').hidden = !net.open;
  $('pass').value = '';
  setPasswordShown(false);
  showError('');
}

function choose(net) {
  prepare(net);
  show('pass');
  if (!net.open) $('pass').focus();
}

// ---------- Підключення ----------

function showProgress(ssid) {
  $('prog-ssid').textContent = ssid;
  show('progress');
}

function setLink(a, url) {
  a.href = url;
  a.textContent = url.replace(/\/$/, '');
}

function showDone(s) {
  $('done-ssid').textContent = s.ssid;
  setLink($('done-ip'), 'http://' + s.ip + '/');
  setLink($('done-host'), 'http://' + s.host + '.local/');
  show('done');
}

async function pollStatus() {
  for (;;) {
    await sleep(1000);
    let s;
    try { s = await getJSON('/wifi/status'); } catch (e) { continue; }
    if (s.state === 'connecting') continue;
    if (s.state === 'connected') { showDone(s); return; }
    show('pass');
    showError(s.state === 'failed' ? (ERRORS[s.error] || ERRORS.other) : ERRORS.other);
    return;
  }
}

$('rescan').addEventListener('click', scan);
$('change').addEventListener('click', scan);
$('back').addEventListener('click', () => show('list'));

$('eye').addEventListener('click', () => {
  setPasswordShown($('pass').type === 'password');
  $('pass').focus();
});

$('form').addEventListener('submit', async e => {
  e.preventDefault();
  const pass = selected.open ? '' : $('pass').value;
  if (!selected.open && !pass) { showError('Введи пароль від Wi-Fi.'); return; }

  showError('');
  showProgress(selected.ssid);
  try {
    await getJSON('/wifi/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'ssid=' + encodeURIComponent(selected.ssid) + '&pass=' + encodeURIComponent(pass)
    });
  } catch (err) {
    show('pass');
    showError(ERRORS.lost);
    return;
  }
  pollStatus();
});

// ---------- Старт ----------

(async function init() {
  let s = null;
  try { s = await getJSON('/wifi/status'); } catch (e) { /* не страшно */ }

  if (s) {
    $('device').textContent = s.name;
    document.title = s.name + ' — Wi-Fi';
    document.querySelectorAll('.host').forEach(el => { el.textContent = s.host + '.local'; });
  }

  // Пристрій уже в мережі — показуємо його адресу (мережу можна змінити кнопкою).
  if (s && s.state === 'connected') { showDone(s); return; }
  // Сторінку могли перезавантажити посеред підключення — показуємо, на чому зупинились.
  if (s && s.state === 'connecting') {
    prepare({ ssid: s.ssid, open: false });
    showProgress(s.ssid);
    pollStatus();
    return;
  }
  scan();
})();
</script>
</body>
</html>
)HTML";
