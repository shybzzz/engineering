// Панель Wi-Fi (GET /wifi/panel.js) — частина модуля wifi_portal, не редагуй.
// Сторінка відводить їй місце: <span id="wifi-button"></span> (кнопка, зазвичай у шапці),
// <div id="wifi-panel"></div> (де розгортатись) і підключає цей скрипт наприкінці <body>.
// Є зв'язок із домашньою мережею — панель згорнута в кнопку; немає — розгорнута.
// Кольори бере зі змінних сторінки --bg, --card, --text, --muted, --line, --accent,
// --on-accent, --danger, --danger-bg; елементи з data-wifi="name|ssid|ip|host|ap" заповнює сама.
// Стан Wi-Fi приходить каналом стану (/state.js: теми "hello", "wifi", "wifi-networks"),
// дії користувача — запити до /api/wifi/... (опис — у wifi_portal.h).
(function () {
'use strict';

const panel = document.getElementById('wifi-panel');
if (!panel) return;

const CSS = `
.wp{--wp-bg:var(--bg,#eef1f4);--wp-card:var(--card,#fff);--wp-text:var(--text,#1b2530);--wp-muted:var(--muted,#66758a);--wp-line:var(--line,#d9e0e7);--wp-accent:var(--accent,#178a4c);--wp-on-accent:var(--on-accent,#fff);--wp-danger:var(--danger,#b42323);--wp-danger-bg:var(--danger-bg,#fdecec)}
@media (prefers-color-scheme:dark){.wp{--wp-bg:var(--bg,#10151b);--wp-card:var(--card,#1a222b);--wp-text:var(--text,#e7ecf1);--wp-muted:var(--muted,#93a2b3);--wp-line:var(--line,#2b3642);--wp-accent:var(--accent,#2fb36a);--wp-on-accent:var(--on-accent,#06210f);--wp-danger:var(--danger,#ffa0a0);--wp-danger-bg:var(--danger-bg,#3a1d1f)}}
.wp,.wp *{box-sizing:border-box}
.wp[hidden],.wp [hidden]{display:none!important}
.wp-toggle,.wp-ghost,.wp-primary,.wp-net,.wp-eye{font:inherit;color:inherit;cursor:pointer}
.wp-toggle{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:8px 14px;font-size:15px;line-height:1.2;white-space:nowrap;color:var(--wp-text);background:var(--wp-card);border:1px solid var(--wp-line);border-radius:999px}
.wp-toggle svg{flex:none;color:var(--wp-muted)}
.wp-toggle.wp-on svg{color:var(--wp-accent)}
.wp-toggle.wp-off svg{color:var(--wp-danger)}
.wp-toggle .wp-cut{display:none}
.wp-toggle.wp-off .wp-cut{display:inline}
.wp-toggle[aria-expanded=true]{border-color:var(--wp-accent)}
.wp-panel{margin:0 0 16px;padding:18px;font-size:17px;line-height:1.45;text-align:left;color:var(--wp-text);background:var(--wp-card);border:1px solid var(--wp-line);border-radius:16px}
.wp-panel h2{margin:0;font-size:18px;line-height:1.3;font-weight:700;overflow-wrap:anywhere}
.wp-panel p{margin:12px 0 0}
.wp-panel a{color:var(--wp-accent)}
.wp-panel b{overflow-wrap:anywhere}
.wp-center{text-align:center}
.wp-row{display:flex;align-items:center;justify-content:space-between;gap:12px}
.wp-panel .wp-note{color:var(--wp-muted);font-size:15px}
.wp-ghost{background:none;border:1px solid var(--wp-line);border-radius:10px;padding:8px 14px;min-height:40px}
.wp-ghost:disabled{opacity:.5}
.wp-back{margin-bottom:14px}
.wp-change{margin-top:18px}
.wp-primary{width:100%;margin-top:16px;min-height:52px;border:0;border-radius:12px;background:var(--wp-accent);color:var(--wp-on-accent);font-weight:600;font-size:18px}
.wp-nets{list-style:none;margin:12px 0 0;padding:0}
.wp-net{display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;min-height:54px;padding:10px 4px;background:none;border:0;border-top:1px solid var(--wp-line);text-align:left}
.wp-name{overflow-wrap:anywhere}
.wp-meta{display:flex;align-items:center;gap:8px;flex:none;color:var(--wp-muted)}
.wp-bars{display:inline-flex;align-items:flex-end;gap:2px;height:16px}
.wp-bars i{width:4px;border-radius:1px;background:var(--wp-line)}
.wp-bars i.wp-lit{background:var(--wp-text)}
.wp-bars i:nth-child(1){height:25%}
.wp-bars i:nth-child(2){height:50%}
.wp-bars i:nth-child(3){height:75%}
.wp-bars i:nth-child(4){height:100%}
.wp-label{display:block;margin:16px 0 6px;font-size:15px;color:var(--wp-muted)}
.wp-field{position:relative}
.wp-field input{width:100%;height:52px;margin:0;padding:0 56px 0 14px;font:inherit;color:inherit;background:var(--wp-bg);border:1px solid var(--wp-line);border-radius:12px}
.wp-field input:focus{outline:2px solid var(--wp-accent);outline-offset:1px}
.wp-eye{position:absolute;top:0;right:0;width:52px;height:52px;display:flex;align-items:center;justify-content:center;background:none;border:0;color:var(--wp-muted)}
.wp-eye.wp-shown .wp-slash{display:none}
.wp-panel .wp-error{padding:10px 12px;border-radius:10px;background:var(--wp-danger-bg);color:var(--wp-danger);font-size:15px}
.wp-spinner{width:44px;height:44px;margin:8px auto 16px;border:4px solid var(--wp-line);border-top-color:var(--wp-accent);border-radius:50%;animation:wp-spin 1s linear infinite}
@keyframes wp-spin{to{transform:rotate(360deg)}}
.wp-ok{width:56px;height:56px;margin:4px auto 12px;border-radius:50%;background:var(--wp-accent);color:var(--wp-on-accent);font-size:32px;line-height:56px}
.wp-addr{font-size:22px;font-weight:600;overflow-wrap:anywhere}
`;

const BUTTON = `
<button type="button" class="wp-toggle" id="wp-toggle" aria-controls="wifi-panel" aria-expanded="false" aria-label="Wi-Fi">
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M1.42 9a16 16 0 0 1 21.16 0"/>
    <path d="M5 12.55a11 11 0 0 1 14.08 0"/>
    <path d="M8.53 16.11a6 6 0 0 1 6.95 0"/>
    <line x1="12" y1="20" x2="12.01" y2="20"/>
    <line class="wp-cut" x1="3" y1="3" x2="21" y2="21"/>
  </svg>
  <span>Wi-Fi</span>
</button>`;

const PANEL = `
<div id="wp-view-list">
  <div class="wp-row">
    <h2>Вибери свою мережу</h2>
    <button type="button" class="wp-ghost" id="wp-rescan">Оновити</button>
  </div>
  <p class="wp-note" id="wp-scan-msg">Шукаю мережі…</p>
  <ul class="wp-nets" id="wp-nets"></ul>
  <p class="wp-note">Пристрій бачить лише мережі 2,4 ГГц.</p>
</div>

<form id="wp-view-pass" autocomplete="off" hidden>
  <button type="button" class="wp-ghost wp-back" id="wp-back">← Інша мережа</button>
  <h2>Мережа «<span id="wp-pass-ssid"></span>»</h2>
  <div id="wp-pass-row">
    <label class="wp-label" for="wp-password">Пароль</label>
    <div class="wp-field">
      <input id="wp-password" type="password" maxlength="64" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false">
      <button type="button" class="wp-eye" id="wp-eye" aria-label="Показати пароль" aria-pressed="false">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
          <circle cx="12" cy="12" r="3"/>
          <line class="wp-slash" x1="3" y1="3" x2="21" y2="21"/>
        </svg>
      </button>
    </div>
  </div>
  <p class="wp-note" id="wp-open-note" hidden>Це відкрита мережа — пароль не потрібен.</p>
  <p class="wp-error" id="wp-error" role="alert" hidden></p>
  <button type="submit" class="wp-primary">Підключити</button>
</form>

<div class="wp-center" id="wp-view-progress" hidden>
  <div class="wp-spinner"></div>
  <h2>Підключаюсь до «<span id="wp-prog-ssid"></span>»…</h2>
  <p class="wp-note">Це триває до пів хвилини. Якщо сторінка перестане відповідати — підключись до цієї мережі та відкрий <b>http://<span class="wp-host">пристрій.local</span></b></p>
</div>

<div class="wp-center" id="wp-view-done" hidden>
  <div class="wp-ok" id="wp-done-ok" aria-hidden="true">✓</div>
  <h2 id="wp-done-title">Wi-Fi підключено</h2>
  <div id="wp-done-info">
    <p>Пристрій у мережі «<span id="wp-done-ssid"></span>».</p>
    <p id="wp-done-how"></p>
    <p><a class="wp-addr" id="wp-done-ip"></a></p>
    <p class="wp-note">або <a id="wp-done-host"></a></p>
  </div>
  <button type="button" class="wp-ghost wp-change" id="wp-change">Вибрати іншу мережу</button>
  <p class="wp-note" id="wp-done-remote" hidden>Щоб вибрати іншу мережу, підключись до Wi-Fi «<span id="wp-done-ap"></span>» і відкрий <b id="wp-done-apip"></b></p>
</div>`;

// ---------- Вбудовування у сторінку ----------

let holder = document.getElementById('wifi-button');
if (!holder) {
  // Місця для кнопки на сторінці немає — ставимо її над панеллю.
  holder = document.createElement('div');
  holder.style.cssText = 'text-align:right;margin:0 0 12px';
  panel.parentNode.insertBefore(holder, panel);
}

const style = document.createElement('style');
style.textContent = CSS;
document.head.appendChild(style);

holder.classList.add('wp');
holder.innerHTML = BUTTON;
panel.classList.add('wp', 'wp-panel');
panel.hidden = true;
panel.innerHTML = PANEL;

const $ = id => document.getElementById('wp-' + id);
const VIEWS = ['list', 'pass', 'progress', 'done'];
const ERRORS = {
  password: 'Схоже, пароль неправильний. Перевір його (натисни на око) і спробуй ще раз.',
  notfound: 'Не бачу цю мережу. Можливо, роутер задалеко або вимкнений.',
  other: 'Не вдалося підключитися. Перевір пароль і спробуй ще раз.',
  lost: 'Пристрій не відповідає. Перевір, чи ти досі підключений до його мережі.'
};
const LOCK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="Потрібен пароль"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';

const toggle = $('toggle');
let selected = null;        // вибрана мережа: {ssid, open}
let view = '';              // що зараз показує панель
let via = '';               // адреса пристрою, через яку відкрито сторінку (тема "hello")
let setup = false;          // сторінку відкрито через мережу налаштування
let wifi = null;            // останній стан Wi-Fi від пристрою (тема "wifi")
let nets = null;            // останній стан пошуку мереж (тема "wifi-networks")
let scanWaiting = false;    // чекаємо на результат пошуку
let scanWanted = Infinity;  // …саме з таким номером (або новішим)
let scanTimer = 0;
let connectWaiting = false; // чекаємо на результат підключення
let attemptWanted = Infinity;

function show(name) {
  view = name;
  VIEWS.forEach(v => { $('view-' + v).hidden = (v !== name); });
}

// Дія користувача — запит до пристрою. Обмеження часу: його мережа може
// ненадовго зникати. Те, що з дії вийшло, приходить каналом стану.
function act(method, url, body) {
  return Promise.race([
    fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }),
    new Promise((resolve, reject) => setTimeout(() => reject(new Error('timeout')), 5000))
  ]);
}

// ---------- Кнопка: згорнути / розгорнути ----------

function setOpen(open) {
  panel.hidden = !open;
  toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
}

// Показує стан на кнопці та заповнює елементи сторінки з data-wifi="...".
function applyStatus(s) {
  const online = s.state === 'connected';
  const label = online ? 'Wi-Fi: підключено до «' + s.ssid + '»' : 'Wi-Fi: не підключено';
  toggle.classList.toggle('wp-on', online);
  toggle.classList.toggle('wp-off', !online);
  toggle.title = label;
  toggle.setAttribute('aria-label', label);

  document.querySelectorAll('[data-wifi]').forEach(el => {
    const value = s[el.getAttribute('data-wifi')];
    if (typeof value === 'string' && value) el.textContent = value;
  });
  panel.querySelectorAll('.wp-host').forEach(el => { el.textContent = s.host + '.local'; });
}

// ---------- Список мереж ----------

function scan() {
  show('list');
  $('nets').innerHTML = '';
  $('scan-msg').textContent = 'Шукаю мережі…';
  $('scan-msg').hidden = false;
  $('rescan').disabled = true;

  scanWaiting = true;
  scanWanted = Infinity;    // номер пошуку дізнаємось із відповіді пристрою
  requestScan();
}

// Просить пристрій почати пошук. Список мереж прийде каналом стану.
async function requestScan() {
  clearTimeout(scanTimer);
  if (!scanWaiting) return;
  // Результат так і не прийшов (пристрій перезапустився?) — попросимо ще раз.
  scanTimer = setTimeout(requestScan, 15000);
  try {
    scanWanted = (await act('POST', '/api/wifi/scans')).scan;
    checkNets();
  } catch (e) {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(requestScan, 1500);
  }
}

// Показує список, коли прийшов результат саме нашого пошуку (а не давнішого).
function checkNets() {
  if (!scanWaiting || !nets || nets.scanning || nets.scan < scanWanted) return;
  scanWaiting = false;
  clearTimeout(scanTimer);
  renderNets(nets.networks);
  $('rescan').disabled = false;
}

function bars(rssi) {
  const level = rssi >= -55 ? 4 : rssi >= -67 ? 3 : rssi >= -78 ? 2 : 1;
  let html = '<span class="wp-bars" role="img" aria-label="Сигнал ' + level + ' з 4">';
  for (let i = 1; i <= 4; i++) html += '<i' + (i <= level ? ' class="wp-lit"' : '') + '></i>';
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
    name.className = 'wp-name';
    name.textContent = n.ssid;          // textContent — назва мережі не може зламати сторінку

    const meta = document.createElement('span');
    meta.className = 'wp-meta';
    meta.innerHTML = (n.open ? '' : LOCK) + bars(n.rssi);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'wp-net';
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
  $('password').type = shown ? 'text' : 'password';
  $('eye').classList.toggle('wp-shown', shown);
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
  $('password').value = '';
  setPasswordShown(false);
  showError('');
}

function choose(net) {
  prepare(net);
  show('pass');
  if (!net.open) $('password').focus();
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

// Відомості про підключення. Змінити мережу можна лише через мережу налаштування.
function showDone(s) {
  const online = s.state === 'connected';
  $('done-ok').hidden = !online;
  $('done-title').textContent = online ? 'Wi-Fi підключено' : 'Wi-Fi не підключено';
  $('done-info').hidden = !online;
  $('done-ssid').textContent = s.ssid;
  $('done-how').textContent = setup
    ? 'Щоб відкрити його з цієї мережі, підключись до неї та відкрий:'
    : 'Його адреса в цій мережі:';
  setLink($('done-ip'), 'http://' + s.ip + '/');
  setLink($('done-host'), 'http://' + s.host + '.local/');
  $('change').hidden = !setup;
  $('done-remote').hidden = setup;
  $('done-ap').textContent = s.ap;
  $('done-apip').textContent = 'http://' + s.apIp;
  show('done');
}

// Показує, чим закінчилось підключення, яке замовила ця сторінка.
function checkAttempt() {
  if (!connectWaiting || !wifi || wifi.attempt < attemptWanted || wifi.state === 'connecting') return;
  connectWaiting = false;
  if (wifi.state === 'connected') { showDone(wifi); return; }
  show('pass');
  showError(wifi.state === 'failed' ? (ERRORS[wifi.error] || ERRORS.other) : ERRORS.other);
}

toggle.addEventListener('click', () => setOpen(panel.hidden));
$('rescan').addEventListener('click', scan);
$('change').addEventListener('click', scan);
$('back').addEventListener('click', () => show('list'));

$('eye').addEventListener('click', () => {
  setPasswordShown($('password').type === 'password');
  $('password').focus();
});

$('view-pass').addEventListener('submit', async e => {
  e.preventDefault();
  const pass = selected.open ? '' : $('password').value;
  if (!selected.open && !pass) { showError('Введи пароль від Wi-Fi.'); return; }

  showError('');
  showProgress(selected.ssid);
  connectWaiting = true;
  attemptWanted = Infinity;   // номер спроби дізнаємось із відповіді пристрою
  try {
    attemptWanted = (await act('PUT', '/api/wifi/network', { ssid: selected.ssid, password: pass })).attempt;
  } catch (err) {
    connectWaiting = false;
    show('pass');
    showError(ERRORS.lost);
    return;
  }
  checkAttempt();
});

// ---------- Стан від пристрою (канал стану) ----------

// Перший стан після відкриття сторінки: вирішуємо, що показати.
function begin(s) {
  // Є зв'язок — панель згорнута в кнопку (data-open на #wifi-panel лишає її розгорнутою).
  if (s.state === 'connected') {
    showDone(s);
    setOpen(panel.hasAttribute('data-open'));
    return;
  }
  setOpen(true);

  // Сторінку відкрито не через мережу налаштування — вибирати мережу звідси не можна.
  if (!setup) { showDone(s); return; }
  // Сторінку могли перезавантажити посеред підключення — показуємо, на чому зупинились.
  if (s.state === 'connecting') {
    prepare({ ssid: s.ssid, open: false });
    showProgress(s.ssid);
    connectWaiting = true;
    attemptWanted = s.attempt;
    return;
  }
  scan();
}

function onWifi(s) {
  const before = wifi;
  wifi = s;
  setup = via !== '' && via === s.apIp;
  applyStatus(s);

  if (!before) { begin(s); return; }
  if (connectWaiting) { checkAttempt(); return; }

  // Зв'язок із домашньою мережею з'явився або зник сам, без участі цієї сторінки.
  const online = s.state === 'connected';
  if (online === (before.state === 'connected')) return;
  if (online) { showDone(s); return; }
  setOpen(true);                                            // без зв'язку панель розгорнута
  if (view !== 'list' && view !== 'pass') showDone(s);      // хто саме вибирає мережу — тому не заважаємо
}

function start() {
  const state = window.deviceState;
  state.on('hello', h => { via = h.via || ''; });
  state.on('wifi', onWifi);
  state.on('wifi-networks', n => { nets = n; checkNets(); });
}

// Канал стану сторінка могла вже підключити сама; якщо ні — підключаємо.
if (window.deviceState) {
  start();
} else {
  const script = document.createElement('script');
  script.src = '/state.js';
  script.onload = start;
  document.head.appendChild(script);
}
})();
