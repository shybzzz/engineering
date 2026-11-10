---
name: thingiverse-remix
description: Create a 3D-printable model or a remix of an existing thing for publishing on Thingiverse (or Printables) — from the original's files and licence through the model, the maker's marks (ALWAYS ask the user whether to add their logo and the spark mark), to a minimal upload package (final print file, a few renders, one name/description/credits file). Use when the user asks to "make a remix of thing:…", "create a model for Thingiverse", "prepare the thing for publishing", "refresh/update the Thingiverse package", "write the Thingiverse description/credits", or starts a new printable model intended for sharing. Ukrainian triggers: «зроби ремікс», «створи ремікс thing …», «створи/зроби модель для thingiverse», «підготуй до публікації», «онови пакет / папку для thingiverse», «напиши опис / кредити для thingiverse», «додай лого».
---

# Model or remix for Thingiverse

This skill wraps `maker:printable-3d-model` (design rules, generator routes, verification — apply it
for all modelling work) with what publishing adds: the original's rights, the maker's marks, the
upload package and its text. Read both before starting; this file wins where they overlap.

Assets next to this file:

- `assets/owner_logo.svg` — the user's logo (origami-bird line art traced by VTracer; one path,
  strokes ~0.05–0.1 mm at badge size, so they MUST be thickened before printing).
- `assets/spark_mark.svg` — the generator's mark: a spark of 12 rounded rays of slightly uneven
  length around a hub, 100 × 100 viewBox, fill-only paths.

## 1. Starting a remix

1. Get the original's files (`files/`, `images/`, `README.txt`, `LICENSE.txt` of the Thingiverse
   download) into the project root and leave them there untouched. Record in the project notes:
   thing id, title, author, licence, download date.
2. Read the licence BEFORE modelling:

   | original licence | you may | the post must |
   |---|---|---|
   | CC BY | remix, share, sell | credit author + thing id + link |
   | CC BY-SA | remix, share | credit + publish under the SAME licence |
   | CC BY-NC | remix, share, not sell | credit + keep NC, say "non-commercial" |
   | CC BY-ND / "no derivatives" | print and modify for yourself, NOT publish a derivative | stop before modelling and tell the user; offer the three ways out: (a) design from scratch from the idea only, without measuring or reusing the original's geometry — then it is not a derivative and the post names the original as inspiration only; (b) ask the author for written permission and quote it in Credits; (c) keep the remix private |
   | CC0 / public domain | anything | credit anyway (good manners) |

3. Inspect the original before copying its ideas: `stl_bodies.py` from `maker:printable-3d-model`
   splits a print-in-place STL into bodies and draws sections; measure hinge pins, clearances,
   wall thicknesses, pockets. Write the measured numbers into the project notes — they go into the
   post ("what was measured") and into `params.json`.
4. Decide what the remix changes and why (one paragraph, agreed with the user). The remix is a
   generated model (route B of `maker:printable-3d-model` for mechanisms, route A for simple
   accessories); the original STL is reference, never the base mesh you edit.

## 2. Maker's marks — always ask first

**Whenever the user asks to create a remix or a model for Thingiverse, ask before adding any
mark** (use `AskUserQuestion` if available, otherwise a plain question — but do ask, every time,
even if a previous project had them):

> Add maker's marks to the model? Options: both (your logo + the spark), only your logo, only the
> spark, none. And where: name the face if you have a preference.

Rules once the answer is in:

- Never add a mark silently, never drop one the user asked for because the face is awkward —
  find another visible face or shrink the mark and say so.
- The user's logo goes on the left (viewer's), the spark on the right, same height class
  (logo ~1.2–1.4 × the spark's height looks balanced: e.g. 11 mm logo, 9 mm spark on a 13 mm lip).
- Deboss 0.5–0.6 mm into a visible flat or leaning face (a lip front, a rail top, a plate's visible
  face), never the bed face of a thin floor, never inside a sliding fit. Height ≤ face height − 2 mm.
- Build them with `fc_svg.py` (`svg_solid` for the logo, `spark_mark` for the spark,
  `place_on_plane` for a leaning face). Line art: `min_stroke` 0.45 mm (the slicer drops narrower
  grooves); keep the logo's facets readable — if details < 1 mm vanish at the chosen height, say so
  and propose a larger height, not a different logo.
- Make the marks parameters (`logos.enabled`, `logos.user_svg`, `logos.spark`, heights, x-positions,
  `logos.depth`) so another maker can drop or swap them; copy `owner_logo.svg` into the project next
  to `params.json` and reference it there (the project must build without this skill's folder).
- Verify with a close-up render straight onto the face and with the mesh check (thin bands can
  create self-intersecting facets; PrusaSlicer `--info` is the tie-breaker). Marks approved by the
  user stay in every later build and in the published STL.

## 3. The upload package (`<project>/thingiverse/`)

Minimal, by the user's standing rule. Exactly:

- the final print file(s): one STL per thing to print (for print-in-place, ONE file with all bodies;
  say "do not split" in the description). Copy, byte-identical, from the generator's output;
- `images/` — three to six renders, numbered in display order, English labels: `01_` hero shot with
  the object the model serves (the phone / the tool / the board in place), `02_` the model alone
  in its working pose, `03_` folded / as-printed pose, `04_` a second pose or variant,
  `05_` a side view that shows the geometry (angle, fit). No close-ups of technical details,
  no coupon render — those belong to the build report, not the post;
- `DESCRIPTION.md` — one file, three H1 sections (section 4).

Nothing else: no fit coupon, no separate bodies, no STEP, no generator zip, no copies of the
original's README/LICENSE (they stay in the project root; attribution lives in Credits). Keep a
source copy of the post text in the project (`THINGIVERSE_POST.md`) and copy it into the package.
Never hand-edit files in the package — regenerate and recopy.

Refresh after every geometry change: recopy the STL, re-render the same views, run the
manifold / shell-count check on the copied file, update the description if a feature changed, then
tell the user which file changed and that the slicer project needs a re-import.

## 4. `DESCRIPTION.md`

```
# Name
<Function> <object> (<what it fits>) - print-in-place remix of thing:<id>   (about 90 characters max)

# Description
<one paragraph: what it is, for what, folded/deployed sizes, "prints flat, in one go, without supports">
<one paragraph: what is inherited from the original, then "New in this remix:" + a bullet list of
 features in user terms (what it does for them), each with the one number that matters>
<one sentence: generated from a parametric script; variants on request>
<one sentence on printing: default slicer profile, no supports, flat, keep bodies as one object,
 how to free the hinges after printing>
## How to use
<numbered steps: deploy, fold, insert the mating object, route cables>

# Credits
- Remix of **"<original title>"** by **<author>**, https://www.thingiverse.com/thing:<id> - <what
  exactly was taken: concept, hinge, pockets>.
- Licence: **<same as original>**.
- Designed by <user's name>; geometry generated with <tool> from a parametric FreeCAD script.
```

NO "Print settings" section: the model is designed to print with the slicer's defaults, and the
one sentence above says so. Add a setting only if the model truly needs a non-default one, and then
only that one. Do NOT put in the description: file lists, parameter names, build internals
(interference tables, sweep checks), the coupon, dimensions nobody needs to use the thing.
Thingiverse also has a "Remix of" field — remind the user to set it to the original thing id.

## 5. Hand-over

Publishing is done by the user from their own account — never post on their behalf. Hand over:
the package path, the list of its files, a one-line summary of what changed since the last
package, and the reminder about the "Remix of" field and the licence choice.

## 6. Checklist before saying "ready"

- [ ] licence of the original allows the remix; licence of the post matches section 1
- [ ] the user was asked about the maker's marks and the answer is implemented (or "none")
- [ ] package = print file(s) + 3–6 numbered renders + `DESCRIPTION.md`, nothing else
- [ ] print file byte-identical to the generator output; manifold, expected shell count
- [ ] description: Name / Description / Credits, no print-settings section, no file or parameter lists
- [ ] credits name title, author, thing id, link, licence; designer and generator named
