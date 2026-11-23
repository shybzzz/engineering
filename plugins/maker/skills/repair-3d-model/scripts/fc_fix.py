"""Check and repair received CAD / mesh files with FreeCAD (>= 1.0), headless.

Run with FreeCAD's own python (Windows: "C:\\Program Files\\FreeCAD 1.0\\bin\\python.exe" -B fc_fix.py ...):

    fc_fix.py check a.step b.step c.stl [--pairs] [--json out.json]   # full check per file (+ interference of every pair)
    fc_fix.py sew in.step out.step [--tol 1e-6] [--keep-facets]        # unsewn shell -> one closed solid
    fc_fix.py solid in.stl out.step [--tol 0.01]                       # watertight mesh -> solid (planar faces)
    fc_fix.py scale in.step out.step 1000                              # uniform scale about the origin
    fc_fix.py                                                          # self-test

As a module: full_check, mesh_check, read_shape, sew_to_solid, stl_to_solid, revolve, write_step, write_stl.
Paths may be non-ASCII: files are copied through an ASCII temp folder because the OCC readers / writers
and Mesh.Mesh() fail on such paths.
"""
import collections, glob, json, math, os, shutil, sys, tempfile

sys.dont_write_bytecode = True


def boot():
    try:
        import FreeCAD
        return FreeCAD
    except ImportError:
        pass
    cands = [os.environ.get("FREECAD_BIN"), os.path.dirname(sys.executable)] + glob.glob(r"C:\Program Files\FreeCAD*\bin")
    cands += glob.glob("/usr/lib/freecad*/lib") + glob.glob("/Applications/FreeCAD.app/Contents/Resources/lib")
    for c in cands:
        if c and os.path.isdir(c) and c not in sys.path:
            sys.path.insert(0, c)
            try:
                import FreeCAD
                return FreeCAD
            except ImportError:
                sys.path.remove(c)
    raise SystemExit("FreeCAD not importable: run with FreeCAD's python or set FREECAD_BIN to its bin folder")


FreeCAD = boot()
import Part  # noqa: E402

V = FreeCAD.Vector
_TMP = tempfile.mkdtemp(prefix="fc_fix_")


def _ascii_copy(path):
    dst = os.path.join(_TMP, "in_%d%s" % (len(os.listdir(_TMP)), os.path.splitext(path)[1].lower()))
    shutil.copyfile(path, dst)
    return dst


def _via_tmp(write, dst):
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    tmp = os.path.join(_TMP, "out_%d%s" % (len(os.listdir(_TMP)), os.path.splitext(dst)[1].lower()))
    write(tmp)
    shutil.move(tmp, dst)


# ------------------------------------------------------------------ checks
def full_check(s, name=""):
    """Everything that has to hold for a printable solid. isValid() alone is NOT enough: it is True for an
    open shell and for a self-intersecting one."""
    r = {"name": name, "type": s.ShapeType, "valid": bool(s.isValid()), "solids": len(s.Solids), "shells": len(s.Shells),
         "faces": len(s.Faces)}
    if not s.Faces:
        r.update({"ok": False, "problems": ["EMPTY: the kernel read no faces from this file (see mesh_probe.py for what is inside)"]})
        return r
    r["closed"] = all(sh.isClosed() for sh in s.Shells)
    # every edge must be used twice. Walk the wires: the seam of a revolved face is used twice by its own
    # wire, a degenerated edge (sphere pole, cone tip) by nobody else. Counting face.Edges calls seams "free".
    cnt = collections.Counter(e.hashCode() for f in s.Faces for w in f.Wires for e in w.OrderedEdges if not e.Degenerated)
    r["free_edges"] = sum(1 for v in cnt.values() if v == 1)
    r["surfaces"] = dict(collections.Counter(type(f.Surface).__name__ for f in s.Faces))
    try:
        s.check(True); r["check"] = "ok"
    except Exception as e:
        r["check"] = " ".join(str(e).split())[:240]
    r["volume"] = float("%.9g" % s.Volume)             # significant digits: a metre-scale model has a tiny volume
    pts = s.tessellate(0.01)[0]                       # BoundBox is loose on curved faces
    r["min"] = [round(min(getattr(p, a) for p in pts), 3) for a in "xyz"]
    r["max"] = [round(max(getattr(p, a) for p in pts), 3) for a in "xyz"]
    r["size"] = [round(r["max"][i] - r["min"][i], 3) for i in range(3)]
    pr = []
    if not r["valid"]: pr.append("isValid() is False")
    if r["solids"] != 1: pr.append("%d solids (a part must be exactly one)" % r["solids"])
    if not r["closed"]: pr.append("shell is open")
    if r["free_edges"]: pr.append("%d free edges (faces meet without sharing the edge)" % r["free_edges"])
    if r["check"] != "ok": pr.append("check(True): " + r["check"])
    if r["solids"] == 1 and s.Volume <= 0: pr.append("volume <= 0: solid is inside out")
    if abs(r["min"][2]) > 1e-3: pr.append("lowest point at z = %g, not on z = 0" % r["min"][2])
    planar = r["surfaces"].get("Plane", 0)
    if planar == r["faces"] and r["faces"] > 100: pr.append("all %d faces are planar: mesh-derived, circles are polygons" % r["faces"])
    if max(r["size"]) < 2.0: pr.append("largest size %.4g: wrong units? confirm one real dimension" % max(r["size"]))
    r["problems"] = pr
    r["ok"] = not [p for p in pr if not p.startswith(("lowest point", "all ", "largest size"))]
    return r


def mesh_check(mesh):
    """FreeCAD mesh report; the volume is summed in double precision (Mesh.Volume is single and is off by
    ~1e-4 of the volume on parts of a few hundred mm)."""
    pts, fac = mesh.Topology
    vol = 0.0
    for a, b, c in fac:
        pa, pb, pc = pts[a], pts[b], pts[c]
        vol += pa.dot(pb.cross(pc)) / 6.0
    bb = mesh.BoundBox
    return {"facets": mesh.CountFacets, "solid": bool(mesh.isSolid()), "non_manifold": bool(mesh.hasNonManifolds()),
            "self_intersections": bool(mesh.hasSelfIntersections()), "components": len(mesh.getSeparateComponents()),
            "volume": round(vol, 3), "min": [round(bb.XMin, 3), round(bb.YMin, 3), round(bb.ZMin, 3)],
            "max": [round(bb.XMax, 3), round(bb.YMax, 3), round(bb.ZMax, 3)]}


def interference(a, b):
    """Common volume of two shapes, from the Solids (the compound of touching parts can report a bogus box)."""
    try:
        return round(sum(x.Volume for x in a.common(b).Solids), 3)
    except Exception:
        return float("nan")


# ------------------------------------------------------------------ read / write
def read_shape(path):
    s = Part.Shape(); s.read(_ascii_copy(path))
    return s


def read_mesh(path):
    import Mesh
    return Mesh.Mesh(_ascii_copy(path))


def write_step(shape, dst):
    """Writes shape.exportStep (keeps baked transforms; Import.export drops the Placement of a single object)."""
    _via_tmp(lambda p: shape.exportStep(p), dst)


def write_stl(shape, dst, lin=0.01, ang=0.1):
    import MeshPart
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False)
    _via_tmp(lambda p: m.write(p, "STL"), dst)
    return m


# ------------------------------------------------------------------ repairs
def sew_to_solid(shape, tol=1e-6, merge_coplanar=True):
    """Faces that meet without sharing edges (the usual result of mesh -> shape -> 'convert to solid')
    -> one closed solid. tol in model units: start tiny, raise only until free_edges == 0."""
    s = shape.copy()
    s.sewShape(tol)
    shell = s.Shells[0] if len(s.Shells) == 1 else Part.Shell(s.Faces)
    solid = Part.Solid(shell)
    if solid.Volume < 0:
        solid.reverse()
    return solid.removeSplitter() if merge_coplanar else solid


def stl_to_solid(path, tol=0.01, merge_coplanar=True):
    m = read_mesh(path)
    s = Part.Shape(); s.makeShapeFromMesh(m.Topology, tol)
    return sew_to_solid(s, 1e-6, merge_coplanar)


def scaled(shape, factor):
    """Uniform scale about the origin. NOT transformGeometry(): that turns every plane into a B-spline
    surface and the result fails check(True)."""
    s = shape.copy()
    s.scale(factor)
    return s


def revolve(profile, axis="z"):
    """Solid of revolution from a closed half-profile [(r, h), ...] with optional rounded steps
    ("arc", (r_mid, h_mid), (r_end, h_end)); h runs along `axis`, the profile may touch the axis."""
    to3 = {"z": lambda r, h: V(r, 0, h), "x": lambda r, h: V(h, r, 0), "y": lambda r, h: V(0, h, r)}[axis]
    edges, cur, first = [], None, None
    for st in profile:
        if st[0] == "arc":
            mid, end = to3(*st[1]), to3(*st[2])
            edges.append(Part.Arc(cur, mid, end).toShape()); cur = end
        else:
            p = to3(*st)
            if cur is None: first = p
            elif (p - cur).Length > 1e-9: edges.append(Part.makeLine(cur, p))
            cur = p
    if (cur - first).Length > 1e-9:
        edges.append(Part.makeLine(cur, first))
    sol = Part.Face(Part.Wire(edges)).revolve(V(0, 0, 0), {"z": V(0, 0, 1), "x": V(1, 0, 0), "y": V(0, 1, 0)}[axis], 360)
    sol = sol if sol.ShapeType == "Solid" else Part.Solid(sol.Shells[0])
    if sol.Volume < 0:
        sol.reverse()
    return sol


def polygon_factor(n):
    """Volume (or area) of a body whose circles are n-gons inscribed in the true circles, over the true one."""
    return math.sin(2 * math.pi / n) / (2 * math.pi / n)


# ------------------------------------------------------------------ CLI
def _load_any(path):
    if path.lower().endswith(".stl"):
        m = read_mesh(path)
        return None, m
    return read_shape(path), None


def _cmd_check(args):
    pairs = "--pairs" in args; args = [a for a in args if a != "--pairs"]
    out = None
    if "--json" in args:
        i = args.index("--json"); out = args[i + 1]; del args[i:i + 2]
    rep, shapes = {"files": {}, "pairs": {}}, {}
    for f in args:
        name = os.path.basename(f)
        s, m = _load_any(f)
        if m is not None:
            r = mesh_check(m); r["ok"] = r["solid"] and not r["non_manifold"] and not r["self_intersections"] and r["components"] == 1
        else:
            r = full_check(s, name); shapes[name] = s
        rep["files"][name] = r
        print(("OK   " if r["ok"] else "FAIL ") + name, json.dumps({k: v for k, v in r.items() if k not in ("name", "problems", "ok")}))
        for p in r.get("problems", []):
            print("     -", p)
        sys.stdout.flush()
    if pairs:
        ks = [k for k in shapes if shapes[k].Solids]
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                v = interference(shapes[ks[i]], shapes[ks[j]])
                rep["pairs"]["%s x %s" % (ks[i], ks[j])] = v
                print("pair %s x %s: common volume %s" % (ks[i], ks[j], v))
    if out:
        json.dump(rep, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return 0 if all(r["ok"] for r in rep["files"].values()) else 1


def _report_fix(before, solid, dst):
    after = full_check(solid, os.path.basename(dst))
    write_step(solid, dst)
    back = full_check(read_shape(dst), "read back")
    print("before:", json.dumps({k: before.get(k) for k in ("type", "solids", "faces", "free_edges", "check", "volume", "size")}))
    print("after :", json.dumps({k: after.get(k) for k in ("type", "solids", "faces", "free_edges", "check", "volume", "size")}))
    print("file  :", json.dumps({k: back.get(k) for k in ("type", "solids", "faces", "free_edges", "check", "volume", "size")}))
    for p in back["problems"]:
        print("     -", p)
    return 0 if back["ok"] else 1


def _selftest():
    # 1. a box whose faces do not share edges -> sew
    box = Part.makeBox(30, 20, 10)
    loose = Part.makeCompound([f.copy() for f in box.Faces])
    r0 = full_check(loose, "loose faces")
    assert r0["solids"] == 0 and r0["free_edges"] == 24 and not r0["ok"], r0
    fixed = sew_to_solid(loose)
    r1 = full_check(fixed, "sewn")
    assert r1["ok"] and r1["free_edges"] == 0 and abs(r1["volume"] - 6000) < 1e-6, r1
    # 2. revolve with a rounded edge, a sphere-topped knob: seams and poles must not count as free edges
    k = 0.35 / math.sqrt(2)
    disc = revolve([(5.35, 0), (40, 0), (40, 12), (35, 12), (35, 6), (5.35, 6), ("arc", (5.35 - k, 6 - 0.35 + k), (5, 5.65)), (5, 0.35),
                    ("arc", (5.35 - k, 0.35 - k), (5.35, 0))])
    knob = revolve([(0, 0), (4, 0), (4, 5), ("arc", (8 * math.cos(0.5), 12 + 8 * math.sin(0.5)), (0, 20))])
    for name, s in (("disc", disc), ("knob", knob)):
        r = full_check(s, name)
        assert r["ok"] and r["free_edges"] == 0, r
    exact = math.pi * (40 ** 2 * 12 - 35 ** 2 * 6 - 5 ** 2 * 6)
    assert 0 < exact - disc.Volume < 3, (disc.Volume, exact)             # the two rounded edges take ~1.7 mm3
    # 3. files: STEP read back identical, STL solid, scale
    d = os.path.join(_TMP, "self"); p = os.path.join(d, "disc.step")
    write_step(disc, p)
    rb = full_check(read_shape(p), "read back")
    assert rb["ok"] and abs(rb["volume"] - disc.Volume) < 1e-3, rb
    m = write_stl(disc, os.path.join(d, "disc.stl"))
    mr = mesh_check(read_mesh(os.path.join(d, "disc.stl")))
    assert mr["solid"] and not mr["non_manifold"] and not mr["self_intersections"] and abs(mr["volume"] - disc.Volume) / disc.Volume < 2e-3, mr
    again = stl_to_solid(os.path.join(d, "disc.stl"), merge_coplanar=False)
    assert full_check(again)["ok"]
    big = scaled(box, 1000)
    assert full_check(big)["ok"] and abs(big.Volume - 6000e9) / 6000e9 < 1e-9
    assert interference(disc, knob) > 0 and interference(disc, box.translated(V(100, 0, 0))) == 0
    assert abs(polygon_factor(32) - 0.99359) < 1e-5
    print("fc_fix self-test OK ->", d)


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not a:
        _selftest(); sys.exit(0)
    cmd, a = a[0], a[1:]
    tol = None
    if "--tol" in a:
        i = a.index("--tol"); tol = float(a[i + 1]); del a[i:i + 2]
    keep = "--keep-facets" in a; a = [x for x in a if x != "--keep-facets"]
    if cmd == "check":
        sys.exit(_cmd_check(a))
    if cmd == "sew":
        s = read_shape(a[0]); sys.exit(_report_fix(full_check(s), sew_to_solid(s, tol or 1e-6, not keep), a[1]))
    if cmd == "solid":
        sys.exit(_report_fix({}, stl_to_solid(a[0], tol or 0.01, not keep), a[1]))
    if cmd == "scale":
        s = read_shape(a[0]); sys.exit(_report_fix(full_check(s), scaled(s, float(a[2])), a[1]))
    raise SystemExit(__doc__)
