# Chicago micromobility trips: public data

E-scooter trips from the City of Chicago’s three trip tables, by month, vendor, community area and route, and
2020 population by community area, ward and census tract. These are the tables behind the scooter figures on
[connorblandford.com/projects/chicago-micromobility](https://connorblandford.com/projects/chicago-micromobility/).

Release 2026-10-02, built from sources pulled 2026-10-02. Data under CC BY 4.0, code under MIT.

DOI: [https://doi.org/10.5281/zenodo.23106922](https://doi.org/10.5281/zenodo.23106922). It stands for every
release and resolves to the latest; Zenodo also gives each release its own.

## Files

| File | One row is |
|---|---|
| [`scooter_trips_year.csv`](data/processed/scooter_trips_year.csv) | a year of one City table, as published and as counted |
| [`scooter_trips_month.csv`](data/processed/scooter_trips_month.csv) | a month of one vendor |
| [`scooter_trips_area_month.csv`](data/processed/scooter_trips_area_month.csv) | a month, vendor and community area: starts, ends, both |
| [`scooter_trips_od_year.csv`](data/processed/scooter_trips_od_year.csv) | trips between two community areas in a year |
| [`scooter_trips_od_month.csv`](data/processed/scooter_trips_od_month.csv) | the same by month |
| [`population_2020.csv`](data/processed/population_2020.csv) | a community area, ward or tract |
| [`facts.json`](data/processed/facts.json) | every figure the release states, with its definition |

The [data dictionary](data/README.md) gives every column and each file’s row count.
[`checksums.sha256`](checksums.sha256) gives each file’s SHA-256.

## Not included

Municipal bike-share trips. Their source, Divvy’s trip files, comes under the
[Divvy Data License Agreement](https://divvybikes.com/data-license-agreement), which bars republishing it. The
project page uses those files in its analysis and cites them. For the same reason, the City’s “Lyft” rows from
2024-07, which also hold municipal classic-bike rides, are published as the City gives them and flagged.

## Method and code

[METHODS.md](METHODS.md) says how the tables are built. To rebuild them, set `SNAPSHOT` in `scripts/schema.py`
to the pull date, then run, from `scripts/`:

```sh
python3 fetch.py YYYY-MM-DD metadata boundaries census scooters   # the only step that uses the network
python3 prep_geo.py && python3 build_geo.py && python3 export_public.py
```

The tables land in `public/`. `tests/test_public.py` checks this release.

## Cite

Blandford, Connor Ulrich. “Chicago micromobility trips.” Data set, release 2026-10-02. connorblandford.com.
https://connorblandford.com/projects/chicago-micromobility/. https://doi.org/10.5281/zenodo.23106922.

Name the release date and the file you used.

## Reuse and corrections

Data, documentation and prose are under [CC BY 4.0](LICENSE); code and `.github/` under [MIT](LICENSE-CODE).
CC BY 4.0 covers this project’s selection, derivation and documentation. The City of Chicago’s records remain
under its data portal’s terms of use.

To report an error, open an issue with the Correction form.
