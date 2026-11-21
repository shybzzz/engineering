# Route C — a native parametric FreeCAD document (PartDesign + Spreadsheet)

Use this route when the deliverable is an **FCStd the owner opens in the FreeCAD GUI** and
changes by editing numbers in a Spreadsheet: a part or a small assembly (one to three bodies)
with a rich feature history, kept in a project folder next to its exports, possibly shared
with collaborators. The document is still generated **from code** — that is what makes it
fully constrained, reproducible and testable — but afterwards it belongs to the owner.

Helpers: `scripts/fc_pd.py` (copy next to the generator, `from fc_pd import *`). Its
self-test at the bottom is a complete miniature generator; read it first.

## 1. Files and ownership

- One generator per model (`tools/build_<model>.py`), shared helpers in one module. A
  generator **overwrites its FCStd from scratch**. Once the owner may have edited the file in
  the GUI, never run the generator over it: change values in the Spreadsheet
  (`fc_pd.set_aliases` does what the owner would do by hand) or ask.
- Safe update while the generator is still the only author: build into a scratch folder →
  run every check → compare the hash of the project's FCStd with the copy generated last
  time (equal = nobody touched it) → copy the new file over it (`fc_pd.save` copies through
  a temp file: no `.FCBak`, non-ASCII folders work) → re-export STEP → re-render. Keep each
  generated version in the scratch folder (`v1.FCStd`, `v2.FCStd`, …) for that comparison.
- **"Next variant" means new files.** A lower / wider / different-angle version gets its own
  FCStd, its own generator and its own render folder; the previous model stays untouched as
  the fallback. When helpers are moved into a shared module for the second generator, prove
  the refactor by regenerating the first model into scratch and comparing volumes — do not
  overwrite the first model to test it.
- STEP / STL / slicer projects / renders are derived: say which ones are stale after a
  change and regenerate the ones you own.
- Derived files of different models carry the same body names (`Holder.stl`, `Key.stl`):
  one temp folder per model.

## 2. The Spreadsheet is the model

- **Inputs on top, a "derived" block of formulas below** (marked "do not edit"). Every number
  a sketch or a feature needs is an alias; nothing is computed only inside the generator.
- Naming: plain names are positive distances (`plate_t`, `wall`, `key_w`); **signed
  coordinates carry their axis as a prefix** (`y_front`, `z_crest`, `u_top`, `w_top`).
  Parameters shared with a sibling model keep the same names. Angles are stored with the
  unit (`15 deg`) and trig takes degrees.
- **Layout rules are formulas**, so the model re-lays itself out when an input changes:
  `min(a; b)` / `max(a; b)` (semicolon!) express "as far back as the insertion path allows",
  "at least the floor thickness", and so on. Example: a guide positioned by
  `chan_w = min(w_platform_edge; w_rim_edge) - ins_gap - key_t`.
- `fc_pd.start()` evaluates every formula in Python too (`ev()`) and asserts that FreeCAD
  agrees — the generator and the document can never drift apart.
- Unknown real-world dimensions (the thickness of the platform the part bolts to) become
  inputs with an assumed value; state the consequence of the other plausible values
  ("for 2 mm set `platform_t = 2`: the window moves to …").

## 3. Sketches: fully constrained by construction

- Every vertex gets `DistanceX` / `DistanceY` from the sketch origin with an expression;
  arcs are locked by radius (half circles by a centre coordinate); circles by centre and
  diameter. `sketch.solve()` returns the degrees of freedom left: demand 0.
- The sign of each coordinate is decided when the generator runs (a zero becomes
  point-on-axis). A parameter change that flips a sign or collapses an edge breaks the
  sketch — that is what the variant sweep (section 6) is for.
- Model every body **in the assembled position, in one coordinate system** — the frame of
  the thing it replaces or mates with (same origin, same "front"). Fits are then plain
  booleans between bodies; the print orientation is applied only at export.
- Inclined features: `tilted_plane()` gives a sketch plane with axes (u, w) = (along the
  slope, slope normal) for side profiles; `slope_plane()` gives planes parallel to the slope
  for pockets on sloped faces. Keep u/w as documented coordinates of the project.
- Draw the **whole side profile of a flat part in one sketch** (blade + bar + ring) instead
  of fusing several pads: tangencies (a ring tangent to the blade) are then exact and there
  are no coincident-face booleans.
- Lettering and logos: copy the outlines into a frozen sketch (`static_wires()`), e.g. from
  the engraved faces of an older model. The document then depends on no font; the size is
  baked in the generator, only the position is driven by the sheet.

## 4. Features that survive parameter changes

Fillet / Chamfer features are the first thing to break when topology shifts (and their
edge references renumber). Prefer geometry that is part of a profile or a cut:

- **Fillets as arcs in the profile sketch** (concave foot of a slope, rounded top edge),
  with tangent points and centres as derived aliases.
- **A profile tangent to a base face dips ~1 mm into the base**, so the arc ends in a step
  inside the material instead of a zero-thickness cusp on the surface.
- **A cut that would end exactly on an existing face or edge goes 1 mm further**
  (`pocket(..., extra=1)`, TwoLengths) — a cut that only touches is a coin toss.
- **Concave fillets where a block lands on a plate along its sides**: pad the block wider by
  the radius on each side, then pocket through with a profile that removes everything
  outside the walls except the arc. The arcs are trimmed by the block's other faces for
  free (no fillet has to run around a corner).
- **Rounding edges by a revolved cut**: `SB.flared_hole()` + `groove()` for a hole with
  rounded mouths (a wire or cord will not chafe), `SB.rounded_rim()` + `groove()` for the
  outer edges of a ring. To round a ring only along its free arc use a partial-angle Groove
  symmetric about the sketch plane and stop ~1° short of both ends, so the cut never ends
  on an existing edge. An attachment rotation above 180° is normalised with a flipped axis:
  rotate about the opposite axis by the complementary angle instead.
- `feature()` tries both directions and keeps the one that really adds / removes material,
  then asserts "valid, one solid" after every step — a failed feature stops the build at
  its own name.

## 5. Export and derived files

- **`Import.export([obj])` drops the Placement of a single top-level object, and
  `shape.rotate()` / `translate()` only change the Placement.** A part "laid flat" that way
  is written in its original position while the in-memory size looks right. Bake the
  transform into the geometry with `shape.transformed(matrix, True)` (planes and cylinders
  stay analytic; `transformGeometry` would turn them into B-splines) or write with
  `shape.exportStep()`. Then **read the written file back** and compare tight size, lowest
  z and volume with the intended shape; print the read-back numbers, not the in-memory ones.
- `BoundBox` is loose on rounded faces (0.2–0.3 mm on a torus): take sizes and the lowest
  point from `shape.tessellate(0.01)`.
- Renders and sections read dimensions from a parameter dump (`fc_dump.py` → `params`)
  rather than repeating numbers; then one render script serves every variant.

## 6. Checks specific to this route

- After the build: every object valid, every sketch DoF 0, every body one solid
  (`fc_pd.report`).
- **Variant sweep**: for each plausible change of every input (both directions, plus the
  combinations the owner is likely to try) → `set_aliases` on a scratch copy → `problems()`
  → the project's fit checks (interference in place, stop, withdrawal path, mating boxes).
  Record in the project notes the list that passed **and the first value that breaks**
  (with the reason: "at 12° there is no room left for the hole in front of the window").
  Repeat the sweep after a change that touches many formulas, and note which list predates
  it.
- A sweep of 20–30 variants with booleans takes longer than a foreground tool call allows:
  run it in the background, one result line per variant, and report when it finishes.
- A question ("what happens if we lower the wedge?") is answered by a sweep on a scratch
  copy and a table of numbers; the project model is not modified for a question.

## 7. Project notes worth keeping (CLAUDE.md or the project skill)

A table of aliases with meaning; the main derived values; the feature tree per body; the
coordinate frames; print orientation and line width; what was verified (with numbers); the
parameter values that pass and the limits that fail; decisions taken on the owner's behalf
that they have not yet confirmed, each with its date; what is *not* done (no slicer project,
never printed, unknown mating dimensions).

## 8. FreeCAD specifics met on this route

- A generator can also be started as
  `FreeCADCmd -c "import sys; sys.argv=['x', r'out.FCStd']; exec(open(r'tools\build.py', encoding='utf-8').read())"`
  from the project root with relative paths — this works in folders with non-ASCII names
  and needs nothing but `FreeCADCmd` on PATH. `__file__` is undefined there: import siblings
  with `sys.path.insert(0, os.path.abspath("tools"))`, after `sys.dont_write_bytecode = True`.
- A cell holding a quantity reads back from `getContents()` as `=15 deg`; a real formula is
  what does not parse as a plain quantity.
- PartDesign needs `AttachmentSupport` in 1.0 (`Support` before); `fc_pd.attach` handles both.
- A sketch on `XZ_Plane` has x = X, y = Z and its normal is −Y; on `YZ_Plane` x = Y, y = Z.
