// Реалізація каналу стану. Опис і спосіб використання — у state_socket.h.
//
// Це невеликий сервер WebSocket (RFC 6455) рівно на те, що потрібно каналу:
// пристрій надсилає текстові повідомлення, від сторінки приймає лише короткі
// кадри ("я тут", ping, close).

#include "state_socket.h"

#include <WiFi.h>
#include <errno.h>
#include <lwip/sockets.h>
#include <mbedtls/base64.h>
#include <mbedtls/sha1.h>

namespace {

// ============================== Налаштування ==============================

const uint16_t SOCKET_PORT          = 81;      // те саме число — у STATE_SOCKET_JS нижче
const uint8_t  MAX_PEERS            = 8;       // скільки сторінок одночасно
const uint8_t  MAX_TOPICS           = 8;
const size_t   MAX_MESSAGE          = 60000;   // довші кадри потребують іншого заголовка
const uint32_t HANDSHAKE_TIMEOUT_MS = 3000;    // скільки чекаємо на запит від щойно підключеного
const uint32_t ALIVE_EVERY_MS       = 5000;    // як часто питаємо сторінки "ти тут?"
const uint32_t SILENCE_LIMIT_MS     = 15000;   // скільки сторінка може мовчати
const uint32_t SEND_WAIT_MS         = 100;     // скільки чекаємо, якщо сторінка не встигає читати

// ============================ Скрипт для сторінок =========================

// GET /state.js — підключення сторінки до каналу (window.deviceState).
const char STATE_SOCKET_JS[] PROGMEM = R"SSJS((function () {
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
)SSJS";

// ================================== Стан ==================================

NetworkServer listener(SOCKET_PORT);
WebServer*    web = nullptr;

struct Topic {
  String name;
  String json;
};
Topic   topics[MAX_TOPICS];
uint8_t topicCount = 0;

// Одна відкрита сторінка
struct Peer {
  NetworkClient client;
  bool     used    = false;
  bool     open    = false;         // привіталися — можна надсилати повідомлення
  uint32_t sinceMs = 0;             // коли підключилась
  uint32_t heardMs = 0;             // коли востаннє щось надіслала
  String   line;                    // рядок запиту, який зараз читаємо
  String   key;                     // Sec-WebSocket-Key із запиту
  uint8_t  frame[2 + 4 + 125];      // кадр від сторінки: заголовок, маска, до 125 байтів
  uint8_t  have    = 0;             // скільки байтів кадру вже прийшло
};
Peer     peers[MAX_PEERS];
uint32_t lastAliveMs = 0;

// ================================ Надсилання ==============================

void drop(Peer& peer) {
  peer.client.stop();
  peer.used = false;
  peer.open = false;
  peer.have = 0;
  peer.line = "";
  peer.key  = "";
}

// Надсилає все або повертає false. Сторінку, яка не встигає читати чи зникла,
// довго не чекаємо: інакше через один загублений планшет завмер би весь loop().
bool sendAll(Peer& peer, const uint8_t* data, size_t length) {
  int fd = peer.client.fd();
  if (fd < 0) return false;

  uint32_t startMs = millis();
  while (length > 0) {
    int sent = ::send(fd, data, length, MSG_DONTWAIT);
    if (sent > 0) {
      data   += sent;
      length -= sent;
      continue;
    }
    if (sent < 0 && errno != EAGAIN && errno != EWOULDBLOCK) return false;
    if (millis() - startMs >= SEND_WAIT_MS) return false;
    delay(2);
  }
  return true;
}

// Один кадр WebSocket. opcode: 1 — текст, 8 — закриття, 10 — pong.
bool sendFrame(Peer& peer, uint8_t opcode, const uint8_t* payload, size_t length) {
  uint8_t head[4];
  size_t  headSize = 2;
  head[0] = 0x80 | opcode;
  if (length < 126) {
    head[1] = length;
  } else {
    head[1]  = 126;
    head[2]  = length >> 8;
    head[3]  = length & 0xFF;
    headSize = 4;
  }
  return sendAll(peer, head, headSize) && sendAll(peer, payload, length);
}

// Надсилає текст; якщо не вийшло — від'єднує сторінку (вона підключиться знову
// й отримає свіжий стан).
void sendText(Peer& peer, const String& text) {
  if (!sendFrame(peer, 1, (const uint8_t*)text.c_str(), text.length())) drop(peer);
}

String topicMessage(const Topic& topic) {
  String message = "{\"topic\":\"";
  message += topic.name;
  message += "\",\"data\":";
  message += topic.json;
  message += '}';
  return message;
}

// ========================== Привітання (handshake) ========================

void finishHandshake(Peer& peer) {
  if (peer.key.length() == 0) {     // це не запит WebSocket
    static const char REFUSAL[] = "HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-Length: 0\r\n\r\n";
    sendAll(peer, (const uint8_t*)REFUSAL, sizeof(REFUSAL) - 1);
    drop(peer);
    return;
  }

  // Відповідь на ключ: base64(sha1(ключ + сталий рядок із RFC 6455))
  String source = peer.key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
  uint8_t hash[20];
  mbedtls_sha1((const unsigned char*)source.c_str(), source.length(), hash);
  unsigned char accept[32];
  size_t        acceptSize = 0;
  mbedtls_base64_encode(accept, sizeof(accept) - 1, &acceptSize, hash, sizeof(hash));
  accept[acceptSize] = 0;

  String reply = "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ";
  reply += (const char*)accept;
  reply += "\r\n\r\n";
  if (!sendAll(peer, (const uint8_t*)reply.c_str(), reply.length())) {
    drop(peer);
    return;
  }

  peer.open    = true;
  peer.heardMs = millis();
  peer.line    = "";
  peer.key     = "";

  // Спершу — через яку адресу пристрою прийшла сторінка, далі — стан усіх тем.
  sendText(peer, "{\"topic\":\"hello\",\"data\":{\"via\":\"" + peer.client.localIP().toString() + "\"}}");
  for (uint8_t i = 0; i < topicCount && peer.used; i++) {
    sendText(peer, topicMessage(topics[i]));
  }
}

// Читає запит рядок за рядком; з усіх заголовків потрібен лише ключ.
void readHandshake(Peer& peer) {
  while (peer.client.available()) {
    char c = peer.client.read();
    if (c == '\r') continue;
    if (c != '\n') {
      if (peer.line.length() < 200) peer.line += c;   // довгі заголовки нам не потрібні
      continue;
    }
    if (peer.line.length() == 0) {                    // порожній рядок — запит закінчився
      finishHandshake(peer);
      return;
    }
    int colon = peer.line.indexOf(':');
    if (colon > 0) {
      String name = peer.line.substring(0, colon);
      name.toLowerCase();
      if (name == "sec-websocket-key") {
        peer.key = peer.line.substring(colon + 1);
        peer.key.trim();
      }
    }
    peer.line = "";
  }
}

// ============================ Кадри від сторінки ==========================

void handleFrame(Peer& peer) {
  uint8_t opcode = peer.frame[0] & 0x0F;
  uint8_t length = peer.frame[1] & 0x7F;
  peer.heardMs = millis();

  if (opcode == 8) {                // сторінка закривається
    sendFrame(peer, 8, nullptr, 0);
    drop(peer);
  } else if (opcode == 9) {         // ping — відповідаємо тим самим вмістом
    uint8_t* mask = peer.frame + 2;
    uint8_t* data = peer.frame + 6;
    for (uint8_t i = 0; i < length; i++) data[i] ^= mask[i % 4];
    if (!sendFrame(peer, 10, data, length)) drop(peer);
  }
  // Усе інше (зокрема "я тут") важливе лише тим, що прийшло.
}

void readFrames(Peer& peer) {
  while (peer.used && peer.client.available()) {
    peer.frame[peer.have++] = peer.client.read();
    if (peer.have < 2) continue;

    uint8_t length = peer.frame[1] & 0x7F;
    bool    masked = peer.frame[1] & 0x80;
    if (length > 125 || !masked) {  // довгих повідомлень від сторінки не чекаємо
      drop(peer);
      return;
    }
    if (peer.have < 2 + 4 + length) continue;

    handleFrame(peer);
    peer.have = 0;
  }
}

// ================================ Веб-сервер ==============================

void handleScript() {
  web->sendHeader("Cache-Control", "no-store");
  web->send_P(200, "application/javascript; charset=utf-8", STATE_SOCKET_JS);
}

void acceptPeer() {
  NetworkClient incoming = listener.accept();
  if (!incoming) return;

  for (Peer& peer : peers) {
    if (peer.used) continue;
    peer.client  = incoming;
    peer.client.setNoDelay(true);   // повідомлення короткі — надсилаємо без затримки
    peer.used    = true;
    peer.open    = false;
    peer.have    = 0;
    peer.sinceMs = millis();
    peer.heardMs = peer.sinceMs;
    return;
  }
  incoming.stop();                  // місць немає; сторінка спробує ще раз
}

}  // namespace

// ============================ Зовнішній інтерфейс =========================

void stateSocketBegin(WebServer& server) {
  web = &server;
  web->on("/state.js", HTTP_GET, handleScript);
  listener.begin();
}

void stateSocketLoop() {
  acceptPeer();

  bool askAlive = millis() - lastAliveMs >= ALIVE_EVERY_MS;
  if (askAlive) lastAliveMs = millis();

  for (Peer& peer : peers) {
    if (!peer.used) continue;
    if (!peer.client.connected()) {
      drop(peer);
      continue;
    }

    if (!peer.open) {
      readHandshake(peer);
      if (peer.used && !peer.open && millis() - peer.sinceMs >= HANDSHAKE_TIMEOUT_MS) drop(peer);
      continue;
    }

    readFrames(peer);
    if (!peer.used) continue;
    if (millis() - peer.heardMs >= SILENCE_LIMIT_MS) {
      drop(peer);
      continue;
    }
    if (askAlive) sendText(peer, "{\"topic\":\"alive\"}");
  }
}

void statePublish(const char* topicName, const String& json) {
  if (json.length() == 0 || json.length() > MAX_MESSAGE) {
    Serial.printf("Канал стану: стан теми \"%s\" порожній або завеликий, не надіслано.\n", topicName);
    return;
  }

  Topic* topic = nullptr;
  for (uint8_t i = 0; i < topicCount; i++) {
    if (topics[i].name == topicName) topic = &topics[i];
  }

  if (topic) {
    if (topic->json == json) return;    // нічого не змінилося
  } else {
    if (topicCount == MAX_TOPICS) {
      Serial.printf("Канал стану: забагато тем, \"%s\" не надіслано.\n", topicName);
      return;
    }
    topic = &topics[topicCount++];
    topic->name = topicName;
  }
  topic->json = json;

  String message = topicMessage(*topic);
  for (Peer& peer : peers) {
    if (peer.used && peer.open) sendText(peer, message);
  }
}
