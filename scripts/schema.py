"""Every fixed decision the build makes, in one place. The build reads no clock: the snapshot it reads and the
release date are written here when a release is cut.

Paths: data/raw/<SNAPSHOT>/ is the pull the build reads (scripts/fetch.py writes it), data/interim/ holds the
build's working tables (not tracked), data/processed/ and site/data/ are the release.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = "2026-10-02"         # the dated pull every build reads
RELEASE_DATE = "2026-10-02"     # moves to the day the release is published, if that is later


def raw(*parts):
    return os.path.join(ROOT, "data", "raw", SNAPSHOT, *parts)


def interim(*parts):
    path = os.path.join(ROOT, "data", "interim", *parts)
    os.makedirs(os.path.dirname(path) if parts and "." in parts[-1] else path, exist_ok=True)
    return path


PROCESSED = os.path.join(ROOT, "data", "processed")
SITE_DATA = os.path.join(ROOT, "site", "data")

# --- rules the page text repeats --------------------------------------------------------------------------
MIN_BASE = 100            # trips the earlier year needs before a percent change is shown, and before a pie is drawn
MIN_CLASSIC = 5           # classic-bike trip ends a station listing needs in a year to count as a docking station
SAME_PLACE_FT = 150       # station listings this close count as one place (new and removed stations, Station only)
PIE_ONLY = [34, 36, 37]   # Armour Square, Oakland, Fuller Park: too narrow to split, so they get a small pie
NEAR_M = 0.0              # no nearest-area fallback for a trip end outside every area (divvy_build)

# --- the City's announced totals, used only as a check ----------------------------------------------------
CITY_TOTALS = {
    # "Mayor Brandon Johnson Announces New Record Of Nearly 13 Million Shared Bike And Scooter Trips In 2025",
    # City of Chicago press release, 2026-01-15, rounded there to a tenth of a million (checked 2026-10-02)
    2025: {"all": 12900000, "divvy": 6800000, "lime": 6100000,
           "source": "https://www.chicago.gov/city/en/depts/mayor/press_room/press_releases/2026/january/micromobility-record-year.html"},
    # CDOT's figures in "CDOT: Chicago set a record in 2024 with 10M+ bike- and scooter-share rides. Actually, make
    # that 11M+!", John Greenfield, Streetsblog Chicago, 2025-01-09 (checked 2026-10-02)
    2024: {"all": 11028554, "divvy": 6681480,
           "source": "https://chi.streetsblog.org/2025/01/09/cdot-chicago-set-a-record-in-2024-with-10m-bike-and-scooter-share-rides-actually-make-that-11m"},
}
