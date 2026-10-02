# Methods

Release 2026-10-02. Sources pulled 2026-10-02.

## Sources

- **City of Chicago data portal:**
  - E-Scooter Trips – 2019 Pilot ([`2kfw-zvte`](https://data.cityofchicago.org/d/2kfw-zvte));
  - E-Scooter Trips – 2020 ([`3rse-fbp6`](https://data.cityofchicago.org/d/3rse-fbp6));
  - E-Scooter Trips, from 2022 ([`2i5w-ykuw`](https://data.cityofchicago.org/d/2i5w-ykuw));
  - Boundaries – Community Areas ([`igwz-8jzy`](https://data.cityofchicago.org/d/igwz-8jzy));
  - Boundaries – Wards, 2023 on ([`p293-wvbd`](https://data.cityofchicago.org/d/p293-wvbd)).
- **U.S. Census Bureau, [TIGERweb](https://tigerweb.geo.census.gov/):** 2020 census blocks with population,
  2020 tracts, and the Evanston and Oak Park boundaries.

## Trips

- The trip tables are aggregated on the portal. The queries are in `scripts/fetch.py`, and their saved
  responses are the snapshot.
- Trips that end before they start are left out. Trips under 60 seconds are counted, as the City counts them.
- Vendor names are as published. The 2019 pilot’s table names no companies.
- From 2024-07 the “Lyft” rows also hold municipal classic-bike rides. They are flagged, not removed.
- The table also lists Coco and Serve, which run sidewalk delivery robots.
- There are no trips for 2023-10 to 2023-12, and no table for 2021.

## Population

Each 2020 census block is placed by its interior point. Tracts are the Census Bureau’s 2020 shapes, clipped to
the city. Evanston and Oak Park come from the Census Bureau’s place shapes.

## Checks

`tests/test_public.py` checks that:

- the manifest lists every file with its hash;
- each figure in facts.json recomputes from the tables;
- every table gives the same yearly totals.
