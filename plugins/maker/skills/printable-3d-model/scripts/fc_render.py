"""Pure numpy z-buffer renderer for FreeCAD shapes (numpy + PIL ship with FreeCAD): orthographic
views with Lambert shading and dark feature edges. Copy next to your generator.

    from fc_render import render
    render([(shape, (120, 160, 220)), (other, (235, 170, 90))], "preview/iso.png", view="iso", title="...")
    render([(shape.common(box(region)), rgb)], "preview/closeup.png", view=(30.0, -125.0))   # (elev, azim)

Views: iso, iso2, front, right, top, back, or an (elevation, azimuth) tuple. Empty/null shapes are
skipped. A full assembly takes a few seconds; crop with shape.common(box) for close-ups.
Self-test: python.exe -B fc_render.py  (writes a PNG to the temp folder)
"""
import math, os, sys, tempfile

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFont

VIEWS = {"iso": (35.0, -45.0), "iso2": (30.0, 225.0), "front": (0.0, -90.0), "right": (0.0, 0.0),
         "top": (89.9, -90.0), "back": (0.0, 90.0)}


def _mesh_of(shape, lin=0.15, ang=0.5):
    import MeshPart
    return MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False)


def _rotation(elev, azim):
    e, a = math.radians(elev), math.radians(azim)
    fwd = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    fwd = -fwd / np.linalg.norm(fwd)
    up0 = np.array([0, 0, 1.0]) if abs(fwd[2]) < 0.999 else np.array([0, 1.0, 0])
    right = np.cross(fwd, up0); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return np.stack([right, up, -fwd])


def _tris(shape, lin=0.15):
    m = _mesh_of(shape, lin=lin)
    pts = np.array([[p.x, p.y, p.z] for p in m.Points], dtype=float)
    fac = np.array([f.PointIndices for f in m.Facets], dtype=int)
    return pts[fac] if len(fac) else np.zeros((0, 3, 3))


def render(items, path, view="iso", size=(1400, 1000), bg=(246, 246, 248), light=(-0.4, -0.5, 0.75),
           title=None, edges=True, scale=None):
    elev, azim = VIEWS[view] if isinstance(view, str) else view
    R = _rotation(elev, azim)
    tris, cols = [], []
    for shape, rgb in items:
        if shape is None or shape.isNull() or len(shape.Faces) == 0:
            continue
        t = _tris(shape)
        if len(t) == 0:
            continue
        tris.append(t); cols.append(np.tile(np.array(rgb, float), (len(t), 1)))
    if not tris:
        raise ValueError("nothing to render")
    T = np.concatenate(tris); C = np.concatenate(cols)
    P = T @ R.T
    W, H = size
    mn, mx = P[:, :, :2].reshape(-1, 2).min(0), P[:, :, :2].reshape(-1, 2).max(0)
    span = mx - mn
    if scale is None:
        scale = min((W - 80) / max(span[0], 1e-6), (H - 80) / max(span[1], 1e-6))
    off = np.array([W / 2, H / 2]) - (mn + mx) / 2 * scale
    S = P.copy()
    S[:, :, 0] = P[:, :, 0] * scale + off[0]
    S[:, :, 1] = H - (P[:, :, 1] * scale + off[1])
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nl = np.linalg.norm(n, axis=1); ok = nl > 1e-9
    n[ok] /= nl[ok][:, None]
    L = np.array(light, float); L /= np.linalg.norm(L)
    cam = R[2]
    n[(n @ cam) < 0] *= -1
    shade = 0.35 + 0.65 * np.clip(n @ L, 0, 1)
    zbuf = np.full((H, W), -1e18)
    img = np.tile(np.array(bg, float), (H, W, 1))
    nid = np.full((H, W), -1, dtype=np.int64)
    for i in np.argsort(S[:, :, 2].mean(1)):
        if not ok[i]:
            continue
        p = S[i]
        x0, x1 = int(max(0, math.floor(p[:, 0].min()))), int(min(W - 1, math.ceil(p[:, 0].max())))
        y0, y1 = int(max(0, math.floor(p[:, 1].min()))), int(min(H - 1, math.ceil(p[:, 1].max())))
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = p[0, :2], p[1, :2], p[2, :2]
        det = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if abs(det) < 1e-9:
            continue
        l1 = ((bx - xs) * (cy - ys) - (cx - xs) * (by - ys)) / det
        l2 = ((cx - xs) * (ay - ys) - (ax - xs) * (cy - ys)) / det
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if not inside.any():
            continue
        depth = l1 * p[0, 2] + l2 * p[1, 2] + l3 * p[2, 2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = inside & (depth > sub)
        sub[upd] = depth[upd]
        img[y0:y1 + 1, x0:x1 + 1][upd] = (C[i] * shade[i])[None, :]
        nid[y0:y1 + 1, x0:x1 + 1][upd] = i
    if edges:
        d = zbuf.copy(); d[d < -1e17] = np.nan
        dz = np.zeros_like(d, dtype=bool)
        for ax_ in (0, 1):
            g = np.abs(np.diff(d, axis=ax_))
            mask = np.nan_to_num(g, nan=1e9) > 1.8 / max(scale, 1e-6)
            if ax_ == 0:
                dz[1:, :] |= mask
            else:
                dz[:, 1:] |= mask
        normals = n[np.where(nid >= 0, nid, 0)]
        for ax_ in (0, 1):
            dotp = (normals[1:, :] * normals[:-1, :]).sum(-1) if ax_ == 0 else (normals[:, 1:] * normals[:, :-1]).sum(-1)
            idd = (nid[1:, :] != nid[:-1, :]) if ax_ == 0 else (nid[:, 1:] != nid[:, :-1])
            m = (dotp < 0.80) & idd
            if ax_ == 0:
                dz[1:, :] |= m
            else:
                dz[:, 1:] |= m
        dz &= nid >= 0
        img[dz] = img[dz] * 0.35
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    if title:
        dr = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            font = ImageFont.load_default()
        dr.text((16, 12), title, fill=(30, 30, 30), font=font)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    im.save(path)
    return scale


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fc_lib import box, cyl, cut
    s = cut(box(0, 0, 0, 40, 30, 8), cyl(5, 20, (20, 15, -1)))
    out = os.path.join(tempfile.gettempdir(), "fc_render_demo.png")
    render([(s, (120, 160, 220))], out, "iso", title="fc_render self-test")
    print("wrote", out)
