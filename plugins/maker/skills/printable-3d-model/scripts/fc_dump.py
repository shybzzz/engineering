"""Dump a FreeCAD document or a STEP file to JSON (+ one STL per body) for inspection and for
render / check scripts that must not hard-code dimensions.

    python.exe -B fc_dump.py <model.FCStd|.step> <out_dir> [name]

FCStd -> <out_dir>/<name>.json with
  params    {alias: value}            every aliased Spreadsheet cell (numbers; angles in degrees)
  formulas  {alias: "=..."}           the cells that are formulas
  bodies    {label: size, bbox, volume, faces, solids, valid, features}
  objects   [name, label, type, expressions, feature properties, named sketch constraints]
and <out_dir>/<label>.stl per body. Read `params` in the renderer instead of repeating numbers
there: then one script serves every variant of the model. Different models export STL files
with the same body names - give each model an output folder of its own.

STEP -> <out_dir>/<name>.json with the bbox, volume and EVERY face (surface type, area, bbox,
mid normal; radius / axis / centre of cylinders, cones, tori, spheres) plus the distinct
circular edges, and <out_dir>/<name>.stl. This is how a part that exists only as STEP is
measured: read planes and radii from the faces, then confirm with sections.

Self-test: python.exe -B fc_dump.py
"""
import json, os, shutil, sys, tempfile

sys.dont_write_bytecode = True
try:
    import FreeCAD
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fc_lib import FreeCAD
import Part, MeshPart  # noqa: E402


def _v3(v, nd=4):
    return [round(v.x, nd), round(v.y, nd), round(v.z, nd)]


def _bb(b, nd=4):
    return [round(x, nd) for x in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)]


def _stl(shape, dst, lin=0.02, ang=0.2):
    tmp = os.path.join(tempfile.mkdtemp(prefix="fc_dump_"), "out.stl")        # mesh writers and non-ASCII paths
    MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False).write(tmp)
    shutil.move(tmp, dst)


def is_formula(contents):
    """A cell holding a quantity reads back as "=15 deg": only what does not parse as a plain
    quantity is a formula."""
    c = str(contents)
    if not c.startswith("="):
        return False
    try:
        FreeCAD.Units.Quantity(c[1:])
        return False
    except Exception:
        return True


def dump_fcstd(path, out, name=None):
    doc = FreeCAD.openDocument(path); doc.recompute()
    res = {"file": os.path.basename(path), "params": {}, "formulas": {}, "bodies": {}, "objects": []}
    for o in doc.Objects:
        rec = {"name": o.Name, "label": o.Label, "type": o.TypeId, "valid": bool(o.isValid())}
        if o.TypeId == "Spreadsheet::Sheet":
            for cell in o.getUsedCells():
                alias = o.getAlias(cell)
                if not alias:
                    continue
                v = o.get(alias)
                res["params"][alias] = float(getattr(v, "Value", v)) if not isinstance(v, str) else v
                if is_formula(o.getContents(cell)):
                    res["formulas"][alias] = o.getContents(cell)
        if getattr(o, "ExpressionEngine", None):
            rec["expressions"] = [list(e) for e in o.ExpressionEngine]
        for p in ("Type", "Length", "Length2", "Angle", "Midplane", "Reversed", "Radius", "Size", "MapMode", "AttachmentOffset", "Placement"):
            if hasattr(o, p):
                rec[p] = str(getattr(o, p))
        if o.TypeId == "Sketcher::SketchObject":
            rec["geometry_count"] = o.GeometryCount
            rec["dof"] = o.solve()
            rec["constraints"] = [(c.Name, c.Type, c.Value) for c in o.Constraints if c.Name]
        if o.TypeId == "PartDesign::Body" and not o.Shape.isNull():
            s, b = o.Shape, o.Shape.BoundBox
            res["bodies"][o.Label] = {"bbox": _bb(b), "size": [round(b.XLength, 4), round(b.YLength, 4), round(b.ZLength, 4)],
                                      "volume_mm3": s.Volume, "area_mm2": s.Area, "faces": len(s.Faces), "solids": len(s.Solids),
                                      "valid": bool(s.isValid()), "tip": o.Tip.Name if o.Tip else None, "features": [f.Name for f in o.Group]}
            _stl(s, os.path.join(out, o.Label + ".stl"))
        res["objects"].append(rec)
    return res


def dump_step(path, out, name):
    tmp = os.path.join(tempfile.mkdtemp(prefix="fc_dump_"), "in.step")        # OCC readers and non-ASCII paths
    shutil.copyfile(path, tmp)
    s = Part.Shape(); s.read(tmp)
    res = {"file": os.path.basename(path), "bbox": _bb(s.BoundBox), "size": [round(s.BoundBox.XLength, 4), round(s.BoundBox.YLength, 4), round(s.BoundBox.ZLength, 4)],
           "volume_mm3": s.Volume, "area_mm2": s.Area, "solids": len(s.Solids), "faces_n": len(s.Faces), "edges_n": len(s.Edges),
           "valid": bool(s.isValid()), "faces": [], "circles": []}
    for i, f in enumerate(s.Faces):
        su = f.Surface
        t = type(su).__name__
        u0, u1, v0, v1 = f.ParameterRange
        rec = {"i": i + 1, "type": t, "area": round(f.Area, 4), "bbox": _bb(f.BoundBox), "wires": len(f.Wires), "edges": len(f.Edges),
               "normal_mid": _v3(f.normalAt((u0 + u1) / 2, (v0 + v1) / 2))}
        if t == "Cylinder":
            rec.update(radius=round(su.Radius, 4), axis=_v3(su.Axis), center=_v3(su.Center))
        elif t == "Toroid":
            rec.update(R=round(su.MajorRadius, 4), r=round(su.MinorRadius, 4), axis=_v3(su.Axis), center=_v3(su.Center))
        elif t == "Cone":
            rec.update(semi_angle_deg=round(su.SemiAngle * 57.29578, 3), axis=_v3(su.Axis), apex=_v3(su.Apex))
        elif t == "Sphere":
            rec.update(radius=round(su.Radius, 4), center=_v3(su.Center))
        res["faces"].append(rec)
    seen = set()
    for e in s.Edges:
        c = e.Curve
        if type(c).__name__ != "Circle":
            continue
        span = round((e.LastParameter - e.FirstParameter) * 57.29578, 2)
        key = (round(c.Radius, 3), tuple(_v3(c.Center, 3)), tuple(abs(x) for x in _v3(c.Axis, 3)), span)
        if key not in seen:
            seen.add(key)
            res["circles"].append({"r": round(c.Radius, 4), "center": _v3(c.Center), "axis": _v3(c.Axis), "span_deg": span})
    _stl(s, os.path.join(out, name + ".stl"), 0.01, 0.1)
    return res


def dump(path, out, name=None):
    os.makedirs(out, exist_ok=True)
    name = name or os.path.splitext(os.path.basename(path))[0]
    res = dump_step(path, out, name) if path.lower().endswith((".step", ".stp")) else dump_fcstd(path, out, name)
    with open(os.path.join(out, name + ".json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=str)
    return res


def _selftest():
    V = FreeCAD.Vector
    work = tempfile.mkdtemp(prefix="fc_dump_test_")
    doc = FreeCAD.newDocument("dump_demo")
    sheet = doc.addObject("Spreadsheet::Sheet", "Spreadsheet")
    for row, (alias, val) in enumerate((("width", "20"), ("angle", "15 deg"), ("half", "=width / 2")), 1):
        sheet.set("A%d" % row, alias); sheet.set("B%d" % row, val); sheet.setAlias("B%d" % row, alias)
    b = doc.addObject("PartDesign::Body", "Block")
    box = b.newObject("PartDesign::AdditiveBox", "Box")
    box.setExpression("Length", "Spreadsheet.width")
    doc.recompute()
    fc = os.path.join(work, "demo.FCStd"); doc.saveAs(fc); FreeCAD.closeDocument(doc.Name)
    r = dump(fc, os.path.join(work, "out"))
    assert r["params"] == {"width": 20.0, "angle": 15.0, "half": 10.0}, r["params"]
    assert list(r["formulas"]) == ["half"] and r["bodies"]["Block"]["size"][0] == 20.0 and os.path.getsize(os.path.join(work, "out", "Block.stl")) > 84
    st = os.path.join(work, "demo.step")
    Part.makeBox(20, 10, 5).cut(Part.makeCylinder(1.5, 9, V(10, 5, -2))).exportStep(st)
    r2 = dump(st, os.path.join(work, "out"), "old_part")
    cyl = [f for f in r2["faces"] if f["type"] == "Cylinder"]
    assert len(cyl) == 1 and cyl[0]["radius"] == 1.5 and r2["size"] == [20.0, 10.0, 5.0], r2["faces"]
    print("fc_dump self-test OK ->", work)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        _selftest(); sys.exit(0)
    r = dump(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    print("DONE ->", sys.argv[2], {k: r[k] for k in ("size", "faces_n") if k in r} or {"params": len(r["params"]), "bodies": list(r["bodies"])})
