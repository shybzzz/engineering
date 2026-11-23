"""Triage of a received 3D model WITHOUT a CAD kernel (stdlib only): what kind of file is it, will a
CAD program read it, and what is wrong with the triangles inside.

    python -I mesh_probe.py part.step other.stl            # report per file
    python -I mesh_probe.py part.step --json report.json   # the same as JSON
    python -I mesh_probe.py part.step --stl rescued.stl    # write the triangles out as binary STL
    python    mesh_probe.py part.step --section x=0 cut.png  # section on a mm grid (needs PIL, e.g. FreeCAD's python)
    python -I mesh_probe.py                                 # self-test

Reads: STEP (header, units, entity census; triangles when the file is a faceted list: POLY_LOOP),
binary / ASCII STL. For a STEP that holds a real or mesh-derived B-rep (ADVANCED_FACE) it reports the
census only - load that one in the CAD kernel (fc_fix.py check).

Triangle report: welded points, free / non-manifold / mis-oriented edges, degenerate faces, shells,
genus (= number of through holes of a closed shell), signed volume, bounding box, and - for bodies
of revolution - the axis, the number of segments per circle and the (z, radius) profile to rebuild from.
"""
import collections, json, math, os, re, struct, sys, tempfile

sys.dont_write_bytecode = True


# ------------------------------------------------------------------ STEP
def step_census(txt):
    flat = txt.replace("\r", "").replace("\n", "")
    hdr = {}
    m = re.search(r"FILE_DESCRIPTION\s*\(\s*\(([^)]*)\)", flat)
    hdr["description"] = m.group(1).strip("' ") if m else ""
    m = re.search(r"FILE_NAME\s*\((.*?)\)\s*;", flat)
    if m:
        f = re.findall(r"'([^']*)'", m.group(1))
        hdr["name"], hdr["date"] = (f + ["", ""])[:2]
        hdr["author_org_system"] = [x for x in f[2:] if x]
    m = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']*)'", flat)
    hdr["schema"] = m.group(1) if m else ""
    ents = collections.Counter(re.findall(r"#\d+\s*=\s*([A-Z_0-9]+)\s*\(", flat))
    units = "unknown"
    if re.search(r"SI_UNIT\s*\(\s*\.MILLI\.\s*,\s*\.METRE\.", flat): units = "mm"
    elif re.search(r"CONVERSION_BASED_UNIT\s*\(\s*'INCH'", flat, re.I): units = "inch"
    elif re.search(r"SI_UNIT\s*\(\s*\$\s*,\s*\.METRE\.", flat): units = "m"
    pts = {int(i): tuple(float(v) for v in c.split(","))
           for i, c in re.findall(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(([^)]*)\)\s*\)", flat) if c.count(",") == 2}
    loops = [[int(v.strip()[1:]) for v in c.split(",")]
             for c in re.findall(r"=\s*POLY_LOOP\s*\(\s*'[^']*'\s*,\s*\(([^)]*)\)\s*\)", flat)]
    faces_with_surface = ents["ADVANCED_FACE"] + ents["FACE_SURFACE"]
    curved = sum(ents[k] for k in ents if k.endswith("_SURFACE") and k not in ("FACE_SURFACE",)) + ents["B_SPLINE_SURFACE_WITH_KNOTS"]
    if loops and faces_with_surface == 0:
        kind = "faceted-no-surfaces"
        verdict = ("a list of polygons (POLY_LOOP) whose FACE entities carry no surface: Open CASCADE based readers "
                   "(seen with FreeCAD 1.0 and PrusaSlicer) give an EMPTY shape. Work from the triangles below.")
    elif loops:
        kind = "faceted"
        verdict = "faceted B-rep (planar polygons); may load, but it is a mesh, not CAD geometry"
    elif faces_with_surface > 100 and curved == 0 and ents["PLANE"] >= 0.9 * faces_with_surface:
        kind = "mesh-derived-brep"
        verdict = ("every face is planar and there are hundreds of them: a mesh converted to B-rep. Expect unsewn edges; "
                   "check it in the CAD kernel (fc_fix.py check)")
    else:
        kind = "brep"
        verdict = "B-rep with analytic surfaces; check it in the CAD kernel (fc_fix.py check)"
    used = sorted({i for l in loops for i in l}) or sorted(pts)
    span = None
    if used:
        P = [pts[i] for i in used if i in pts]
        span = [round(max(p[a] for p in P) - min(p[a] for p in P), 6) for a in range(3)]
    scale_hint = ""
    if span and units == "mm" and max(span) < 2.0:
        scale_hint = "declared mm but the whole model spans %.3g: probably metres (x1000) or inches written as mm - confirm one real dimension" % max(span)
    return {"header": hdr, "schema_units": units, "entities": dict(ents.most_common(12)), "kind": kind, "verdict": verdict,
            "coordinate_span": span, "scale_hint": scale_hint}, pts, loops


def step_triangles(pts, loops):
    tris = []
    for l in loops:
        p = [pts[i] for i in l]
        for j in range(1, len(p) - 1):
            tris.append((p[0], p[j], p[j + 1]))
    return tris


# ------------------------------------------------------------------ STL
def read_stl(path):
    raw = open(path, "rb").read()
    n = struct.unpack("<I", raw[80:84])[0] if len(raw) >= 84 else -1
    if len(raw) == 84 + 50 * n:
        return [tuple(struct.unpack_from("<3f", raw, 84 + 50 * i + 12 + 12 * k) for k in range(3)) for i in range(n)]
    v = [tuple(float(x) for x in m) for m in re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", raw.decode("ascii", "replace"))]
    return [tuple(v[i:i + 3]) for i in range(0, len(v) - 2, 3)]


def write_stl(path, tris, header="rescued triangles"):
    with open(path, "wb") as f:
        f.write(header.encode("ascii", "replace")[:80].ljust(80, b" ")); f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            u = [b[i] - a[i] for i in range(3)]; w = [c[i] - a[i] for i in range(3)]
            n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
            L = math.sqrt(sum(x * x for x in n)) or 1.0
            f.write(struct.pack("<12fH", *[x / L for x in n], *a, *b, *c, 0))


# ------------------------------------------------------------------ analysis
def analyse(tris, weld=1e-4):
    """Topology and size of a triangle soup; points closer than `weld` are one vertex."""
    key = lambda p: tuple(int(round(v / weld)) for v in p)
    ids, V, T = {}, [], []
    degenerate = 0
    for t in tris:
        tri = []
        for p in t:
            k = key(p)
            if k not in ids:
                ids[k] = len(V); V.append(p)
            tri.append(ids[k])
        if len(set(tri)) < 3:
            degenerate += 1
            continue
        T.append(tuple(tri))
    und, dirn = collections.Counter(), collections.Counter()
    vol = area = 0.0
    parent = list(range(len(V)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a, b, c in T:
        for i, j in ((a, b), (b, c), (c, a)):
            und[(min(i, j), max(i, j))] += 1; dirn[(i, j)] += 1
        parent[find(b)] = find(a); parent[find(c)] = find(a)
        pa, pb, pc = V[a], V[b], V[c]
        u = [pb[i] - pa[i] for i in range(3)]; w = [pc[i] - pa[i] for i in range(3)]
        n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        area += math.sqrt(sum(x * x for x in n)) / 2
        vol += (pa[0] * n[0] + pa[1] * n[1] + pa[2] * n[2]) / 6
    free = sum(1 for v in und.values() if v == 1)
    nonman = sum(1 for v in und.values() if v > 2)
    misor = sum(1 for v in dirn.values() if v > 1)
    shells = len({find(i) for i in range(len(V))})
    r = {"triangles": len(T), "degenerate_triangles": degenerate, "points": len(V), "edges": len(und),
         "free_edges": free, "non_manifold_edges": nonman, "misoriented_edges": misor, "shells": shells,
         "closed_manifold": free == 0 and nonman == 0, "signed_volume": round(vol, 3), "area": round(area, 3)}
    if V:
        r["bbox_min"] = [round(min(p[a] for p in V), 4) for a in range(3)]
        r["bbox_max"] = [round(max(p[a] for p in V), 4) for a in range(3)]
        r["size"] = [round(r["bbox_max"][a] - r["bbox_min"][a], 4) for a in range(3)]
    if r["closed_manifold"] and T:
        chi = len(V) - len(und) + len(T)
        r["euler"] = chi
        g = (2 * shells - chi) / 2
        r["through_holes_total"] = int(g) if g == int(g) else g
    r["problems"] = problems(r)
    return r, V, T


def problems(r):
    out = []
    if r["triangles"] == 0: out.append("no triangles")
    if r["free_edges"]: out.append("%d free edges: the surface is open" % r["free_edges"])
    if r["non_manifold_edges"]: out.append("%d edges shared by more than two faces" % r["non_manifold_edges"])
    if r["misoriented_edges"]: out.append("%d edges walked twice in the same direction: flipped faces" % r["misoriented_edges"])
    if r["degenerate_triangles"]: out.append("%d degenerate triangles" % r["degenerate_triangles"])
    if r["shells"] > 1: out.append("%d separate shells in one file" % r["shells"])
    if r["closed_manifold"] and r["signed_volume"] < 0: out.append("negative volume: normals point inwards")
    if r.get("bbox_min") and abs(r["bbox_min"][2]) > 1e-3: out.append("lowest point at z = %g, not on z = 0" % r["bbox_min"][2])
    return out


def revolution(V, min_segments=8):
    """Is the vertex cloud a body of revolution made of n-gons? -> axis, n and the (height, radius) profile."""
    best = None
    for ax in (2, 1, 0):
        o = [a for a in range(3) if a != ax]
        c = [sum(p[o[0]] for p in V) / len(V), sum(p[o[1]] for p in V) / len(V)]
        rings = collections.defaultdict(list)
        for p in V:
            rings[round(p[ax] / 0.05)].append(math.hypot(p[o[0]] - c[0], p[o[1]] - c[1]))
        counts, profile, on_axis = collections.Counter(), [], 0
        for h in sorted(rings):
            rs = sorted(rings[h]); cl = [[rs[0]]]
            for x in rs[1:]:
                if x - cl[-1][-1] <= 0.02 + 0.002 * x: cl[-1].append(x)
                else: cl.append([x])
            for g in cl:
                if g[-1] < 1e-3: on_axis += len(g); continue
                counts[len(g)] += len(g)
                profile.append((round(h * 0.05, 2), round(sum(g) / len(g), 3), len(g)))
        if not counts:
            continue
        n, covered = max(counts.items(), key=lambda kv: kv[1])
        # several stacked rings fall into one height bin: accept multiples of n as well
        covered = sum(v for k, v in counts.items() if k % n == 0)
        share = (covered + on_axis) / len(V)
        if n >= min_segments and (best is None or share > best["share"]):
            rmax = max(p[1] for p in profile)
            best = {"axis": "xyz"[ax], "centre": [round(c[0], 4), round(c[1], 4)], "segments": n, "share": round(share, 3),
                    "max_radius": rmax, "chord_error_at_max_radius": round(rmax * (1 - math.cos(math.pi / n)), 3),
                    "volume_factor_polygon_over_circle": round(math.sin(2 * math.pi / n) / (2 * math.pi / n), 5),
                    "profile_height_radius_count": profile}
    return best if best and best["share"] >= 0.9 else None


def section_png(path, parts, axis, value):
    """parts: [(name, V, T)]. Cut by the plane axis = value; picture axes are the other two, mm grid."""
    from PIL import Image, ImageDraw
    ax = "xyz".index(axis); o = [a for a in range(3) if a != ax]
    cols = [(60, 110, 190), (200, 60, 50), (40, 150, 110), (220, 150, 40), (130, 80, 170)]
    segs = []
    for k, (_, V, T) in enumerate(parts):
        for t in T:
            p = [V[i] for i in t]; s = [q[ax] - value - 1.234e-7 for q in p]; hit = []
            for i in range(3):
                a, b, sa, sb = p[i], p[(i + 1) % 3], s[i], s[(i + 1) % 3]
                if (sa < 0) != (sb < 0):
                    f = sa / (sa - sb); hit.append((a[o[0]] + f * (b[o[0]] - a[o[0]]), a[o[1]] + f * (b[o[1]] - a[o[1]])))
            if len(hit) == 2: segs.append((hit, cols[k % len(cols)]))
    assert segs, "the plane misses the model"
    h0 = math.floor(min(q[0] for s, _ in segs for q in s)) - 2; h1 = math.ceil(max(q[0] for s, _ in segs for q in s)) + 2
    v0 = math.floor(min(q[1] for s, _ in segs for q in s)) - 2; v1 = math.ceil(max(q[1] for s, _ in segs for q in s)) + 2
    sc = max(2.0, min(40.0, 1800.0 / max(h1 - h0, v1 - v0)))
    W, H = int((h1 - h0) * sc), int((v1 - v0) * sc)
    im = Image.new("RGB", (W, H), (250, 250, 248)); d = ImageDraw.Draw(im)
    step = 1 if sc >= 10 else (5 if sc >= 3 else 10)
    for g in range(int(h0), int(h1) + 1):
        if g % step == 0:
            bold = g % (step * 5) == 0
            d.line([((g - h0) * sc, 0), ((g - h0) * sc, H)], fill=(150, 150, 150) if bold else (218, 218, 218))
            if bold: d.text(((g - h0) * sc + 2, H - 12), str(g), fill=(80, 80, 80))
    for g in range(int(v0), int(v1) + 1):
        if g % step == 0:
            bold = g % (step * 5) == 0
            d.line([(0, H - (g - v0) * sc), (W, H - (g - v0) * sc)], fill=(150, 150, 150) if bold else (218, 218, 218))
            if bold: d.text((2, H - (g - v0) * sc - 12), str(g), fill=(80, 80, 80))
    for (a, b), col in segs:
        d.line([((a[0] - h0) * sc, H - (a[1] - v0) * sc), ((b[0] - h0) * sc, H - (b[1] - v0) * sc)], fill=col, width=3)
    d.text((4, 2), "section %s = %g ; horizontal %s, vertical %s, mm" % (axis, value, "xyz"[o[0]], "xyz"[o[1]]), fill=(0, 0, 0))
    im.save(path)
    return len(segs)


def probe(path):
    rep = {"file": os.path.basename(path)}
    tris = None
    if path.lower().endswith((".step", ".stp")):
        cen, pts, loops = step_census(open(path, encoding="utf-8", errors="replace").read())
        rep.update(cen)
        if loops: tris = step_triangles(pts, loops)
    else:
        rep["kind"] = "stl"; tris = read_stl(path)
    V = T = None
    if tris is not None:
        rep["mesh"], V, T = analyse(tris)
        rev = revolution(V) if V else None
        if rev: rep["revolution"] = rev
    return rep, V, T


def _print(rep):
    print("==", rep["file"], "-", rep["kind"])
    if "verdict" in rep:
        h = rep["header"]
        print("   written by:", ", ".join(h.get("author_org_system", [])) or "?", "| schema", h["schema"], "| units", rep["schema_units"], "|", h["description"])
        print("   ", rep["verdict"])
        if rep["scale_hint"]: print("   SCALE:", rep["scale_hint"])
    m = rep.get("mesh")
    if m:
        print("   %d triangles, %d points, shells %d, closed manifold %s, through holes %s, size %s, volume %s" %
              (m["triangles"], m["points"], m["shells"], m["closed_manifold"], m.get("through_holes_total", "?"), m.get("size"), m["signed_volume"]))
        for p in m["problems"]: print("   PROBLEM:", p)
    r = rep.get("revolution")
    if r:
        print("   body of revolution about %s: every circle is a %d-gon, chord error %.3f at r = %.2f" %
              (r["axis"], r["segments"], r["chord_error_at_max_radius"], r["max_radius"]))
        print("   profile (height, radius, points): " + "  ".join("(%g, %g, %d)" % p for p in r["profile_height_radius_count"]))


def _selftest():
    # a 16-gon tube, 10 high, r 5, with a 16-gon hole r 2 whose wall is closed by a cap BELOW the bottom
    # (the classic "hole drawn, not cut"), written as a faceted STEP with surfaceless FACEs
    n, pts, loops = 16, [], []
    ring = lambda r, z: [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n)]

    def add(p):
        pts.append(p); return len(pts) + 100
    R = [[add(p) for p in ring(*a)] for a in ((5, 0), (5, 10), (2, 10), (2, -0.2))]
    for a, b in zip(R, R[1:]):
        for i in range(n):
            j = (i + 1) % n
            loops.append((a[i], a[j], b[j])); loops.append((a[i], b[j], b[i]))
    for i in range(1, n - 1):
        loops.append((R[0][0], R[0][i + 1], R[0][i])); loops.append((R[3][0], R[3][i], R[3][i + 1]))
    txt = ["ISO-10303-21;", "HEADER;", "FILE_DESCRIPTION(('selftest - faceted B-rep, mm'),'2;1');",
           "FILE_NAME('t.step','2000-01-01',('someone'),('somewhere'),'','','');", "FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));", "ENDSEC;", "DATA;",
           "#10=(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.));"]
    txt += ["#%d=CARTESIAN_POINT('',(%.4f,%.4f,%.4f));" % (i + 101, *p) for i, p in enumerate(pts)]
    k = 5000
    for l in loops:
        txt += ["#%d=POLY_LOOP('',(%s));" % (k, ",".join("#%d" % i for i in l)), "#%d=FACE_OUTER_BOUND('',#%d,.T.);" % (k + 1, k), "#%d=FACE('',(#%d));" % (k + 2, k + 1)]
        k += 3
    txt += ["ENDSEC;", "END-ISO-10303-21;"]
    d = tempfile.mkdtemp(prefix="mesh_probe_")
    p = os.path.join(d, "t.step")
    open(p, "w").write("\n".join(txt))
    rep, V, T = probe(p)
    _print(rep)
    m = rep["mesh"]
    assert rep["kind"] == "faceted-no-surfaces" and rep["schema_units"] == "mm"
    assert m["closed_manifold"] and m["through_holes_total"] == 0, m          # a tube should have 1: the hole is capped
    assert any("not on z = 0" in x for x in m["problems"]), m["problems"]
    assert rep["revolution"]["segments"] == 16 and rep["revolution"]["axis"] == "z", rep["revolution"]
    s = os.path.join(d, "t.stl"); write_stl(s, [tuple(V[i] for i in t) for t in T])
    rep2, _, _ = probe(s)
    assert rep2["mesh"]["triangles"] == m["triangles"] and abs(rep2["mesh"]["signed_volume"] - m["signed_volume"]) < 0.01
    try:
        assert section_png(os.path.join(d, "t.png"), [("t", V, T)], "x", 0.0) > 0
    except ImportError:
        print("   (PIL not available: section skipped)")
    print("mesh_probe self-test OK ->", d)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        _selftest(); sys.exit(0)
    opt = {}
    for flag, nargs in (("--json", 1), ("--stl", 1), ("--section", 2)):
        if flag in a:
            i = a.index(flag); opt[flag] = a[i + 1:i + 1 + nargs]; del a[i:i + 1 + nargs]
    reps, parts = [], []
    for f in a:
        rep, V, T = probe(f)
        reps.append(rep); _print(rep)
        if V: parts.append((rep["file"], V, T))
    if "--json" in opt:
        json.dump(reps, open(opt["--json"][0], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if "--stl" in opt and parts:
        write_stl(opt["--stl"][0], [tuple(V[i] for i in t) for _, V, T in parts for t in T])
    if "--section" in opt and parts:
        ax, val = opt["--section"][0].split("=")
        print("section segments:", section_png(opt["--section"][1], parts, ax, float(val)))
