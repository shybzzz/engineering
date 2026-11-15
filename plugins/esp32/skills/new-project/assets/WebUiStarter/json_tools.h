/*
  JSON для адрес /api/... — без сторонніх бібліотек.

  Відповідь складай звичайним рядком; текст, що прийшов ззовні (назви мереж,
  введене користувачем), вставляй через jsonEscape():

      String json = "{\"name\":\"" + jsonEscape(name) + "\",\"on\":true}";

  Тіло запиту (server.arg("plain"), коли сторінка надсилає
  Content-Type: application/json) читай функціями jsonGet...():

      bool on;
      if (!jsonGetBool(server.arg("plain"), "on", on)) { ...відповісти 400... }

  jsonGet...() бачать лише поля верхнього рівня об'єкта {"ключ": значення, ...}
  і повертають false, якщо поля немає або воно іншого типу.
*/

#pragma once

#include <Arduino.h>

// Готує текст до вставки в JSON-рядок (екранує лапки, зворотну риску, керівні символи).
inline String jsonEscape(const String& text) {
  String out;
  out.reserve(text.length() + 8);
  for (size_t i = 0; i < text.length(); i++) {
    char c = text[i];
    if (c == '"' || c == '\\') {
      out += '\\';
      out += c;
    } else if ((uint8_t)c < 0x20) {
      char buf[8];
      snprintf(buf, sizeof(buf), "\\u%04x", (unsigned)c);
      out += buf;
    } else {
      out += c;
    }
  }
  return out;
}

namespace json_tools_detail {

inline void skipSpace(const String& s, size_t& i) {
  while (i < s.length() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) i++;
}

// Чотири шістнадцяткові цифри після \u
inline bool readHex4(const String& s, size_t i, uint32_t& value) {
  if (i + 4 > s.length()) return false;
  value = 0;
  for (size_t k = 0; k < 4; k++) {
    char c = s[i + k];
    uint8_t digit;
    if (c >= '0' && c <= '9')      digit = c - '0';
    else if (c >= 'a' && c <= 'f') digit = c - 'a' + 10;
    else if (c >= 'A' && c <= 'F') digit = c - 'A' + 10;
    else return false;
    value = (value << 4) | digit;
  }
  return true;
}

inline void appendUtf8(String& out, uint32_t code) {
  if (code == 0) return;                      // нульовий символ обірвав би рядок
  if (code < 0x80) {
    out += (char)code;
  } else if (code < 0x800) {
    out += (char)(0xC0 | (code >> 6));
    out += (char)(0x80 | (code & 0x3F));
  } else if (code < 0x10000) {
    out += (char)(0xE0 | (code >> 12));
    out += (char)(0x80 | ((code >> 6) & 0x3F));
    out += (char)(0x80 | (code & 0x3F));
  } else {
    out += (char)(0xF0 | (code >> 18));
    out += (char)(0x80 | ((code >> 12) & 0x3F));
    out += (char)(0x80 | ((code >> 6) & 0x3F));
    out += (char)(0x80 | (code & 0x3F));
  }
}

// Читає рядок у лапках, що починається в s[i]; i стає одразу після нього.
// out == nullptr — лише пропустити.
inline bool readString(const String& s, size_t& i, String* out) {
  if (i >= s.length() || s[i] != '"') return false;
  i++;
  while (i < s.length()) {
    char c = s[i++];
    if (c == '"') return true;
    if (c != '\\') {
      if (out) *out += c;
      continue;
    }
    if (i >= s.length()) return false;
    char e = s[i++];
    char plain;
    switch (e) {
      case '"': case '\\': case '/': plain = e; break;
      case 'b': plain = '\b'; break;
      case 'f': plain = '\f'; break;
      case 'n': plain = '\n'; break;
      case 'r': plain = '\r'; break;
      case 't': plain = '\t'; break;
      case 'u': {
        uint32_t code;
        if (!readHex4(s, i, code)) return false;
        i += 4;
        // Символи поза основною площиною (емодзі) записані двома \u підряд
        uint32_t low;
        if (code >= 0xD800 && code <= 0xDBFF && i + 6 <= s.length() && s[i] == '\\' && s[i + 1] == 'u' &&
            readHex4(s, i + 2, low) && low >= 0xDC00 && low <= 0xDFFF) {
          code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00);
          i += 6;
        }
        if (out) appendUtf8(*out, code);
        continue;
      }
      default: return false;
    }
    if (out) *out += plain;
  }
  return false;   // рядок не закрито
}

// Пропускає одне значення будь-якого типу.
inline bool skipValue(const String& s, size_t& i) {
  if (i >= s.length()) return false;
  if (s[i] == '"') return readString(s, i, nullptr);

  if (s[i] == '{' || s[i] == '[') {
    int depth = 0;
    while (i < s.length()) {
      char c = s[i];
      if (c == '"') {
        if (!readString(s, i, nullptr)) return false;
        continue;
      }
      i++;
      if (c == '{' || c == '[') depth++;
      if ((c == '}' || c == ']') && --depth == 0) return true;
    }
    return false;
  }

  size_t start = i;   // число, true, false або null
  while (i < s.length() && s[i] != ',' && s[i] != '}' && s[i] != ']' &&
         s[i] != ' ' && s[i] != '\t' && s[i] != '\n' && s[i] != '\r') i++;
  return i > start;
}

// Ставить i на початок значення поля key.
inline bool findValue(const String& s, const char* key, size_t& i) {
  i = 0;
  skipSpace(s, i);
  if (i >= s.length() || s[i] != '{') return false;
  i++;
  for (;;) {
    skipSpace(s, i);
    String name;
    if (!readString(s, i, &name)) return false;   // сюди потрапляє і кінець об'єкта "}"
    skipSpace(s, i);
    if (i >= s.length() || s[i] != ':') return false;
    i++;
    skipSpace(s, i);
    if (name == key) return true;
    if (!skipValue(s, i)) return false;
    skipSpace(s, i);
    if (i >= s.length() || s[i] != ',') return false;
    i++;
  }
}

// Чи закінчується значення в s[i] (далі кома, дужка, пробіл або кінець тексту).
inline bool valueEnds(const String& s, size_t i) {
  if (i >= s.length()) return true;
  char c = s[i];
  return c == ',' || c == '}' || c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

}  // namespace json_tools_detail

// "ключ": "текст"
inline bool jsonGetString(const String& json, const char* key, String& out) {
  size_t i;
  if (!json_tools_detail::findValue(json, key, i)) return false;
  String value;
  if (!json_tools_detail::readString(json, i, &value)) return false;
  out = value;
  return true;
}

// "ключ": true | false
inline bool jsonGetBool(const String& json, const char* key, bool& out) {
  size_t i;
  if (!json_tools_detail::findValue(json, key, i)) return false;
  const char* at = json.c_str() + i;
  if (strncmp(at, "true", 4) == 0 && json_tools_detail::valueEnds(json, i + 4)) {
    out = true;
    return true;
  }
  if (strncmp(at, "false", 5) == 0 && json_tools_detail::valueEnds(json, i + 5)) {
    out = false;
    return true;
  }
  return false;
}

// "ключ": ціле число
inline bool jsonGetInt(const String& json, const char* key, long& out) {
  size_t i;
  if (!json_tools_detail::findValue(json, key, i)) return false;
  const char* at = json.c_str() + i;
  if (*at != '-' && (*at < '0' || *at > '9')) return false;
  char* end = nullptr;
  long value = strtol(at, &end, 10);
  if (end == at || !json_tools_detail::valueEnds(json, i + (end - at))) return false;   // 1.5 — не ціле
  out = value;
  return true;
}
