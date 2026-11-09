"""SVG logo -> FreeCAD solid for embossing / debossing (route B), without importSVG.

FreeCAD's importSVG is GUI-oriented and failed headless on a traced (VTracer) path with an OCC
error, so this parses the path data itself: M/L/H/V/C/S/Q/T/Z, absolute and relative, curves
flattened, sub-paths nested by containment (odd depth = hole), polygons simplified to print scale.

    from fc_svg import svg_solid, spark_mark, place_on_plane
    solid, info = svg_solid("logo.svg", height_mm=11, depth=0.6, min_stroke=0.45)   # drawn in XY, z = depth axis
    part = part.cut(place_on_plane(solid, origin=(x, y, z), normal=(0, -1, 0), up=(0, 0, 1)))

Line art (traced drawings) has strokes far thinner than a nozzle at badge size: `min_stroke` grows
every stroke by a band outside each outer wire and inside each hole wire (offsetting the whole face
makes OCC drop the holes). `info` reports the traced stroke width and the band applied.
Self-test: python.exe -B fc_svg.py   (writes two PNG-free STL files to the temp folder)
"""
import math
import os
import re
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fc_lib import V, fuse, export_stl, FreeCAD  # noqa: E402

import Part  # noqa: E402

_TOK = re.compile(r"[MmLlHhVvCcSsQqTtZzAa]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _bez(p0, p1, p2, p3, n):
    out = []
    for k in range(1, n + 1):
        t = k / n; u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def _quad(p0, p1, p2, n):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (k / n for k in range(1, n + 1))]


def parse_path(d, steps=6):
    """Closed polygons [(x, y), ...] in SVG units (y down) from one path's d attribute."""
    toks = _TOK.findall(d)
    polys, cur = [], []
    pos = start = (0.0, 0.0)
    prev_c = prev_q = None
    i, cmd = 0, None

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v

    def close():
        nonlocal cur, pos
        if len(cur) >= 3:
            polys.append(cur)
        cur = []; pos = start

    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                close(); prev_c = prev_q = None
                continue
        rel, c = cmd.islower(), cmd.upper()
        if c == "M":
            x, y = num(), num()
            if rel: x += pos[0]; y += pos[1]
            if cur: close()
            pos = start = (x, y); cur = [pos]; cmd = "l" if rel else "L"; prev_c = prev_q = None
        elif c == "L":
            x, y = num(), num()
            if rel: x += pos[0]; y += pos[1]
            pos = (x, y); cur.append(pos); prev_c = prev_q = None
        elif c == "H":
            x = num(); pos = ((x + pos[0]) if rel else x, pos[1]); cur.append(pos); prev_c = prev_q = None
        elif c == "V":
            y = num(); pos = (pos[0], (y + pos[1]) if rel else y); cur.append(pos); prev_c = prev_q = None
        elif c in ("C", "S"):
            if c == "C":
                x1, y1, x2, y2, x, y = (num() for _ in range(6))
                if rel: x1 += pos[0]; y1 += pos[1]; x2 += pos[0]; y2 += pos[1]; x += pos[0]; y += pos[1]
            else:
                x2, y2, x, y = (num() for _ in range(4))
                if rel: x2 += pos[0]; y2 += pos[1]; x += pos[0]; y += pos[1]
                x1, y1 = (2 * pos[0] - prev_c[0], 2 * pos[1] - prev_c[1]) if prev_c else pos
            cur += _bez(pos, (x1, y1), (x2, y2), (x, y), steps); prev_c = (x2, y2); prev_q = None; pos = (x, y)
        elif c in ("Q", "T"):
            if c == "Q":
                x1, y1, x, y = (num() for _ in range(4))
                if rel: x1 += pos[0]; y1 += pos[1]; x += pos[0]; y += pos[1]
            else:
                x, y = num(), num()
                if rel: x += pos[0]; y += pos[1]
                x1, y1 = (2 * pos[0] - prev_q[0], 2 * pos[1] - prev_q[1]) if prev_q else pos
            cur += _quad(pos, (x1, y1), (x, y), steps); prev_q = (x1, y1); prev_c = None; pos = (x, y)
        elif c == "A":                                  # rare in traces: chord
            for _ in range(5): num()
            x, y = num(), num()
            if rel: x += pos[0]; y += pos[1]
            pos = (x, y); cur.append(pos)
        else:
            raise ValueError(f"unsupported SVG path command {cmd!r}")
    if cur:
        close()
    return polys


def _area(p):
    return 0.5 * sum(p[k][0] * p[(k + 1) % len(p)][1] - p[(k + 1) % len(p)][0] * p[k][1] for k in range(len(p)))


def _inside(pt, poly):
    x, y = pt; c = False
    for k in range(len(poly)):
        x1, y1 = poly[k]; x2, y2 = poly[(k + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _simplify(p, tol):
    if len(p) < 6:
        return p

    def dp(pts):
        if len(pts) < 3:
            return pts
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1e-12
        far, idx = 0.0, 0
        for k in range(1, len(pts) - 1):
            d = abs(dy * (pts[k][0] - x0) - dx * (pts[k][1] - y0)) / L
            if d > far:
                far, idx = d, k
        return dp(pts[:idx + 1])[:-1] + dp(pts[idx:]) if far > tol else [pts[0], pts[-1]]
    j = max(range(len(p)), key=lambda k: (p[k][0] - p[0][0]) ** 2 + (p[k][1] - p[0][1]) ** 2)
    out = dp(p[:j + 1])[:-1] + dp(p[j:] + [p[0]])[:-1]
    return out if len(out) >= 3 else p


def svg_polygons(path, height_mm, mirror=False, min_feature=0.06):
    """All <path d> of an SVG file -> polygons in mm, height_mm tall, centred, y up."""
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    ds = re.findall(r'<path[^>]*\sd="([^"]+)"', txt, flags=re.S)
    if not ds:
        raise ValueError(f"no <path d=...> in {path} (convert text/shapes to paths first)")
    polys = []
    for d in ds:
        polys += parse_path(d)
    xs = [x for p in polys for x, _ in p]; ys = [y for p in polys for _, y in p]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    s = height_mm / (y1 - y0); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sx = -s if mirror else s
    out = []
    for p in polys:
        q = _simplify([(sx * (x - cx), -s * (y - cy)) for x, y in p], min_feature / 3)
        if abs(_area(q)) >= min_feature * min_feature:
            out.append(q)
    return out, (x1 - x0) * s


def _wire(poly):
    return Part.makePolygon([V(x, y, 0) for x, y in poly] + [V(poly[0][0], poly[0][1], 0)])


def polygons_to_faces(polys):
    """Even containment depth = outer boundary, odd = hole of its parent."""
    polys = sorted(polys, key=lambda p: -abs(_area(p)))
    depth, parent = [0] * len(polys), [None] * len(polys)
    for i, p in enumerate(polys):
        for j in range(i):
            if _inside(p[0], polys[j]):
                depth[i] += 1
                if parent[i] is None or depth[j] >= depth[parent[i]]:
                    parent[i] = j
    faces = []
    for i, p in enumerate(polys):
        if depth[i] % 2:
            continue
        holes = [polys[k] for k in range(len(polys)) if parent[k] == i and depth[k] == depth[i] + 1]
        try:
            f = Part.Face([_wire(p)] + [_wire(h) for h in holes])
            if not f.isValid():
                raise ValueError
        except Exception:
            f = Part.Face(_wire(p))
            for h in holes:
                f = f.cut(Part.Face(_wire(h)))
        faces.append(f)
    return faces


def thicken(polys, min_stroke, res=0.04):
    """Line-art logos traced from a drawing have strokes far thinner than a nozzle at badge size.
    Estimate the stroke width (2*area/perimeter of the even-odd filled drawing) and, if it is below
    min_stroke, thicken on a raster: fill the polygons even-odd on a grid of `res` mm, dilate with a
    disc of radius delta, and trace the result back into polygons (contourpy). OCC's 2D offsets either
    dropped the holes or left sliver facets; a raster never does. Returns (polygons, stroke, delta)."""
    import numpy as np
    from matplotlib.path import Path
    from scipy import ndimage
    import contourpy
    xs = [x for p in polys for x, _ in p]; ys = [y for p in polys for _, y in p]
    pad = min_stroke + 3 * res
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    nx, ny = int((x1 - x0) / res) + 1, int((y1 - y0) / res) + 1
    gx = x0 + res * np.arange(nx); gy = y0 + res * np.arange(ny)
    GX, GY = np.meshgrid(gx, gy)
    pts = np.column_stack([GX.ravel(), GY.ravel()])
    mask = np.zeros(pts.shape[0], dtype=bool)
    for p in polys:
        mask ^= Path(p).contains_points(pts)                       # even-odd fill
    mask = mask.reshape(ny, nx)
    area = float(mask.sum()) * res * res                           # filled area of the drawing
    per = sum(math.hypot(p[k][0] - p[k - 1][0], p[k][1] - p[k - 1][1]) for p in polys for k in range(len(p)))
    stroke = 2 * area / per if per else min_stroke                 # strokes: area ~ stroke * length, per ~ 2 * length
    if stroke >= min_stroke:
        return polys, stroke, 0.0
    delta = (min_stroke - stroke) / 2
    r = max(1, int(round(delta / res)))
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    mask = ndimage.binary_dilation(mask, structure=(xx * xx + yy * yy) <= r * r)
    gen = contourpy.contour_generator(x=gx, y=gy, z=mask.astype(float))
    out = []
    for line in gen.lines(0.5):
        q = [(float(x), float(y)) for x, y in line]
        if len(q) > 2 and abs(q[0][0] - q[-1][0]) < 1e-9 and abs(q[0][1] - q[-1][1]) < 1e-9:
            q = q[:-1]
        q = _simplify(q, res * 0.6)
        if len(q) >= 3 and abs(_area(q)) > min_stroke * min_stroke:
            out.append(q)
    return out, stroke, delta


def prism(faces, depth, front=1.0):
    """Extrude faces drawn in XY from z = -depth (inside the part) to z = +front (outside): cut it."""
    solids = []
    for f in faces:
        s = f.copy(); s.translate(V(0, 0, -depth)); solids.append(s.extrude(V(0, 0, depth + front)))
    return fuse(*solids) if len(solids) > 1 else solids[0]


def svg_solid(path, height_mm, depth, min_stroke=0.45, mirror=False):
    polys, width = svg_polygons(path, height_mm, mirror)
    polys, stroke, delta = thicken(polys, min_stroke)
    faces = polygons_to_faces(polys)
    return prism(faces, depth), {"width_mm": round(width, 2), "traced_stroke_mm": round(stroke, 3),
                                 "band_mm": round(delta, 3), "faces": len(faces)}


def spark_mark(height, depth, spokes=12):
    """A deterministic spark / asterisk: rounded rays of uneven length around a hub (a generator's mark)."""
    R = height / 2; w = 0.21 * R; r0 = 0.10 * R
    lengths = [1.0, 0.86, 0.95, 0.9, 1.0, 0.88, 0.97, 0.9, 1.0, 0.85, 0.95, 0.9]
    jitter = [0, 3, -2, 4, 0, -3, 2, 4, -1, 3, -2, 1]
    parts = [Part.makeCylinder(0.16 * R, depth + 1.0, V(0, 0, -depth))]
    for k in range(spokes):
        a = math.radians(k * 360.0 / spokes + jitter[k % 12]); L = (R - w / 2) * lengths[k % 12]
        bx = Part.makeBox(L - r0, w, depth + 1.0, V(r0, -w / 2, -depth)); bx.rotate(V(0, 0, 0), V(0, 0, 1), math.degrees(a))
        parts += [bx, Part.makeCylinder(w / 2, depth + 1.0, V(L * math.cos(a), L * math.sin(a), -depth))]
    return fuse(*parts)


def place_on_plane(solid, origin, normal, up):
    """Move a mark built in XY (z = outward normal of the drawing) onto a face: its centre to `origin`,
    its +z to the face's OUTWARD `normal`, its +y to `up` (both unit vectors, perpendicular)."""
    n = V(*normal); u = V(*up); r = u.cross(n)       # right-handed: right = up x normal
    m = FreeCAD.Matrix(r.x, u.x, n.x, origin[0], r.y, u.y, n.y, origin[1], r.z, u.z, n.z, origin[2], 0, 0, 0, 1)
    s = solid.copy(); s.transformShape(m)
    return s


if __name__ == "__main__":
    tmp = tempfile.gettempdir()
    svg = os.path.join(tmp, "fc_svg_demo.svg")
    with open(svg, "w", encoding="utf-8") as f:   # a ring with a square hole and a separate triangle, as path data
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="M10 10 L90 10 L90 90 L10 90 Z '
                'M40 40 L60 40 L60 60 L40 60 Z M20 95 l10 -8 l10 8 z"/></svg>')
    s, info = svg_solid(svg, 10.0, 0.6, min_stroke=0.0)
    assert s.isValid() and len(s.Solids) == 1, "svg_solid broke"
    print("svg_solid:", info, "volume %.2f" % s.Volume)
    k = spark_mark(9.0, 0.6)
    assert k.isValid() and len(k.Solids) == 1
    box = Part.makeBox(30, 10, 20)
    cut = box.cut(place_on_plane(k, (15, 0, 10), (0, -1, 0), (0, 0, 1))).removeSplitter()
    assert cut.isValid() and len(cut.Solids) == 1 and cut.Volume < box.Volume
    export_stl(cut, os.path.join(tmp, "fc_svg_demo.stl"))
    print("spark deboss on a box face ok, wrote", os.path.join(tmp, "fc_svg_demo.stl"))
