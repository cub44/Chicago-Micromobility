"""The public release (public/): the City's e-scooter trip tables and 2020 population by area.

Only data the City of Chicago and the Census Bureau publish goes here. Nothing derived from Divvy's trip files
does, because the Divvy Data License Agreement bars republishing them: not the municipal bike trips, and not the
removal of municipal classic-bike rides from the City's "Lyft" rows, which needs those files.

    public/data/processed/   the CSVs and facts.json
    public/data/README.md    the data dictionary, with each file's row count
    public/checksums.sha256  every file in data/processed/, paths rooted there
"""
import csv, glob, hashlib, io, json, os
from collections import defaultdict
from schema import RELEASE_DATE, ROOT, SNAPSHOT, interim, raw

OUT = os.path.join(ROOT, "public")
PROC = os.path.join(OUT, "data", "processed")
TABLES = [("2kfw-zvte", False), ("3rse-fbp6", True), ("2i5w-ykuw", True)]     # (dataset, has a vendor field)
CLASSIC_FROM = "2024-07"         # the City's "Lyft" rows also hold municipal classic-bike rides from this month
city = lambda *p: json.load(open(raw("city", *p), encoding="utf-8"))
area = lambda v: str(int(float(v))) if v not in (None, "") else ""     # community area numbers as text; blank = none
month = lambda v: v[:7]

os.makedirs(PROC, exist_ok=True)
for old in glob.glob(os.path.join(PROC, "*")):
    os.remove(old)


def flags(m, vendor):
    """Pipe-delimited, alphabetical; registered in data/README.md."""
    out = []
    if vendor == "Lyft" and m >= CLASSIC_FROM:
        out.append("includes_classic_bike_rides")
    return "|".join(sorted(out))


def write_csv(name, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    with open(os.path.join(PROC, name), "w", encoding="utf-8", newline="") as fh:
        fh.write(buf.getvalue())
    return len(rows)


COUNTS = {}

# ---------- trips by year: as published, and what the table holds once negative durations are left out ----------
rows = []
for ds, _ in TABLES:
    kept = {r["yr"]: int(r["n"]) for r in city(f"{ds}_year.json")}
    for r in city(f"{ds}_removed.json"):
        rows.append([r["yr"], ds, int(r["n"]), int(r["short"]) - int(r["negative"]), int(r["negative"]), kept[r["yr"]],
                     "includes_classic_bike_rides" if ds == "2i5w-ykuw" and r["yr"] >= CLASSIC_FROM[:4] else ""])
rows.sort()
COUNTS["scooter_trips_year.csv"] = write_csv("scooter_trips_year.csv",
                                             ["year", "dataset", "trips_as_published", "under_60_seconds", "negative_duration", "trips", "flags"], rows)

# ---------- trips by month and vendor ----------
vm = defaultdict(int)
for ds, vend in TABLES:
    if not vend:
        for r in city(f"{ds}_month.json"):
            vm[(month(r["m"]), ds, "")] += int(r["n"])
    else:
        for r in city(f"{ds}_ca_month_s.json"):
            vm[(month(r["m"]), ds, r.get("vendor") or "")] += int(r["n"])
rows = [[m, ds, v, n, flags(m, v)] for (m, ds, v), n in sorted(vm.items())]
COUNTS["scooter_trips_month.csv"] = write_csv("scooter_trips_month.csv", ["month", "dataset", "vendor", "trips", "flags"], rows)

# ---------- trips by month, vendor and community area: starts, ends, and trips with both ends there ----------
am = defaultdict(lambda: [0, 0, 0])
for ds, vend in TABLES:
    for k, side in enumerate(("s", "e", "same")):
        for r in city(f"{ds}_ca_month_{side}.json"):
            am[(month(r["m"]), ds, (r.get("vendor") or "") if vend else "", area(r.get("ca")))][k] += int(r["n"])
rows = [[m, ds, v, a, *n, flags(m, v)] for (m, ds, v, a), n in sorted(am.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], (len(kv[0][3]), kv[0][3])))]
COUNTS["scooter_trips_area_month.csv"] = write_csv("scooter_trips_area_month.csv",
                                                   ["month", "dataset", "vendor", "community_area", "starts", "ends", "start_and_end", "flags"], rows)

# ---------- origin and destination by year, and by month ----------
oy = defaultdict(int)
for ds, vend in TABLES:
    for r in city(f"{ds}_od_ca_year_vendor.json" if vend else f"{ds}_od_ca_year.json"):
        oy[(r["yr"], ds, r.get("vendor") or "", area(r.get("s")), area(r.get("e")))] += int(r["n"])
sk = lambda a: (len(a), a)
rows = [[y, ds, v, s, e, n, "includes_classic_bike_rides" if v == "Lyft" and y >= CLASSIC_FROM[:4] else ""]
        for (y, ds, v, s, e), n in sorted(oy.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], sk(kv[0][3]), sk(kv[0][4])))]
COUNTS["scooter_trips_od_year.csv"] = write_csv("scooter_trips_od_year.csv",
                                                ["year", "dataset", "vendor", "start_community_area", "end_community_area", "trips", "flags"], rows)
om = defaultdict(int)
for ds, vend in TABLES:
    for p in sorted(glob.glob(raw("city", f"{ds}_od_ca_month", "*.json"))):
        for r in json.load(open(p, encoding="utf-8")):
            om[(month(r["m"]), ds, (r.get("vendor") or "") if vend else "", area(r.get("s")), area(r.get("e")))] += int(r["n"])
rows = [[m, ds, v, s, e, n, flags(m, v)] for (m, ds, v, s, e), n in sorted(om.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], sk(kv[0][3]), sk(kv[0][4])))]
COUNTS["scooter_trips_od_month.csv"] = write_csv("scooter_trips_od_month.csv",
                                                 ["month", "dataset", "vendor", "start_community_area", "end_community_area", "trips", "flags"], rows)

# ---------- 2020 population and area by community area, ward and tract (Census blocks by interior point) ----------
geo = json.load(open(interim("points", "geo.json"), encoding="utf-8"))
pop_rows = []
for kind, layer in (("community_area", "ca"), ("ward", "ward"), ("tract", "tract")):
    for f in geo[layer]["features"]:
        pr = f["properties"]
        place = "Chicago"
        if pr.get("sub"):
            place = "Evanston" if (pr["id"] == "78" or "Evanston" in pr["label"]) else "Oak Park"
        if kind == "ward" and pr.get("sub"):
            continue                      # Evanston and Oak Park have no Chicago wards
        pop_rows.append([kind, pr["id"], pr["label"], place, pr["pop"], pr["sqmi"]])
pop_rows.sort(key=lambda r: (["community_area", "ward", "tract"].index(r[0]), sk(r[1])))
COUNTS["population_2020.csv"] = write_csv("population_2020.csv", ["geo_type", "geo_id", "name", "place", "population_2020", "area_sq_mi"], pop_rows)

# ---------- facts.json: figures from these tables only ----------
yr = {(r[1], r[0]): r for r in csv.reader(open(os.path.join(PROC, "scooter_trips_year.csv"), encoding="utf-8")) if r[0] != "year"}
view = lambda ds: json.load(open(raw("city", "views", f"{ds}.json"), encoding="utf-8"))
from datetime import datetime
from zoneinfo import ZoneInfo
def source(sid, ds):
    v = view(ds)
    return {"id": sid, "name": f"{v['name']} (City of Chicago data portal, {ds})", "url": f"https://data.cityofchicago.org/d/{ds}",
            "pulled": SNAPSHOT, "rows_updated": datetime.fromtimestamp(v["rowsUpdatedAt"], ZoneInfo("America/Chicago")).date().isoformat()}
SOURCES = [source("scooters_2019", "2kfw-zvte"), source("scooters_2020", "3rse-fbp6"), source("scooters", "2i5w-ykuw"),
           source("community_areas", "igwz-8jzy"), source("wards", "p293-wvbd"),
           {"id": "census", "name": "TIGERweb, 2020 census blocks, tracts and places (U.S. Census Bureau)",
            "url": "https://tigerweb.geo.census.gov/", "pulled": SNAPSHOT}]
FACTS = {}
def fact(key, value, label, definition, source_file, sources, unit):
    FACTS[key] = {"value": value, "display": f"{value:,}" if isinstance(value, int) else str(value), "label": label,
                  "definition": definition, "source_file": source_file, "sources": sources, "rounding": None,
                  **({"unit": unit} if unit else {})}
per = {"2kfw-zvte": "scooters_2019", "3rse-fbp6": "scooters_2020", "2i5w-ykuw": "scooters"}
for (ds, y), r in sorted(yr.items(), key=lambda kv: kv[0][1]):
    fact(f"scooter_trips_{y}", int(r[5]), f"Trips in the City’s e-scooter trip table, {y}",
         f"Trips started in {y} in the City’s table for that year, those with a negative trip duration left out.",
         "scooter_trips_year.csv", [per[ds]], "trips")
v25 = defaultdict(int)
for r in csv.reader(open(os.path.join(PROC, "scooter_trips_month.csv"), encoding="utf-8")):
    if r[0][:4] == "2025" and r[1] == "2i5w-ykuw":
        v25[r[2]] += int(r[3])
for v in sorted(v25):
    fact(f"scooter_trips_2025_{v.lower()}", v25[v], f"Trips under vendor “{v}” in the City’s e-scooter trip table, 2025",
         f"Trips started in 2025 under vendor “{v}”, as the City publishes them, negative durations left out." +
         (" From 2024-07 these rows also hold municipal classic-bike rides." if v == "Lyft" else ""),
         "scooter_trips_month.csv", ["scooters"], "trips")
chi = [r for r in pop_rows if r[0] == "community_area" and r[3] == "Chicago"]
fact("community_areas", len(chi), "Chicago community areas", "Rows of population_2020.csv for Chicago community areas.", "population_2020.csv", ["community_areas"], "areas")
fact("population_2020_chicago", sum(r[4] for r in chi), "Chicago’s 2020 population, by census block",
     "2020 census block populations summed over the blocks whose interior point falls in a Chicago community area.",
     "population_2020.csv", ["census", "community_areas"], "people")
first = min(r["first"] for ds, _ in TABLES for r in city(f"{ds}_year.json"))[:10]
last = max(r["last"] for ds, _ in TABLES for r in city(f"{ds}_year.json"))[:10]
fact("scooter_first_date", first, "First day of scooter trips", "The start date of the earliest trip in the City’s three tables.", "scooter_trips_year.csv", ["scooters_2019"], None)
fact("scooter_last_date", last, "Last day of scooter trips", "The start date of the latest trip in the City’s three tables.", "scooter_trips_year.csv", ["scooters"], None)
out = {"schema": 1, "project": "chicago-micromobility", "release": RELEASE_DATE, "snapshot_date": SNAPSHOT,
       "coverage": {"start": first[:7], "end": last[:7]}, "generated_by": "scripts/export_public.py", "sources": SOURCES,
       "facts": FACTS, "invariants": [{"sum": [k for k in FACTS if k.startswith("scooter_trips_2025_")], "equals": "scooter_trips_2025"}]}
with open(os.path.join(PROC, "facts.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
    fh.write("\n")

# ---------- the data dictionary, with row counts ----------
DICT = f"""# Data dictionary

Release {RELEASE_DATE}, built from a snapshot of the sources pulled {SNAPSHOT}. Files are UTF-8 CSV with a header
row. Blank means missing, never zero. Read every id as text. Months are `YYYY-MM`.

Types: `text`, `integer`, `decimal`, `date` (`YYYY-MM` or `YYYY-MM-DD`).

## Flags

`flags` is pipe-delimited and alphabetical, or empty.

| Flag | Meaning |
|---|---|
| `includes_classic_bike_rides` | From 2024-07 the City’s “Lyft” rows also hold municipal classic-bike rides, not only scooter trips. They are not removed here: telling them apart needs the municipal system’s trip files, which are not republished. |

## scooter_trips_year.csv

One row is a year of one City table. Rows: {COUNTS['scooter_trips_year.csv']:,}. Key: `year`, `dataset`.

| Column | Type | Definition |
|---|---|---|
| `year` | text | Start year of the trip |
| `dataset` | text | City portal id: `2kfw-zvte` (2019 pilot), `3rse-fbp6` (2020 pilot), `2i5w-ykuw` (2022 on) |
| `trips_as_published` | integer | Every row of the table that year |
| `under_60_seconds` | integer | Trips of 0 to 59 seconds (counted in `trips`) |
| `negative_duration` | integer | Trips that end before they start (left out of `trips`) |
| `trips` | integer | Trips with a duration of zero or more |
| `flags` | text | See Flags (the 2022-on table from 2024, whose “Lyft” rows hold classic rides from 2024-07) |

## scooter_trips_month.csv

One row is a month of one vendor in one table. Rows: {COUNTS['scooter_trips_month.csv']:,}. Key: `month`, `dataset`, `vendor`.

| Column | Type | Definition |
|---|---|---|
| `month` | date | Start month |
| `dataset` | text | City portal id |
| `vendor` | text | As published; blank for the 2019 pilot, whose table names no companies |
| `trips` | integer | Trips with a duration of zero or more |
| `flags` | text | See Flags |

## scooter_trips_area_month.csv

One row is a month, vendor and community area in one table. Rows: {COUNTS['scooter_trips_area_month.csv']:,}. Key: `month`, `dataset`, `vendor`, `community_area`.

| Column | Type | Definition |
|---|---|---|
| `month`, `dataset`, `vendor` | | As in scooter_trips_month.csv |
| `community_area` | text | City community area number, 1 to 77; blank where the table gives none |
| `starts` | integer | Trips starting in the area |
| `ends` | integer | Trips ending in the area |
| `start_and_end` | integer | Trips with both ends in the area |
| `flags` | text | See Flags |

## scooter_trips_od_year.csv

One row is a start area and end area for a year, vendor and table. Rows: {COUNTS['scooter_trips_od_year.csv']:,}. Key: every column but `trips` and `flags`.

| Column | Type | Definition |
|---|---|---|
| `year`, `dataset`, `vendor` | | As above |
| `start_community_area`, `end_community_area` | text | Community area numbers; blank where the table gives none |
| `trips` | integer | Trips with a duration of zero or more |
| `flags` | text | See Flags (“Lyft” rows from 2024, whose rows hold classic rides from 2024-07) |

## scooter_trips_od_month.csv

The same by month. Rows: {COUNTS['scooter_trips_od_month.csv']:,}. Key: every column but `trips` and `flags`. `flags` as above.

## population_2020.csv

One row is a community area, ward or census tract. Rows: {COUNTS['population_2020.csv']:,}. Key: `geo_type`, `geo_id`.

| Column | Type | Definition |
|---|---|---|
| `geo_type` | text | `community_area`, `ward` (2023 map) or `tract` (2020) |
| `geo_id` | text | Community area number (78 Evanston, 79 Oak Park), ward number, or 11-digit tract GEOID |
| `name` | text | Display name |
| `place` | text | Chicago, Evanston or Oak Park |
| `population_2020` | integer | 2020 census population of the blocks whose interior point falls in the shape |
| `area_sq_mi` | decimal | Area of the shape in square miles (tracts clipped to the city) |

## facts.json

Every figure the release states, with its definition, source file and sources.
"""
with open(os.path.join(OUT, "data", "README.md"), "w", encoding="utf-8") as fh:
    fh.write(DICT)

# ---------- the manifest ----------
with open(os.path.join(OUT, "checksums.sha256"), "w", encoding="utf-8") as fh:
    for n in sorted(os.listdir(PROC)):
        fh.write(f"{hashlib.sha256(open(os.path.join(PROC, n), 'rb').read()).hexdigest()}  data/processed/{n}\n")
print("public/:", ", ".join(f"{k} {v:,}" for k, v in COUNTS.items()))
