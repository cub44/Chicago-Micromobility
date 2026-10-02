"""The boundary and population inputs the other steps share (data/interim/geo/).

  suburbs.geojson            Evanston (78) and Oak Park (79), where Divvy has had stations, from the Census
                             Bureau's 2020 place shapes, numbered after Chicago's 77 community areas
  blocks_assigned.npz        every 2020 Cook County census block: population, interior point, and the community
                             area and 2023 ward that point falls in; its tract is the first 11 digits of its GEOID
  tracts2020_clipped.geojson the Census Bureau's 2020 tracts that hold a Chicago block, clipped to the city (the
                             City's own tract file leaves out 10 tracts with Chicago blocks, three on the lakefront)
  block_place.npy            for each block, 78 or 79 where its interior point is in Evanston or Oak Park
  suburb_tracts.geojson      the tracts holding Evanston or Oak Park blocks, cut to each place, with the
                             population of the place's blocks in them (pieces under 5,000 square meters dropped)

Tracts are taken in the order the earlier pulls returned them: Chicago's in sorted batches of 150 GEOIDs, each
batch in the layer's own order, and the suburbs' in the layer's order.
"""
import glob, json, collections
import numpy as np, shapely
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union
from schema import interim, raw

KX, KY = 111320 * np.cos(np.radians(41.85)), 110574.0
P = lambda x, y, z=None: (np.asarray(x) * KX, np.asarray(y) * KY)
load = lambda path: json.load(open(path, encoding="utf-8"))

# ---------- Evanston and Oak Park ----------
out = []
for f in load(raw("census", "tigerweb_2020_places_evanston_oakpark.geojson"))["features"]:
    n = f["properties"]["NAME"]
    num, name = (78, "EVANSTON") if n.startswith("Evanston") else (79, "OAK PARK")
    out.append({"type": "Feature", "properties": {"area_numbe": str(num), "community": name, "geoid": f["properties"]["GEOID"],
                                                  "pop100": f["properties"]["POP100"]}, "geometry": f["geometry"]})
with open(interim("geo", "suburbs.geojson"), "w", encoding="utf-8") as fh:
    json.dump({"type": "FeatureCollection", "features": out}, fh)
print("suburbs", [(x["properties"]["area_numbe"], x["properties"]["community"]) for x in out])

# ---------- census blocks: placed by interior point ----------
blocks = [f["attributes"] for p in sorted(glob.glob(raw("census", "tigerweb_2020_blocks_cook-*.json")))
          for f in load(p)["features"]]
assert len({b["GEOID"] for b in blocks}) == len(blocks), "a block appears twice across the pages"
lat = np.array([float(b["INTPTLAT"]) for b in blocks]); lng = np.array([float(b["INTPTLON"]) for b in blocks])
pop = np.array([int(b["POP100"] or 0) for b in blocks]); geoid = [b["GEOID"] for b in blocks]
pts = shapely.points(lng * KX, lat * KY)


def assign(path, key):
    feats = load(path)["features"]
    geoms = [transform(P, shape(f["geometry"])) for f in feats]
    keys = [str(f["properties"][key]).split(".")[0] for f in feats]
    tree = shapely.STRtree(geoms)
    v = np.array([""] * len(pts), dtype=object)
    ip, ig = tree.query(pts, predicate="within")
    v[ip] = [keys[i] for i in ig]
    return v


ca = assign(raw("city", "igwz-8jzy.geojson"), "area_numbe")
ward = assign(raw("city", "p293-wvbd.geojson"), "ward")
tract = np.array([g[:11] for g in geoid], dtype=object)
inchi = ca != ""
print("blocks", len(blocks), "inside a community area", int(inchi.sum()), "population", int(pop[inchi].sum()))
np.savez(interim("geo", "blocks_assigned.npz"), pop=pop, ca=ca.astype(str), ward=ward.astype(str), tract=tract.astype(str), lat=lat, lng=lng)

# ---------- tracts ----------
cook = [f for p in sorted(glob.glob(raw("census", "tigerweb_2020_tracts_cook-*.geojson"))) for f in load(p)["features"]]
by_geoid = {f["properties"]["GEOID"]: f for f in cook}
assert len(by_geoid) == len(cook), "a tract appears twice across the pages"
order = {f["properties"]["GEOID"]: i for i, f in enumerate(cook)}
chicago = sorted(set(tract[inchi]))
missing = [t for t in chicago if t not in by_geoid]
assert not missing, f"tracts with Chicago blocks missing from the pull: {missing[:5]}"
tr = [by_geoid[t] for i in range(0, len(chicago), 150) for t in sorted(chicago[i:i + 150], key=order.get)]
city = unary_union([shape(f["geometry"]) for f in load(raw("city", "igwz-8jzy.geojson"))["features"]]).buffer(0)
clipped = []
for f in tr:
    g = shape(f["geometry"]).buffer(0).intersection(city)
    if g.is_empty or transform(P, g).area < 1.0: continue
    g = g if g.geom_type in ("Polygon", "MultiPolygon") else unary_union([x for x in getattr(g, "geoms", [g]) if x.geom_type in ("Polygon", "MultiPolygon")])
    clipped.append({"type": "Feature", "properties": {"GEOID": f["properties"]["GEOID"], "NAME": f["properties"]["NAME"]}, "geometry": mapping(g)})
with open(interim("geo", "tracts2020_clipped.geojson"), "w", encoding="utf-8") as fh:
    json.dump({"type": "FeatureCollection", "features": clipped}, fh)
print("clipped tracts", len(clipped), "of", len(tr))

# ---------- Evanston and Oak Park blocks and tracts ----------
sub = {f["properties"]["area_numbe"]: (f["properties"]["community"], shape(f["geometry"])) for f in out}
upts = shapely.points(lng, lat)
place_of = np.array([""] * len(blocks), dtype=object)
for k, (name, g) in sub.items():
    place_of[shapely.contains(g, upts)] = k
tp = collections.Counter()
for t, k, p in zip(tract, place_of, pop):
    if k: tp[(t, k)] += int(p)
tids = {t for t, k in tp}
pieces = []
for f in sorted((by_geoid[t] for t in tids), key=lambda f: order[f["properties"]["GEOID"]]):
    g = shape(f["geometry"]).buffer(0)
    for k, (name, pg) in sub.items():
        part = g.intersection(pg)
        if part.is_empty or transform(P, part).area < 5000: continue
        pieces.append({"type": "Feature", "properties": {"GEOID": f["properties"]["GEOID"], "NAME": f["properties"]["NAME"], "place": k,
                                                        "place_name": name.title(), "pop": tp.get((f["properties"]["GEOID"], k), 0)},
                       "geometry": mapping(part)})
with open(interim("geo", "suburb_tracts.geojson"), "w", encoding="utf-8") as fh:
    json.dump({"type": "FeatureCollection", "features": pieces}, fh)
np.save(interim("geo", "block_place.npy"), place_of.astype(str))
print("suburb tract pieces", len(pieces), "population", sum(f["properties"]["pop"] for f in pieces))
