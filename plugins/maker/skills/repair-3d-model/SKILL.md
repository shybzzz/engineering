---
name: repair-3d-model
description: Diagnose and repair a 3D model received from someone else (STEP / STL / 3MF made in Blender, a mesh converter, a chat assistant or CAD) so that it opens, is one valid closed solid and prints — a file that opens empty, a shell that is not a solid, non-manifold or self-intersecting geometry, a hole that is drawn but not cut, faceted "circles", wrong scale, parts not on the bed — without changing the author's design, and tell the author what went wrong. Use when the user says "fix this model", "the model has errors", "repair the STEP / STL", "why does it open empty", "FreeCAD shows a shell, not a solid", "the slicer says non-manifold / shows nothing", "convert this mesh to a real solid", "the model came in the wrong scale", "write up what was wrong so it does not happen again". Ukrainian triggers: «виправ помилки в моделі», «пофікси модель», «модель з помилками», «полагодь STEP / STL», «чому файл відкривається порожнім», «FreeCAD показує оболонку, а не тіло», «слайсер каже non-manifold», «зроби з сітки нормальне тіло», «модель не в тому масштабі», «поясни, що було не так, щоб більше так не робили».
---

# Repairing a received 3D model

Someone else made the model; your job is to hand back files that open everywhere, are valid solids
and print, **with the same design**. For designing new parts and for every printability rule use
`maker:printable-3d-model`; this skill covers what comes before: finding out what a broken file
really contains and choosing the repair.

Scripts next to this file (run them, do not re-derive them):

- `scripts/mesh_probe.py` — triage without a CAD kernel (stdlib only, `python -I`): STEP header
  (who wrote it, schema, units), entity census and a verdict on the file's kind; for faceted STEP
  and STL the triangle report (free / non-manifold / flipped edges, shells, **through holes**,
  volume, size, lowest z) and, for bodies of revolution, the axis, the segment count and the
  `(height, radius)` profile. `--stl` writes the triangles out, `--section x=0 out.png` draws a
  cut on a millimetre grid (needs PIL: run it with FreeCAD's python). Self-test: no arguments.
- `scripts/fc_fix.py` — FreeCAD ≥ 1.0 headless: `check` (the full B-rep / mesh check, `--pairs`
  for interference), `sew` (unsewn shell → solid), `solid` (watertight STL → solid), `scale`;
  as a module also `revolve(profile)`, `full_check`, `mesh_check`, `write_step`, `write_stl`.
  Self-test: no arguments. Run with FreeCAD's own `python.exe -B`.

## 0. Ground rules

- **Never modify what was received.** Copy it to an ASCII temp folder to work on; outputs get a
  suffix (`_fixed`) or their own folder next to the originals.
- **The design is not yours.** Keep every dimension, clearance and shape. Where the file
  contradicts itself (a hole that is half there) make the one reading the rest of the model
  supports, and list it as an interpretation with the parameter that undoes it. Printability
  problems of the design (overhangs, a part taller than the printer, needless mass) are
  **reported, not fixed**, unless the user asks.
- A repair is a script with a `PARAMS` block kept next to its output, not hand edits: the next
  correction is a changed number and a re-run.
- Project notes (CLAUDE.md, project skills) with known facts about the author's tools, the agreed
  scale or earlier repairs take precedence over the defaults here; write new findings back there.

## 1. Triage — find out what the file is before touching it

1. `python -I scripts/mesh_probe.py <files>` and read the verdict:

   | kind | what it is | next step |
   |---|---|---|
   | `brep` | real CAD geometry (cylinders, planes, …) | `fc_fix.py check` |
   | `mesh-derived-brep` | hundreds of planar faces: a mesh pushed through "shape from mesh → convert to solid" | `fc_fix.py check`; expect an open shell (section 3a) |
   | `faceted` / `faceted-no-surfaces` | a list of polygons written as STEP text, typically by a script or a chat assistant | the kernel may read **nothing**; work from the triangle report (3b / 3c) |
   | `stl` | a mesh | triangle report; `fc_fix.py check` for self-intersections |

2. `fc_fix.py check <files> [--pairs]` for everything the kernel can read. A file that gives
   `EMPTY` is not corrupt and not "still downloading" once its size is stable: look at its kind.
3. Confirm with the slicer, the program the file is for:
   `prusa-slicer-console --info <file>` (STEP and STL) — `number_of_facets = 0` is the same
   emptiness seen from the user's side.
4. Look at it: one section through the main axis (`--section`) of all parts together, and a
   close-up of every joint. Self-intersections and half-made holes are obvious in a section and
   invisible in a shaded view.
5. Write down what was **measured** (sizes, radii, clearances between mating parts, the position
   of each part) before repairing: the repaired files are checked against these numbers.

What the checks mean — do not stop at the first green light:

- `isValid()` is `True` for an open shell and for a self-intersecting one. Required: exactly one
  solid, closed shell, 0 free edges, `check(True)` passes.
- A closed, manifold mesh can still be wrong. Compare **through holes** (genus) with what the part
  should have: a tray with a hub hole must report 1; 0 means the hole's wall is capped somewhere.
  `mesh_check` → `self_intersections` and a section confirm it.
- Scale: a "millimetre" file whose model spans less than 2 units is in metres (mesh tools with a
  1 m default unit) or inches. Never guess the factor: find one dimension the user can confirm.
- Circles as n-gons: the vertex radius is the intended radius; the flats sit at `r·cos(π/n)`, the
  visible error is `r·(1 − cos(π/n))` (0.5 mm on a 220 mm disc with 32 segments), and the polygon
  body has `sin(2π/n)/(2π/n)` of the true volume.

## 2. Symptom → cause → repair

| symptom | usual cause | repair |
|---|---|---|
| CAD and slicer open the STEP empty | faceted text STEP whose faces have no surface | triangles → rebuild (3b) or mesh repair (3c) |
| `Shell`, 0 solids, free edges in coincident pairs | mesh → shape conversion left the faces unsewn | sew (3a) |
| `check(True)` reports self-intersection | overlapping bodies fused by hand, or an unsewn shell | sew first; if it stays, find the place in a section and rebuild that feature |
| closed mesh, wrong number of through holes | a cylinder pushed into the body instead of a boolean cut; its cap may even stick out of the far side | cut the hole for real (rebuild, or boolean on the sewn solid) |
| everything 1000× (or 25.4×) too small | unit of the source program | `fc_fix.py scale` after the factor is confirmed |
| faceted rims, pins and holes that are polygons | default segment counts of the mesh program | rebuild as analytic geometry (3b) when the part is prismatic or a body of revolution |
| lowest point not at z = 0, parts floating in assembly position | exported as modelled | export each part in print orientation on z = 0, plus one assembly file |
| "flat" faces that wander by 0.05–0.1 mm, odd numbers like 110.251 | dragged by mouse, scaled by eye | flatten and round to 0.01 mm in the rebuild; say so |
| several shells, flipped normals, degenerate triangles in an STL | export of unjoined objects | mesh repair (3c); several shells may be intentional (print-in-place) — ask |

## 3. The three repairs

Choose by what the geometry **is**, not by what is quickest:

| the part is | repair | result |
|---|---|---|
| any shape, already a B-rep that only fails to close | 3a sew | same faces, one solid |
| a body of revolution, a prism, plates with holes — anything a few dimensions describe | 3b rebuild | true circles, a handful of faces, a STEP anyone can edit |
| organic / sculpted, or too intricate to re-dimension | 3c mesh repair | a clean mesh; stays faceted |

### 3a. Sew

`fc_fix.py sew in.step out.step` (`sewShape(tol)` → `Part.Solid` → `removeSplitter`). Start with
`--tol 1e-6` in model units and raise it only until `free_edges` is 0; a tolerance near the size
of real features welds things that were meant to be apart. The script prints before / after / the
file read back: volume and size must be unchanged. `--keep-facets` skips the merge of coplanar
triangles when the triangle count must stay.

### 3b. Rebuild from measurements

1. Take the profile from `mesh_probe.py` (`revolution.profile_height_radius_count`) or, for
   prisms, from sections; cluster values that differ by noise and round to 0.01 mm. Radii are the
   vertex radii.
2. Put the numbers in `PARAMS`, one group per part, in the part's own frame: print orientation,
   lowest face on z = 0. Small edge rounds present in the mesh (a hole edge flaring by a few
   tenths over a few steps) become arcs in the profile; steps below 0.1 mm that appear once are
   noise and are dropped.
3. Build with `fc_fix.revolve(profile)` (or booleans of primitives), one valid solid per part.
4. Prove it is the same part: size equal to the received one, volume × polygon factor within
   ~0.1 % of the received volume (a sphere made of few rings may differ by ~1 %), and every mating
   clearance equal to the measured one.
5. Assemble the rebuilt parts at the measured positions: common volume 0 for every pair, contacts
   named.

### 3c. Mesh repair

When the shape cannot be re-dimensioned: `mesh_probe.py --stl` rescues triangles from a faceted
STEP; then FreeCAD `Mesh` (`removeDuplicatedPoints`, `harmonizeNormals`, `fixSelfIntersections`,
`fillupHoles`) or the slicer's own repair, re-checking after each step. Defects that are design
intent gone wrong (a capped hole) are not a mesh-repair job: convert to a solid (`fc_fix.py solid`)
and cut the feature, or rebuild that part.

## 4. Verification — before handing anything over

1. `fc_fix.py check` on every **written** file, not on the in-memory shape: one solid, closed,
   0 free edges, `check(True)` ok, size and lowest z as intended.
2. STL of every print part: solid, no non-manifolds, no self-intersections, one component.
3. The slicer reads each file: `manifold = yes`, `number_of_parts = 1`, facets > 0.
4. `check --pairs` on the assembly positions: 0 everywhere except named contacts.
5. The same section as in the triage, now of the fixed parts, next to the received one.
6. The printer: if a slicer project (`.3mf`) is around, read bed size and nozzle from it and say
   whether each part fits (height too).

Report the numbers from these outputs. If a check fails, the file is not delivered as fixed.

## 5. Handing over

- What was wrong, as a table: defect → why it matters → what was done; then the interpretations
  made, the design remarks left untouched, and the list of files (which to print, which to edit).
- Mesh-derived results stay meshes: say when a "fixed" STEP is still made of triangles.
- **If the user wants the author to learn from it** (a note or a document for the person who made
  the model), write for that person, in their language and at their level, no code. The lessons
  that cover almost every case:
  1. STL stores triangles, STEP stores exact shapes; renaming or "converting" triangles into a
     STEP does not make CAD geometry. Send STL from a mesh program, STEP from a CAD program.
  2. Holes are cut (boolean difference, applied; the cutter sticks out on both sides), never
     pushed in as a separate body.
  3. Raise the segment count for anything round and large (≥ 128 for a 200 mm disc, ≥ 64 for a
     pin); or draw round parts in CAD as one revolved sketch.
  4. Type dimensions as numbers; apply all transforms and merge doubled vertices before export.
  5. One part per file, lying on z = 0 the way it prints, millimetres; name one control
     dimension in the message.
  6. Open the exported file itself in the slicer before sending: the part is visible, the size is
     right, no "non-manifold" warning, the first layer shows holes as holes.
  7. Send the source file of the program along with the exports.
  Start that note with what was right (scale, clearances, naming): it is feedback, not a verdict.

## Gotchas

- `freecadcmd script.py` runs the script and then waits in an interactive console; use FreeCAD's
  `bin/python.exe -B script.py` (or `freecadcmd -c "exec(open(...).read())" < /dev/null`).
- Open CASCADE readers / writers and `Mesh.Mesh(path)` fail on non-ASCII paths: go through an
  ASCII temp copy (the scripts do). Never name a script after a stdlib module (`inspect.py`).
- Count free edges over `face.Wires[*].OrderedEdges`, skipping `Degenerated`: `face.Edges`
  reports every seam of a revolved face as free.
- `Mesh.Volume` is single precision (off by ~1e-4 of the volume on 200 mm parts); sum in double.
- `transformGeometry` turns planes into B-splines and the result fails `check(True)`; scale with
  `shape.scale`.
- Reading and checking a mesh-derived STEP of a few thousand faces takes about a minute per
  step: allow a long timeout, run batches in the background.
- A file in a cloud-synced folder may still be downloading right after it appears: compare its
  size with the expected one before calling it broken.
