# Plan

Goal: a model you could actually use to plan a high-speed maglev network in Minnesota, with every
cost traceable to a source and every hazard priced in. Built in phases; each phase replaces guesses
from the one before with measurements.

## Phase 0: parametric model (done 2026-11-03)

- `params/*.yaml`: 87 parameters with ranges, units, confidence and sources.
- `network/*.yaml`: 20 places, 7 lines in 3 phases, segments with planner-estimated shares.
- `mnmaglev check | report`: validation, kinematics + energy, capital, land, wetlands, opex,
  materials and ore, Monte Carlo P10/P50/P90, sensitivity ranking, Leaflet map.
- 9 tests: haversine, closed-form trapezoid run time, air density, curve radius, quantities add up,
  spine plausibility, Monte Carlo ordering.

## Decisions

- **2026-11-03, Twin Cities station = one Midway hub** between Minneapolis and St. Paul (placeholder
  site Snelling & University), fed by the Green Line, the A Line and buses, like local lines
  feeding a regional trunk (BART) or Japan's Shin-Yokohama / Shin-Osaka. Why: both cities served
  equally (no St. Paul-left-out problem), no downtown tunnels ($68.9 bn vs $73.3 bn P50 for the
  spine), and one hub works for two systems. MSP stays a stop for airport - Rochester trips.
  The St. Cloud line also starts at the hub. Kept as a variant: `downtown_minneapolis`.
- **Two-system corridor (in the model since 2026-11-03, held on the spine):** reserve land for a
  second system beside the first (45 m extra in the country, 12 m in cities) and build city
  structures, long-bridge foundations and stations for two from day one; build system A, run it
  while the next generation (B) goes up beside it, then alternate. Lines opt in with
  `reserve_second_system: true`; the report prices it for every line. Spine: P50 $7.5 bn (~11% of
  the line). The rural land strip is cheap (~$0.6 bn with contingency); the build-for-two
  provisions in cities and stations are most of it, and `costs.reserve.urban_provision` (30%,
  placeholder) is the number to research. Open: Minnesota eminent-domain limits on taking land for
  a future system (options, willing sellers, farm leaseback), one environmental review for both
  strips or two, and a cheaper "land only" option (no city provisions, B finds its own way into
  the cities).

## Phase 1: research pass (next)

Work through docs/RESEARCH.md from the top of the sensitivity table down: replace placeholders with
sourced numbers, tighten ranges, add `params/benchmarks.yaml` (real projects as checks: Shanghai,
Chuo Shinkansen, California HSR, Brightline West, NLX) and a test that the model reproduces their
per-km costs with their structure mix. Check every "verify" in the YAML.

Decisions for Jon along the way:
- Midway hub site: Snelling & University (placeholder), Prospect Park, or on the Midway rail corridor;
  pick with transit access, land, noise; check MnDOT's "Rethinking I-94" corridor work for a space reservation.
- Cruise speed: 430 km/h (Shanghai-proven) vs 500+ (TR09) vs ~600 (CRRC); trades energy, curve
  radius and noise for time.
- Elevated-by-default (snow, drifting, crossings) vs more at-grade (cheaper, but snow clearance).

## Phase 2: GIS corridors (route search)

Turn straight lines into real alignments and measure the segment shares instead of estimating them.

- Data (docs/SOURCES.md): MN 0.5 m statewide lidar DEM (resampled to ~10-30 m for search),
  land cover (NLCD / MN land cover), National Wetlands Inventory, FEMA NFHL floodplains, soils
  (SSURGO: peat/organic), MnGeo parcels with assessed values, MnDOT and rail right-of-way,
  public and tribal lands, protected areas.
- Cost surface per cell: land price + structure cost (from slope/terrain) + wetland mitigation +
  floodplain + peat + crossings (roads, rivers, rail) + "no-go" layers.
- Least-cost path with maglev geometry: minimum curve radius (4.6 km at 430 km/h, from
  `geo.min_curve_radius_m`), max gradient, vertical curves; then smoothing into clothoids.
  Options: a graph search on a coarse grid with turning-angle constraints, then local refinement.
- Output: `network/alignments/*.geojson`; segments read their shares from these instead of YAML.
- Tools: Python (rasterio, geopandas, shapely, pyproj). Big rasters go to `data/` (gitignored; D: if large).

## Phase 3: hazards priced in (docs/HAZARDS.md)

For each hazard: how often, how bad, what the design does about it, what it costs (capital adder,
O&M, downtime). Flood stages per crossing (FEMA + NOAA Atlas 14, climate-adjusted), freezing rain
and icing frequency, snow drift on open farmland, freeze-thaw cycles, wind limits on high
viaducts, extreme cold for electronics, lake-effect snow at Duluth, spring thaw load limits for
construction haul roads.

## Phase 4: operations with OSRD (integrations/osrd)

Export alignments to RailJSON, describe the maglev as rolling stock (effort curve, no adhesion
limit), run OSRD for running times and a timetable; compare with `kinematics.py` (should agree
within a few %). Then capacity: how many trains per hour the spine can take, single vs dual track
sections, station layouts.

## Phase 5: power with Calliope (integrations/calliope)

Traction demand time series (from OSRD runs or kinematics) at substation nodes along each line;
MISO grid connection costs, winter peaks (heating + dense air), on-site/contracted wind and solar,
storage. Output: power supply capital + energy price per kWh to feed back into params.

## Phase 6: magnetics and the 3D view (sim/, Rust)

- cfsem: size the long stator (thrust needed for the grades and the drag computed here) and the
  levitation magnets, giving stator iron and aluminium per km. Builds on what
  [cortenforge-cfsem](https://github.com/YoungMoolahBaby/cortenforge-cfsem) `maglev-train` learned
  (cfsem has no magnetic materials, so iron-core EMS needs the image method or hybrid magnets).
- CortenForge + Bevy: the city-builder view. Lidar terrain, the alignment as guideway, piers,
  stations, trains moving on the OSRD timetable, overlays (land cost, floodplain, wetlands, snow).

## Phase 7: demand and economics

Ridership (gravity model on city populations and travel times vs driving and flying; benchmark
NLX and Zip Rail studies), fares and revenue, benefit-cost analysis per the federal guidance,
funding scenarios, phasing.

## Phase 8: materials supply chain

From taconite to guideway: Mesabi pellets -> which steel mills (rebar, strand, plate, electrical
steel); Duluth Complex copper-nickel permitting reality vs market copper; aluminium (imported);
cement and aggregate (taconite tailings as aggregate?); embodied carbon per km.
