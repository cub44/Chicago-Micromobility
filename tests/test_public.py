"""The public release: exactly the City and Census tables and facts.json, each in the manifest with its hash, the
figures recomputing from the tables, and nothing derived from the municipal system's trip files.

Runs in the private repository (release under public/) and in the public one (release at its root)."""
import csv, hashlib, json, os, re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = os.path.join(HERE, "public") if os.path.isdir(os.path.join(HERE, "public", "data")) else HERE
PROC = os.path.join(REL, "data", "processed")
FILES = ["facts.json", "population_2020.csv", "scooter_trips_area_month.csv", "scooter_trips_month.csv",
         "scooter_trips_od_month.csv", "scooter_trips_od_year.csv", "scooter_trips_year.csv"]
FLAGS = {"includes_classic_bike_rides"}
rows = lambda name: list(csv.DictReader(open(os.path.join(PROC, name), encoding="utf-8")))


def test_exactly_the_public_files():
    assert sorted(n for n in os.listdir(PROC) if not n.startswith(".")) == FILES


def test_the_manifest_covers_every_file_with_its_hash():
    listed = {}
    for line in open(os.path.join(REL, "checksums.sha256"), encoding="utf-8").read().splitlines():
        digest, path = line.split("  ", 1)
        listed[path] = digest
    assert sorted(listed) == [f"data/processed/{n}" for n in FILES]
    for path, digest in listed.items():
        assert hashlib.sha256(open(os.path.join(REL, path), "rb").read()).hexdigest() == digest, path


def test_nothing_from_the_municipal_trip_files():
    for n in FILES:
        text = open(os.path.join(PROC, n), encoding="utf-8").read()
        assert "Divvy" not in text and "divvy" not in text, n
    assert {r["dataset"] for r in rows("scooter_trips_year.csv")} == {"2kfw-zvte", "3rse-fbp6", "2i5w-ykuw"}


def test_conventions():
    for n in FILES:
        if not n.endswith(".csv"):
            continue
        for r in rows(n):
            if "month" in r:
                assert re.fullmatch(r"\d{4}-\d{2}", r["month"]), (n, r)
            if r.get("flags"):
                parts = r["flags"].split("|")
                assert parts == sorted(parts) and set(parts) <= FLAGS, (n, r)
            for k in ("trips", "starts", "ends", "start_and_end", "population_2020"):
                if k in r:
                    assert r[k].isdigit(), (n, k, r)


def test_facts_are_complete_and_recompute():
    f = json.load(open(os.path.join(PROC, "facts.json"), encoding="utf-8"))
    for key in ("schema", "project", "release", "snapshot_date", "generated_by", "sources", "facts", "invariants"):
        assert key in f, key
    ids = {s["id"] for s in f["sources"]}
    for key, v in f["facts"].items():
        for field in ("value", "display", "label", "definition", "source_file", "sources", "rounding"):
            assert field in v, (key, field)
        assert v["source_file"] in FILES and set(v["sources"]) <= ids and v["definition"].endswith("."), key
        assert v["display"] == (f"{v['value']:,}" if isinstance(v["value"], int) else str(v["value"])), key
    for inv in f["invariants"]:
        assert sum(f["facts"][k]["value"] for k in inv["sum"]) == f["facts"][inv["equals"]]["value"], inv
    by_year = {}
    for r in rows("scooter_trips_year.csv"):
        by_year[r["year"]] = by_year.get(r["year"], 0) + int(r["trips"])
        assert int(r["trips_as_published"]) - int(r["negative_duration"]) == int(r["trips"]), r
    for y, n in by_year.items():
        assert f["facts"][f"scooter_trips_{y}"]["value"] == n, y
    month = {}
    for r in rows("scooter_trips_month.csv"):
        month[r["month"][:4]] = month.get(r["month"][:4], 0) + int(r["trips"])
    assert month == by_year


def test_every_table_counts_the_same_trips():
    total = lambda name, col, key: {k: v for k, v in _sum(rows(name), col, key).items()}
    year = total("scooter_trips_year.csv", "trips", lambda r: r["year"])
    assert total("scooter_trips_od_year.csv", "trips", lambda r: r["year"]) == year
    assert total("scooter_trips_od_month.csv", "trips", lambda r: r["month"][:4]) == year
    assert total("scooter_trips_area_month.csv", "starts", lambda r: r["month"][:4]) == year
    assert total("scooter_trips_area_month.csv", "ends", lambda r: r["month"][:4]) == year


def _sum(rs, col, key):
    out = {}
    for r in rs:
        out[key(r)] = out.get(key(r), 0) + int(r[col])
    return out
