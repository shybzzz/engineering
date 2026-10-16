---
name: printable-3d-model
description: Design and generate 3D models for FDM printing (STL/STEP/3MF) from code — accessories for existing objects (trays, boxes, stands, lids), parametric parts with engraved text/logos, and multi-part printed mechanisms (carriages, guides, wheels, brackets) built with a parametric FreeCAD generator; manifold checks, support-free design rules, assemblability, fit-test coupons, previews and slicer hand-off. Use when the user asks to "make/create a 3D model for printing", "generate an STL", "make a tray/box/stand for …", "prepare for printing", "measure this STL", "why does the slicer say non-manifold", "will it fit on the bed", "the printed part is too tight/loose/rubs/needs supports", or when STL/3MF files must be inspected, scaled or arranged without mesh libraries. Ukrainian triggers: «зроби/створи 3D-модель для друку», «згенеруй STL», «зроби лоток/бокс/підставку під …», «підготуй до друку», «виміряй STL», «чому non-manifold», «чи влізе на столик», «деталь туга/болтається/треться/потребує підтримок».
---

# Printable 3D model: from measurement to a file the slicer accepts

You work as a design engineer who designs a part for a specific printer and
generates it **from code**, not by clicking in CAD. The goal is a file the slicer
accepts without warnings, that prints **without supports**, that can actually be
**assembled**, and that fits the real objects on the first try. Helper scripts live
next to this file in `scripts/`:

- `scripts/stl_info.py` — stdlib-only STL inspection: size, z-min, volume, manifold, shell count.
- `scripts/mesh_kit.py` — template module for generating watertight STL:
  `Mesh.tri/loft/flat/engrave/pocket/check/write`, text from a font, SVG logo.
  Self-test: `python -I mesh_kit.py demo.stl`.

Two generation routes — pick one up front:

| Route | When | Tooling |
|---|---|---|
| **A. Mesh from code** | one-off accessories: trays, boxes, stands, lids, plaques with engraving | Python stdlib + `shapely` (+ `fontTools`), `mesh_kit.py`, STL out |
| **B. Parametric B-rep generator** | mechanisms of several interacting printed parts that are iterated (print → measure → change a parameter → regenerate → reprint), parts that must mate with existing hardware (bearings, screws, nuts, ropes) or with an existing printed set | FreeCAD ≥ 1.0 headless Python, `params.json` + builders + `derive()`, STEP out (section 7) |

The design rules (sections 2–5) and the checks (section 8) apply to both.

## 0. Pin down the inputs first

Before writing code, establish and record in a `PARAMS` block (route A) or
`params.json` (route B):

1. **Printer and bed** (the user may say "столик"/"стіл"): bed size, nozzle, layer
   height. If a `.3mf` project is around, extract them from it (`zipfile`;
   `Metadata/project_settings.config` is JSON with every setting,
   `Metadata/model_settings.config` maps objects to source files,
   `Metadata/plate_N.json` has per-plate bboxes). Every printed part must fit the
   bed with a brim margin (≥ 5 mm per side).
2. **Real dimensions of the objects the part mates with** — measure them from the
   STL/STEP (`stl_info.py`, or load the STEP in FreeCAD and measure the B-rep); do
   not trust file names: a suffix may mean anything (e.g. a board's cell size, not
   the figure's height). For a seat/pocket what matters is the *profile*, not the
   bbox: find the widest point, whether the base is cylindrical and up to what
   height (slice the mesh along Z). For hardware (bearings, screws, nuts, cords)
   measure the real item with calipers; measure cords/ropes **under tension**.
3. **Project memory**: if the project already has a CLAUDE.md / `.claude/skills/*`
   / memory with measured dimensions, clearances, fit-coupon results and
   preferences — they take precedence over this skill.

## 1. Pitfalls of input meshes and models

- **The mesh does not sit on Z = 0.** Exports from Fusion/other CAD often have
  z-min < 0. The slicer drops it onto the bed itself, but any script that measures
  height or stacks parts must subtract z-min first.
- **Scale between "sizes" of a set is non-linear.** If a set comes in two sizes, do
  not assume the ratio from the names — measure the factor and scale from the
  nearer one.
- **"Identical" file pairs may be different meshes** (different triangle count) —
  compare counts before treating one as a rescale of the other.
- **File names contain typos** (double underscores etc.): search with globs, not
  exact names; print the list of files found.
- Binary STL: 80-byte header, uint32 count, then 50 bytes per triangle
  (12 float32 + uint16). Read it with `struct`; numpy/trimesh may be absent.
- A full product STEP can be huge (tens of MB with every PCB component). Copy it
  to an ASCII temp path, load with `Import.insert` under FreeCAD's Python (may take
  a minute), skip sub-bodies you don't need by label, and keep a **simplified
  envelope** of it (a few boxes/cylinders in `params.json`) for everyday
  interference checks — re-measure the envelope when the product model changes,
  and check big changes against the real B-rep, not only the envelope.

## 2. Design rules for FDM — support-free by design

**Print orientation is part of the design.** Decide for every part how it lies
on the bed (flat wide face down; blocks "standing as installed" if that keeps
pockets open; frames flat, visible face up) and bake that orientation into the
export (route B: a per-part `print_rot`, possibly a function of the parameters).
Then walk through the part **in that orientation** before handing it over —
the user slices every part and inspects it layer by layer; "needs supports" is a
design defect, not a slicer setting:

- **Overhangs ≥ 45° from horizontal.** A boss on a vertical wall is a horizontal
  cone → half-angle ≥ 45° (or a teardrop); its base must stay ≥ 0.5 mm inside
  the body face it sits near, so keep bosses short (thicker wall) rather than
  letting them break through a face.
- **No hole inside a bridge.** A ceiling spanning two cheeks is a bridge; a round
  hole in its middle leaves bridge lines with nothing to land on. Openings in a
  bridged wall must span the whole bridge (rectangular window from cheek to cheek,
  45° chamfers instead of round bells). Enable the slicer's bridge detection for
  10–15 mm bridges; a pocket ceiling may be lowered only if the moving part still
  clears.
- **Pockets through, or open upwards.** Two bearing pockets with a web between
  them = a bridge needing supports → one bearing per wheel, through pocket.
  Holes from below get 45° chamfers; use concave flares instead of straight
  ledges.
- **Horizontal pockets sag** ≈ 0.2–0.4 mm in the print — add radial clearance for
  anything that must turn inside one.
- **No plastic without function.** Geometry that only adds material (webs,
  decorative fills) is rejected too.
- **Surface defects are defects.** The user also looks at the surfaces in a 3D
  viewer: a feature fused onto a filleted edge leaves a "tooth"; a fuse overlap
  that shifts a visible face leaves a step. See the B-rep rules in section 7.
- **Elephant foot** squeezes first-layer holes: slicer setting, or bump the
  affected diameter by 0.1 mm.

Other FDM rules:

- **Walls:** at least 2 nozzle perimeters (0.8 mm at 0.4), ≥ 2 mm between pockets,
  ≥ 3 mm pocket to edge. After generation **print the thinnest wall as a number**
  and check it. Walls under a groove or around a bearing pocket: ≥ 1.5 mm.
- **Engraving:** depth 2–3 layers (0.4–0.6 mm at 0.2); letter stroke ≥ 2 nozzles.
  For small text thicken the outline with `buffer(+0.1…0.15 mm)`; if a word doesn't
  fit, reduce cap height, not the margin. Text on the **bottom face is mirrored**
  in X in the model so it reads when the part is flipped.
- **Pocket floors** flat; if weight/stability matters leave a recess for epoxy or a
  solid base — per the user's intent.
- **Design language:** an accessory repeats the silhouette and geometry of the
  object it is made for (same corner radius, same chamfers, same profile
  "character"); fonts for lettering match the object's style (geometric objects →
  geometric sans such as Century Gothic/Futura; Windows fonts are in
  `C:\Windows\Fonts`).
- **One part per file:** if two identical parts are needed, generate one and say
  "print twice"; a mirrored part is generated by mirroring the original, never
  hand-built.
- **Materials:** PETG (or ASA) for structural parts, 0.2 mm layers, 3 perimeters,
  40 % infill; wheels/rollers 100 % or ≥ 60 %; TPU only for sliding bushings.
  Infill lowers effective permittivity and absorbs moisture — matters for RF parts.

## 3. Assemblability — zero interference is not enough

An interference/boolean check only proves parts don't overlap in their final
position. It says nothing about how a captive part gets there. For **every captive
part** (wheel, bearing, bushing, nut, screw):

- state the **insertion path**: an opening at least as large as the part along a
  straight line (a wheel Ø18 cannot enter a pocket whose face window is 15 mm —
  this exact mistake passed every interference check);
- state the **assembly order** and check the **fastener is reachable** with the
  neighbours already mounted (counterbores not hidden behind tabs, nut slots open
  to a face, screw heads not under a module);
- never close a slot that a part enters sideways;
- say it explicitly in the answer/report whenever a geometry change touches an
  insertion path — the user reads the models closely and expects this reasoning.

## 4. Fits, clearances and the fit-test coupon

- Default clearances: "snug but removable" seat — **+0.8 mm on diameter** (0.4 per
  side); 1.5 mm on diameter was judged "rattles". Free fit 1.0–1.2 mm. If the
  object is conical/flared, measure the diameter at the height where it touches
  the pocket.
- Reference PETG results from one well-tuned printer (re-measure on yours):
  M3 clearance bore that spins freely Ø3.2; self-tapping M3 hole Ø2.8; hex nut
  pocket = nominal across-flats + 0 (light press); 623 bearing (3×10×4) is a firm
  press in a Ø10.0 pocket (pocket = OD + 0.0).
- **Fit-test coupon** — a small plate with rows of holes/pockets bracketing each
  critical fit, printed **first on any new printer or material** and whenever
  either changes. Rows from a notched corner upwards, values increasing left→right,
  legend in the report:
  1. clearance holes (e.g. Ø3.0–3.6 for M3) → smallest that lets the screw spin
     freely = rotating bore; the one that is a light slide = clearance hole;
  2. tap holes (Ø2.4–2.8 for M3) → the one the screw self-taps firmly without
     cracking;
  3. larger bolts if used (Ø4.8–5.4 for M5);
  4. hex nut pockets (AF nominal / +0.2 / +0.4) → light press fit;
  5. bearing pockets (OD −0.1 … +0.2) → firm press on the outer ring by hand, no
     hammer.
  Write the chosen values into `params.json` with the date, printer and material;
  everything else derives from them. Rebuild and print the real parts only after
  the coupon.
- **Fit wording decides the sign.** "Вільно/loose" vs "туго/tight" flips the sign
  of a clearance correction; a fit was once reported loose, then corrected to a
  firm press. Confirm before changing a clearance parameter.
- After a test print ask what rattled / didn't fit and change **a parameter**, not
  the geometry by hand; keep parameter versions in `PARAMS`/`params.json` so size
  variants live in one script with an argument.

## 5. Bearings, wheels and rolling guides

- **One bearing per wheel**, through pocket, wheel width = bearing width
  (anything wider needs a floor that the inner ring would rub on).
- **Bearing interface rule:** nothing that turns with the wheel may touch the inner
  ring; nothing fixed may touch the outer ring. Locate the inner ring with cone
  bosses on the fixed cheeks (tip Ø ≤ inner-ring Ø ≈ bore + 2.2, half-angle ≥ 45°
  for printability, 0.1 mm to the ring each side). If the wheel is inserted
  sideways the ring is *located* between the boss tips, not clamped — the screw
  cannot pull the cheeks together; say so if someone expects a clamped ring (true
  clamping needs separate cone spacers).
- A plain Ø3.2 bore on an M3 screw has ≈ 0.2–0.3 mm radial play; bearings remove
  it.
- **Thin cord between two grooved wheels:** the two grooves must form a closed
  channel — rim gap = cord Ø − 2·pinch − 2·groove depth ≪ cord Ø and ≥ 0.2 (touching
  rims roll on each other like external gears); groove chord ≥ width of the pinched
  cord, or the cord bulges over the groove edge into the gap and jams. Oversized
  grooves (sized for a Ø8 rope) let a Ø2 cord escape and wedge in the 1.4 mm rim
  gap. Keep a groove flank ≥ 1.5 mm on plain wheels (≥ 0.8 is the minimum on a
  4 mm wheel over a through pocket).
- Pinch between opposing wheels: 0 = wheels just touch the cord; raise it for grip,
  watching the rim gap; lower it if the carriage binds or the cord is hard to
  thread.

## 6. Route A — generating a mesh without a mesh library

Use `scripts/mesh_kit.py` (or its patterns). Key invariants that guarantee a
watertight result:

1. **Every triangle through `tri(a, b, c, want)`**: the winding is flipped so the
   normal has a positive dot product with `want` (any vector "outwards from the
   body" near that face). For cones/flares add a vertical component to `want` so
   it is not perpendicular to the face.
2. **Round all coordinates to 5 decimals** in one place (`R()`) so shared vertices
   of walls and flat faces coincide bit-for-bit.
3. **Flat faces with holes** (top with pockets, bottom with engraving) — `shapely`
   polygon minus holes, triangulated with `shapely.constrained_delaunay_triangles`
   (shapely ≥ 2.1): it **adds no vertices**, so ring vertices match the wall rings.
4. **Loft between rings** only with equal vertex counts; for rounded rectangles
   generate the ring as a function of inset with a fixed number of points per arc.
5. **Engraving = three parts:** remainder of the face, the "ceiling" of the recess
   at depth, and the recess walls with normals pointing into the cavity (test a
   point near the edge for being inside the contour).
6. **Text from a font** — `fontTools` pen → contours → polygons with even-odd fill
   (`symmetric_difference`), scale by cap height, slight tracking (~0.06 em) reads
   better engraved. **Logo** — from a single-contour SVG (VTracer) with an
   M/L/H/V/C/Q/Z command parser, Y flipped.
7. **STL write** — binary, normals computed from the winding. File starts at z = 0.

Environment: `fonttools`, `shapely>=2.1`, `numpy` are usually not installed
system-wide — create a venv in the scratchpad, don't install into the system. Put
the generator script in the project next to its output; temp files in the
scratchpad. Run `python -I` when reading foreign files.

## 7. Route B — parametric B-rep generator (FreeCAD)

Layout that has proven itself for multi-part printed mechanisms:

- `params.json` — **every** dimension in mm, grouped (`rope`, `wheel`, `block`,
  `frame`, `screw`, `module` envelope, `fit_test` rows, `parts` on/off); a
  `variants` dict of **nested override dicts** (`basic` {}, `bearing` {…}, …), each
  building into its own output folder.
- `parts.py` — `derive(P) → D` computes every derived number (widths, hole
  positions, gaps) in one place and **raises `ValueError` naming the parameter to
  change** when an invariant is violated (overhang half-angle < 45°, wall under a
  pocket < 1.5 mm, rim gap < 0.2, a boss base breaking through a face, an axle hole
  cutting a tab, a bracket wider than the gap it sits in, a feature only valid with
  a certain station type). Printability constraints go here so they cannot regress.
  One `build_<name>(P, D)` per part; a `PARTS` registry (builder, qty, material,
  `print_rot`, colour, notes) and a `PRINT_ORDER`.
- `lib.py` — B-rep helpers, export via an ASCII temp path, tessellation checks.
- `render.py` — z-buffer PNG previews (numpy + PIL ship with FreeCAD) with feature
  edges: iso/front/right/top per part, assembly, assembly with ropes/hardware.
- `main.py` + `run.cmd`/`run.sh` — CLI: `build [--variant=X|all]`, `part NAME`,
  `fit` (coupon only), `preview`, `params` (effective params + derived JSON);
  dotted CLI overrides (`wheel.od=20 block.station=bushing`) on top of a variant;
  `--out`, `--tag`, `--no-preview`, `--no-step`. Exit 0 only when
  `geometry problems: none; interferences: 0`; 1 = invalid part or interference,
  2 = usage, 3 = exception (traceback also in the build log).
- Outputs per variant: `<part>.step` **in print orientation on z = 0** (the user
  slices STEP directly; STL export optional — the mesh sanity check still runs on an
  in-memory tessellation), `assembly.step`/`.FCStd` in assembly orientation,
  `preview/*.png`, a human-language build report (key/derived dimensions, part
  table with qty/material/size/volume/mass, print settings, hardware BOM,
  interference table, tessellation checks, coupon legend), `params_used.json`, the
  build log. Nothing else belongs in the output folder; never hand-edit it.

B-rep modelling rules:

- Every builder returns **one valid closed solid**. Cut features slightly oversized
  (+0.01 … +1 mm) through faces to avoid coincident-face booleans.
- **Fused features must meet the body on a flat face or a sharp edge; fillet after
  the fuse.** A gusset fused onto an already-filleted edge leaves a tooth; a fuse
  overlap that shifts the slope line leaves a step. Un-round the edge, run the
  slope exactly through it (obtuse edge), then fillet that edge on its own.
- All mating hole positions of different parts come from the **same derived
  numbers** (`D["hole_x"]`, …) so they can never drift apart; a mirrored part is
  `mirror_x` of its twin.
- Assembly + **interference check** (`common` volume) for every pair that can
  collide; every pair must be 0 except named, expected contacts (e.g. wheel ×
  rope pinch), whose expected magnitude you state. Then reason about insertion
  paths (section 3) — the check cannot see them.
- **Reusing already printed parts:** when wheels/blocks change but the frame is
  printed, hold the derived dimensions the frame depends on (block width/height)
  by tuning secondary parameters (cheek thickness, clearances) and verify the
  frame STEP is identical by boolean difference (common = both volumes, A−B =
  B−A = 0). Always tell the user which STEP files changed, which must be
  reprinted, and which printed parts stay.
- Keep a **symptom → parameter table** in the project skill (wheel too tight →
  `bore_d`; rubs the cheeks → `axial_clear`; needs supports under a ceiling → slot
  window; …) and extend it after every test print.

FreeCAD gotchas:

- **Do not run `FreeCADCmd.exe script.py …` with non-ASCII paths on Windows**: it
  garbles argv ("Unknown exception while processing file") and runs scripts with
  `__name__ != "__main__"`. Run FreeCAD's own `bin\python.exe` and bootstrap
  `import FreeCAD` from the interpreter's folder / an env var (`FREECAD_BIN`) /
  standard install paths; on Linux/macOS fall back to `freecadcmd`. From
  PowerShell call `.\run.cmd`.
- FreeCAD's console codepage is cp1251/cp1252 and its stdout is unreliable:
  reconfigure stdout to UTF-8 or write results to a file.
- OCC writers choke on non-ASCII paths: export to an ASCII temp file, then move.
  Don't "simplify" that away.
- Table keys (bearing sizes) are strings; a CLI value `623` parses as a number —
  normalise in `derive()`, and raise on unknown keys.
- FreeCAD drops `.FCBak` backups next to `.FCStd` on save — disposable.
- Shared cloud-synced folders (Google Drive): set `sys.dont_write_bytecode = True`
  before imports and run ad-hoc Python with `-B` (no `__pycache__` syncing to
  collaborators); writers retry on the sync client's transient file locks; parallel
  builds are fine only into different output folders.
- Assembly previews with a pure-numpy rasteriser take ~10 s — `--no-preview` for
  quick numeric iterations.

## 8. Verification — mandatory before handing over a file

1. Own check in the script: every oriented edge exactly once and its reverse
   exactly once (`bad_edges == 0`), signed volume > 0; print size and volume. Route
   B: `valid`, `closed`, `solids = 1` per part, then the tessellation `solid = True`
   with no non-manifold/self-intersections; `derive()` raised nothing;
   interference table all `0.00` except the named contacts.
2. Independent check by a slicer: `prusa-slicer-console.exe --info <stl>` → expect
   `manifold = yes`, `number_of_parts = 1`. Or `stl_info.py <stl> --parts`.
3. Size ≤ bed − brim; seat diameters = measured + clearance (print a table
   "part → pocket diameter").
4. **Printability walk-through in print orientation** (section 2) and
   **insertion paths** (section 3) — stated in the answer, not assumed.
5. If non-manifold: typical causes — inconsistent vertex rounding, rings of
   different length, a triangulation that added vertices, a duplicate face on a
   shared edge, degenerate triangles (zero normal — skip them).

Report honestly: numbers from the check output, not "should be fine".

## 9. Previews and documentation

- Generate previews together with the model: top view with dimension lines and
  labels, a section, bottom view (already "flipped", as a person sees it), a
  simple shaded render (painter's algorithm or z-buffer: back-face culling, depth
  sort, Lambert shading). Read the PNGs after every geometry change. Labels in
  English if the file goes to Thingiverse/Printables; the build report in the
  collaborators' language.
- Rasterising SVG: take `width`/`height` from the SVG root and capture headless
  Edge/Chrome at exactly that size with `--force-device-scale-factor=2`, otherwise
  the field is empty; wait ~1 s after the call — the process returns before the
  file is written.
- Photos of the printed part on a busy background: cut out with `rembg` (u2net);
  brightness thresholds don't separate shadows from gloss.
- Slicer project files (`.3mf`) are **manual snapshots**: after a rebuild the
  STEP/STL must be re-imported by hand — say so, and name the current one.
- Remix of someone else's thing — honour the original licence (CC BY-NC → credit
  the author, thing-id, non-commercial); in the post: what, for what, print
  settings, what was measured, how to scale.

## 10. Working loop with the user

1. Measure and show a table of dimensions → agree clearances and layout (ASCII
   sketch of rows / assembly frame: which axis is across, towards the module, up).
2. Generate, check, show previews and numbers (size, thinnest wall, volume, mass
   at the chosen infill).
3. Print the fit coupon first on a new printer/material; then the parts.
4. After a test print or a trial run ask what rattled / rubbed / didn't go in /
   needed supports; map the symptom to a **parameter** (or a builder change if the
   topology is wrong), regenerate, re-check, and say what to reprint.
5. Decorative elements (logos, lettering) the user approved stay; don't offer a
   "clean version" unless asked. When the user specifies a form themselves (a
   sketch, a three-step description), implement their spec rather than an
   alternative.

## Environment pitfalls (Windows)

- Console cp1251: `print("Ø")` crashes — write `dia`. Paths with spaces and
  Cyrillic — always quoted.
- Don't rewrite scripts containing Cyrillic through PowerShell `Get-/Set-Content`
  (mojibake) and don't rely on bash heredocs to create files — use the Write/Edit
  tools.
- Slicers have CLIs: `prusa-slicer-console.exe`, `bambu-studio.exe`,
  `orca-slicer.exe` (`--help` for flags); PrusaSlicer `--info` is the handiest
  manifold check.
