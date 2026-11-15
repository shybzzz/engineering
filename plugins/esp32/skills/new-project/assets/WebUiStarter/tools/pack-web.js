// Пакує теку web/ у web_pages.h: кожен файл стискається gzip і стає масивом
// байтів у флеш-пам'яті пристрою. Пристрій віддає його як є, із заголовком
// Content-Encoding: gzip, — розпаковує вже браузер.
//
//   node tools/pack-web.js            запакувати — після кожної зміни у web/, перед збиранням прошивки
//   node tools/pack-web.js --check    лише перевірити, що web_pages.h відповідає теці web/
//                                     (код виходу 1 — не відповідає: прошивка віддала б старі сторінки)
//
// Назва масиву — з шляху файлу: web/index.html -> WEB_INDEX_HTML,
// web/wifi-panel.js -> WEB_WIFI_PANEL_JS, web/img/logo.svg -> WEB_IMG_LOGO_SVG.
// Сторонніх бібліотек не потрібно — лише Node.js.

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const SKETCH = path.join(__dirname, '..');
const WEB = path.join(SKETCH, 'web');
const OUT = path.join(SKETCH, 'web_pages.h');
const CHECK = process.argv.includes('--check');

const TYPES = {
  html: 'text/html; charset=utf-8', js: 'application/javascript; charset=utf-8', css: 'text/css; charset=utf-8',
  json: 'application/json', svg: 'image/svg+xml', txt: 'text/plain; charset=utf-8',
  png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif', ico: 'image/x-icon',
  woff2: 'font/woff2'
};
const TEXT = ['html', 'js', 'css', 'json', 'svg', 'txt'];

function listFiles(dir, prefix) {
  let found = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const rel = prefix ? prefix + '/' + entry.name : entry.name;
    if (entry.isDirectory()) found = found.concat(listFiles(path.join(dir, entry.name), rel));
    else found.push(rel);
  }
  return found;
}

if (!fs.existsSync(WEB)) { console.error('Немає теки web/ поруч зі скетчем: ' + WEB); process.exit(2); }

const files = listFiles(WEB, '').sort().map(rel => {
  const ext = path.extname(rel).slice(1).toLowerCase();
  let data = fs.readFileSync(path.join(WEB, rel));
  // Текст — завжди з кінцями рядків LF: той самий файл дає той самий результат на будь-якому комп'ютері.
  if (TEXT.includes(ext)) data = Buffer.from(data.toString('utf8').replace(/\r\n/g, '\n'), 'utf8');
  const type = TYPES[ext] || 'application/octet-stream';
  return {
    rel, data, type,
    name: 'WEB_' + rel.replace(/[^A-Za-z0-9]+/g, '_').toUpperCase(),
    hash: crypto.createHash('sha256').update(type + '\n').update(data).digest('hex').slice(0, 16)
  };
});

if (!files.length) { console.error('У теці web/ немає файлів.'); process.exit(2); }
const names = files.map(f => f.name);
const twice = names.find((name, i) => names.indexOf(name) !== i);
if (twice) { console.error('Два файли дають одну назву ' + twice + ' — перейменуй один із них.'); process.exit(2); }

// Рядок-підпис кожного файлу в заголовку: за ним --check бачить, що змінилось.
const stamp = f => '// web/' + f.rel + ' [' + f.hash + ']';

if (CHECK) {
  const have = fs.existsSync(OUT) ? fs.readFileSync(OUT, 'utf8').split(/\r?\n/).filter(line => /^\/\/ web\/.* \[[0-9a-f]{16}\]/.test(line)).map(line => line.replace(/\].*$/, ']')) : [];
  const want = files.map(stamp);
  const stale = want.filter(line => !have.includes(line)).map(line => line.replace(/^\/\/ /, '').replace(/ \[.*$/, ''));
  const gone = have.filter(line => !want.includes(line) && !want.some(w => w.split(' [')[0] === line.split(' [')[0])).map(line => line.replace(/^\/\/ /, '').replace(/ \[.*$/, ''));
  if (!stale.length && !gone.length) { console.log('web_pages.h відповідає теці web/ (файлів: ' + files.length + ').'); process.exit(0); }
  if (stale.length) console.error('Змінено або додано, але не запаковано: ' + stale.join(', '));
  if (gone.length) console.error('Є у web_pages.h, але вже немає у web/: ' + gone.join(', '));
  console.error('Запусти: node tools/pack-web.js');
  process.exit(1);
}

function gzip(data) {
  const packed = zlib.gzipSync(data, { level: 9 });
  packed.writeUInt32LE(0, 4);   // без часу стиснення
  packed[8] = 2;                // найсильніше стиснення
  packed[9] = 255;              // без назви операційної системи
  return packed;
}

let text = `// ЗГЕНЕРОВАНО скриптом tools/pack-web.js із теки web/ — руками не редагуй.
// Змінив щось у web/ — запусти:   node tools/pack-web.js
//
// Тут сторінки пристрою, стиснуті gzip, лежать у флеш-пам'яті. Віддавати так:
//
//     server.on("/", HTTP_GET, [] { webSend(server, WEB_INDEX_HTML); });
//
// webSend() додає заголовок Content-Encoding: gzip — розпаковує браузер.

#pragma once

#include <Arduino.h>
#include <WebServer.h>

struct WebFile {
  const uint8_t* data;   // вміст, стиснутий gzip
  size_t         size;   // скільки це байтів
  const char*    type;   // Content-Type
};

// Відповідь 200 із файлом із теки web/.
inline void webSend(WebServer& server, const WebFile& file) {
  server.sendHeader("Content-Encoding", "gzip");
  server.sendHeader("Cache-Control", "no-store");
  server.send_P(200, file.type, (PGM_P)file.data, file.size);
}
`;

let before = 0, after = 0;
for (const f of files) {
  const packed = gzip(f.data);
  before += f.data.length; after += packed.length;
  const rows = [];
  for (let i = 0; i < packed.length; i += 20) {
    rows.push('  ' + Array.from(packed.subarray(i, i + 20), b => '0x' + b.toString(16).padStart(2, '0')).join(','));
  }
  text += '\n' + stamp(f) + ' — ' + f.data.length + ' -> ' + packed.length + ' байтів\n' +
    'const uint8_t ' + f.name + '_GZ[] PROGMEM = {\n' + rows.join(',\n') + '\n};\n' +
    'const WebFile ' + f.name + ' = { ' + f.name + '_GZ, sizeof(' + f.name + '_GZ), "' + f.type + '" };\n';
  console.log((f.name + ' ').padEnd(26, '.') + ' web/' + f.rel + ': ' + f.data.length + ' -> ' + packed.length + ' байтів');
}

fs.writeFileSync(OUT, text);
console.log('web_pages.h — файлів: ' + files.length + ', ' + before + ' -> ' + after + ' байтів (' + Math.round(100 * after / before) + ' %)');
