# Engineering

Особистий маркетплейс для Claude Code: скіли, команди та агенти, які я перевикористовую у всіх проєктах.

## Структура

```
engineering/
├── .claude-plugin/
│   └── marketplace.json          # каталог маркетплейсу
└── plugins/
    └── toolkit/                  # мій базовий плагін
        ├── .claude-plugin/
        │   └── plugin.json       # маніфест плагіна
        └── skills/
            ├── save-skill/       # «збережи цей скіл у хмарі» → автозбереження сюди
            │   └── SKILL.md
            └── conventional-commit/   # приклад скіла
                └── SKILL.md
```

## Перший запуск (один раз)

1. Створи порожній репозиторій на GitHub (можна приватний), наприклад `engineering`.
2. Запуш цю папку туди:
   ```bash
   cd engineering
   git remote add origin git@github.com:YOUR-GITHUB-USERNAME/engineering.git
   git push -u origin main
   ```
3. Встав свій справжній `YOUR-GITHUB-USERNAME` у:
   - `plugins/toolkit/skills/save-skill/SKILL.md` (рядок MARKETPLACE_REPO)
   - цей README
4. Підключи маркетплейс у Claude Code:
   ```bash
   claude plugin marketplace add YOUR-GITHUB-USERNAME/engineering
   claude plugin install toolkit@engineering
   ```
   (або всередині сесії: `/plugin marketplace add ...` та `/plugin install toolkit@engineering`; при встановленні обирай scope **user** — щоб плагін був у всіх твоїх сесіях)

## На кожній новій машині

```bash
claude plugin marketplace add YOUR-GITHUB-USERNAME/engineering
claude plugin install toolkit@engineering
```

## Щоденне використання

- **Зберегти знання з розмови:** скажи Claude «збережи цей скіл у хмарі» — спрацює скіл `save-skill`, і Claude сам створить SKILL.md, закомітить і запушить сюди.
- **Підтягнути оновлення на іншій машині:** `/plugin marketplace update engineering`.
- **Локальні правки без пушу:** редагуй файли і виконай `/reload-plugins` у сесії.
- **Перевірка валідності:** `claude plugin validate .` з кореня репозиторію.

## Додати новий скіл вручну

1. Створи папку `plugins/toolkit/skills/<назва-скіла>/` з файлом `SKILL.md`:
   ```markdown
   ---
   name: назва-скіла
   description: Одне-два речення — КОЛИ використовувати скіл, з тригер-фразами.
   ---

   # Інструкції для моделі...
   ```
2. Підніми `version` у `plugins/toolkit/.claude-plugin/plugin.json`.
3. Закоміть і запуш.

## Claude Desktop (Cowork)

У налаштуваннях плагінів Desktop-застосунку додай маркетплейс, вказавши `YOUR-GITHUB-USERNAME/engineering`, і встанови `toolkit` зі списку — ті самі скіли працюватимуть і там.
