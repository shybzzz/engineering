---
name: syllabus
description: Create or update a university course syllabus (силабус навчальної дисципліни) as a .docx in the department's current format, synchronised with a specific educational programme (ОПП/ОНП) — competencies (ЗК, ФК/СК), programme learning outcomes (ПРН), links to other courses, goal and objectives, hours, a verified literature list, assessment criteria and the course scheme. Use when the user asks «створи/онови силабус», «зроби силабус з дисципліни …», «синхронізуй силабус з ОПП», «перенеси силабус у новий формат/шаблон», «онови літературу в силабусі», «додай викладача в силабус», "create/update the syllabus for …", or when a syllabus .docx has to be checked against a programme document.
---

# Syllabus: from the programme document to an approved-format .docx

A syllabus is a formal document that gets checked against the educational programme during
accreditation. Everything in it that quotes the programme — component code, credits, competencies,
learning outcomes — must come from the programme document of the right year, read by you in this
session, not from memory and not from another programme's syllabus.

The deliverable is a `.docx` built from the department's example syllabus (the template) with
`scripts/syllabus_docx.py`, plus a short report of what came from where and what is still open.

## 0. Pin down the inputs

Establish these before writing anything; ask only for what you cannot find:

| Input | Where it comes from |
|---|---|
| The course and the **programme** it is taught in (name, level, specialty, year of the edition) | the user; the old syllabus; the programme pages |
| Template: a recent syllabus of the department in the **current format** | the project folder (often an «Приклад» / example file) |
| The previous syllabus of this course, if any | the project folder; the faculty site |
| Lecturers and their titles | the user; staff pages |
| Approval line (protocol number and date), course page URL | the user |

- **A course title can sit in several programmes** (bachelor, master, PhD; different specialties),
  sometimes under a slightly different name. Search the programme documents for it; if it occurs in
  more than one, or in none under that exact name, ask the user which programme the syllabus is for.
  The level changes everything: hours, credits, competency lists, terminology.
- If the project keeps notes on where programme documents are published (CLAUDE.md, a project
  skill, memory), use them first; otherwise find the faculty's programme pages and record the
  locations in the project for next time.

## 1. Read the programme document

1. Get the programme edition of the year the syllabus is approved in. If that edition is not
   published, **stop and ask**: the user either supplies the file or explicitly agrees to use the
   newest published edition. In the second case say so in the final report and name the edition.
2. Many programme PDFs are scans, and competency matrices never survive text extraction. Render
   the pages to images (`pdftoppm -jpeg -r 110 …`, zoom the matrix with `-r 220 -x -y -W -H`) and
   read them as images. Never reconstruct a matrix from garbled `pdftotext` output.
3. Take from the document:
   - the component's code and exact name, credits, form of final control (list of components);
   - the semester (structural-logical scheme);
   - **which** ЗК / ФК (СК) / ПРН the component provides — from the matrices, the column of this
     component, each row checked on the zoomed image;
   - the verbatim wording of those competencies and outcomes;
   - the programme's goal, focus and features — the course goal is worded to serve them;
   - the other components (for prerequisites and links).
4. Read the curriculum (навчальний план) for the split of hours: lectures / practical / laboratory /
   seminar / self-study and hours per week. If it contradicts the previous syllabus, follow the
   curriculum and flag the difference in the report — it changes the scheme and the grading.
5. Quote competencies and outcomes **verbatim**, including the programme's own slips; do not fix
   them silently. Mention notable slips in the report so the user can decide.
6. Specialty and field codes change between editions (old numeric vs new letter codes). Use the
   codes valid for the approval year and say so if the programme document you read uses older ones.

## 2. Lecturers

- Staff pages are a starting point, not proof. A person holding the **position** (посада) of доцент
  or професор does not necessarily hold the academic **title** (вчене звання); pages mix them up.
- Write each lecturer as «ПІБ, науковий ступінь, [вчене звання,] посада». Add the title only when
  it is confirmed — for the user themself, ask; for colleagues, flag in the report that the titles
  come from the staff page.
- When the user says how a line must read, write it exactly so and record it in the project.

## 3. Write the content

Follow the template's rows and their order; do not invent sections it does not have. Typical rows
and what goes in them:

- **Назва дисципліни** — name plus the component code from the programme.
- **Інформація про дисципліну** — status (нормативна / вибіркова), cycle or block, programme, level,
  specialty, semester, credits.
- **Коротка анотація** — what the course covers and what it is for at this level.
- **Мета та цілі** — one paragraph for the goal, tied explicitly to the programme's goal and focus;
  one for objectives. Keep the wording of the previous syllabus where it is still true.
- **Література** — see section 4.
- **Обсяг курсу** — total hours = credits × 30; classroom hours by type; self-study. Must equal the
  curriculum and the sum of the scheme rows.
- **Очікувані результати навчання** — «Знати: …», «Вміти: …», then the competencies and the
  programme learning outcomes from step 1, verbatim, with their codes.
- **Пререквізити** — prior knowledge, then the links to other components of **this** programme:
  what the course builds on and where its results are used. Only components that are really in the
  programme; alternatives from the same elective block as the course are never its prerequisites;
  do not state semesters you have not seen in the structural-logical scheme.
- **Необхідне обладнання** — lecture room, practical room, software, as in the template.
- **Критерії оцінювання** — keep the previous distribution of points unless the user asks to change
  it. Points must sum to 100 and divide into whole points per assignment; give the rubric per
  grade as the template does. If the number of assignments changed (hours changed), redistribute
  and report it.
- **Питання до екзамену / заліку** — an indicative list covering every topic of the scheme.
- **СХЕМА КУРСУ** — one row per class. Lecture rows × hours = lecture hours of the curriculum, same
  for practical / laboratory rows. Each row: week, topic with short theses, form of the class,
  literature numbers from the list, hours, deadline.

Rules that apply throughout:

- **Terminology follows the level and the curriculum**: студент / здобувач / аспірант; ОПП for
  professional programmes, ОНП for research ones; «практичні» vs «лабораторні» exactly as the
  curriculum names the hours. After building, scan for leftovers from the template's course.
- **Carry over** topics, policies and grading from the previous syllabus; update what is outdated
  (tool names, platform addresses, staff).
- **Never invent** a protocol number, a date, a URL, a room, a title. Unknown fields are written as
  `[[what is missing]]` — the script highlights them yellow and lists them. Copy the approval line
  from the example only when the user says to.
- Write in the language of the template.

## 4. Literature

Requirements commonly set for syllabi (use the department's own if the user states different
numbers): 15–20 entries in total; the first 5 (основна) not older than 5 years at approval;
додаткова may be older; include електронні ресурси.

- **Verify every entry** against a publisher page, a library catalogue, a repository record or a DOI
  landing page — authors, title, edition, publisher, year, pages. Do not cite from memory. An entry
  you cannot confirm is dropped; a detail you cannot confirm is left out rather than guessed.
- Verification is slow and independent of the rest: delegate it to a subagent early, with the
  candidate list, the age rule and the instruction to return per-field verification, then continue
  with sections 1–3 while it runs.
- Second editions often change authors; cite the title page of the edition you list.
- Re-check entries inherited from the old syllabus: page counts, publisher names and repository
  URLs are frequently wrong or dead. Keep the ones that verify, with corrected details.
- Prefer sources that match the course's actual platform and tools; include verified sources in
  the language of instruction where they exist (university repositories).
- Electronic resources: official documentation with URLs you fetched in this session.
- Use one bibliographic style for all entries — the template's.
- Number the list continuously across the groups; the scheme cites these numbers. Let the script
  do the numbering (`{{lit:key1,key2}}`), so reordering the list never breaks the scheme.

## 5. Build the document

`scripts/syllabus_docx.py` (python-docx) fills a copy of the template; the template is never
modified. It keeps the template's page setup, title page, table borders and widths, detects the
fonts from the template, and replaces the content of every cell.

```bash
python scripts/syllabus_docx.py selftest                        # once per machine
python scripts/syllabus_docx.py inspect  <template.docx>        # paragraph indices, tables, widths, fonts
python scripts/syllabus_docx.py extract  <old_or_template.docx> <content.json>   # starting point
python scripts/syllabus_docx.py build    <template.docx> <content.json> <out.docx>
```

Start from `extract` of the template (correct rows and labels) or of the previous syllabus in the
same format, then edit the JSON. Keep the content JSON in the project next to the syllabus: the
next update is an edit of that file and a rebuild.

### Content file

```json
{
  "meta": {"title": "Силабус з навчальної дисципліни «…»", "author": "Кафедра …"},
  "options": {
    "year": 2026,
    "hours": {"Лекція": 32, "Практичне заняття": 16},
    "forbidden": ["<course name of the template>", "<its lecturer>", "<its programme name>"],
    "scheme_widths": null,
    "lit_group_titles": {"core": "Основна література:", "extra": "Додаткова література:", "web": "Інтернет-ресурси:"}
  },
  "title": [
    {"contains": "протокол", "text": "(протокол № … від … р.)"},
    {"index": 20, "text": "«Назва дисципліни»,"}
  ],
  "literature": [
    {"key": "smith", "group": "core", "text": "Smith J. Title (2nd Edition). – City: Publisher, 2024. – 300 p."}
  ],
  "info": [
    {"label": "Назва дисципліни", "items": ["… (шифр …)"]},
    {"label": "Література для вивчення дисципліни", "items": [{"literature": true}]},
    {"label": "Критерії оцінювання", "items": ["**Жирний початок:** текст", {"kind": "crit", "text": "5 балів – …"}]}
  ],
  "scheme": {
    "header": {"4": "Завдання, год"},
    "rows": [
      ["1", ["**Тема лекції.**", "Короткі тези."], "Лекція", "{{lit:smith}}, Сайт курсу https://…", "2", "До наступного заняття"]
    ]
  }
}
```

- `title` — title-page paragraphs to replace, found by `index` (from `inspect`) or by `contains`.
- `info` — one object per row of the info table, in order; rows are added or removed to match.
  `label: null` keeps the template's label. An item is a string (justified paragraph) or
  `{"kind", "text", "bold", "hanging"}` with kind `body` | `left` | `center` | `num` | `crit`
  (`num` and `crit` are hanging-indent paragraphs; write list numbers as `"1.\t…"`).
  `{"literature": true}` expands to the numbered list with group headings.
- `scheme.rows` — one list per class, one cell spec per template column; a cell is a string or a
  list of items. `scheme.header` overrides header cells by column index.
- Markup in any text: `**bold**`, `[[placeholder]]` (yellow, reported), `{{lit:key,key}}` (replaced
  by the entries' numbers), URLs become hyperlinks, `\t` is a tab.
- `options.scheme_widths` — column widths in twips when a column breaks words; keep the template's
  total (shown by `inspect`). `options.scheme_align` — paragraph kind per column.

### What the build checks

It prints `WARN:` lines (and exits 2 with `--strict`) for: literature count outside the range, core
entries not first / wrong count / older than the limit for `options.year`, entries never cited in
the scheme, scheme hours per form of class differing from `options.hours`, and any `forbidden`
string surviving in the output. Unknown literature keys and rows with the wrong number of cells are
errors. Set `year`, `hours` and `forbidden` every time — without them those checks do not run.
Resolve every warning or explain it in the report.

### Overwriting

Save under a new, descriptive file name; never overwrite the template or the previous syllabus.
Before rebuilding over a file you produced earlier, confirm the user has not edited it since
(compare with your last build copy); if they have, apply the change to their version instead.

## 6. Verify before reporting

1. Render the result and look at it: on Windows with Word installed,
   `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/docx2pdf.ps1 -In out.docx -Out out.pdf`
   (works on a temporary copy in its own hidden Word instance); elsewhere LibreOffice
   `soffice --headless --convert-to pdf`. Then `pdftoppm -jpeg -r 70 out.pdf page` and read the
   pages: title page, a page with the literature, the start and the end of the scheme.
2. Look for: words broken inside narrow scheme columns (fix with `scheme_widths`), a title-page
   line that wraps, rows split across pages, leftovers of the template's course, yellow
   placeholders you did not intend.
3. Confirm the numbers: info rows match the template; lecture and practical rows match the hours;
   points sum to 100; the literature numbers cited in the scheme exist.
4. A small text-only change after a verified build can be confirmed by reading the changed cell
   back with python-docx; say in the report that the page was not re-rendered.

## 7. Report

State, briefly and without burying the caveats:

- which programme document and edition the competencies, codes and semester come from, and which
  curriculum the hours come from — especially when it is not the edition of the approval year;
- what differs from the previous syllabus (hours, number of assignments, grading split, codes);
- which lecturer details come from staff pages and are unconfirmed;
- literature: counts per group, entries dropped or corrected from the old list, details that could
  not be verified;
- every `[[placeholder]]` still in the file.

Then record in the project (CLAUDE.md or a project skill) what the next syllabus will need: where
the programme documents are, the template path, the user's corrections to names and titles.
