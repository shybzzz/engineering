"""Inspect STL files with the stdlib only (no numpy/trimesh needed).

Usage:  python -I stl_info.py <file.stl> [more.stl ...] [--parts]

Prints, per file: triangle count, bounding box, size, z-min (meshes are often NOT on
Z=0), signed volume, number of non-manifold edges and (with --parts) the number of
connected shells. Exit code 1 if any file is non-manifold or has negative volume.

Binary STL: 80-byte header, uint32 triangle count, then 50 bytes per triangle
(normal 3f, three vertices 9f, uint16 attribute). ASCII STL is detected by the
"solid" prefix and a parsable "facet" body.
"""
import struct, sys, os
from collections import defaultdict


def read_stl(path):
    with open(path, "rb") as f:
        data = f.read()
    tris = []
    if data[:5] == b"solid" and b"facet" in data[:1000]:
        nums = []
        for line in data.decode("ascii", "replace").splitlines():
            parts = line.split()
            if parts and parts[0] == "vertex":
                nums.append(tuple(float(v) for v in parts[1:4]))
        tris = [tuple(nums[i:i + 3]) for i in range(0, len(nums) - 2, 3)]
        return data[:80].rstrip(b"\0 ").decode("ascii", "replace"), tris
    n = struct.unpack_from("<I", data, 80)[0]
    off = 84
    for _ in range(n):
        v = struct.unpack_from("<12f", data, off)
        tris.append(((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])))
        off += 50
    return data[:80].rstrip(b"\0 ").decode("ascii", "replace"), tris


def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]


def analyse(tris, want_parts=False):
    xs = [p[0] for t in tris for p in t]; ys = [p[1] for t in tris for p in t]; zs = [p[2] for t in tris for p in t]
    bbox = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
    vol = sum(dot(a, cross(b, c)) for a, b, c in tris) / 6.0
    edges = defaultdict(int)
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            edges[(u, v)] += 1
    bad = sum(1 for e, n in edges.items() if n != 1 or edges.get((e[1], e[0]), 0) != 1)
    parts = None
    if want_parts:
        parent = {}
        def find(x):
            while parent.setdefault(x, x) != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for a, b, c in tris:
            ra, rb, rc = find(a), find(b), find(c)
            parent[rb] = ra; parent[find(rc)] = find(ra)
        parts = len({find(v) for v in list(parent)})
    return bbox, vol, bad, parts


def main(argv):
    want_parts = "--parts" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print(__doc__); return 2
    rc = 0
    print(f"{'file':40s} {'tris':>8s} {'size x*y*z (mm)':>24s} {'z-min':>8s} {'vol cm3':>9s} {'bad edges':>9s}" + ("  parts" if want_parts else ""))
    for path in files:
        header, tris = read_stl(path)
        if not tris:
            print(f"{os.path.basename(path):40s}  (empty)"); rc = 1; continue
        bbox, vol, bad, parts = analyse(tris, want_parts)
        size = f"{bbox[3]-bbox[0]:.2f}*{bbox[4]-bbox[1]:.2f}*{bbox[5]-bbox[2]:.2f}"
        line = f"{os.path.basename(path)[:40]:40s} {len(tris):8d} {size:>24s} {bbox[2]:8.2f} {vol/1000:9.2f} {bad:9d}"
        if want_parts: line += f"  {parts}"
        print(line)
        if bad or vol <= 0: rc = 1
    if rc:
        print("WARNING: non-manifold edges or non-positive volume -> fix before slicing (check winding / duplicate vertices)")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
