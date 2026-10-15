---
name: ua-docs-style
description: Formatting and style conventions for the Ukrainian engineering documents (*_ua.md and their Confluence ports) of ALL investigations under this Investigation/ folder (Vibration Detection, Box Vibration, Different, future ones). Use whenever creating, editing, or extending these documents — every modification must preserve the academic-article structure, LaTeX math, and the numbering/cross-referencing system described here.
---

# Ukrainian docs — academic style conventions

Applies to every human-facing Ukrainian document of every investigation under
`<Investigation>/` — future `*_ua.md` drafts in an investigation's `docs/`
folder and the documents already ported to Confluence (pages under the
boomprj space are the source of truth for their content). As of 2026-09-02
ALL Vibration Detection documents are ported and their md files deleted:
approach → page 270041089, channel comparison → 270237697, motor RPM
crosscheck → 269746185 (children of the parent page 269746177, whose
Confluence title was not renamed on 2026-09-25 and still carries the old
term).
Edit such pages via the Atlassian MCP tools (contentFormat html) keeping the
same structure and conventions, EXCEPT math: Confluence does not render LaTeX,
so on those pages math is typeset as Unicode/HTML instead — italic variables
(`<em>v</em>`), Unicode superscripts/subscripts (², ₁, ₂, ₖ, ₛ), real symbols
(−, ·, ≈, √, π), bold letters for vectors (state "вектори позначено жирним").
Displayed formulas sit in a `<blockquote>` with the number as bold `(N)` at the
line end after `&nbsp;` spacing; the numbering/referencing rules («формула (N)»,
sequential, every formula cited) still apply. Full porting/publishing mechanics
(site ids, DOI rules, md→Confluence handover) live in the Investigation-level
skill `port-investigation-to-confluence`
(`<Investigation>/.claude/skills/`). Does NOT apply to
`plan.md`-type internal working notes, generated CLAUDE.md files, or
`docs/results/` reports.

## Document structure

Scientific-article layout, in this order: title (H1) → `## Анотація` →
numbered sections `## 1. …`, subsections `### N.M. …` → `## Висновки`
(numbered points) → `## Література` (always the LAST section). No "phases",
no roadmap/plan sections — the user removed them deliberately; future work is
at most one sentence in Висновки.

## Language and terminology

- Ukrainian, academic register, audience = engineers. Explanations should stay
  accessible: after every formula, say in words what it means.
- Transliterated anglicisms are allowed ONLY when no established Ukrainian term
  exists. Known substitutions already enforced: «накладання спектрів» (not
  «аліасинг»; give "(англ. aliasing)" in parentheses at first mention),
  «група» (not «кластер»), «продукти взаємної модуляції» (not
  «інтермодуляційні продукти»), «п'ять найсильніших піків» (not «топ-5»).
  Accepted borrowings (established terms): гістерезис, трекер, гомодинний,
  биття, семпл, бін.
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
  is stronger than one that holds "у наближенні".
- The same first-use rule applies to technical terms and abbreviations, per
  document: AC-енергія, рушій (engine), ФВЧ, EMA, SNR, RMS, ODR, FIFO etc.
  get a short worded
  explanation (with the English expansion in parentheses for borrowed
  abbreviations) the first time they appear — including terms that first
  appear inside a diagram or table (explain them in the prose right after it).

## Figures

- Image files live in `docs/img/<topic>/` (e.g. `img/chan/`), referenced by
  relative path. Figures that come from scripts must be regenerated by the
  script, never hand-edited; the generating command is named in the document
  (e.g. `python py/chan_compare_report.py`).
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
- Prefer authoritative sources: original papers, standard textbooks
  (Oppenheim & Schafer), IEEE journals, manufacturer datasheets.
- **Every entry is verified and carries a DOI where one is registered — already
  in the md draft, not only at the Confluence port.** For EVERY entry
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
  quoting IEC dimensions).
- Known results (keep in sync with the list in
  `port-investigation-to-confluence`). Verified DOIs: Wilson, Taylor, Doherty,
  Ghaboussi 1973 "Incompatible displacement models"
  `10.1016/B978-0-12-253250-4.50008-7`; Taylor, Beresford, Wilson 1976
  `10.1002/nme.1620100602`; Gibson & Ashby "Cellular Solids" 2nd ed. 1997
  `10.1017/CBO9781139878326`; Schenk & Gärtner 2004 (PARDISO)
  `10.1016/j.future.2003.07.011`; Gent 1958 (Shore hardness → Young's
  modulus) `10.5254/1.3542351`. Checked 2026-09-20, NO registered DOI (only
  reviews have one): Clough & Penzien "Dynamics of Structures"; Steinberg
  "Vibration Analysis for Electronic Equipment"; IEC 60086-2; ST LIS3DH
  datasheet (DocID17530 Rev 2, December 2016); Oppenheim & Schafer.

## Paragraph/section endings

Never end a paragraph, subsection, or section with a table, a figure, a
caption, or a bare citation. After each table/figure add at least one closing
sentence that interprets it («Отже, …», «Результат табл. N підтверджує …»).
The only exception is `## Література` itself.

## When modifying

1. Adding a formula/figure/table in the middle → renumber everything after it
   and update ALL in-text references (grep the document for `\tag{`, `Рис.`,
   `Табл.`, `[N]` patterns to find them).
2. New figures: extend the generating script in `py/` (or add a new one),
   regenerate the PNGs, keep captions in sync with what the script draws.
3. Numbers/claims that come from measurements must match the current outputs
   of the investigation's pipeline (for Vibration Detection:
   `docs/results/allrecs/summaries.json`, comparison scripts); rerun the
   script rather than editing numbers by hand.
3a. Factual claims about recordings (aircraft, payload, what happened during
   the vibration episode, sensor mode) must name their source in place: the operator's
   note file (`readme.txt`, `*.docx`, `*.gdoc`, `config.txt`) with its path
   relative to the investigation's data root (for Vibration Detection: the
   AccLogs root) — never an absolute path, never an unsourced
   assertion. If no operator note exists, say so explicitly and attribute the
   numbers to our own analysis.
4. Cross-links to documents that live in Confluence use the page URL
   (https://boom-prj.atlassian.net/wiki/spaces/boomprj/pages/<id>) with the
   document title in «лапки» as the link text, e.g.
   «див. [«Вибір каналу попередньої обробки…»](…/pages/270237697), розділ 3».
   Links between md drafts still on disk use plain relative file names,
   never absolute paths.
5. After editing, verify: all tags sequential; all figures/tables/references
   cited; no section ends on a table/figure/citation; terminology rules held;
   every «Література» entry checked on Crossref and given its DOI (or
   confirmed to have none).
