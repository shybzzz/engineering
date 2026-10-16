"""mesh_kit: build watertight binary STL from scratch with Python + shapely, no mesh library.

Copy this file next to your generator (or import it) and build the solid from faces:

    from mesh_kit import Mesh, ring, UP, DOWN
    m = Mesh()
    lo = ring(cx, cy, r, SEG, z=0);  hi = ring(cx, cy, r, SEG, z=10)
    m.loft(lo, hi, outward=(cx, cy))                 # cylindrical wall
    m.flat(Polygon(xy(lo)), 0, DOWN)                 # bottom cap
    m.engrave(Polygon(xy(hi)), text_shape(...), 10, UP, depth=0.6)   # top cap with recess
    print(m.check()); m.write("part.stl")

Rules that keep the result manifold (learned the hard way):
  * every face goes through Mesh.tri(a, b, c, want) - winding is fixed automatically so the
    normal has a positive dot with `want` (any vector pointing out of the solid near that face);
  * all coordinates are rounded to 5 decimals, so vertices shared between a wall ring and a
    flat face coincide exactly;
  * flat faces with holes are triangulated with shapely.constrained_delaunay_triangles,
    which adds NO new vertices, so ring vertices on the face match the loft rings bit-for-bit;
  * never let two rings that should be joined have different vertex counts.

Needs: shapely>=2.1 (constrained_delaunay_triangles), numpy; fonttools only for text_shape.
Run `python -I mesh_kit.py demo.stl` for a self-test: a round coaster with an engraved word,
a pocket and a chamfered rim; it prints the manifold check and writes the file.
"""
import math, struct, re
from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from shapely import affinity

UP, DOWN = (0, 0, 1), (0, 0, -1)
ROUND = 5


def R(p):
    return (round(p[0], ROUND), round(p[1], ROUND), round(p[2], ROUND))
def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def xy(pts): return [(p[0], p[1]) for p in pts]


def ring(cx, cy, r, seg, z):
    """closed circle as `seg` points (list, not repeated at the end), counter-clockwise"""
    return [R((cx + r*math.cos(2*math.pi*k/seg), cy + r*math.sin(2*math.pi*k/seg), z)) for k in range(seg)]


def rounded_rect(x0, y0, x1, y1, rc, z, arc=24):
    """rounded-rectangle ring with a fixed vertex count (4*(arc+1)) - loftable between insets"""
    pts = []
    for cx, cy, a0 in [(x1-rc, y1-rc, 0.0), (x0+rc, y1-rc, 0.5), (x0+rc, y0+rc, 1.0), (x1-rc, y0+rc, 1.5)]:
        for k in range(arc+1):
            a = (a0 + 0.5*k/arc)*math.pi
            pts.append(R((cx + rc*math.cos(a), cy + rc*math.sin(a), z)))
    return pts


def polys(g):
    return list(g.geoms) if hasattr(g, "geoms") else ([g] if not g.is_empty else [])


def snap(shape):
    """round shapely coordinates like R() does, so face triangles match wall vertices"""
    return shapely.transform(shape, lambda a: np.round(a, ROUND))


class Mesh:
    def __init__(self):
        self.tris = []

    def tri(self, a, b, c, want):
        a, b, c = R(a), R(b), R(c)
        n = cross(sub(b, a), sub(c, a))
        if n == (0, 0, 0):
            return
        if dot(n, want) < 0:
            b, c = c, b
        self.tris.append((a, b, c))

    def loft(self, lo, hi, outward=None, inward=False, up=0.0):
        """quad strip between two rings of equal length. `outward`=(cx,cy) axis the normal
        points away from (or toward, if inward=True); `up` adds a vertical component
        (use for conical/flared walls so `want` is never perpendicular to the face)."""
        n = len(lo); assert n == len(hi), "rings must have the same vertex count"
        for k in range(n):
            a, b, c, d = lo[k], lo[(k+1) % n], hi[(k+1) % n], hi[k]
            mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2
            if outward is None:
                want = (0, 0, 1)
            else:
                vx, vy = mx - outward[0], my - outward[1]
                if inward: vx, vy = -vx, -vy
                want = (vx, vy, up*math.hypot(vx, vy))
            self.tri(a, b, c, want); self.tri(a, c, d, want)

    def flat(self, face, z, normal):
        """planar face (shapely Polygon/MultiPolygon, holes allowed) at height z"""
        face = snap(face)
        for t in shapely.constrained_delaunay_triangles(face).geoms:
            c = list(t.exterior.coords)[:3]
            self.tri((c[0][0], c[0][1], z), (c[1][0], c[1][1], z), (c[2][0], c[2][1], z), normal)

    def engrave(self, face, shape, z, normal, depth):
        """face at height z with outward `normal` (UP/DOWN); `shape` is recessed by `depth`
        into the solid: emits the remaining face, the recess ceiling and the recess walls."""
        face, shape = snap(face), snap(shape)
        zr = z - depth*normal[2]
        self.flat(face.difference(shape), z, normal)
        self.flat(shape, zr, normal)
        for poly in polys(shape):
            for ring_ in [poly.exterior, *poly.interiors]:
                pts = list(ring_.coords)
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    mx, my = (ax+bx)/2, (ay+by)/2
                    nx, ny = -(by-ay), (bx-ax)                      # left normal of the edge
                    inside = shape.contains(Point(mx + 1e-3*nx, my + 1e-3*ny))
                    want = (nx, ny, 0) if inside else (-nx, -ny, 0)  # normal points into the cavity
                    self.tri((ax, ay, z), (bx, by, z), (bx, by, zr), want)
                    self.tri((ax, ay, z), (bx, by, zr), (ax, ay, zr), want)

    def pocket(self, cx, cy, r, z_top, depth, seg, chamfer=0.0):
        """cylindrical blind hole from the face at z_top; returns (hole polygon to cut out of
        the top face, floor disk polygon at z_top-depth). Optional 45-degree rim chamfer."""
        z_floor = z_top - depth
        bot = ring(cx, cy, r, seg, z_floor)
        if chamfer > 0:
            top = ring(cx, cy, r + chamfer, seg, z_top)
            mid = ring(cx, cy, r, seg, z_top - chamfer)
            self.loft(top, mid, outward=(cx, cy), inward=True, up=-1.0)  # cone: normal toward axis and up
            self.loft(mid, bot, outward=(cx, cy), inward=True)
        else:
            top = ring(cx, cy, r, seg, z_top)
            self.loft(top, bot, outward=(cx, cy), inward=True)
        return Polygon(xy(top)), Polygon(xy(bot))

    def check(self):
        """edge-manifold test + signed volume. Every directed edge must occur exactly once
        and its reverse exactly once. Returns dict; bad_edges must be 0, volume > 0."""
        edges = defaultdict(int)
        for a, b, c in self.tris:
            for u, v in ((a, b), (b, c), (c, a)):
                edges[(u, v)] += 1
        bad = [e for e, n in edges.items() if n != 1 or edges.get((e[1], e[0]), 0) != 1]
        vol = sum(dot(a, cross(b, c)) for a, b, c in self.tris) / 6.0
        xs = [p[0] for t in self.tris for p in t]; ys = [p[1] for t in self.tris for p in t]; zs = [p[2] for t in self.tris for p in t]
        return dict(triangles=len(self.tris), bad_edges=len(bad), volume_cm3=round(vol/1000, 2),
                    size=(round(max(xs)-min(xs), 2), round(max(ys)-min(ys), 2), round(max(zs)-min(zs), 2)),
                    z_min=round(min(zs), 3))

    def write(self, path, header="generated by mesh_kit"):
        with open(path, "wb") as f:
            f.write(header.encode("ascii", "replace")[:80].ljust(80, b"\0"))
            f.write(struct.pack("<I", len(self.tris)))
            for a, b, c in self.tris:
                n = cross(sub(b, a), sub(c, a)); L = math.sqrt(dot(n, n)) or 1
                f.write(struct.pack("<12fH", n[0]/L, n[1]/L, n[2]/L, *a, *b, *c, 0))


# ---------------- 2D shapes for engraving ----------------
def text_shape(text, font_path, cap_height, tracking=0.06, bold=0.0, flatten=8):
    """word outline as a shapely polygon, scaled so capital letters are `cap_height` mm tall,
    bottom-left near (0,0). tracking: extra letter spacing in em; bold: extra stroke per side (mm)
    for small lettering that would otherwise be thinner than ~2 nozzle widths."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.basePen import BasePen

    class FlatPen(BasePen):
        def __init__(self, gs):
            super().__init__(gs); self.contours = []; self.cur = None
        def _moveTo(self, p): self.cur = [p]
        def _lineTo(self, p): self.cur.append(p)
        def _curveToOne(self, p1, p2, p3):
            p0 = self.cur[-1]
            for i in range(1, flatten+1):
                t = i/flatten; u = 1-t
                self.cur.append((u**3*p0[0]+3*u*u*t*p1[0]+3*u*t*t*p2[0]+t**3*p3[0],
                                 u**3*p0[1]+3*u*u*t*p1[1]+3*u*t*t*p2[1]+t**3*p3[1]))
        def _qCurveToOne(self, p1, p2):
            p0 = self.cur[-1]
            for i in range(1, flatten+1):
                t = i/flatten; u = 1-t
                self.cur.append((u*u*p0[0]+2*u*t*p1[0]+t*t*p2[0], u*u*p0[1]+2*u*t*p1[1]+t*t*p2[1]))
        def _closePath(self):
            if self.cur and len(self.cur) >= 3: self.contours.append(self.cur)
            self.cur = None
        def _endPath(self): self._closePath()

    font = TTFont(font_path); gs = font.getGlyphSet(); cmap = font.getBestCmap()
    upm = font["head"].unitsPerEm

    def glyph(ch):
        pen = FlatPen(gs); gs[cmap[ord(ch)]].draw(pen)
        shape = None
        for c in pen.contours:
            p = Polygon(c).buffer(0)
            if p.is_empty: continue
            shape = p if shape is None else shape.symmetric_difference(p)   # even-odd: holes in O, B, R...
        return shape, gs[cmap[ord(ch)]].width

    cap_units = getattr(font["OS/2"], "sCapHeight", 0) or glyph("H")[0].bounds[3]
    x = 0; parts = []
    for ch in text:
        if ch == " ":
            x += upm*0.3; continue
        s, adv = glyph(ch)
        if s is not None: parts.append(affinity.translate(s, x, 0))
        x += adv + tracking*upm
    sc = cap_height/cap_units
    shape = affinity.scale(unary_union(parts), sc, sc, origin=(0, 0))
    if bold > 0:
        shape = shape.buffer(bold, join_style="mitre").simplify(0.02)
    return snap(shape)


def fit(shape, width=None, height=None, cx=0.0, cy=0.0, mirror_x=False):
    """scale `shape` uniformly to the given width or height and centre it on (cx, cy).
    mirror_x=True for engravings on the UNDERSIDE so they read correctly when flipped."""
    b = shape.bounds
    sc = width/(b[2]-b[0]) if width else height/(b[3]-b[1])
    shape = affinity.scale(shape, -sc if mirror_x else sc, sc, origin=(0, 0))
    b = shape.bounds
    return snap(affinity.translate(shape, cx-(b[0]+b[2])/2, cy-(b[1]+b[3])/2))


def svg_path_shape(svg_file, flatten=10):
    """even-odd fill of all <path d="..."> in an SVG with absolute M/L/H/V/C/Q/Z commands
    (what VTracer and most 'flatten transforms' exports write). Y is flipped to model space."""
    txt = open(svg_file, encoding="utf-8").read()
    rings = []
    for d in re.findall(r'\sd="([^"]+)"', txt):
        tokens = re.findall(r'[MLHVCQZ]|-?\d*\.?\d+(?:e-?\d+)?', d, flags=re.I)
        cur = []; cmd = None; pos = (0.0, 0.0); i = 0
        def num():
            nonlocal i; i += 1; return float(tokens[i-1])
        while i < len(tokens):
            t = tokens[i]
            if t.isalpha():
                cmd = t; i += 1
                if cmd in "Zz":
                    if len(cur) >= 3: rings.append(cur)
                    cur = []
                continue
            if cmd in "Mm" and cur:            # implicit lineto after moveto
                cmd = "L"
            if cmd in "MmLl":
                x, y = num(), num(); pos = (pos[0]+x, pos[1]+y) if cmd.islower() else (x, y); cur.append(pos)
            elif cmd in "Hh":
                x = num(); pos = (pos[0]+x if cmd.islower() else x, pos[1]); cur.append(pos)
            elif cmd in "Vv":
                y = num(); pos = (pos[0], pos[1]+y if cmd.islower() else y); cur.append(pos)
            elif cmd in "CcQq":
                k = 3 if cmd in "Cc" else 2
                cps = [(num(), num()) for _ in range(k)]
                if cmd.islower(): cps = [(pos[0]+p[0], pos[1]+p[1]) for p in cps]
                p0 = pos
                for s in range(1, flatten+1):
                    u = s/flatten; v = 1-u
                    if k == 3:
                        pt = (v**3*p0[0]+3*v*v*u*cps[0][0]+3*v*u*u*cps[1][0]+u**3*cps[2][0],
                              v**3*p0[1]+3*v*v*u*cps[0][1]+3*v*u*u*cps[1][1]+u**3*cps[2][1])
                    else:
                        pt = (v*v*p0[0]+2*v*u*cps[0][0]+u*u*cps[1][0], v*v*p0[1]+2*v*u*cps[0][1]+u*u*cps[1][1])
                    cur.append(pt)
                pos = cps[-1]
            else:
                i += 1
        if len(cur) >= 3: rings.append(cur)
    shape = None
    for rpts in rings:
        p = Polygon(rpts).buffer(0)
        if p.is_empty: continue
        shape = p if shape is None else shape.symmetric_difference(p)
    return affinity.scale(shape, 1, -1, origin=(0, 0))   # SVG y goes down


# ---------------- self-test ----------------
if __name__ == "__main__":
    import sys, os
    out = sys.argv[1] if len(sys.argv) > 1 else "mesh_kit_demo.stl"
    SEG, RAD, H = 96, 40.0, 8.0
    m = Mesh()
    outer_lo, outer_hi = ring(0, 0, RAD, SEG, 0), ring(0, 0, RAD, SEG, H)
    m.loft(outer_lo, outer_hi, outward=(0, 0))
    hole, floor = m.pocket(15, 0, 10.0, H, 4.0, SEG, chamfer=1.0)
    top = Polygon(xy(outer_hi)).difference(hole)
    # engraved word on the top face, left of the pocket; falls back to a star if no font given
    font = os.environ.get("MESH_KIT_FONT")
    if font and os.path.exists(font):
        word = fit(text_shape("DEMO", font, 5.0), width=22, cx=-16, cy=0)
    else:
        word = fit(Polygon([(math.cos(a)*(1 if k % 2 else 2), math.sin(a)*(1 if k % 2 else 2))
                            for k, a in enumerate(2*math.pi*np.arange(10)/10)]), width=20, cx=-16, cy=0)
    m.engrave(top, word, H, UP, depth=0.6)
    m.flat(floor, H-4.0, UP)
    m.flat(Polygon(xy(outer_lo)), 0, DOWN)
    info = m.check(); print(info)
    assert info["bad_edges"] == 0 and info["volume_cm3"] > 0, "demo mesh is not watertight"
    m.write(out, "mesh_kit demo coaster"); print("wrote", out)
