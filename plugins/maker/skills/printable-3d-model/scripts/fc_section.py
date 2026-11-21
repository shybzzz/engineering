"""Cross-sections of FreeCAD shapes on a millimetre grid (numpy + PIL ship with FreeCAD): the
picture to send the user when a fit, a wall or a profile is discussed - they can read
dimensions off the grid and draw the change they want straight on it.

    from fc_section import section
    section("sections/10_section_x0.png", [(holder, (20, 60, 150)), (key, (200, 30, 40))],
            origin=(0, 0, 0), normal=(1, 0, 0), ax_h=(0, 1, 0), ax_v=(0, 0, 1),
            title="Section x=0 (key axis): horizontal Y, vertical Z, mm")

Every shape is cut by the plane through `origin` with `normal`; ax_h / ax_v are the model
directions of the picture axes (any orthonormal pair in the plane, so a section across an
inclined feature is as easy as an axis-aligned one). The cut material is tinted, the outline
is drawn in the shape's colour: give mating parts contrasting colours. Grid lines every 1 mm,
bold and numbered every 5 mm, in the coordinates along ax_h / ax_v.
depth_from=<v>: plot (v - coordinate) growing downward, e.g. depth below a top face.
A plane that coincides with a face gives a degenerate cut: move it by 0.01 mm.
Self-test: python.exe -B fc_section.py   (writes a PNG to the temp folder)
"""
import math, os, sys, tempfile

sys.dont_write_bytecode = True
try:
    import FreeCAD
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fc_lib import FreeCAD
import Part  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFont  # noqa: E402

V = FreeCAD.Vector


def _font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def cut_loops(shape, origin, normal, ax_h, ax_v, deflection=0.02):
    """Closed polylines [(h, v), ...] of the section of `shape`, in picture coordinates."""
    n, h, v = V(*normal), V(*ax_h), V(*ax_v)
    n.normalize(); h.normalize(); v.normalize()
    assert abs(n.dot(h)) < 1e-6 and abs(n.dot(v)) < 1e-6 and abs(h.dot(v)) < 1e-6, "normal, ax_h, ax_v must be mutually perpendicular"
    loops = []
    for w in shape.slice(n, V(*origin).dot(n)):
        pts = w.discretize(Deflection=deflection)
        if len(pts) >= 3:
            loops.append([(p.dot(h), p.dot(v)) for p in pts])
    return loops


def section(path, shapes, origin, normal, ax_h, ax_v, title="", depth_from=None, scale=24, margin=2):
    """Draw the section of shapes [(shape, rgb)] and save it to `path` (PNG). scale = pixels
    per mm. Returns the number of loops drawn per shape (0 = the plane misses that shape)."""
    cuts = [(cut_loops(s, origin, normal, ax_h, ax_v), col) for s, col in shapes]
    if depth_from is not None:
        cuts = [([[(a, depth_from - b) for a, b in lp] for lp in loops], col) for loops, col in cuts]
    allp = [p for loops, _ in cuts for lp in loops for p in lp]
    assert allp, "the plane misses every shape"
    h0, h1 = math.floor(min(p[0] for p in allp)) - margin, math.ceil(max(p[0] for p in allp)) + margin
    v0, v1 = math.floor(min(p[1] for p in allp)) - margin, math.ceil(max(p[1] for p in allp)) + margin
    top = 40
    wd, ht = int((h1 - h0) * scale), int((v1 - v0) * scale) + top
    px = lambda a: (a - h0) * scale
    py = (lambda b: top + (b - v0) * scale) if depth_from is not None else (lambda b: ht - (b - v0) * scale)
    im = Image.new("RGB", (wd, ht), (250, 250, 248))
    for loops, col in cuts:                       # material: even-odd fill, so holes stay empty
        mask = Image.new("1", (wd, ht), 0)
        for lp in loops:
            one = Image.new("1", (wd, ht), 0)
            ImageDraw.Draw(one).polygon([(px(a), py(b)) for a, b in lp], fill=1)
            mask = ImageChops.logical_xor(mask, one)
        tint = tuple(int(c + (255 - c) * 0.78) for c in col)
        im.paste(Image.new("RGB", (wd, ht), tint), (0, 0), mask)
    d, font = ImageDraw.Draw(im), _font(18)
    for g in range(int(h0), int(h1) + 1):
        d.line([(px(g), top), (px(g), ht)], fill=(140, 140, 140) if g % 5 == 0 else (205, 205, 205))
        if g % 5 == 0:
            d.text((px(g) + 3, ht - 22), str(g), fill=(80, 80, 80), font=font)
    for g in range(int(v0), int(v1) + 1):
        d.line([(0, py(g)), (wd, py(g))], fill=(140, 140, 140) if g % 5 == 0 else (205, 205, 205))
        if g % 5 == 0:
            d.text((3, py(g) - 22), str(g), fill=(80, 80, 80), font=font)
    for loops, col in cuts:
        for lp in loops:
            d.line([(px(a), py(b)) for a, b in lp] + [(px(lp[0][0]), py(lp[0][1]))], fill=col, width=3)
    d.rectangle([0, 0, wd, top - 1], fill=(250, 250, 248))
    d.text((6, 8), title, fill=(0, 0, 0), font=font)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    im.save(path)
    return [len(loops) for loops, _ in cuts]


if __name__ == "__main__":
    body = Part.makeBox(30, 20, 12, V(-15, -10, 0)).cut(Part.makeBox(16, 8, 9, V(-8, -4, 3)))
    body = body.cut(Part.makeCylinder(2, 40, V(0, -20, 6), V(0, 1, 0)))          # cross hole along Y
    pin = Part.makeCylinder(1.5, 26, V(0, -13, 6), V(0, 1, 0))
    out = os.path.join(tempfile.gettempdir(), "fc_section_demo.png")
    n = section(out, [(body, (20, 60, 150)), (pin, (200, 30, 40))], (0.01, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                "Section x=0: horizontal Y, vertical Z, mm")
    assert n[0] >= 1 and n[1] == 1, n
    s = math.sqrt(0.5)
    out2 = os.path.join(tempfile.gettempdir(), "fc_section_demo_oblique.png")
    n2 = section(out2, [(body, (20, 60, 150))], (0, 0, 6), (0, s, s), (1, 0, 0), (0, -s, s), "Oblique section (45 deg)", depth_from=10)
    assert n2[0] >= 1, n2
    im = Image.open(out).convert("RGB")
    cols = {c for _, c in im.getcolors(1 << 20)}
    assert (20, 60, 150) in cols and (200, 30, 40) in cols
    print("fc_section self-test OK ->", out, out2, n, n2)
