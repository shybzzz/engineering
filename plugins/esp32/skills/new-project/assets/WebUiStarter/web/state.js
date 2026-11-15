// Канал стану для сторінок (GET /state.js) — частина модуля state_socket, не редагуй.
// Дає сторінці window.deviceState: on('тема', fn), onLink(fn), connected. Опис — у state_socket.h.
(function () {
'use strict';
if (window.deviceState) return;

const PORT = 81;              // те саме число — SOCKET_PORT у state_socket.cpp
const RETRY_MS = 1500;        // через скільки пробуємо підключитися знову
const OPEN_LIMIT_MS = 5000;   // скільки чекаємо на підключення
const SILENCE_MS = 12000;     // пристрій озивається щоп'ять секунд; довша тиша — зв'язку немає

const listeners = {};         // тема -> функції
const latest = {};            // тема -> останній стан
const linkListeners = [];
let socket = null;
let connected = false;
let heardAt = 0;              // коли востаннє щось чули (або почали підключатися)
let retryTimer = 0;

function setConnected(value) {
  if (connected === value) return;
  connected = value;
  linkListeners.forEach(fn => fn(value));
}

function open() {
  clearTimeout(retryTimer);
  heardAt = Date.now();
  let ws;
  try {
    ws = new WebSocket('ws://' + location.hostname + ':' + PORT + '/');
  } catch (e) {
    retryTimer = setTimeout(open, RETRY_MS);
    return;
  }
  socket = ws;
  ws.onopen = () => {
    if (ws !== socket) return;
    heardAt = Date.now();
    setConnected(true);
  };
  ws.onmessage = event => {
    if (ws !== socket) return;
    heardAt = Date.now();
    let message;
    try { message = JSON.parse(event.data); } catch (e) { return; }
    if (message.topic === 'alive') { ws.send('1'); return; }   // "я тут"
    latest[message.topic] = message.data;
    (listeners[message.topic] || []).forEach(fn => fn(message.data));
  };
  ws.onclose = () => { if (ws === socket) lost(); };
}

function lost() {
  const old = socket;
  socket = null;
  if (old) {
    old.onopen = old.onmessage = old.onclose = null;
    try { old.close(); } catch (e) { /* уже закрито */ }
  }
  setConnected(false);
  clearTimeout(retryTimer);
  retryTimer = setTimeout(open, RETRY_MS);
}

// Зв'язок може зникнути без жодного сигналу (планшет винесли з кімнати) —
// помічаємо це з того, що пристрій замовк.
function check() {
  if (!socket) return;
  const limit = socket.readyState === 1 ? SILENCE_MS : OPEN_LIMIT_MS;
  if (Date.now() - heardAt > limit) lost();
}
setInterval(check, 3000);

// Сторінку знову відкрили після перерви — не чекаємо, перевіряємо одразу.
document.addEventListener('visibilitychange', () => {
  if (document.hidden) return;
  if (socket) check(); else open();
});

window.deviceState = {
  // fn(стан) — одразу, якщо стан теми вже відомий, і після кожної зміни.
  on(topic, fn) {
    (listeners[topic] = listeners[topic] || []).push(fn);
    if (topic in latest) fn(latest[topic]);
  },
  // fn(true | false) — одразу і щоразу, коли зв'язок із пристроєм з'являється чи зникає.
  onLink(fn) {
    linkListeners.push(fn);
    fn(connected);
  },
  get connected() { return connected; }
};

open();
})();
