---
name: ua-docs-style
description: Formatting and style conventions for Ukrainian engineering/research documents written in the style of an academic article (Claude Docs, Markdown drafts with LaTeX math, Confluence pages) — structure, terminology, numbered formulas/figures/tables, cross-referencing, verified references with DOIs — plus the default workflow: write the document as a Claude Doc, the user comments in it, Claude answers/fixes, and only then the project's own documentation is updated. Use whenever creating, editing, extending, or reviewing such a document (investigation reports, technical notes, method descriptions in Ukrainian), or when the user asks «оформи за стилем», «перевір документ на відповідність стилю», «додай формулу/рисунок/таблицю/джерело», «створи документ у Claude Docs», «перенеси звіт у клод док», «прочитай коментарі», «я прокоментував документ», «документ готовий, онови документацію». Every modification must preserve the article structure and the numbering/cross-referencing system described here.
---

# Ukrainian docs — academic style conventions

Applies to every human-facing Ukrainian engineering document that is meant to
be read as a technical article: Claude Docs, Markdown drafts (`*_ua.md` or
similar) and the same documents published to Confluence. When a document
exists both as an md draft and as a Confluence page, the project decides which
is the source of truth — ask or check the project's CLAUDE.md/skills; by
default a published Confluence page wins over a stale draft. While a document
is under review in a Claude Doc (workflow below), the Claude Doc is the working
copy.

Does NOT apply to internal working notes (`plan.md`-type files), generated
CLAUDE.md files, or auto-generated result reports.

## Default workflow: write in a Claude Doc, review by comments

Use this sequence whenever the session has the Claude Docs connector and the
user has not asked for another medium (an md file only, Confluence only). If
the connector is absent, say so and fall back to an md draft.

1. **Create the document as a Claude Doc**, following every convention of this
   skill (structure, numbering, terminology, references) and «Claude Docs
   specifics» below, and give the user the link. If the document already
   exists as an md draft or a Confluence page, port it without changing its
   content.
2. **The user reads it and leaves comments and questions in the doc.** Wait for
   them; do not keep polishing the document on your own meanwhile.
3. **On the user's signal** («прочитай коментарі», «я прокоментував», or a
   comment sent to Claude from the doc) read ALL comment threads of the doc in
   one query and handle every one of them:
   - a question → answer in its thread; if the question shows the text itself
     was unclear, also improve the text and say so in the reply;
   - a requested correction → make it in the doc and reply briefly with what
     changed (the edit itself is visible in the doc — do not repeat it);
   - something only the user can decide or supply → say so in the thread.
   Keep numbering and cross-references consistent after every change (see
   «When modifying»). Do not resolve threads the user wrote — they close them.
   Report in chat: how many threads there were, what was changed, what is
   still open. Steps 2–3 repeat until the user says the document is settled.
4. **Only when the user says the document is settled** («все стало на свої
   місця», «документ готовий») update the project's own documentation to match
   the final doc: the md/Confluence counterpart of the document if the project
   keeps one, the knowledge files Claude maintains there (CLAUDE.md findings,
   skill baselines, indexes, memory) and every number or statement elsewhere
   that the review changed. Until then the project files stay as they were —
   do not propagate statements that are still under review. List in chat which
   project files were updated.

## Claude Docs specifics

Mechanics (creating, filling, comments, uploads) follow the Claude Docs
connector's own instructions — load them first. Fill the doc section by
section (heading + body per call), all text first, images last. Style
differences from an md draft:

- **Inline math is not rendered.** Write it as plain Unicode text: θ ≈ 21,4°,
  H·cos θ, Δτ, x₀, T_лог — real symbols (−, ·, ×, ≈, °), Unicode
  sub/superscripts where they exist, an underscore otherwise. This covers
  prose, table headers and figure captions.
- **Displayed formulas** go into a ```` ```latex ```` code block of bare TeX
  (no `$$`), numbered with `\tag{N}`; degree as `^\circ`, decimal comma
  `{,}`, Cyrillic units inside `\text{…}`. The numbering and referencing
  rules of «Math» are unchanged.
- **Figures**: upload the image files to the doc, then place
  `![Рис. N](blob/<id>)` directly above the italic caption paragraph
  `*Рис. N. …*`. Same numbering and «referenced before it appears» rule.
- **Tables**: pipe tables with the bold `**Табл. N.**` caption line above.
- **Links**: relative links to project files do not resolve in a cloud doc —
  keep the file name/path as inline code without a link; external URLs become
  explicit links (`[url](url)`).
- Add nothing the article structure does not have: no byline, date chip,
  summary or «key takeaways» section.
- When porting from md, these are changes of notation, not of content; tell
  the user which ones were made.

## Confluence specifics

Edit Confluence pages via the Atlassian MCP tools (contentFormat html) keeping
the same structure and conventions, EXCEPT math: Confluence does not render
LaTeX, so there math is typeset as Unicode/HTML instead — italic variables
(`<em>v</em>`), Unicode superscripts/subscripts (², ₁, ₂, ₖ, ₛ), real symbols
(−, ·, ≈, √, π), bold letters for vectors (state «вектори позначено жирним»).
Displayed formulas sit in a `<blockquote>` with the number as bold `(N)` at the
line end after `&nbsp;` spacing; the numbering/referencing rules («формула (N)»,
sequential, every formula cited) still apply. If the project has its own
porting/publishing skill (site ids, space keys, md→Confluence handover), follow
it for the mechanics; this skill covers only style.

## Document structure

Scientific-article layout, in this order: title (H1) → `## Анотація` →
numbered sections `## 1. …`, subsections `### N.M. …` → `## Висновки`
(numbered points) → `## Література` (always the LAST section). No "phases",
no roadmap/plan sections; future work is at most one sentence in Висновки.

## Language and terminology

- Ukrainian, academic register, audience = engineers. Explanations should stay
  accessible: after every formula, say in words what it means.
- Transliterated anglicisms are allowed ONLY when no established Ukrainian term
  exists. Known substitutions: «накладання спектрів» (not «аліасинг»; give
  "(англ. aliasing)" in parentheses at first mention), «група» (not
  «кластер»), «продукти взаємної модуляції» (not «інтермодуляційні
  продукти»), «п'ять найсильніших піків» (not «топ-5»). Accepted borrowings
  (established terms): гістерезис, трекер, гомодинний, биття, семпл, бін.
- Apostrophe in Ukrainian words: `'` (п'ять, з'являється).

## Math

- All formulas in LaTeX: inline `$f_0$, $\cos\theta$, $F_s$`; displayed
  formulas as `$$ ... \tag{N} $$` (KaTeX renders in VSCode preview).
- EVERY displayed formula is numbered with `\tag{N}`, sequentially through the
  whole document in order of appearance, and EVERY numbered formula must be
  referenced from the text at least once — as «формула (N)», «за (N)»,
  «згідно з (N)», «рекурсія (3)–(4)» etc. If a formula is never referenced,
  either reference it or inline it.
- Multi-line derivations: `$$\begin{aligned} ... \end{aligned} \tag{N}$$` with
  `&&\text{— пояснення}` per line.
- Decimal comma in Ukrainian prose numbers inside math: `$0{,}89$`.
- **Every symbol is explained at its first appearance.** If a formula uses a
  symbol not already defined in the text above it, add a definition — either
  in the introducing sentence («…з амплітудою $A$ і частотою $f_0$…») or in a
  «де $X$ — …, $Y$ — …» clause immediately after the formula. This applies to
  vectors ($\vec g$, $\vec v$ — name their components/meaning), subscripted
  variants ($v_{\parallel}$, $A_{\parallel}$, $f_{max}$), indices/lengths
  ($k$, $N$) and derived quantities ($f_a$). The rule is STRICT and covers
  every occurrence of math notation: the анотація, table headers/columns
  (e.g. $P(f)$ must be defined in the text introducing the table), figure
  captions, and left-hand sides of formulas ($q(t)$, $n(t)$ — a formula
  defines its right side, the name on the left still needs a worded meaning).
  When checking a document, walk ALL math in order — prose, formulas, tables —
  and verify each symbol was defined earlier or in the attached «де …» clause.
- Every approximate equality (≈) must be justified: name the expansion or
  theorem used (e.g. біноміальний ряд для $\sqrt{1+x}$), state the validity
  condition (what is small compared to what) and the order of the truncation
  error. Where an exact intermediate form already carries the qualitative
  conclusion, show it before the approximation — a result that holds exactly
  is stronger than one that holds «у наближенні».
- The same first-use rule applies to technical terms and abbreviations, per
  document: e.g. AC-енергія, рушій (engine), ФВЧ, EMA, SNR, RMS, ODR, FIFO
  get a short worded explanation (with the English expansion in parentheses
  for borrowed abbreviations) the first time they appear — including terms
  that first appear inside a diagram or table (explain them in the prose
  right after it).

## Figures

- Image files live in an image folder next to the document (e.g.
  `img/<topic>/`), referenced by relative path. Figures that come from scripts
  must be regenerated by the script, never hand-edited; the generating command
  is named in the document (e.g. `python <script>.py`).
- Every figure: `![Рис. N](relative/path.png)` immediately followed by an
  italic caption line: `*Рис. N. Повний підпис реченням.*`
- Numbered sequentially per document; every figure referenced in text
  («наведено на рис. N», «як видно з рис. N») BEFORE it appears.

## Tables

- Every table gets a bold caption line ABOVE it: `**Табл. N.** Підпис.`
- Numbered sequentially per document (separate counter from figures); every
  table referenced in text («зведено в табл. N») before it appears.

## References

- Single numbered list under `## Література` at the very end; no footnotes,
  no inline bibliographies elsewhere.
- Every entry MUST be cited in the body as `[N]` (or `[N, §X.Y]`) at least
  once; every `[N]` in the body must exist in the list. When adding/removing
  an entry, renumber and update all in-text citations.
- Prefer authoritative sources: original papers, standard textbooks,
  peer-reviewed journals, standards, manufacturer datasheets.
- **Every entry is verified and carries a DOI where one is registered —
  already in the md draft, not only at publication.** For EVERY entry
  (papers, book chapters AND books) search Crossref
  (`https://api.crossref.org/works?query.bibliographic=<title+authors>`), then
  confirm the candidate via `https://api.crossref.org/works/<doi>`: title,
  authors, year, and for articles volume/issue/pages must match the entry —
  correct the entry from the Crossref record if they differ. Beware book
  reviews and same-titled chapters by other authors (a review's DOI is NOT the
  book's DOI), and a different edition/publisher is a different work. Append in
  md as `DOI: [10.xxxx/yyyy](https://doi.org/10.xxxx/yyyy).` Leave the entry
  without a DOI only when the search finds none — never guess or fabricate one.
  Entries without a DOI must still be identifiable: datasheets get document
  id + revision + date (read them off the PDF), standards get number:year and
  edition, web documents get a URL.
- Verify the CLAIM as well as the bibliographic record: the cited source must
  actually contain what the sentence attributes to it. Give a section/table
  number (`[N, §X.Y]`, `[N, табл. K]`) only if it was checked in the source
  itself; if the source text is not at hand (paywalled standard, book not on
  disk), cite without a locator and, where possible, add an accessible
  secondary source that reproduces the fact (e.g. a manufacturer datasheet
  quoting a standard's dimensions).
- If the project keeps a list of already-verified references (DOIs found or
  confirmed absent), reuse it instead of re-searching, and extend it when a
  new source is verified.

## Paragraph/section endings

Never end a paragraph, subsection, or section with a table, a figure, a
caption, or a bare citation. After each table/figure add at least one closing
sentence that interprets it («Отже, …», «Результат табл. N підтверджує …»).
The only exception is `## Література` itself.

## When modifying

1. Adding a formula/figure/table in the middle → renumber everything after it
   and update ALL in-text references (grep the document for `\tag{`, `Рис.`,
   `Табл.`, `[N]` patterns to find them).
2. New figures: extend the generating script (or add a new one), regenerate
   the PNGs, keep captions in sync with what the script draws.
3. Numbers/claims that come from measurements must match the current outputs
   of the project's processing pipeline (summary files, comparison scripts);
   rerun the script rather than editing numbers by hand.
3a. Factual claims about the measured objects or recordings (what was tested,
   under which conditions, what happened, device mode) must name their source
   in place: the operator's note file (`readme.txt`, `*.docx`, `*.gdoc`,
   `config.txt`, …) with its path relative to the project's data root — never
   an absolute path, never an unsourced assertion. If no operator note exists,
   say so explicitly and attribute the numbers to our own analysis.
4. Cross-links to documents that live in Confluence use the page URL
   (`https://<site>.atlassian.net/wiki/spaces/<space>/pages/<id>`) with the
   document title in «лапки» as the link text, e.g.
   «див. [«Назва документа…»](…/pages/<id>), розділ 3».
   Links between md drafts still on disk use plain relative file names,
   never absolute paths.
5. After editing, verify: all tags sequential; all figures/tables/references
   cited; no section ends on a table/figure/citation; terminology rules held;
   every «Література» entry checked on Crossref and given its DOI (or
   confirmed to have none).
