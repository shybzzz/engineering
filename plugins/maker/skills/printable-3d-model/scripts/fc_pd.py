"""PartDesign + Spreadsheet helpers for a generator of a NATIVE parametric FreeCAD document:
an FCStd the owner opens in the GUI and drives from the Spreadsheet (route C of the skill).
Copy next to your generator and `from fc_pd import *`.

The recipe: every dimension lives in the Spreadsheet (inputs on top, derived formulas below)
and every sketch vertex gets DistanceX / DistanceY from the sketch origin driven by a
spreadsheet expression, so sketches are fully constrained (DoF 0) and the whole model follows
the sheet. Expressions are written once, in spreadsheet syntax with bare aliases
("plate_w / 2"); ev() evaluates them numerically, fx() turns them into FreeCAD expressions.
Angles are in degrees and stored in the sheet with their unit ("20 deg"); min() / max() take
arguments separated by ";" as in FreeCAD.

    doc = start("Model", INPUTS, DERIVED)      # [(alias, value, comment)], [(alias, formula, comment)]
    B = body("Holder")
    sk, b = sketch(B, "PlateSketch", plane(B, "XY_Plane"))
    b.loop([("plate_w / 2", "-plate_l / 2"), ...])
    pad(B, "Plate", sk, "plate_t")
    report(B); save(doc, out_path)

Run with FreeCAD's own python.exe (-B) or with FreeCADCmd -c "...exec(open(...).read())".
Self-test: python.exe -B fc_pd.py
"""
import os, sys, re, math, shutil, tempfile

sys.dont_write_bytecode = True
try:
    import FreeCAD
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fc_lib import FreeCAD            # fc_lib.boot() finds the FreeCAD installation
import Part, Sketcher  # noqa: E402
from FreeCAD import Vector as V, Placement, Rotation  # noqa: E402

__all__ = ["P", "V", "Placement", "Rotation", "ev", "fx", "start", "body", "SB", "attach", "plane", "sketch", "check",
           "feature", "pad", "pocket", "groove", "tilted_plane", "slope_plane", "static_wires", "set_aliases",
           "problems", "report", "save"]

P = {}          # alias -> numeric value (angles in degrees)
doc = None      # set by start()
_FUN = {"cos": lambda d: math.cos(math.radians(d)), "sin": lambda d: math.sin(math.radians(d)),
        "tan": lambda d: math.tan(math.radians(d)), "sqrt": math.sqrt, "abs": abs, "min": min, "max": max}
_UNIT = re.compile(r"(?<=[0-9)])\s*(deg|mm)\b")


def ev(expr):
    """Numeric value of a spreadsheet-style expression with the current parameters."""
    return float(eval(_UNIT.sub("", str(expr)).replace("^", "**").replace(";", ","), dict(_FUN), P))


def fx(expr):
    """The same expression as a FreeCAD expression referring to the Spreadsheet."""
    return re.sub(r"[A-Za-z_][A-Za-z0-9_]*", lambda m: "Spreadsheet." + m.group(0) if m.group(0) in P else m.group(0), str(expr))


def start(name, inputs, derived, headers=("Parameter", "Value", "Description"), derived_title="Derived (formulas, do not edit)"):
    """New document with the Spreadsheet: inputs [(alias, value, comment)] on top, then the
    derived formulas [(alias, formula, comment)]. Fills P and returns the document. The sheet
    is checked against the Python evaluation, so ev() and FreeCAD can never disagree."""
    global doc
    P.clear()
    for a, v, _ in inputs:
        P[a] = float(str(v).split()[0])
    for a, f, _ in derived:
        P[a] = ev(f)
    doc = FreeCAD.newDocument(name)
    sheet = doc.addObject("Spreadsheet::Sheet", "Spreadsheet")
    for col, text in zip("ABC", headers):
        sheet.set(col + "1", text)
    row = 2
    for a, v, c in inputs:
        sheet.set("A%d" % row, a); sheet.set("B%d" % row, str(v)); sheet.setAlias("B%d" % row, a); sheet.set("C%d" % row, c); row += 1
    row += 1
    sheet.set("A%d" % row, derived_title); row += 1
    for a, f, c in derived:
        sheet.set("A%d" % row, a); sheet.set("B%d" % row, "=" + f); sheet.setAlias("B%d" % row, a); sheet.set("C%d" % row, c); row += 1
    doc.recompute()
    for a, _, _ in derived:
        v = sheet.get(a)
        assert abs(float(getattr(v, "Value", v)) - P[a]) < 1e-6, "sheet and ev() disagree on %s: %s vs %s" % (a, v, P[a])
    return doc


def body(name):
    return doc.addObject("PartDesign::Body", name)


class SB:
    """Sketch builder: every vertex gets DistanceX / DistanceY to the origin driven by a
    spreadsheet expression. The sign is decided when the generator runs (a constraint value
    cannot change sign later), a zero coordinate becomes PointOnObject on the axis."""

    def __init__(self, sk):
        self.sk = sk

    def _dist(self, kind, geo, pos, expr):
        v = ev(expr)
        if abs(v) < 1e-7:
            self.sk.addConstraint(Sketcher.Constraint("PointOnObject", geo, pos, -2 if kind == "DistanceX" else -1))
            return
        if v > 0:
            i = self.sk.addConstraint(Sketcher.Constraint(kind, -1, 1, geo, pos, v)); e = fx(expr)
        else:
            i = self.sk.addConstraint(Sketcher.Constraint(kind, geo, pos, -1, 1, -v)); e = "-(" + fx(expr) + ")"
        self.sk.setExpression("Constraints[%d]" % i, e)

    def fix(self, geo, pos, xe, ye):
        self._dist("DistanceX", geo, pos, xe); self._dist("DistanceY", geo, pos, ye)

    def loop(self, verts, segs=None):
        """Closed loop through verts [(x_expr, y_expr)]. segs[i] describes the piece from
        verts[i] to verts[i+1]: None = line, or (cx_expr, cy_expr, 'ccw'|'cw', lock[, r_expr])
        for an arc; lock 'r' fixes its radius (r_expr), 'x' / 'y' fixes that centre coordinate
        instead (use for half circles, where the radius alone is ill-conditioned)."""
        sk, n = self.sk, len(verts)
        pts = [(ev(x), ev(y)) for x, y in verts]
        ids = []
        for i in range(n):
            p, q = pts[i], pts[(i + 1) % n]
            s = segs[i] if segs else None
            if s is None:
                ids.append((sk.addGeometry(Part.LineSegment(V(p[0], p[1], 0), V(q[0], q[1], 0)), False), 1, 2))
                continue
            c = (ev(s[0]), ev(s[1]))
            r = math.hypot(p[0] - c[0], p[1] - c[1])
            ap, aq = math.atan2(p[1] - c[1], p[0] - c[0]), math.atan2(q[1] - c[1], q[0] - c[0])
            a1, a2, sp, ep = (ap, aq, 1, 2) if s[2] == "ccw" else (aq, ap, 2, 1)
            if a2 <= a1:
                a2 += 2 * math.pi
            g = sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(c[0], c[1], 0), V(0, 0, 1), r), a1, a2), False)
            ids.append((g, sp, ep))
            if s[3] == "r":
                j = sk.addConstraint(Sketcher.Constraint("Radius", g, r)); sk.setExpression("Constraints[%d]" % j, fx(s[4]))
            else:
                self._dist("DistanceX" if s[3] == "x" else "DistanceY", g, 3, s[0] if s[3] == "x" else s[1])
        for i in range(n):
            sk.addConstraint(Sketcher.Constraint("Coincident", ids[i][0], ids[i][2], ids[(i + 1) % n][0], ids[(i + 1) % n][1]))
        for i in range(n):
            self.fix(ids[i][0], ids[i][1], *verts[i])

    def circle(self, cxe, cye, de):
        g = self.sk.addGeometry(Part.Circle(V(ev(cxe), ev(cye), 0), V(0, 0, 1), ev(de) / 2), False)
        self.fix(g, 3, cxe, cye)
        j = self.sk.addConstraint(Sketcher.Constraint("Diameter", g, ev(de))); self.sk.setExpression("Constraints[%d]" % j, fx(de))

    def flared_hole(self, half, r, f):
        """Half profile (above the sketch H axis, which is the hole axis) of a through hole of
        radius r between faces at x = ±half, both mouths rounded by radius f. Cut it with groove()."""
        o, i_, rf = "(%s) + 1" % half, "(%s) - (%s)" % (half, f), "(%s) + (%s)" % (r, f)
        neg = lambda e: "-(%s)" % e
        self.loop([(neg(o), "0"), (o, "0"), (o, rf), (half, rf), (i_, r), (neg(i_), r), (neg(half), rf), (neg(o), rf)],
                  [None, None, None, (i_, rf, "cw", "r", f), None, (neg(i_), rf, "cw", "r", f), None, None])

    def arrow(self, tail, length, head, width, shaft):
        """Outline of an arrow that points along sketch +y and is symmetric about the sketch
        V axis: tail end at y = tail, tip at y = tail + length, head of the given length and
        width, shaft of the given width (an insertion-direction mark, pocketed 0.5 mm deep)."""
        y1, y2 = "(%s) + (%s) - (%s)" % (tail, length, head), "(%s) + (%s)" % (tail, length)
        hs, hw = "(%s) / 2" % shaft, "(%s) / 2" % width
        neg = lambda e: "-(%s)" % e
        self.loop([(neg(hs), tail), (hs, tail), (hs, y1), (hw, y1), ("0", y2), (neg(hw), y1), (neg(hs), y1)])

    def rounded_rim(self, half, r, f):
        """Two profiles (above the sketch H axis, which is the axis of a disc of radius r
        between faces at x = ±half) of the material to remove so that both outer edges of the
        disc get rounded by radius f. Cut it with groove(); a partial angle rounds only an arc."""
        i_, o, ri, ro = "(%s) - (%s)" % (half, f), "(%s) + 1" % half, "(%s) - (%s)" % (r, f), "(%s) + 1" % r
        neg = lambda e: "-(%s)" % e
        self.loop([(i_, r), (i_, ro), (o, ro), (o, ri), (half, ri)], [None, None, None, None, (i_, ri, "ccw", "r", f)])
        self.loop([(neg(i_), r), (neg(i_), ro), (neg(o), ro), (neg(o), ri), (neg(half), ri)], [None, None, None, None, (neg(i_), ri, "cw", "r", f)])


def attach(obj, support, offset=None, exprs=()):
    """Attach a sketch / datum plane flat onto `support`; exprs = [("Base.z", "expr"), ("Rotation.Angle", "expr")]
    bind the attachment offset to the Spreadsheet."""
    setattr(obj, "AttachmentSupport" if hasattr(obj, "AttachmentSupport") else "Support", [(support, "")])
    obj.MapMode = "FlatFace"
    if offset is not None:
        obj.AttachmentOffset = offset
    for prop, e in exprs:
        obj.setExpression("AttachmentOffset." + prop, fx(e))


def plane(b, role):
    """Origin plane of a body: 'XY_Plane' (sketch x = X, y = Y), 'XZ_Plane' (x = X, y = Z,
    normal -Y), 'YZ_Plane' (x = Y, y = Z)."""
    return [f for f in b.Origin.OriginFeatures if f.Role == role][0]


def sketch(b, name, support, offset=None, exprs=()):
    sk = b.newObject("Sketcher::SketchObject", name)
    attach(sk, support, offset, exprs)
    return sk, SB(sk)


def check(sk):
    """The sketch must solve and be fully constrained (solve() returns the DoF left)."""
    doc.recompute()
    code = sk.solve()
    print("  sketch %-14s solve=%s geo=%d constraints=%d" % (sk.Name, code, sk.GeometryCount, sk.ConstraintCount))
    assert code == 0, "sketch %s: solve() = %s (> 0: DoF left, < 0: conflicting / redundant)" % (sk.Name, code)


def feature(b, kind, name, sk, grow, **props):
    """Add a Pad / Pocket and pick the direction (Reversed) that really adds / removes material.
    props are feature properties (Type, Length, Length2, Midplane, ...); exprs={"Length": "expr"}."""
    check(sk)
    before = b.Shape.Volume if b.Tip is not None and not b.Shape.isNull() else 0.0
    f = b.newObject("PartDesign::" + kind, name)
    f.Profile = sk
    exprs = props.pop("exprs", {})
    for k, v in props.items():
        setattr(f, k, v)
    for k, e in exprs.items():
        f.setExpression(k, fx(e))
    best = None
    for rev in (False, True):
        f.Reversed = rev
        doc.recompute()
        if f.isValid() and not f.Shape.isNull():
            d = f.Shape.Volume - before
            if (d > 1e-6) if grow else (d < -1e-6):
                if best is None or abs(d) > abs(best[1]):
                    best = (rev, d)
        if props.get("Midplane"):
            break
    assert best is not None, "%s %s does not change the solid" % (kind, name)
    f.Reversed = best[0]
    doc.recompute()
    assert f.isValid() and f.Shape.isValid() and len(f.Shape.Solids) == 1, name
    print("  %-7s %-13s reversed=%-5s dV=%+9.2f -> V=%.2f" % (kind, name, best[0], best[1], f.Shape.Volume))
    return f


def pad(b, name, sk, length, **props):
    """Pad by a spreadsheet expression; Midplane=True for a symmetric one."""
    return feature(b, "Pad", name, sk, True, Length=ev(length), exprs={"Length": length}, **props)


def pocket(b, name, sk, depth=None, extra=None, **props):
    """Pocket: through all (depth None), by an expression, or by an expression plus a fixed
    `extra` mm the other way (TwoLengths) - use the extra when the cut would otherwise end
    exactly on an existing face or edge."""
    if depth is None:
        return feature(b, "Pocket", name, sk, False, Type="ThroughAll", **props)
    if extra:
        return feature(b, "Pocket", name, sk, False, Type="TwoLengths", Length=ev(depth), Length2=float(extra), exprs={"Length": depth}, **props)
    return feature(b, "Pocket", name, sk, False, Type="Length", Length=ev(depth), exprs={"Length": depth}, **props)


def groove(b, name, sk, angle=None):
    """Revolved cut about the sketch H axis: the full turn, or `angle` (an expression in
    degrees, e.g. "270 deg - angle") symmetric about the sketch plane."""
    check(sk)
    before = b.Shape.Volume
    g = b.newObject("PartDesign::Groove", name)
    g.Profile = sk
    g.ReferenceAxis = (sk, ["H_Axis"])
    if angle is None:
        g.Angle = 360.0
    else:
        g.Angle = ev(angle); g.Midplane = True
        g.setExpression("Angle", fx(angle))
    doc.recompute()
    assert g.isValid() and g.Shape.isValid() and len(g.Shape.Solids) == 1 and g.Shape.Volume < before, name
    print("  Groove  %-13s dV=%+9.2f -> V=%.2f" % (name, g.Shape.Volume - before, g.Shape.Volume))
    return g


def _uw(angle):
    c, s = math.cos(math.radians(ev(angle))), math.sin(math.radians(ev(angle)))
    return V(0, c, s), V(0, -s, c)


def tilted_plane(b, name, angle):
    """Datum plane = the YZ plane turned by `angle` (expression) about the X axis: sketch
    x = u (up a slope that rises towards +Y, global (0, cos, sin)), sketch y = w (the slope
    normal, (0, -sin, cos)). Draw side profiles of inclined features in it."""
    pl = b.newObject("PartDesign::Plane", name)
    attach(pl, plane(b, "YZ_Plane"), Placement(V(0, 0, 0), Rotation(V(0, 0, 1), ev(angle))), [("Rotation.Angle", angle)])
    doc.recompute()
    u, w = _uw(angle)
    r = pl.Placement.Rotation
    assert (r.multVec(V(1, 0, 0)) - u).Length < 1e-6 and (r.multVec(V(0, 1, 0)) - w).Length < 1e-6, "%s axes are not (u, w)" % name
    return pl


def slope_plane(b, name, angle, w):
    """Datum plane parallel to the same slope at the distance `w` (expression) along its
    normal: sketch x = X, sketch y = u, plane normal = w. For features on / under a sloped face."""
    pl = b.newObject("PartDesign::Plane", name)
    u, wv = _uw(angle)
    attach(pl, plane(b, "XY_Plane"), Placement(wv * ev(w), Rotation(V(1, 0, 0), ev(angle))),
           [("Base.y", "-(%s) * sin(%s)" % (w, angle)), ("Base.z", "(%s) * cos(%s)" % (w, angle)), ("Rotation.Angle", angle)])
    doc.recompute()
    m = pl.Placement
    assert (m.Rotation.multVec(V(1, 0, 0)) - V(1, 0, 0)).Length < 1e-6 and (m.Rotation.multVec(V(0, 1, 0)) - u).Length < 1e-6 \
        and abs(m.Base.dot(wv) - ev(w)) < 1e-6 and abs(m.Base.dot(u)) < 1e-6, "%s is not the plane w = %s" % (name, w)
    return pl


def static_wires(sk, wires, to2d):
    """Copy the edges of `wires` into the sketch as frozen (Block) geometry: lettering or a
    logo outline taken from another model, so the document depends on no font. to2d maps a
    3D point to sketch (x, y). Size and position are then baked in; move the word with the
    sketch's attachment offset."""
    n = 0
    for w in wires:
        for e in w.OrderedEdges:
            c = e.Curve
            if type(c).__name__ == "Line":
                p, q = to2d(e.valueAt(e.FirstParameter)), to2d(e.valueAt(e.LastParameter))
                sk.addGeometry(Part.LineSegment(V(p[0], p[1], 0), V(q[0], q[1], 0)), False)
            else:
                bs = c.toBSpline(e.FirstParameter, e.LastParameter)
                nb = Part.BSplineCurve()
                nb.buildFromPolesMultsKnots([V(*to2d(p), 0) for p in bs.getPoles()], bs.getMultiplicities(), bs.getKnots(), False, bs.Degree, bs.getWeights())
                sk.addGeometry(nb, False)
            n += 1
    for g in range(sk.GeometryCount):
        sk.addConstraint(Sketcher.Constraint("Block", g))
    doc.recompute()
    return n


def _is_formula(contents):
    c = str(contents)
    if not c.startswith("="):
        return False
    try:
        FreeCAD.Units.Quantity(c[1:])       # a quantity input reads back as "=20 deg"
        return False
    except Exception:
        return True


def set_aliases(d, overrides):
    """Write new values into input cells by alias ({"angle": "20 deg", "wall": 2.5}) and
    recompute - what the owner does in the GUI. Use it to test parameter variants."""
    sheet = d.getObject("Spreadsheet")
    for a, v in overrides.items():
        cell = sheet.getCellFromAlias(a)
        assert cell, "no alias %s in the Spreadsheet" % a
        assert not _is_formula(sheet.getContents(cell)), "%s is a derived formula, not an input" % a
        sheet.set(cell, str(v))
    d.recompute()


def problems(d):
    """What is wrong with the document after a recompute: objects in an error state, sketches
    that no longer solve, bodies that are invalid or not exactly one solid. [] = fine."""
    out = []
    for o in d.Objects:
        if not o.isValid():
            out.append("%s: invalid" % o.Name)
        elif o.TypeId == "Sketcher::SketchObject" and o.solve() != 0:
            out.append("%s: sketch solve() = %s" % (o.Name, o.solve()))
        elif o.TypeId == "PartDesign::Body" and (o.Shape.isNull() or not o.Shape.isValid() or len(o.Shape.Solids) != 1):
            out.append("%s: body is not one valid solid" % o.Label)
    return out


def report(*bodies):
    """Final recompute, validity check of every object and a one-line summary per body."""
    doc.recompute()
    bad = problems(doc)
    assert not bad, "problems: %s" % bad
    for b in bodies:
        s = b.Shape; bb = s.BoundBox
        print("%s: valid=%s solids=%d volume=%.1f mm3 bbox x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f" %
              (b.Label, s.isValid(), len(s.Solids), s.Volume, bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))


def save(d, dst):
    """Save through an ASCII temp file and copy over `dst`: works with non-ASCII folders and
    leaves no .FCBak next to an existing file."""
    tmp = os.path.join(tempfile.mkdtemp(prefix="fc_pd_"), "model.FCStd")
    d.saveAs(tmp)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    shutil.copyfile(tmp, dst)
    return dst


if __name__ == "__main__":
    INPUTS = [("plate_w", 30, "plate width (X)"), ("plate_l", 44, "plate length (Y)"), ("plate_t", 4, "plate thickness"),
              ("plate_r", 4, "corner radius"), ("angle", "20 deg", "slope of the wedge"), ("y_lo", -14, "foot of the slope (signed Y)"),
              ("y_hi", 10, "front face of the wedge (signed Y)"), ("block_w", 12, "wedge width"), ("hole_d", 3, "cross hole"),
              ("hole_y", 5, "cross hole position"), ("hole_up", 3, "cross hole axis above the plate"), ("hole_round", 0.5, "rounding of the hole mouths"),
              ("arrow_len", 8, ""), ("arrow_head", 3.5, ""), ("arrow_w", 4.6, ""), ("arrow_shaft", 1.7, ""), ("arrow_depth", 0.5, "")]
    DERIVED = [("z_hi", "plate_t + (y_hi - y_lo) * tan(angle)", "crest height"),
               ("w_top", "plate_t * cos(angle) - y_lo * sin(angle)", "slope face along its normal"),
               ("u_lo", "y_lo * cos(angle) + plate_t * sin(angle)", "foot of the slope along the slope"),
               ("x_max", "max(plate_w; block_w) / 2", "widest half width")]
    d = start("fc_pd_demo", INPUTS, DERIVED)
    B = body("Holder")
    sk, b = sketch(B, "PlateSketch", plane(B, "XY_Plane"))
    hw, hl, r = "plate_w / 2", "plate_l / 2", "plate_r"
    xi, yi = "plate_w / 2 - plate_r", "plate_l / 2 - plate_r"
    n = lambda e: "-(%s)" % e
    b.loop([(xi, n(hl)), (hw, n(yi)), (hw, yi), (xi, hl), (n(xi), hl), (n(hw), yi), (n(hw), n(yi)), (n(xi), n(hl))],
           [(xi, n(yi), "ccw", "r", r), None, (xi, yi, "ccw", "r", r), None, (n(xi), yi, "ccw", "r", r), None, (n(xi), n(yi), "ccw", "r", r), None])
    pad(B, "Plate", sk, "plate_t")
    sk, b = sketch(B, "WedgeSketch", plane(B, "YZ_Plane"))          # dips 1 mm into the plate: no zero-thickness cusp
    b.loop([("y_lo", "plate_t - 1"), ("y_hi", "plate_t - 1"), ("y_hi", "z_hi"), ("y_lo", "plate_t")])
    pad(B, "Wedge", sk, "block_w", Midplane=True)
    sk, b = sketch(B, "ArrowSketch", slope_plane(B, "SlopeTop", "angle", "w_top"))
    b.arrow("u_lo + 3", "arrow_len", "arrow_head", "arrow_w", "arrow_shaft")
    pocket(B, "Arrow", sk, "arrow_depth")
    sk, b = sketch(B, "HoleSketch", plane(B, "XY_Plane"), Placement(V(0, P["hole_y"], P["plate_t"] + P["hole_up"]), Rotation()),
                   [("Base.y", "hole_y"), ("Base.z", "plate_t + hole_up")])
    b.flared_hole("block_w / 2", "hole_d / 2", "hole_round")
    groove(B, "CrossHole", sk)
    side = tilted_plane(B, "SlopeSide", "angle")
    sk, b = sketch(B, "NotchSketch", side)
    b.loop([("u_lo + 14", "w_top - 1.5"), ("u_lo + 18", "w_top - 1.5"), ("u_lo + 18", "w_top + 1"), ("u_lo + 14", "w_top + 1")])
    pocket(B, "Notch", sk, None, Midplane=True)
    report(B)
    v0 = B.Shape.Volume
    for over in ({"angle": "30 deg"}, {"plate_t": 6, "block_w": 16}, {"y_lo": -18, "arrow_len": 6, "arrow_head": 3}):
        set_aliases(d, over)
        bad = problems(d)
        print("variant %-45s -> V=%.1f %s" % (over, B.Shape.Volume, bad or "ok"))
        assert not bad and abs(B.Shape.Volume - v0) > 1
    try:
        set_aliases(d, {"z_hi": 20})
        raise SystemExit("a derived formula was overwritten")
    except AssertionError:
        pass
    out = save(d, os.path.join(tempfile.gettempdir(), "fc_pd_demo.FCStd"))
    FreeCAD.closeDocument(d.Name)
    d2 = FreeCAD.openDocument(out); d2.recompute()
    assert not problems(d2) and abs(float(d2.getObject("Spreadsheet").get("y_lo")) + 18) < 1e-9
    print("fc_pd self-test OK ->", out)
