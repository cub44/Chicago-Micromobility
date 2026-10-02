# Data dictionary

Release 2026-10-02, built from a snapshot of the sources pulled 2026-10-02. Files are UTF-8 CSV with a header
row. Blank means missing, never zero. Read every id as text. Months are `YYYY-MM`.

Types: `text`, `integer`, `decimal`, `date` (`YYYY-MM` or `YYYY-MM-DD`).

## Flags

`flags` is pipe-delimited and alphabetical, or empty.

| Flag | Meaning |
|---|---|
| `includes_classic_bike_rides` | From 2024-07 the City’s “Lyft” rows also hold municipal classic-bike rides, not only scooter trips. They are not removed here: telling them apart needs the municipal system’s trip files, which are not republished. |

## scooter_trips_year.csv

One row is a year of one City table. Rows: 6. Key: `year`, `dataset`.

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

One row is a month of one vendor in one table. Rows: 156. Key: `month`, `dataset`, `vendor`.

| Column | Type | Definition |
|---|---|---|
| `month` | date | Start month |
| `dataset` | text | City portal id |
| `vendor` | text | As published; blank for the 2019 pilot, whose table names no companies |
| `trips` | integer | Trips with a duration of zero or more |
| `flags` | text | See Flags |

## scooter_trips_area_month.csv

One row is a month, vendor and community area in one table. Rows: 8,797. Key: `month`, `dataset`, `vendor`, `community_area`.

| Column | Type | Definition |
|---|---|---|
| `month`, `dataset`, `vendor` | | As in scooter_trips_month.csv |
| `community_area` | text | City community area number, 1 to 77; blank where the table gives none |
| `starts` | integer | Trips starting in the area |
| `ends` | integer | Trips ending in the area |
| `start_and_end` | integer | Trips with both ends in the area |
| `flags` | text | See Flags |

## scooter_trips_od_year.csv

One row is a start area and end area for a year, vendor and table. Rows: 29,563. Key: every column but `trips` and `flags`.

| Column | Type | Definition |
|---|---|---|
| `year`, `dataset`, `vendor` | | As above |
| `start_community_area`, `end_community_area` | text | Community area numbers; blank where the table gives none |
| `trips` | integer | Trips with a duration of zero or more |
| `flags` | text | See Flags (“Lyft” rows from 2024, whose rows hold classic rides from 2024-07) |

## scooter_trips_od_month.csv

The same by month. Rows: 133,205. Key: every column but `trips` and `flags`. `flags` as above.

## population_2020.csv

One row is a community area, ward or census tract. Rows: 961. Key: `geo_type`, `geo_id`.

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
