"""Pull every source into data/raw/<date>/: the only step that touches the network.

    python3 scripts/fetch.py [YYYY-MM-DD]      (default: today's date in Chicago)

Each file is written once. A rerun on the same date skips files that already exist, so an interrupted pull
resumes; a pull on a later date goes into its own folder and never touches an earlier one. Responses are saved
as the source sent them (the City's "Lyft" pages gzip-compressed, to keep them small). At the end MANIFEST.json
lists every file with its source, URL or query, bytes and sha256, and each portal dataset's name, row-update
time and columns.

Sources:
  divvy/    Divvy's trip files, from the divvy-tripdata bucket that divvybikes.com/system-data links (Divvy Data
            License Agreement); the bucket listing is kept beside them
  city/     City of Chicago data portal: the three e-scooter trip tables aggregated on the portal (the queries are
            in this file), the 2013-2019 Divvy Trips table by station and year, community areas, 2023 wards, the
            Divvy Equity Priority Area, and each dataset's metadata
  lyft/     every row of the City's 2022-on scooter table under vendor "Lyft" from 2024-07 on, for the match that
            finds Divvy's classic-bike rides among them (build.lyft_classic)
  census/   Census Bureau TIGERweb (2020): Cook County blocks with population and interior points, Cook County
            tracts, and the Evanston and Oak Park outlines
An app token in the environment (SOCRATA_APP_TOKEN) is sent if present; the pull works without one.
"""
import gzip, hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTAL = "https://data.cityofchicago.org"
BUCKET = "https://divvy-tripdata.s3.amazonaws.com/"
TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer"
SCOOTERS = [("2kfw-zvte", False), ("3rse-fbp6", True), ("2i5w-ykuw", True)]   # (dataset, has a vendor field)
DATASETS = ["2kfw-zvte", "3rse-fbp6", "2i5w-ykuw", "fg6s-gzvg", "igwz-8jzy", "p293-wvbd", "mdn7-scnt"]
LYFT_FROM = "2024-07"
F = "trip_duration >= 0"     # trips that end before they start are left out (the same rule as for Divvy)

DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", DATE), DATE
OUT = os.path.join(ROOT, "data", "raw", DATE)
SOURCES = {}     # path relative to OUT -> {"source", "url" or "query"}


def http(url, data=None, timeout=600, tries=5):
    headers = {}     # urllib's own User-Agent: TIGERweb's firewall rejects some custom ones
    if url.startswith(PORTAL) and os.environ.get("SOCRATA_APP_TOKEN"):
        headers["X-App-Token"] = os.environ["SOCRATA_APP_TOKEN"]
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            body = e.read()[:300] if isinstance(e, urllib.error.HTTPError) else b""
            print(f"  retry {i + 1}: {str(e)[:120]} {body!r}", flush=True)
            time.sleep(20 * (i + 1))
    raise RuntimeError(f"gave up on {url[:200]}")


def save(rel, body, source, url=None, query=None, gz=False):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if gz:
        body = gzip.compress(body, mtime=0)
    with open(path + ".part", "wb") as f:
        f.write(body)
    os.replace(path + ".part", path)
    note(rel, source, url, query)


def note(rel, source, url=None, query=None):
    SOURCES[rel] = {"source": source, **({"url": url} if url else {}), **({"query": query} if query else {})}


def have(rel, source, url=None, query=None):
    if os.path.exists(os.path.join(OUT, rel)):
        note(rel, source, url, query)
        return True
    return False


def soql(ds, query, rel=None, check=None):
    """A SoQL query on the portal; the parsed rows. With rel, the response is saved (or read back if saved)."""
    url = f"{PORTAL}/resource/{ds}.json?$query=" + urllib.parse.quote(query)
    if rel and have(rel, ds, query=query):
        rows = json.load(open(os.path.join(OUT, rel)))
    else:
        for i in range(4):
            body = http(url)
            rows = json.loads(body)
            if isinstance(rows, list):
                break
            print(f"  portal error ({i + 1}): {str(rows)[:200]}", flush=True)
            time.sleep(20 * (i + 1))
        else:
            raise RuntimeError(f"{ds}: {query[:120]}")
        if check:
            check(rows)
        if rel:
            save(rel, body, ds, query=query)
    return rows


total = lambda rows: sum(int(r["n"]) for r in rows)


def portal_metadata():
    for ds in DATASETS:
        rel = f"city/views/{ds}.json"
        url = f"{PORTAL}/api/views/{ds}.json"
        if not have(rel, ds, url=url):
            save(rel, http(url), ds, url=url)


def boundaries():
    for ds, limit in (("igwz-8jzy", 100), ("p293-wvbd", 5000), ("mdn7-scnt", 500)):
        rel = f"city/{ds}.geojson"
        url = f"{PORTAL}/resource/{ds}.geojson?$limit={limit}"
        if not have(rel, ds, url=url):
            body = http(url)
            n = len(json.loads(body)["features"])
            assert 0 < n < limit, (ds, n)
            save(rel, body, ds, url=url)


def divvy():
    rel = "divvy/listing.xml"
    if not have(rel, "divvy-tripdata", url=BUCKET):
        save(rel, http(BUCKET), "divvy-tripdata", url=BUCKET)
    xml = open(os.path.join(OUT, rel), encoding="utf-8").read()
    assert "<IsTruncated>false</IsTruncated>" in xml, "the bucket listing is truncated; page it with a marker"
    keys = re.findall(r"<Key>(.*?)</Key>.*?<ETag>&quot;(.*?)&quot;</ETag>.*?<Size>(\d+)</Size>", xml, re.S)
    for key, etag, size in keys:
        if not key.endswith(".zip"):
            continue
        rel = f"divvy/{key}"
        if have(rel, "divvy-tripdata", url=BUCKET + key):
            continue
        body = http(BUCKET + urllib.parse.quote(key))
        assert len(body) == int(size), (key, len(body), size)
        if "-" not in etag:      # a single-part upload's ETag is the file's MD5
            assert hashlib.md5(body).hexdigest() == etag, key
        save(rel, body, "divvy-tripdata", url=BUCKET + key)
        print(f"  {key} {int(size) / 1e6:.1f} MB", flush=True)


def scooters():
    """The page's scooter tables, aggregated on the portal. Each query's totals are checked against the year
    counts, so a truncated response stops the pull."""
    for ds, vend in SCOOTERS:
        v = "vendor, " if vend else ""
        p = f"city/{ds}"
        allyr = soql(ds, "SELECT date_extract_y(start_time) AS yr, count(*) AS n, min(start_time) AS first, "
                         "max(start_time) AS last GROUP BY yr ORDER BY yr LIMIT 100", f"{p}_year_all.json")
        soql(ds, "SELECT date_extract_y(start_time) AS yr, count(*) AS n, sum(case(trip_duration < 60, 1, true, 0)) AS short, "
                 "sum(case(trip_duration < 0, 1, true, 0)) AS negative GROUP BY yr ORDER BY yr LIMIT 100", f"{p}_removed.json")
        yr = soql(ds, f"SELECT date_extract_y(start_time) AS yr, count(*) AS n, min(start_time) AS first, max(start_time) AS last "
                      f"WHERE {F} GROUP BY yr ORDER BY yr LIMIT 100", f"{p}_year.json")
        N = total(yr)
        print(ds, "as published", total(allyr), "counted", N, flush=True)
        soql(ds, f"SELECT date_trunc_ym(start_time) AS m, count(*) AS n WHERE {F} GROUP BY m ORDER BY m LIMIT 200",
             f"{p}_month.json", check=lambda rows: total(rows) == N or sys.exit(f"{ds} month total"))
        for side, col, extra in (("s", "start_community_area_number", ""), ("e", "end_community_area_number", ""),
                                 ("same", "start_community_area_number",
                                  " AND start_community_area_number = end_community_area_number")):
            def ok(rows, side=side):
                assert len(rows) < 50000 and (side == "same" or total(rows) == N), (ds, side)
            soql(ds, f"SELECT date_trunc_ym(start_time) AS m, {v}{col} AS ca, count(*) AS n WHERE {F}{extra} "
                     f"GROUP BY m, {v}ca ORDER BY m, {v}ca LIMIT 50000", f"{p}_ca_month_{side}.json", check=ok)
        ok_od = lambda rows: (len(rows) < 50000 and total(rows) == N) or sys.exit(f"{ds} od year")
        if vend:
            soql(ds, f"SELECT date_extract_y(start_time) AS yr, vendor, start_community_area_number AS s, "
                     f"end_community_area_number AS e, count(*) AS n WHERE {F} GROUP BY yr, vendor, s, e "
                     f"ORDER BY yr, vendor, s, e LIMIT 100000", f"{p}_od_ca_year_vendor.json",
                 check=lambda rows: (len(rows) < 100000 and total(rows) == N) or sys.exit(f"{ds} od year"))
        else:
            soql(ds, f"SELECT date_extract_y(start_time) AS yr, start_community_area_number AS s, end_community_area_number AS e, "
                     f"count(*) AS n WHERE {F} GROUP BY yr, s, e ORDER BY yr, s, e LIMIT 50000", f"{p}_od_ca_year.json", check=ok_od)
            soql(ds, f"SELECT date_extract_y(start_time) AS yr, start_community_area_number AS ca, count(*) AS n WHERE {F} "
                     f"GROUP BY yr, ca ORDER BY yr, ca LIMIT 2000", f"{p}_start_ca_year.json")
        # origin and destination by month, a quarter at a time for the big table (the portal times out on whole years)
        od = 0
        for y in sorted(int(r["yr"]) for r in yr):
            spans = [(1, 4), (4, 7), (7, 10), (10, 13)] if ds == "2i5w-ykuw" else [(1, 13)]
            for a, b in spans:
                lo = f"{y}-{a:02d}-01T00:00:00"
                hi = f"{y + (b == 13)}-{(b if b < 13 else 1):02d}-01T00:00:00"
                rows = soql(ds, f"SELECT date_trunc_ym(start_time) AS m, {v}start_community_area_number AS s, "
                                f"end_community_area_number AS e, count(*) AS n WHERE {F} AND start_time >= '{lo}' "
                                f"AND start_time < '{hi}' GROUP BY m, {v}s, e ORDER BY m, {v}s, e LIMIT 200000",
                            f"{p}_od_ca_month/{y}-{a:02d}.json", check=lambda rows: len(rows) < 200000 or sys.exit("od month limit"))
                od += total(rows)
        assert od == N, (ds, "od month", od, N)
        if ds == "2i5w-ykuw":
            soql(ds, f"SELECT date_trunc_ym(start_time) AS m, vendor, count(*) AS n WHERE {F} GROUP BY m, vendor "
                     f"ORDER BY m, vendor LIMIT 1000", f"{p}_vendor_month.json",
                 check=lambda rows: total(rows) == N or sys.exit("vendor month total"))


def divvy_portal():
    """The City's 2013-2019 Divvy Trips table: yearly counts, and trips by station, coordinates and year, which
    place the 2013-2019 trips (Divvy's own files of those years give station ids only)."""
    ds = "fg6s-gzvg"
    soql(ds, "SELECT date_extract_y(start_time) AS yr, count(*) AS n, min(start_time) AS first, max(start_time) AS last "
             "GROUP BY yr ORDER BY yr LIMIT 100", f"city/{ds}_year.json")
    for side, pre in (("start", "from"), ("end", "to")):
        soql(ds, f"SELECT date_extract_y(start_time) AS yr, {pre}_station_id AS sid, {pre}_latitude AS lat, "
                 f"{pre}_longitude AS lng, count(*) AS n GROUP BY yr, sid, lat, lng ORDER BY yr, sid, lat, lng LIMIT 50000",
             f"city/{ds}_{side}_station_year.json", check=lambda rows: len(rows) < 50000 or sys.exit("station limit"))


def lyft():
    """Every Lyft row from 2024-07 to the table's last month, 50,000 rows a page in trip_id order."""
    ds = "2i5w-ykuw"
    last = max(r["last"] for r in json.load(open(os.path.join(OUT, f"city/{ds}_year_all.json"))))[:7]
    y, m = map(int, LYFT_FROM.split("-"))
    while f"{y}-{m:02d}" <= last:
        ym, nxt = f"{y}-{m:02d}", f"{y + (m == 12)}-{m % 12 + 1:02d}"
        off, page, ids = 0, 0, set()
        while True:
            query = ("SELECT trip_id, start_time, trip_duration, start_community_area_number AS s, end_community_area_number AS e "
                     f"WHERE vendor = 'Lyft' AND start_time >= '{ym}-01T00:00:00' AND start_time < '{nxt}-01T00:00:00' "
                     f"ORDER BY trip_id LIMIT 50000 OFFSET {off}")
            rel = f"lyft/{ym}-{page:03d}.json.gz"
            if have(rel, ds, query=query):
                rows = json.loads(gzip.decompress(open(os.path.join(OUT, rel), "rb").read()))
            else:
                body = http(f"{PORTAL}/resource/{ds}.json?$query=" + urllib.parse.quote(query))
                rows = json.loads(body)
                assert isinstance(rows, list), str(rows)[:200]
                save(rel, body, ds, query=query, gz=True)
            ids.update(r["trip_id"] for r in rows)
            off += 50000
            page += 1
            if len(rows) < 50000:
                break
        assert len(ids) == off - 50000 + len(rows), (ym, "repeated trip ids")
        print(ym, "Lyft rows", len(ids), flush=True)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def tiger_pages(layer, where, fields, rel_stem, geometry, page_size):
    """A TIGERweb layer query, page by page in OBJECTID order."""
    off, n = 0, 0
    while True:
        q = {"where": where, "outFields": fields, "orderByFields": "OBJECTID", "resultOffset": off,
             "resultRecordCount": page_size, "f": "geojson" if geometry else "json"}
        if geometry:
            q.update({"returnGeometry": "true", "outSR": "4326", "geometryPrecision": "6"})
        else:
            q["returnGeometry"] = "false"
        url = f"{TIGER}/{layer}/query?" + urllib.parse.urlencode(q)
        rel = f"census/{rel_stem}-{n:02d}.{'geojson' if geometry else 'json'}"
        if have(rel, "TIGERweb", url=url):
            d = json.load(open(os.path.join(OUT, rel)))
        else:
            body = http(url)
            d = json.loads(body)
            assert "error" not in d, str(d)[:300]
            save(rel, body, "TIGERweb", url=url)
        got = len(d.get("features", []))
        more = d.get("exceededTransferLimit") or (d.get("properties") or {}).get("exceededTransferLimit")
        print(f"  {rel_stem} page {n}: {got}", flush=True)
        if got == 0 or (got < page_size and not more):
            return
        off += got
        n += 1


def census():
    tiger_pages(10, "STATE='17' AND COUNTY='031'", "GEOID,TRACT,POP100,INTPTLAT,INTPTLON", "tigerweb_2020_blocks_cook", False, 20000)
    tiger_pages(6, "STATE='17' AND COUNTY='031'", "GEOID,TRACT,NAME,POP100,AREALAND,AREAWATER", "tigerweb_2020_tracts_cook", True, 500)
    url = (f"{TIGER}/26/query?where=STATE%3D%2717%27+AND+NAME+IN+(%27Evanston+city%27,%27Oak+Park+village%27)"
           "&outFields=NAME,GEOID,POP100,AREALAND&returnGeometry=true&outSR=4326&geometryPrecision=6&f=geojson")
    rel = "census/tigerweb_2020_places_evanston_oakpark.geojson"
    if not have(rel, "TIGERweb", url=url):
        body = http(url)
        assert len(json.loads(body)["features"]) == 2
        save(rel, body, "TIGERweb", url=url)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest():
    datasets = {}
    for ds in DATASETS:
        v = json.load(open(os.path.join(OUT, f"city/views/{ds}.json")))
        datasets[ds] = {"name": v.get("name"), "url": f"{PORTAL}/d/{ds}",
                        "rows_updated": datetime.fromtimestamp(v["rowsUpdatedAt"], ZoneInfo("America/Chicago")).date().isoformat()
                        if v.get("rowsUpdatedAt") else None,
                        "columns": sorted(c["fieldName"] for c in v.get("columns", []))}
    files = {}
    for dirpath, _, names in os.walk(OUT):
        for name in names:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, OUT)
            if rel == "MANIFEST.json" or name.endswith(".part") or name.startswith("."):
                continue
            files[rel] = {"bytes": os.path.getsize(path), "sha256": sha256(path), **SOURCES.get(rel, {})}
    missing = sorted(set(SOURCES) - set(files))
    assert not missing, missing
    unexplained = sorted(set(files) - set(SOURCES))
    assert not unexplained, f"files no step of this pull wrote or checked: {unexplained[:5]}"
    m = {"pulled": DATE, "datasets": datasets, "files": dict(sorted(files.items()))}
    with open(os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1, ensure_ascii=False, sort_keys=False)
        f.write("\n")
    print("MANIFEST.json:", len(files), "files,", round(sum(v["bytes"] for v in files.values()) / 1e6), "MB")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("snapshot", OUT, flush=True)
    steps = sys.argv[2:] or ["metadata", "boundaries", "census", "divvy_portal", "scooters", "lyft", "divvy"]
    for step in steps:
        print("==", step, flush=True)
        {"metadata": portal_metadata, "boundaries": boundaries, "census": census, "divvy_portal": divvy_portal,
         "scooters": scooters, "lyft": lyft, "divvy": divvy}[step]()
    if not sys.argv[2:]:
        manifest()
