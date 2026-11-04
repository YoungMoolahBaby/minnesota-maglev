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
- **2026-11-03, sibling systems side by side** (Jon): the next generation goes right beside the
  current one in the same corridor, not on a separate route. Why: it matches how construction
  works (build beside, shift service over, rebuild the old one, like a freeway rebuild); one land
  deal, one review, shared stations, power and maintenance access; and two generations running side
  by side is a visible showcase for innovation. Cost: both share one corridor's hazards (a flood,
  ice storm or tornado can hit both), and building next to a live line needs separation or slow
  orders. Jon (2026-11-03): shared hazards go into the planning (docs/HAZARDS.md, shared corridor),
  and the systems sit far enough apart to build either without much limitation on the other:
  `land.reserve.construction_separation` = 50 m between rights-of-way (~70 m centre to centre),
  sized to crane and piling-rig fall zones (placeholder).
- **Two-system corridor (in the model since 2026-11-03, held on the spine):** reserve land for a
  second system beside the first (B's own right-of-way + 50 m separation in the country, 12 m in cities) and build city
  structures, long-bridge foundations and stations for two from day one; build system A, run it
  while the next generation (B) goes up beside it, then alternate. Lines opt in with
  `reserve_second_system: true`; the report prices it for every line. Spine: P50 $8.1 bn (~12% of
  the line, ~$9.9 bn after pass 2). The land is cheap (~$1.3 bn with contingency); the build-for-two
  provisions in cities and stations are most of it, and `costs.reserve.urban_provision` (30%,
  placeholder) is the number to research. Open: Minnesota eminent-domain limits on taking land for
  a future system (options, willing sellers, farm leaseback), one environmental review for both
  strips or two, and a cheaper "land only" option (no city provisions, B finds its own way into
  the cities).
- **2026-11-03, local supply policy on** (Jon): use Minnesota's own mines and build the guideway
  beams and stator packs in Minnesota. Modelled as `settings.local_supply` in network/lines.yaml with
  `costs.local_supply.*`: one beam plant for the whole network (1.5% of beam civil), stator-pack
  assembly (1% of systems), taconite aggregate on north-zone segments, supply contracts (-1
  contingency point). Spine saving ~$1.7 bn P50 (~1.7%). Materials are ~4% of construction, so the
  ore itself barely moves cost; the case for it is supply security, price stability, jobs and Range
  revenue (production tax ~$2.3 M on the spine), which belong in the economics phase.
- **2026-11-03, fusion power as part of the megaproject** (Jon): the megaproject builds its own
  small fusion units (~50 MWe, Helion / Zap Energy class) instead of buying a slice of a big plant,
  and builds MORE than the trains need instead of batteries; the surplus powers neighbouring users
  (hydrogen steelmaking on the Range, data centres, the Midway hub district, de-icing) or the grid.
  `settings.fusion: own` in network/lines.yaml, `params/power.yaml`, `src/mnmaglev/power.py`
  (second-by-second timetable demand) and `fusion.py` (fleet sized to the 1-second peak + 10% + one
  spare, added phase by phase, learning curve on later units). Spine: 24 MW average, 123 MW peak,
  4 units, ~$6.9 bn P50, ~86% surplus. Strategic, not a cost saving at wholesale prices; no fusion
  plant has made net electricity yet, and Minnesota's moratorium may cover it (unresolved).
- **2026-11-03, winter ice: all four measures** (Jon): targeted heating of critical spots during
  icing, storm trains and sweepers, clearing vehicles / slow orders / bus backup, and overnight
  warming of the whole guideway with idle fusion units (new; no railway found doing it). Modelled
  in params/winter.yaml and src/mnmaglev/winter.py, `settings.winter_heating: targeted`. Heating
  adds to the storm-time peak in fusion sizing (spine 4 -> 5 units); heating the whole line during
  icing would need 10. Overnight warming fits in the idle units.
- **2026-11-03, staggered timetable** (Jon): departures staggered at the Midway hub instead of every
  line leaving on the hour. `mnmaglev timetable --write` -> network/timetable.yaml (offsets per line
  and direction, phase by phase, minimising the network's 1-second power peak; a direction that
  starts at or passes the hub must connect within 5-12 minutes both ways). Peaks: spine 123 -> 75 MW,
  phase 2 246 -> 137, all 485 -> 237. Fusion fleet 5/8/14 -> 4/6/10 units; the fleet must also cover
  overnight ice warming, which now sets the full network's size.

## Phase 1: research pass (in progress; passes 1-2 done 2026-11-03)

Pass 1 sourced the top cost drivers (docs/RESEARCH.md items 1-5, reference/benchmarks.yaml,
`mnmaglev benchmarks`); the spine went from $77 bn to $101 bn P50. The benchmarks file and
`tests/test_benchmarks.py` (every anchor inside its parameter range) are the pattern for the rest.
Pass 2 sourced the verify items (climate, frost, census, land, wetlands, power price, Transrapid
geometry and materials, ore) and stations, depot, switch, vehicles, crews and O&M, incl. the FRA
2005 Report to Congress tables; the spine is $101 bn P50. Of 112 parameters: 17 high, 28 medium,
29 low confidence, 38 still placeholders (mostly adders, reserve and local-supply rates, service).

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

**Slice 1 done 2026-11-03 (spine):** `src/mnmaglev/gis.py`, `mnmaglev gis <line>`. USGS 3DEP
elevation (ImageServer) + NLCD 2021 land cover (MRLC WCS) on a 210 m EPSG:5070 grid (7x7 NLCD
pixels per cell, exact class fractions); cost surface from the model's nominal parameters
(structure by cover, land by cover and zone, wetland mitigation, wetland as peat proxy, terrain);
skimage MCP least-cost path between stations; simplified and filleted to the minimum radius
(3,980 m at cruise, 861 m within 15 km of stations); measured per piece, split at climate-zone
latitudes; guideway profile for <=10% grades gives pier heights. Outputs network/alignments/
spine.geojson and network/measured/spine.yaml; `use_measured: true` makes the model use them
(`--no-measured` for the estimates). Spine 354 km, $93.5 bn P50 (estimates: 389 km, $108.1 bn).

**Slice 2 done 2026-11-03 (spine): FEMA floodplains.** NFHL MapServer layer 28 queried per 25 km
tile (count query = map coverage; features in 1% / 0.2% zones and floodways, simplified 15 m),
rasterised at 30 m and averaged per cell. Cost surface: floodway cells priced as bridge, flood
zones get `costs.adders.floodplain`. Measured per piece: floodplain_share, floodplain_1pct_share,
floodway_km, flood_map_coverage; floodway runs count as bridges. The model uses the measured share
where FEMA has maps and the estimate elsewhere. Spine 353 km, 5.7% in flood zones (estimate ~6%),
floodway bridges 0.9 km (Mississippi) and 2.0 km (Minnesota River); line +$2.1 bn P50, spine with
fusion $94.0 bn (one unit fewer after re-optimising the timetable).

**Slice 3 done 2026-11-03 (spine): suburbs and freeway corridors.** NLCD 2021 impervious surface
and impervious descriptor (MRLC WCS, same 30 m grid). Built-up share per cell = ramp on non-road
impervious % (primary and secondary roads left out) from `land.developed.impervious_low` 20% to
`impervious_high` 35%, set from the spine grid's own cells (developed open space p90 19%,
low-intensity median 36%); built-up km are priced as urban viaduct (structure share
`urban_viaduct` on the measured pieces). Freeway corridor = cells with a primary road (descriptor
20, interstates and freeways, 2018 NavStreets) along at least one cell length; there the land is
class `existing_corridor`, now priced as `land.corridor.price_factor` x the land around it (was a
flat $50k/acre, more than the farmland beside it), and guideway gets `costs.adders.highway_corridor`.
Spine 356 km; built-up viaduct 15 -> 33 km; ~12 km beside freeways; line +$6.9 bn; spine with
fusion $102.8 bn (4 units: the new route's 1-second peak is 75 MW, the slice-2 route's was 65).
Rail corridors not modelled (freight railroads set separations case by case, 25-200 ft).

**Phase 2 lines routed 2026-11-03** (iron_range, west, southwest; `use_measured: true`), and the
curve fitting made local: each station-to-station leg of the least-cost path is simplified at
300 m, then, while a curve doesn't fit between its neighbours, the vertex (failing or adjacent)
whose removal adds the least cost on the cost surface is dropped; stations stay fixed. The old
single global tolerance grew to 1.45 km on the west line and cut across lakes (9.6 km of bridge;
~3 km of lake crossings on the spine too). Measured: spine 357 km, Duluth - Hibbing 126 (est.
136), Midway - Moorhead 375 (386), MSP - Mankato 105 (111). Spine with fusion $97.0 bn, phase 2
$234 bn, all $456 bn (phase 3 lines still estimated). The MRLC server answered one of three
parallel downloads with a firewall captcha page; downloads now keep only real TIFFs and retry.

**Tall piers priced 2026-11-03.** Each measured piece records metres x km of guideway above 5, 10,
..., 30 m (`pier_excess_m_km`); the model interpolates at `costs.guideway.pier_height_ref` (20 m,
Transrapid's standard elevated class tops out there) and charges `costs.guideway.tall_pier_per_m`
(0.6 MUSD per km per metre, placeholder engineering estimate). Spine +$67 M P50, Iron Range
+$73 M, others 0: the grade limit needs tall piers only on the Duluth hillside. The route search
doesn't see pier height yet (only a slope term), which matters little at these amounts. Monte
Carlo draws now come from one random stream per parameter; that moved every P50 once by about
the seed-to-seed noise (spine $97.0 -> $97.7 bn; seeds 1-5 give $97.3-97.7 bn).

Next slices, in order of how much they move the result: the phase 3 lines, SSURGO organic soils
(real peat), parcels and buildings, public and tribal lands, and a price for what following a
highway saves in permits and review.

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

The fusion fleet and its demand are already modelled (power.py, fusion.py, 2026-11-03). Calliope
then optimises the mix hour by hour: fusion units, grid, flexible surplus users (electrolysers for
H2-DRI steel, data centres, district heat), and whether staggering departures at the Midway hub
shrinks the peak (and the fleet). Also: cfsem models the fusion units' pulsed air-core coils in
`sim/` (cfsem has no iron, which suits these coil systems better than the maglev magnets).

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
