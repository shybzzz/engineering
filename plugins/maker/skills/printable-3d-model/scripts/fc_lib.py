"""B-rep helpers for a FreeCAD (>= 1.0) headless generator: bootstrap, primitives, booleans,
checks and exports via ASCII temp paths. Copy next to your generator and `from fc_lib import *`.

Run with FreeCAD's own python.exe (Windows: "C:\\Program Files\\FreeCAD 1.0\\bin\\python.exe" -B main.py)
or set FREECAD_BIN. Self-test: python.exe -B fc_lib.py
"""
import os, sys, glob, json, math, shutil, tempfile

sys.dont_write_bytecode = True


def boot():
    """Make FreeCAD importable; returns the FreeCAD module."""
    try:
        import FreeCAD  # noqa: F401
        return FreeCAD
    except ImportError:
        pass
    cands = []
    if os.environ.get("FREECAD_BIN"):
        cands.append(os.environ["FREECAD_BIN"])
    cands.append(os.path.dirname(sys.executable))
    cands += glob.glob(r"C:\Program Files\FreeCAD*\bin")
    cands += glob.glob("/usr/lib/freecad*/lib") + glob.glob("/Applications/FreeCAD.app/Contents/Resources/lib")
    for c in cands:
        if c and os.path.isdir(c) and c not in sys.path:
            sys.path.insert(0, c)
            try:
                import FreeCAD  # noqa: F401
                return FreeCAD
            except ImportError:
                sys.path.remove(c)
    raise SystemExit("FreeCAD not importable: set FREECAD_BIN to FreeCAD's bin folder")


FreeCAD = boot()
import Part  # noqa: E402

V = FreeCAD.Vector
X, Y, Z = V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)


# ----------------------------------------------------------------- primitives
def box(x0, y0, z0, x1, y1, z1):
    """Axis-aligned box between two corners (any order)."""
    return Part.makeBox(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), V(min(x0, x1), min(y0, y1), min(z0, z1)))


def cyl(r, h, p=(0, 0, 0), d=Z):
    return Part.makeCylinder(r, h, V(*p), d)


def cone(r1, r2, h, p=(0, 0, 0), d=Z):
    return Part.makeCone(r1, r2, h, V(*p), d)


def prism(pts, z0, z1):
    """Extrude a closed polygon given in the XY plane (list of (x, y)) from z0 to z1 along Z."""
    vs = [V(x, y, z0) for x, y in pts] + [V(pts[0][0], pts[0][1], z0)]
    return Part.Face(Part.makePolygon(vs)).extrude(V(0, 0, z1 - z0))


def prism_yz(pts, x0, x1):
    """Extrude a closed polygon given in the YZ plane (list of (y, z)) from x0 to x1 along X."""
    vs = [V(x0, y, z) for y, z in pts] + [V(x0, pts[0][0], pts[0][1])]
    return Part.Face(Part.makePolygon(vs)).extrude(V(x1 - x0, 0, 0))


def prism_xz(pts, y0, y1):
    """Extrude a closed polygon given in the XZ plane (list of (x, z)) from y0 to y1 along Y."""
    vs = [V(x, y0, z) for x, z in pts] + [V(pts[0][0], y0, pts[0][1])]
    return Part.Face(Part.makePolygon(vs)).extrude(V(0, y1 - y0, 0))


def loft_rect(bx0, by0, bx1, by1, tx0, ty0, tx1, ty1, z0, z1):
    """Ruled loft between a bottom and a top rectangle (a frustum). NOTE: the side faces come out as
    B-spline surfaces and OCC refuses fillets that run onto them - build a frustum from a box and
    planar wedge cuts (prism_xz / prism_yz) when edges on the slopes must be filleted."""
    def wire(x0, y0, x1, y1, z):
        return Part.makePolygon([V(x0, y0, z), V(x1, y0, z), V(x1, y1, z), V(x0, y1, z), V(x0, y0, z)])
    return Part.makeLoft([wire(bx0, by0, bx1, by1, z0), wire(tx0, ty0, tx1, ty1, z1)], True, True)


def round_end(r, x0, x1, y_axis, z_axis, toward):
    """Printable rounded end of a flat part that turns about an X-parallel axis (hinge knuckle, toe):
    semicircle on top, 45 deg chamfer below, everything inside radius r so it sweeps freely.
    `toward` = +1/-1: direction (in Y) in which the end protrudes from the axis."""
    c = cyl(r, x1 - x0, (x0, y_axis, z_axis), X)
    y_far = y_axis + toward * r
    c = c.cut(box(x0 - 1, min(y_axis, y_far) - 0.01, -1, x1 + 1, max(y_axis, y_far) + 0.01, z_axis))
    return c.fuse(prism_yz([(y_axis, z_axis - r), (y_far, z_axis), (y_axis, z_axis)], x0, x1))


def fuse(*shapes):
    s = shapes[0]
    for o in shapes[1:]:
        s = s.fuse(o)
    return s.removeSplitter()


def cut(s, *tools):
    for t in tools:
        s = s.cut(t)
    return s.removeSplitter()


def rot(shape, center, axis, deg):
    """Rotated copy; right-handed: +deg about +X tips +Y towards +Z."""
    s = shape.copy()
    s.rotate(V(*center), V(*axis), deg)
    return s


def move(shape, dx=0, dy=0, dz=0):
    s = shape.copy()
    s.translate(V(dx, dy, dz))
    return s


def mirror_x(shape):
    return shape.mirror(V(0, 0, 0), V(1, 0, 0))


# ----------------------------------------------------------------- checks
def shape_report(name, s):
    bb = s.BoundBox
    return {"name": name, "valid": bool(s.isValid()), "solids": len(s.Solids), "volume_mm3": round(s.Volume, 1),
            "size_mm": [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)],
            "bbox_min": [round(bb.XMin, 2), round(bb.YMin, 2), round(bb.ZMin, 2)],
            "bbox_max": [round(bb.XMax, 2), round(bb.YMax, 2), round(bb.ZMax, 2)]}


def mesh_of(shape, lin=0.04, ang=0.35):
    import MeshPart
    return MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False)


def mesh_report(mesh):
    return {"facets": mesh.CountFacets, "solid": bool(mesh.isSolid()), "non_manifold": bool(mesh.hasNonManifolds()),
            "self_intersections": bool(mesh.hasSelfIntersections()), "components": len(mesh.getSeparateComponents())}


def interference(a, b):
    """Common volume of two shapes (0 = no overlap). Touching / coplanar solids may give a valid compound
    with a bogus BoundBox: judge by the Solids' volumes, and shift one part by 0.05 mm to tell contact
    from overlap."""
    try:
        return round(a.common(b).Volume, 3)
    except Exception:
        return float("nan")


def min_distance(a, b):
    try:
        return round(a.distToShape(b)[0], 3)
    except Exception:
        return float("nan")


# ----------------------------------------------------------------- export (OCC writers choke on non-ASCII paths)
def _via_ascii_tmp(write, dst):
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(dst)[1], prefix="fc_", dir=tempfile.gettempdir())
    os.close(fd)
    write(tmp)
    shutil.move(tmp, dst)


def export_step(shape, dst):
    _via_ascii_tmp(lambda p: shape.exportStep(p), dst)


def export_stl(shape_or_mesh, dst, lin=0.04, ang=0.35):
    import Mesh
    m = shape_or_mesh if isinstance(shape_or_mesh, Mesh.Mesh) else mesh_of(shape_or_mesh, lin, ang)
    _via_ascii_tmp(lambda p: m.write(p, "STL"), dst)
    return m


def export_stl_multi(meshes, dst):
    """One STL with several shells (print-in-place: all bodies in one file, one object in the slicer)."""
    import Mesh
    m = Mesh.Mesh()
    for x in meshes:
        m.addMesh(x)
    _via_ascii_tmp(lambda p: m.write(p, "STL"), dst)
    return m


def export_fcstd(named_shapes, dst):
    doc = FreeCAD.newDocument("gen")
    for name, s in named_shapes:
        o = doc.addObject("Part::Feature", name)
        o.Shape = s
    doc.recompute()
    _via_ascii_tmp(lambda p: doc.saveAs(p), dst)
    FreeCAD.closeDocument(doc.Name)


def dump_json(obj, dst):
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    b = cut(box(0, 0, 0, 20, 20, 8), cyl(3, 20, (10, 10, -1)))
    k = round_end(4, 0, 20, 0, 4, -1)
    s = fuse(b, k)
    print(shape_report("demo", s), mesh_report(mesh_of(s)))
    assert s.isValid() and len(s.Solids) == 1
    tmp = os.path.join(tempfile.gettempdir(), "fc_lib_demo.stl")
    export_stl(s, tmp); print("wrote", tmp)
