"""Boundary file for the two Leaflet maps (data/interim/points/geo.json): community areas, 2023 wards, 2020 tracts (Census shapes
clipped to the city), each with its label, land area in square miles and 2020 census population."""
import json, os, collections
import numpy as np, shapely
from shapely.geometry import shape, mapping
from shapely.ops import transform
from schema import interim, raw
KX, KY = 111320 * np.cos(np.radians(41.85)), 110574.0
P = lambda x, y, z=None: (np.asarray(x) * KX, np.asarray(y) * KY)
SQMI = 2589988.11
disp = lambda v: {"OHARE": "O’Hare", "MCKINLEY PARK": "McKinley Park"}.get(v) or v.title()
# 2020 census population by block (TIGERweb POP100), placed by each block's interior point
b = np.load(interim("geo", "blocks_assigned.npz"), allow_pickle=True)
inchi = b["ca"] != ""
POP = {"ca": collections.Counter(), "ward": collections.Counter(), "tract": collections.Counter()}
for c, w, t, p in zip(b["ca"][inchi], b["ward"][inchi], b["tract"][inchi], b["pop"][inchi]):
    POP["ca"][str(c)] += int(p); POP["tract"][str(t)] += int(p)
    if w: POP["ward"][str(w)] += int(p)
# Evanston (78) and Oak Park (79): blocks by interior point in the Census place shapes (prep_geo.py)
place = np.load(interim("geo", "block_place.npy"), allow_pickle=True)
for k in ("78", "79"):
    n = int(b["pop"][place == k].sum()); POP["ca"][k] = n; POP["ward"][k] = n
def rnd(o):
    if isinstance(o, (list, tuple)):
        if o and isinstance(o[0], (int, float)): return [round(o[0], 5), round(o[1], 5)]
        return [rnd(x) for x in o]
    return o
def polys(g):
    """Polygon parts only: clipping can leave stray lines or points in a GeometryCollection."""
    if g.geom_type in ("Polygon", "MultiPolygon"): return g
    from shapely.ops import unary_union
    return unary_union([x for x in getattr(g, "geoms", []) if x.geom_type in ("Polygon", "MultiPolygon")])

def feat(g, fid, label, pop, tol, sub=False):
    g = polys(g)
    area = transform(P, g).area / SQMI
    m = mapping(g.simplify(tol, preserve_topology=True))
    return {"type": "Feature", "properties": {"id": fid, "label": label, "sqmi": round(area, 3), "pop": int(pop), **({"sub": True} if sub else {})},
            "geometry": {"type": m["type"], "coordinates": rnd(json.loads(json.dumps(m["coordinates"])))}}
ca_src = json.load(open(raw("city", "igwz-8jzy.geojson"), encoding="utf-8"))["features"]
ca_geom = {str(int(float(f["properties"]["area_numbe"]))): shape(f["geometry"]) for f in ca_src}
ca_name = {str(int(float(f["properties"]["area_numbe"]))): disp(f["properties"]["community"]) for f in ca_src}
ca_tree = shapely.STRtree(list(ca_geom.values())); ca_keys = list(ca_geom)
geo = {"ca": [feat(g, k, ca_name[k], POP["ca"][k], 0.00015) for k, g in ca_geom.items()], "ward": [], "tract": []}
for f in json.load(open(raw("city", "p293-wvbd.geojson"), encoding="utf-8"))["features"]:
    k = str(int(float(f["properties"]["ward"])))
    geo["ward"].append(feat(shape(f["geometry"]), k, f"Ward {k}", POP["ward"][k], 0.00015))
for f in json.load(open(interim("geo", "tracts2020_clipped.geojson"), encoding="utf-8"))["features"]:
    g = shape(f["geometry"]); k = f["properties"]["GEOID"]
    hits = ca_tree.query(g, predicate="intersects")
    where = max(hits, key=lambda h: ca_geom[ca_keys[h]].intersection(g).area) if len(hits) else None
    name = f["properties"]["NAME"].replace("Census Tract ", "Tract ")
    geo["tract"].append(feat(g, k, name + (f" ({ca_name[ca_keys[where]]})" if where is not None else ""), POP["tract"][k], 0.00008))
for f in json.load(open(interim("geo", "suburbs.geojson"), encoding="utf-8"))["features"]:
    k = f["properties"]["area_numbe"]; g = shape(f["geometry"]); name = disp(f["properties"]["community"])
    geo["ca"].append(feat(g, k, name, POP["ca"][k], 0.00015, sub=True))
    geo["ward"].append(feat(g, k, name, POP["ward"][k], 0.00015, sub=True))
for f in json.load(open(interim("geo", "suburb_tracts.geojson"), encoding="utf-8"))["features"]:
    pr = f["properties"]; POP["tract"][pr["GEOID"]] = pr["pop"]
    geo["tract"].append(feat(shape(f["geometry"]), pr["GEOID"], pr["NAME"].replace("Census Tract ", "Tract ") + f" ({pr['place_name']})", pr["pop"], 0.00008, sub=True))
epa = shape(json.load(open(raw("city", "mdn7-scnt.geojson"), encoding="utf-8"))["features"][0]["geometry"])
geo["epa"] = [feat(epa, "epa", "Equity Priority Area", 0, 0.00015)]
# Chicago's outline, for map 3's stations-only view: the community areas merged into one shape
from shapely.ops import unary_union
geo["city"] = [feat(unary_union(list(ca_geom.values())), "chicago", "Chicago", sum(POP["ca"][k] for k in ca_geom), 0.00015)]
out = {k: {"type": "FeatureCollection", "features": v} for k, v in geo.items()}
with open(interim("points", "geo.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, separators=(",", ":"))
for k, v in geo.items():
    print(k, len(v), "population", sum(f["properties"]["pop"] for f in v), "sq mi", round(sum(f["properties"]["sqmi"] for f in v), 1),
          "no residents", [f["properties"]["label"] for f in v if not f["properties"]["pop"]][:8])
print("bytes", os.path.getsize(interim("points", "geo.json")))
with open(interim("pop2020.json"), "w", encoding="utf-8") as fh:
    json.dump({k: dict(v) for k, v in POP.items()}, fh)
