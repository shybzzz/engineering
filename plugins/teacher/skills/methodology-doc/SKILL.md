---
name: methodology-doc
description: Build a student methodology (методичка / skrypt) for one course topic as a Claude Doc — numbered theory with generated figures, a step-by-step algorithm, a worked example, a script-generated problem set with cross-checked answers and a verified literature list — in Ukrainian with a direct translation tab (Polish or another language). Use when the user asks «зроби методичку», «створи методичку з теми …», «методичка у формі артефакту», «методичку польською і українською», «зроби задачі з відповідями для студента», "make a study guide / problem set for the student", or wants an existing methodology doc extended with a new topic.
---

# Methodology doc: course topic → bilingual Claude Doc with a verified problem set

A methodology here is a self-contained teaching text for one topic that a student can study on
their own: theory in the notation of their course, an algorithm for the exam-type problems, one
fully worked example, and a batch of practice problems whose answers were computed by a script
and cross-checked by a second method. It is delivered as a Claude Doc (one tab per language),
not as a local file, so the tutor and the student can read, comment and edit it in place.

## 0. Collect the inputs before writing anything

1. **Source material.** Read everything the project holds for the topic: syllabus pages (lecture
   and class topics, hours, textbook list), the student's notebook photos (problem statements,
   the lecturer's notation, the order of questions, the solving checklist), any earlier
   methodology in the same project. Zoom into photos with PIL when the handwriting is small;
   recompute every draft number before trusting it — drafts are source material, not an answer key.
2. **Format to match.** If a methodology already exists, read its tab outline and a few sections
   in full (`read` with `projection: "outline"`, then `view` by block) and copy its conventions:
   section names and numbering, how formulas, figures, tables and the literature are typeset.
   Do not invent a second format within one project.
3. **Notation and terminology of the course.** Take the symbols, the exam phrasing and the
   target-language terms from the lecturer's materials and the course's primary textbook; keep a
   short glossary (UA ↔ target language) and use it consistently in both tabs.
4. **Audience.** The student. Write for someone who can already do the prerequisite calculations
   and needs exactly one new thing explained; say in words what every formula means.

## 1. Document structure (fixed)

Follow the `ua-docs-style` conventions (numbered sections, every formula `\tag{N}`-numbered and
referenced, every figure/table numbered and referenced before it appears, every symbol defined at
first use, «Література» last, no section ending on a figure or table). The sections, in order:

| # | Section | Content |
|---|---------|---------|
| 1 | Вступ | what the text teaches, prerequisites, "after this the student can …" list, **Табл. 1** with all symbols and units, notation remarks (angle units, decimal comma, calculator mode) |
| 2 | Теоретичні відомості | 2.1 … 2.N subsections, each: concept → formula → "де …" → figure → one closing sentence; summary tables where cases branch |
| 3 | Покрокова інструкція | 3.1 general algorithm in the order the exam asks the questions (mirror the lecturer's checklist), then one variant per problem scheme, then a "typical errors" paragraph built from the student's real slips |
| 4 | Приклад розв'язання | the student's own notebook problem, solved as «Крок 1 … Крок N» with every intermediate number, checks (Kirchhoff, power balance, phasor diagram), and the instructive twist (e.g. the same circuit with one element removed) |
| 5 | Задачі | problem statement common to all, bullet list "scheme k — figure, table, problems a–b: find …", then one table per scheme |
| 6 | Відповіді | one table per scheme, rounding rule, "if your result differs by sign / magnitude, check …" |
| — | Література | 3–5 entries: the course's primary textbook, its problem book, a Ukrainian textbook, one English reference; each cited in the body; Crossref-checked, with the "no DOI (checked DATE)" line when none exists |

Formulas: ```latex code blocks of bare TeX with `\tag{N}`, multi-line as `\begin{aligned}`.
Prose uses Unicode subscripts (U₁, I_A, X_M) and the decimal comma. Figures: a media paragraph
followed by an italic caption paragraph `*Рис. N. …*`. Tables: a bold caption `**Табл. N.** …`
above a pipe table. The translation tab keeps identical numbers for formulas, figures and tables;
only the language, units (В/Ом/А ↔ V/Ω/A) and panel letters (а/б/в ↔ a/b/c) change.

## 2. Tooling: everything numeric comes from scripts

Create `tools/<topic>/` in the project and keep these files there (they are the source of truth
for the doc; numbers are never typed by hand):

- **`gen_problems.py`** — defines the problem schemes (typically 5 schemes × 10 problems),
  parameter pools, a fixed `random.Random(<seed>)`, and for every scheme **two independent
  solvers** (e.g. a closed-form/node method and a direct linear system, or a transformation to
  another topology) plus a conservation check (power balance, Kirchhoff sums). `assert` that the
  solvers agree for every problem; reject degenerate parameter sets (near-resonance, huge
  currents, accidentally symmetric data). Output: `tables_<lang>.md` for each language (header
  words and variant letters from a per-language dictionary, units translated, values identical),
  `problems.json`, and a printout of the worked example with all intermediate values.
  Changing the seed, pools or scheme order changes every answer, so after the tables are pasted
  into the doc the seed is frozen.
- **`draw_figs.py`** — schemdraw for circuits/flowcharts, matplotlib for phasor or function plots,
  PIL to compose panels into one PNG per figure. Produce `fig/figN_<lang>.png` for every language:
  only panel letters and text-bearing figures (flowcharts) differ, all other labels are symbolic.
  Open every PNG and look at it before using it; fix overlapping labels, missing node labels and
  empty margins. Name the generating command in the project notes.
- **`doc_<lang>.md`** — the full text of each tab with `![Рис. N](fig/figN_<lang>.png)` links and
  `<!-- Sk problems -->` / `<!-- Sk answers -->` placeholders where the generated tables go. Write
  the source language first, translate section by section, then push to the doc.

Known pitfalls (schemdraw 0.23, Windows): `Source`-type elements (sources, meters) ignore
`.at(p1).to(p2)` — place them with `.at(p1).theta(angle).length(d)`; `.label()` must be called
before `d.add()`, not on the returned element; on vertical elements `loc="top"` lands on the left
and `loc="bottom"` on the right; set `length=` on `CurrentLabel` for short wires; the console code
page is cp1251, so run Python with `PYTHONIOENCODING=utf-8` when printing non-ASCII.

## 3. Writing order in Claude Docs

1. Load the docs skill/instructions, then create the doc **first**: title, byline chips, one
   `pending` block per section with a plain-words intent. Open it for the user.
2. Fill one section per `update` call (`replace` the pending block with `## heading` + body),
   prose sections in reading order. Captions go in as italic paragraphs now; images come later.
   Paste the generated tables from `tables_<lang>.md` into sections 5 and 6.
3. A write is capped at **32 KB**; an over-cap batch member is refused and nothing lands. Split
   long content at a section boundary and append the rest with `insert` at `{"kind":"root"}`,
   `side: "end"`.
4. Figures last: upload all PNGs of all languages as artifact assets in one call (the doc's link
   as `url`, `asset: true`, `file_paths`), `create` one blob per asset id, then insert
   `![Рис. N](blob/<id>)` **before** each caption paragraph (caption block ids come from the
   fill acks — no re-read needed).
5. Translation tab: one `batch` with the file create, the prose node (first half of the text with
   its own byline chips and blob image lines), the file pointer update and the project patch that
   names and orders the tabs (main tab `a0` named by its language, translation `a1`); then append
   the second half. Record the doc id, tab ids and body ids in the project notes.
6. Hand over with one short line and the link. Then update the project's CLAUDE.md (doc link and
   ids, script paths, conventions that are not obvious from the files) and memory.

## 4. QA checklist before handing over

- Formula tags sequential across the tab; every `(N)` referenced; every symbol defined at first
  use (walk prose, formulas, table headers, captions in order).
- Every figure and table referenced in text before it appears; no section ends on a figure,
  table or bare citation.
- All numbers in sections 4–6 equal the script output; the worked example's intermediate values
  were printed by the script, not derived by hand.
- Problem tables and answer tables have the same problem numbers; variant letters match the
  figure panels.
- Literature: each entry cited at least once, Crossref queried for each, DOI appended or the
  "none registered (checked DATE)" line present.
- Translation tab: same headings/numbers, units converted, glossary terms used, panel letters
  changed, the same blob images in the same places.
- The "typical errors" paragraph names the student's actual mistakes (radian mode, angle added
  instead of subtracted, dropped sign, method applied outside its validity) without naming the
  student.

## 5. Extending an existing methodology

Edit the existing doc in place (read the outline, target blocks by id or by quoted text); never
recreate it. When adding a formula, figure or table in the middle, renumber everything after it
in both tabs and update all references. When adding problems, extend `gen_problems.py` with a new
scheme that keeps the two-solver `check()`, regenerate the tables and re-paste them.
