"""List the faces of a solid that overhang in a given print orientation (FreeCAD >= 1.0).

    python.exe -B fc_overhang.py <model.FCStd|.step> --up 0,1,0 [--label Holder] [--limit 45]

--up     the MODEL direction that points up on the printer ("0,0,1" as modelled, "0,1,0" for a
         part printed standing on its -Y end)
--label  body / object label inside an FCStd (default: every PartDesign body and Part feature)
--limit  steepest allowed angle from the vertical, degrees (default 45). Faces designed at
         exactly 45 deg sit on the threshold: run with --limit 44 so they are not listed.

A face counts where its outward normal points down more steeply than the limit; the part
resting on the bed is skipped. The tool cannot tell a bridge (a ceiling held at both ends)
from a free overhang, and it does not know what the listed face carries: judge every row by
its size, its height above the bed and what sits on top of it. Typical harmless rows: ceilings
of small horizontal holes, the first ~1.4 mm of a rounding that is tangent to the bed.

As a module:  from fc_overhang import overhangs;  rows = overhangs(shape, (0, 1, 0), 45)
Self-test:    python.exe -B fc_overhang.py
"""
import os, sys, math, shutil, tempfile

sys.dont_write_bytecode = True
try:
    import FreeCAD
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fc_lib import FreeCAD
import Part  # noqa: E402


def overhangs(shape, up, limit=45.0, deflection=0.02):
    """[(area_mm2, face_no, surface_type, flattest_deg_from_horizontal, h_min, h_max, BoundBox)],
    largest first; heights are above the bed along `up`, the box is in model coordinates."""
    up = FreeCAD.Vector(*up); up.normalize()
    thr = -math.cos(math.radians(limit))
    meshes = [f.tessellate(deflection) for f in shape.Faces]
    bed = min(p.dot(up) for pts, _ in meshes for p in pts)      # not from Vertexes: a round bottom has none at its lowest point
    rows = []
    for i, f in enumerate(shape.Faces):
        pts, tris = meshes[i]
        area, worst, hmin, hmax, box = 0.0, 0.0, 1e9, -1e9, FreeCAD.BoundBox()
        for a, b, c in tris:
            pa, pb, pc = pts[a], pts[b], pts[c]
            cen = (pa + pb + pc) * (1.0 / 3)
            try:
                n = f.normalAt(*f.Surface.parameter(cen))
            except Exception:
                continue
            d = n.dot(up)
            if d >= thr:
                continue
            h = cen.dot(up) - bed
            if h < 0.02 and d < -0.999:          # lies on the bed
                continue
            area += (pb - pa).cross(pc - pa).Length / 2
            worst = min(worst, d); hmin, hmax = min(hmin, h), max(hmax, h)
            for p in (pa, pb, pc):
                box.add(p)
        if area > 0.01:
            rows.append((area, i + 1, type(f.Surface).__name__, math.degrees(math.acos(min(1.0, -worst))), hmin, hmax, box))
    return sorted(rows, key=lambda r: -r[0])


def print_rows(name, up, limit, rows):
    print("%s, up = (%g, %g, %g), limit %g deg from vertical: %d overhanging faces, %.1f mm2 in total" %
          (name, up[0], up[1], up[2], limit, len(rows), sum(r[0] for r in rows)))
    for area, i, t, flat, hmin, hmax, b in rows:
        print("  Face%-4d %-9s %7.2f mm2  flattest %4.1f deg from horizontal  height above bed %.1f-%.1f  x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f" %
              (i, t, area, flat, hmin, hmax, b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax))


def load(path, label=None):
    """[(name, shape)] from an FCStd (bodies / Part features, or the one with `label`) or a STEP file."""
    if path.lower().endswith((".step", ".stp")):
        tmp = os.path.join(tempfile.mkdtemp(prefix="fc_oh_"), "in.step")      # OCC readers and non-ASCII paths
        shutil.copyfile(path, tmp)
        s = Part.Shape(); s.read(tmp)
        return [(os.path.basename(path), s)]
    doc = FreeCAD.openDocument(path); doc.recompute()
    if label:
        return [(label, doc.getObjectsByLabel(label)[0].Shape)]
    inside = {f.Name for o in doc.Objects if o.TypeId == "PartDesign::Body" for f in o.Group}
    return [(o.Label, o.Shape) for o in doc.Objects
            if o.TypeId == "PartDesign::Body" or (o.isDerivedFrom("Part::Feature") and o.Name not in inside and not o.Shape.isNull() and o.Shape.Solids)]


def _selftest():
    V = FreeCAD.Vector
    blk = Part.makeBox(20, 20, 20)
    blk = blk.cut(Part.makeCylinder(3, 30, V(10, -5, 10), V(0, 1, 0)))                                  # horizontal hole: its ceiling overhangs
    ledge = Part.makeBox(8, 20, 3, V(20, 0, 12))                                                         # flat ledge on the side: overhang
    cham = Part.Face(Part.makePolygon([V(0, 0, 14), V(-6, 0, 20), V(0, 0, 20), V(0, 0, 14)])).extrude(V(0, 20, 0))   # 45 deg lean-out
    s = blk.fuse(ledge).fuse(cham).removeSplitter()
    assert s.isValid() and len(s.Solids) == 1
    r45, r44 = overhangs(s, (0, 0, 1), 45), overhangs(s, (0, 0, 1), 44)
    print_rows("selftest", (0, 0, 1), 44, r44)
    kinds = sorted((t, round(a)) for a, _, t, *_ in r44)
    assert ("Plane", 160) in kinds and any(t == "Cylinder" for t, _ in kinds), kinds                     # ledge underside 8 x 20, hole ceiling
    assert not any(abs(flat - 45) < 0.5 for _, _, _, flat, *_ in r44), "the 45 deg face must pass at limit 44"
    assert len(r45) >= len(r44)
    on_side = overhangs(s, (0, 1, 0), 44)                                                                # standing on the -Y end: prism, nothing hangs
    assert not on_side, on_side
    print("fc_overhang self-test OK")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        _selftest(); sys.exit(0)
    opt = {"--up": "0,0,1", "--label": None, "--limit": "45"}
    path = args[0]
    for k, v in zip(args[1::2], args[2::2]):
        assert k in opt, "unknown option %s" % k
        opt[k] = v
    up = tuple(float(c) for c in opt["--up"].split(","))
    for name, shape in load(path, opt["--label"]):
        print_rows(name, up, float(opt["--limit"]), overhangs(shape, up, float(opt["--limit"])))
