"""Split an STL into its separate bodies and draw sections (for print-in-place models).

Usage:  python -P -E stl_bodies.py <file.stl> <out_dir> [--z 1,3.3,6] [--x 31,99] [--dpi 70]

Prints every body's bounding box / volume / watertightness, then writes
  <out_dir>/bodies_z.png   coloured top-view sections of all bodies at the given heights (mm above z-min)
  <out_dir>/sections_x.png YZ sections (all bodies) at the given X positions (mm from x-min)
Needs trimesh, shapely, matplotlib (user site-packages: run with -P -E, not -I).
"""
import argparse, os, sys

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS = ["#9ecae1", "#fdae6b", "#a1d99b", "#e377c2", "#c7c7c7", "#dbdb8d"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stl"); ap.add_argument("out")
    ap.add_argument("--z", default="1,3.3,6"); ap.add_argument("--x", default="")
    ap.add_argument("--dpi", type=int, default=70)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    m = trimesh.load(a.stl)
    m.apply_translation(-m.bounds[0])                 # origin at the min corner, z = 0
    bodies = sorted(m.split(only_watertight=False), key=lambda p: -p.volume)
    print(f"{os.path.basename(a.stl)}: size {np.round(m.extents, 2).tolist()} bodies {len(bodies)}")
    for i, b in enumerate(bodies):
        lo, hi = np.round(b.bounds, 2)
        print(f"  body {i}: min {lo.tolist()} max {hi.tolist()} vol {b.volume:.0f} mm3 faces {len(b.faces)} watertight {b.is_watertight}")

    zs = [float(v) for v in a.z.split(",") if v.strip()]
    fig, axes = plt.subplots(1, len(zs), figsize=(9 * len(zs), 8), squeeze=False)
    for ax, z in zip(axes[0], zs):
        for i, b in enumerate(bodies):
            s = b.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
            if s is None:
                continue
            p2, T = s.to_2D()
            for poly in p2.polygons_full:
                x, y = np.array(poly.exterior.xy)
                pts = np.c_[x, y, np.zeros_like(x), np.ones_like(x)] @ T.T
                ax.fill(pts[:, 0], pts[:, 1], color=COLS[i % len(COLS)], ec="k", lw=0.6, alpha=0.85)
                for h in poly.interiors:
                    x, y = np.array(h.xy)
                    pts = np.c_[x, y, np.zeros_like(x), np.ones_like(x)] @ T.T
                    ax.fill(pts[:, 0], pts[:, 1], color="white", ec="k", lw=0.6)
        ax.set_aspect("equal"); ax.grid(True, lw=0.3); ax.set_title(f"z = {z} mm (one colour per body)")
    plt.tight_layout(); plt.savefig(os.path.join(a.out, "bodies_z.png"), dpi=a.dpi)
    print("wrote", os.path.join(a.out, "bodies_z.png"))

    xs = [float(v) for v in a.x.split(",") if v.strip()]
    if xs:
        fig, axes = plt.subplots(len(xs), 1, figsize=(20, 4 * len(xs)), squeeze=False)
        for ax, x in zip(axes[:, 0], xs):
            for i, b in enumerate(bodies):
                s = b.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
                if s is None:
                    continue
                for ent in s.entities:
                    pts = s.vertices[ent.points]
                    ax.plot(pts[:, 1], pts[:, 2], color=COLS[i % len(COLS)].replace("#", "#"), lw=1.0)
            ax.set_aspect("equal"); ax.grid(True, lw=0.3); ax.set_title(f"YZ section at x = {x} mm")
        plt.tight_layout(); plt.savefig(os.path.join(a.out, "sections_x.png"), dpi=a.dpi)
        print("wrote", os.path.join(a.out, "sections_x.png"))


if __name__ == "__main__":
    sys.exit(main())
