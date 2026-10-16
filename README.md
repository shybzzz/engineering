# Engineering

Особистий маркетплейс для Claude Code: скіли, команди та агенти, які я перевикористовую у всіх проєктах.

## Структура

```
engineering/
├── .claude-plugin/
│   └── marketplace.json          # каталог маркетплейсу
└── plugins/
    ├── toolkit/                  # мій базовий плагін
    │   ├── .claude-plugin/
    │   │   └── plugin.json       # маніфест плагіна
    │   └── skills/
    │       ├── save-skill/            # «збережи цей скіл у хмарі» → автозбереження сюди
    │       │   └── SKILL.md
    │       ├── conventional-commit/   # коміти за Conventional Commits
    │       │   └── SKILL.md
    │       └── ua-docs-style/         # стиль українських інженерних документів
    │           └── SKILL.md
    └── maker/                    # виготовлення фізичних речей (3D-друк)
        ├── .claude-plugin/
        │   └── plugin.json
        └── skills/
            └── printable-3d-model/    # 3D-модель для друку: вимірювання → генерація STL → перевірка
                ├── SKILL.md
                └── scripts/
                    ├── stl_info.py    # інспекція STL (stdlib): розміри, z-min, manifold
                    └── mesh_kit.py    # шаблон генератора watertight STL (shapely + fonttools)
```

## Скіли

### Плагін `toolkit`

| Скіл | Коли спрацьовує | Що робить |
|------|-----------------|-----------|
| `save-skill` | «збережи цей скіл у хмарі», «збережи в маркетплейс» | Створює/оновлює SKILL.md у цьому репозиторії, прибираючи проєктну специфіку; переписує скіл-джерело в проєкті так, що він посилається на скіл маркетплейсу і містить лише проєктні деталі; піднімає версію плагіна, оновлює README, комітить і пушить. |
| `conventional-commit` | будь-який коміт у проєктах користувача, «закоміть» | Пише повідомлення комітів за стандартом Conventional Commits. |
| `ua-docs-style` | створення/редагування/перевірка українських інженерних документів у стилі наукової статті | Структура статті (Анотація → розділи → Висновки → Література), LaTeX-математика з нумерацією формул, нумерація рисунків і таблиць, термінологія, перевірені джерела з DOI через Crossref, правила для Confluence-сторінок. |

### Плагін `maker`

| Скіл | Коли спрацьовує | Що робить |
|------|-----------------|-----------|
| `printable-3d-model` | «зроби 3D-модель для друку», «згенеруй STL», «зроби лоток/бокс/підставку під …», «виміряй STL», «чому non-manifold», «чи влізе на столик» | Повний цикл: вимірювання вхідних STL/3MF (пастки: z-min ≠ 0, нелінійний масштаб, назви), правила конструювання під FDM без підтримок (зазори, стінки, гравіювання, фаски), генерація watertight STL кодом без mesh-бібліотек (`mesh_kit.py`), обов'язкова перевірка manifold своїм чеком і слайсером, SVG-прев'ю і підготовка публікації. |

## Перший запуск (один раз)

1. Створи порожній репозиторій на GitHub (можна приватний), наприклад `engineering`.
2. Запуш цю папку туди:
   ```bash
   cd engineering
   git remote add origin git@github.com:shybzzz/engineering.git
   git push -u origin main
   ```
3. Встав свій справжній `shybzzz` у:
   - `plugins/toolkit/skills/save-skill/SKILL.md` (рядок MARKETPLACE_REPO)
   - цей README
4. Підключи маркетплейс у Claude Code:
   ```bash
   claude plugin marketplace add shybzzz/engineering
   claude plugin install toolkit@engineering
   ```
   (або всередині сесії: `/plugin marketplace add ...` та `/plugin install toolkit@engineering`; при встановленні обирай scope **user** — щоб плагін був у всіх твоїх сесіях)

## На кожній новій машині

```bash
claude plugin marketplace add shybzzz/engineering
claude plugin install toolkit@engineering
claude plugin install maker@engineering
```

## Щоденне використання

- **Зберегти знання з розмови:** скажи Claude «збережи цей скіл у хмарі» — спрацює скіл `save-skill`, і Claude сам створить SKILL.md, закомітить і запушить сюди.
- **Підтягнути оновлення на іншій машині:** `/plugin marketplace update engineering`.
- **Локальні правки без пушу:** редагуй файли і виконай `/reload-plugins` у сесії.
- **Перевірка валідності:** `claude plugin validate .` з кореня репозиторію.

## Додати новий скіл вручну

1. Створи папку `plugins/<плагін>/skills/<назва-скіла>/` з файлом `SKILL.md` (`toolkit` — загальні робочі скіли, `maker` — все про виготовлення фізичних речей):
   ```markdown
   ---
   name: назва-скіла
   description: Одне-два речення — КОЛИ використовувати скіл, з тригер-фразами.
   ---

   # Інструкції для моделі...
   ```
2. Підніми `version` у `plugins/<плагін>/.claude-plugin/plugin.json`.
3. Додай скіл у дерево структури та таблицю «Скіли» в цьому README.
4. Закоміть і запуш.

## Claude Desktop (Cowork)

У налаштуваннях плагінів Desktop-застосунку додай маркетплейс, вказавши `shybzzz/engineering`, і встанови `toolkit` та `maker` зі списку — ті самі скіли працюватимуть і там.
