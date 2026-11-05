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
- **2026-11-04, Denver via Des Moines and Omaha** (Jon): a phase 4 line Twin Cities - Owatonna -
  Albert Lea - Mason City - Ames - Des Moines - Omaha - Lincoln - Grand Island - Kearney - North Platte - DEN -
  Denver, not Twin Cities - Chicago - Denver (the rail network's shape, 82% longer than direct) and
  not direct via Sioux Falls (shortest, but ~800 km of nearly empty high plains). Why: 21% longer
  than direct but people the whole way, Iowa's and Nebraska's cities on it, and Des Moines - Denver
  is the trunk a Chicago - Denver line would share. Needs Iowa, Nebraska and Colorado partners.
- **2026-11-04, robot security patrols** (Jon): autonomous ground robots with magnetic gradiometers
  and aerial robots (dock-based drones) watch all the track, charged from the network's own power
  (the fusion fleet). `settings.security: robots`, params/security.yaml, src/mnmaglev/security.py.
  Robots sweep both guideway beams every night while no trains run and the long stator is off,
  comparing each pass with a baseline magnetic map (foreign ferrous objects, tampering, shifted
  stator packs); drones overfly every point of the route hourly, day and night; remote operators
  (10 units each) supervise from an operations room, as BNSF flies its dock-based drones. Fleet
  from coverage: spine 18 robots, 18 drones, 24 docks; network through phase 4 176 robots, 165
  drones, 229 docks, $86 M capital before soft costs and contingency, $32 M/yr (mostly operators),
  0.7 MW of charging (no change to the fusion fleet). Through phase 4 $759.3 bn P50 (was $759.1).
  Cheap next to the line; the open questions are whether a gradiometer can see small objects
  against the stator's own steel, and FAA rules for beyond-visual-line-of-sight flights (RESEARCH 35).
- **2026-11-03, staggered timetable** (Jon): departures staggered at the Midway hub instead of every
  line leaving on the hour. `mnmaglev timetable --write` -> network/timetable.yaml (offsets per line
  and direction, phase by phase, minimising the network's 1-second power peak; a direction that
  starts at or passes the hub must connect within 5-12 minutes both ways). Peaks: spine 123 -> 75 MW,
  phase 2 246 -> 137, all 485 -> 237. Fusion fleet 5/8/14 -> 4/6/10 units; the fleet must also cover
  overnight ice warming, which now sets the full network's size.
- **2026-11-05, cost growth from the reference class** (Jon): contingency is no longer a flat 40%;
  `costs.soft.contingency` is sampled along the rail reference-class curve at the earliest business-
  case stage (median +19%, P80 +121%, mean ~+66%), plus a first-of-kind premium on the maglev-
  specific items (systems, vehicles, switches), full on phase 1 and ~30% of it on later lines. The
  report gives the mean (expected cost) and P80 next to P10 / P50 / P90. Why: rail cost growth is
  skewed (most projects overrun a little, some double), and the flat 40% got the middle about right
  but not the tail. Budget on the mean (as UK appraisal does) or P80; FTA funds at P65.

## Phase 1: research pass (in progress; passes 1-5 done 2026-11-05)

Pass 1 sourced the top cost drivers (docs/RESEARCH.md items 1-5, reference/benchmarks.yaml,
`mnmaglev benchmarks`); the spine went from $77 bn to $101 bn P50. The benchmarks file and
`tests/test_benchmarks.py` (every anchor inside its parameter range) are the pattern for the rest.
Pass 2 sourced the verify items (climate, frost, census, land, wetlands, power price, Transrapid
geometry and materials, ore) and stations, depot, switch, vehicles, crews and O&M, incl. the FRA
2005 Report to Congress tables; the spine is $101 bn P50. Of 112 parameters: 17 high, 28 medium,
29 low confidence, 38 still placeholders (mostly adders, reserve and local-supply rates, service).
Pass 3 (2026-11-04, guideway civil costs; three research agents in parallel, every figure used
checked against its source): conventional HSR viaducts as comparators, US urban viaducts and
Minnesota bridge unit costs. Elevated guideway 65 -> **75** MUSD/km (45-120): anchors now run 60-90
(Transrapid Munich itemised 60, HS2 viaduct target 65 / budget 90, SCMaglev viaduct 76, FRA
Pittsburgh 79, Pittsburgh promoter 81; median ~77), Texas Central's civil contract averages 64 per
km over a route half on viaduct; Minnesota bridges cost about half the US state average (FHWA 2025:
$208 vs $393/ft2), so the value sits a little below the median. At grade follows by the German
ratio: 52 -> **60** (36-95). Urban viaduct stays 150 with CA HSR San Jose unit prices (157-176
without their contingency) as new anchors. Context only (other cost levels): China HSR viaduct
~23, India ~18, a plain Minnesota highway-type deck ~27 per km. Every line +6-9%: spine with fusion
$100.8 bn (was $94.3), phase 2 $248.4 bn, phase 3 $480.7 bn, through phase 4 $802.7 bn (P10 685.6,
P90 933.2). The elevated guideway is still the top driver (correlation 0.52 -> 0.60, the range is
wider): the evidence moved it up, it didn't narrow it. Not found: a published guideway share of
Shanghai's cost, Chuo Shinkansen viaduct-only costs, CA HSR construction packages split by
structure, Brightline West's civil contract.
Pass 4 (2026-11-05, propulsion, power supply and control; three research agents again: maglev
sources, conventional HSR systems, long-stator components bottom-up; every figure used checked
against its source). `costs.systems.propulsion_power_control` 27 -> **21** MUSD/km (10-40), low ->
medium confidence. New anchors: the Berlin-Hamburg planning company's itemisation (stator carrier,
winding, power plant, operations control; 1993) 20.7, Transrapid International's unit prices for
Pittsburgh (1991) 19.6, FRA Anaheim-Ontario 19.1; anchor median 20.2. Two corrections to what we
held: Vieregg-Rössler's Munich power line was their own doubling of the ICE electrification cost
(27.0 -> 20.2 halved back), and FRA Table A-3 states a 10-30% contingency for Baltimore-Washington
and Pittsburgh, now removed as for CA HSR (BW 32.1 -> 26.7; Pittsburgh guideway 78.8 -> 65.7, which
moves the elevated-guideway anchor median 77 -> 71 while the value stays 75). Context: Shanghai
(Siemens share, no stator) ~31, Chuo electrical lines ~30 (SCMaglev, mostly tunnel), conventional
HSR systems 3.5-9 per km (China, HS2 contracts, CA HSR). Bottom-up from Shanghai's scope of supply
(~4,170 stator packs and ~32 km of winding cable per route-km, 2 switch stations per km, substations
10-50 km apart): ~11 hardware, 15-19 with installation. Every line -2-3%: spine with fusion
$98.3 bn, phase 2 $241.9 bn, phase 3 $467.7 bn, through phase 4 $779.7 bn (P10 667.9, P90 906.7).
Open: older electrical anchors are inflated with the highway construction index (~3.2x since 2002);
BLS producer prices rose 3.2x for transformers, 2.2x for motors and generators, 1.4x for electrical
machinery as a whole, so an electrical blend would put them ~15-25% lower (docs/RESEARCH.md).
Pass 5 (2026-11-05, contingency and cost growth; three research agents: maglev and HSR cost
histories, the reference-class literature, US and Minnesota projects; every figure used checked
against its source). Evidence, cost growth from an early estimate: rail reference class at the UK's
earliest business-case stage (OGP for DfT 2020, n=355) median +19%, mean +56%, P80 +121%, 7 in 10
overran; US New Starts from entry to preliminary engineering (FTA 2020, 29 projects, our recount)
median 1.18, mean 1.54, P80 1.68, but ~1.00 from the funding agreement; FTA's minimum contingency
40% at 15% design (P65); Flyvbjerg (2006) rail 40% at P50, 57% at P80 from the decision to build.
Maglev and new HSR: Chuo 5.52 -> 11.0 trillion yen on the same route (1.58-1.76x after JR Central's
own price items; the growth came from ground, seismic design, spoil and prices), Munich Transrapid
1.85 -> 3.4 bn EUR in six months before cancellation, HS2 Phase One 35-45 -> 70.9-82.2 bn GBP (2019
prices) since the 2020 notice to proceed, Shanghai 1.12x (8.9 -> 9.943 bn RMB, the only low case).
Minnesota: Southwest LRT 1.25 -> 2.86 bn (2.29x YOE, +38% after the start of construction, OLA);
Central Corridor and Northstar came in under their funding agreements. The model now samples cost
growth along that rail curve and adds a first-of-kind premium (decision above). Effect: through
phase 4 P50 $779.7 -> $706.3 bn, but the mean is **$932.5 bn**, P80 $1,284.9 bn, P90 $1,775.6 bn
(was P90 $906.7 bn); spine P50 $93.6 bn, mean $121.6 bn, P80 $166.5 bn. Cost growth now dominates
the uncertainty (+0.96); the report also ranks parameters against the base estimate, where the
elevated guideway (+0.67) and systems (+0.51) still lead.

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
(structure by cover, land by cover and zone, wetland mitigation, peat from SSURGO, terrain);
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

**Phase 3 lines routed 2026-11-04** (north_woods, southern_link, great_lakes; `use_measured: true`),
so every line now runs on a measured route. St. Cloud - Bemidji 233 km (est. 250), Rochester -
Mankato 125 (132), Rochester - Chicago 556 (593); all curves fit, smoothed routes within 2% of the
least-cost path. Chicago line P50 $139.3 bn (est. $138.5): shorter, but more suburbs, bridges and
land, and piers up to 96 m off the Mississippi bluffs and across the Driftless Area (+$0.6 bn).
Network 1,877 km, all phases $453.7 bn (estimates $471.2), fleet 4 / 6 / 9 units. Phase 1-2
timetable offsets unchanged. Wisconsin and Illinois are priced with Minnesota land prices and
climate zones (RESEARCH 29).

**Slice 4, peat soils, 2026-11-04.** gSSURGO 30 m map unit keys from UC Davis SoilWeb's WCS
(the service soilDB's `mukey.wcs` uses; ~1-2 MB per 63 km tile) and each map unit's components
from USDA Soil Data Access: peat = the Histosol share (peat and muck), where the survey is
complete; wetland stands in where it isn't (NOTCOM; 91-100% coverage per line). gSSURGO, not
gNATSGO: SoilWeb's gNATSGO keys weren't in SDA's live tables. The peat adder
(`costs.adders.peat_soft_ground`) is unchanged and still a placeholder (RESEARCH 30). With peat
cheaper up north the least-cost path moved, and on the west line the corner-deleting curve fit
then cut across the Otter Tail lakes (6.9 km of bridges); a refinement pass (move corners, add
gentle bends where that lowers the cost and every curve fits) fixed it and every line now
smooths to within 2% of its least-cost path. All seven lines re-routed: spine 353 km, $94.3 bn
with fusion (3 units, by 0.2 MW), phase 2 $230.1 bn, all $446.4 bn; peat alone -$3.5 bn.

**Slice 5, buildings and parcels, 2026-11-04.** FEMA / ORNL USA Structures (CC BY 4.0; centroid,
occupancy class and footprint of every building over 450 sq ft, national) and MnGeo's open county
parcels (assessed land EMV per acre; 59 of 87 counties), both from ArcGIS feature services in
10 km tiles within 15 km of each line's last alignment (land cover stands in further out). A
building is taken when the right-of-way touches it: per km through a cell, sum (W + sqrt(footprint))
x 1000 / cell area, checked against polygon geometry in a test. Takes are priced per home (assessed
building value, median $254,500 from 367,871 spine-grid parcels, + Uniform Act relocation) and per
m2 for businesses and farm buildings (+ business relocation, placeholders), plus demolition; not
in dense urban cells (street running), over water or in freeway right-of-way. Land: parcel EMV
x `land.parcels.emv_to_market` where counties publish parcels, class prices elsewhere; the suburban
class price is now land only, from the parcels ($0.23 M/acre, was $0.35 M incl. buildings). Both
go into the cost surface, so the router steers around houses. All seven lines re-routed (all
curves fit): spine 352 km, ~535 homes and ~32 other buildings taken ($0.2 bn nominal), line P50
$87.5 bn (was $88.8 bn: land at parcel prices, -$0.2 bn nominal, mostly NLCD 'urban' cells in
small cities that were priced like downtown Minneapolis); with fusion $94.6 bn, up $0.3 bn because
the fleet went back to 4 units (the 1-second peak moved 74.6 -> 87.2 MW on a route 0.3 km
shorter; phase 2 130 -> 167 MW, 5 -> 6 units). Correction (later the same day): those peaks ran on
the slice-4 timetable offsets; `mnmaglev timetable` without `--write` only prints, so the offsets
re-optimised for the new routes were never saved (fixed with phase 4, below).
Phase 2 $228.6 bn, all $443.0 bn (was $446.4 bn). Network: 2,312 homes and 214 other buildings
taken.
The routes now steer around houses: counted cell by cell along each path at the 20 m elevated width
on the same building layers, homes taken went spine 480 -> 460, west 486 -> 417, Great Lakes
946 -> 757 (old alignments vs new; other buildings about the same). The report's counts differ
because it averages building density over each measured piece.

**Slice 6, public and tribal land, 2026-11-04.** USGS PAD-US 4.1 fee lands (National Map service;
owner, manager, designation, unit name; public domain) and Census TIGER federal reservations and
off-reservation trust land. Section 4(f) land = publicly owned parks, recreation areas, refuges
(incl. FWS waterfowl production areas, state WMAs and SNAs), conservation and historic areas;
national, state and county forests are multiple-use and priced like the land around them. Where a
route uses 4(f) land outside freeway right-of-way it buys replacement land
(`land.public.section_4f_replacement`); tribal land costs `land.tribal.consent_multiplier` x the land
price. The route search also pays `section_4f_avoidance_km` (1 km of elevated guideway per km of
4(f) land) and `tribal.avoidance_km` (2) to stay out: placeholders, since 49 U.S.C. 303 allows a
use only without a feasible and prudent alternative and 25 CFR 169 needs the tribe's consent. Each
measured line lists the named units it crosses. All seven lines re-routed (all curves fit): 4(f)
land crossed 84 -> 15 km over the network, tribal land 1.8 -> 0 km (the Chicago line left Ho-Chunk
trust land; the spine now stays on the Minnesota side of the St. Croix, through Chengwatana State
Forest, instead of crossing the riverway into Wisconsin and back). The avoidance isn't free: spine
353 -> 359 km (around Duluth's hillside parks, +1.1 min),
west 371 -> 379 km (around Elm Creek Park Reserve), and on the Chicago line built-up viaduct
19.7 -> 28.0 km, because in the suburbs the parks and forest preserves were the open gaps. Line P50
spine $88.8 bn (was $87.5), west 80.9 (80.3), southwest 24.1 (23.5), Chicago 139.5 (137.3); 4(f)
replacement land and tribal premiums $33 M nominal in all. Spine with fusion $95.8 bn, phase 2
$231.1 bn, all $447.8 bn (was $443.0; P10 387.3, P90 518.1). Fusion fleet 4 / 6 / 9 units, still on
the stale slice-4 offsets (spine 1-second peak 74.8 MW); see phase 4 for the re-optimised timetable.

**Phase 4 line: Twin Cities - Des Moines - Omaha - Denver, 2026-11-04 (planner estimates).** Jon
(2026-11-04): reach Denver from Minneapolis through Des Moines and Omaha, not through Chicago, and
serve Iowa's and Nebraska's cities; Albert Lea a stop too (Jon: "a solid town"). Straight-line km: MSP - Chicago - Denver 2,049, this route
1,394, MSP - Denver direct 1,122; Des Moines - Omaha - Denver is also the trunk a Chicago - Denver
line would share (Chicago - Des Moines - Omaha - Denver is as short as Chicago - Denver direct,
1,478). Stations: MSP, Owatonna (transfer to the Rochester - Mankato line), Albert Lea, Mason City, Ames, Des
Moines, Omaha / Council Bluffs, Lincoln, Grand Island, Kearney, North Platte, Denver airport (DEN),
Denver Union Station; I-35 to Des Moines (Owatonna, Albert Lea, Mason City, Ames and Ankeny lie
within a few km of the straight line), I-80 and the Platte valley, I-76 to Denver (via North Platte
is 26 km longer than Kearney - Denver direct). Populations: 2020 Census via TIGERweb. Shares,
bridges and urban km are planner estimates until GIS routes it; Minnesota land prices and climate
zones stand in (RESEARCH 34). Result: 1,486 km, MSP - Denver 4 h 26 with 11 intermediate stops
(MSP - Des Moines ~1 h 11 of running time, - Omaha ~1 h 44), $302.9 bn P50 (P10 258.6, P90 353.0),
$204 M per km, 23 trains; the Albert Lea stop adds ~5 min and $2.4 bn P50. Timetable re-optimised for every phase with `--write` (the slice 5 and 6
routes had run on stale offsets): 1-second peaks 67 / 134 / 236 / 390 MW, fusion fleet 3 / 6 / 9 /
16 units (phase 4's seven new units are set by overnight ice warming of the long line, $8.2 bn).
Spine with fusion $94.2 bn (3 units again), phase 2 $231.1 bn, phase 3 $447.8 bn, through phase 4
$759.1 bn (P10 654.3, P90 880.9).

**Denver line routed on GIS, 2026-11-04** (`use_measured: true`). Its bounding box (631k km2, an
L of mostly empty plains) would have been ~3.5 GB of rasters and 14 M cells, so lines can now be
routed in sections (`gis_split_at` in lines.yaml; `mnmaglev gis <line> --section N` routes one
section on its own grid, `--reuse-sections` joins them): four grids split at Des Moines, Lincoln and
North Platte (211k km2, 1.4 GB, cached on D: through a junction at data/raw/gis/heartland), run in
parallel in 25-63 min each; the sections meet at the split stations. All curves fit (surface cost
smoothed 111.4 vs least-cost path 114.9 bn: the refinement pass beats the raw path). Measured 1,434 km (planner
1,486; detours 1.01-1.07 outside the metro approaches), MSP - Denver 4 h 12, $288.1 bn P50 (P10
246.1, P90 335.7; planner $303.0 bn), $201 M per km, 22 trains; ~1,140 homes taken (Omaha - Lincoln
234, Ames - Des Moines 187, the MSP approach 154); bridges: the Missouri 420 m, the Platte 1.4 km
south of Omaha and 0.6 km toward Grand Island. Fusion fleet 3 / 6 / 9 / 15 units. Through phase 4
$743.4 bn (P10 640.8, P90 862.9). Caveats: land out of state is priced with Minnesota class prices
(no parcels), so NLCD 'urban' cells in Omaha, Lincoln and Denver cost $3 M/acre (the slice-5
problem; land $1.7 bn of the line), and the route crosses 5.9 km of Rocky Mountain Arsenal National
Wildlife Refuge between DEN and Denver: going around through Commerce City and Montbello costs more
as urban viaduct than the 4(f) penalty, but a refuge crossing needs a compatibility finding under
16 U.S.C. 668dd and the refuge is a former chemical-weapons Superfund site. RTD's A Line runs from
DEN to Union Station in a rail corridor along its south edge; rail corridors aren't modelled yet.
Quick fix the same day: a new point type `via` (cities.yaml), a point the GIS route must pass
through (legs run between stations and via points; pieces are still measured station to station),
and `den_a_line` south-east of the refuge near I-70 and Pena Blvd. Section 3 re-routed (7 min on
cached data): the refuge is out, DEN - Denver 31.1 -> 34.2 km, 4(f) land on it 2.3 km (City Park
golf course). A measured piece spanning planner segments now inherits along the chain, the segment
arriving at its end winning (DEN - Denver keeps its 30% urban tunnel; before, it took the via
segment's 0%). Line: 1,437 km, 4 h 12, $289.6 bn P50 (P10 247.4, P90 337.2); through phase 4
$744.8 bn (P10 641.9, P90 864.3); other lines unchanged. Still open: from the via point the route
heads straight for downtown through Park Hill (362 homes on that piece) instead of the A Line's
40th Avenue rail corridor; the rail-corridor slice or a second via point would fix it.

Next slices, in order of how much they move the result: how hard to avoid 4(f) land (the
placeholder avoidance moved ~$4.8 bn; RESEARCH 33), out-of-state land prices and parcels
(Wisconsin's statewide parcel layer; RESEARCH 32), a price for what following a highway saves in
permits and review, travel time in the route search (detours cost minutes it doesn't see), and the
fusion fleet's sensitivity to the 1-second peak (it swings a unit, ~$1.7 bn, when the timetable
offsets aren't re-optimised after a re-route; `gis` should re-run the timetable, or warn).
Out-of-state land prices and parcels for the Denver and Chicago lines (RESEARCH 29, 32, 34), and
rail corridors (the DEN - Denver approach should follow RTD's A Line into Union Station; a via point
keeps it out of Rocky Mountain Arsenal NWR for now), and a higher avoidance weight (or a no-go) for
national wildlife refuges. Also: small water crossings (<100 m, or cells under half water) aren't counted as
bridges.

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

## Phase 9: value engineering (later, after design development)

Jon (2026-11-05): bring the price down at the value-engineering stage with the Boltzmann trade model
from cortenforge-play (`src/trade`: closed giving loops where everyone comes out ahead, chosen as a
QUBO and annealed on CortenForge's thermostat). Two fits:
- Design options as a QUBO: discrete choices per segment (elevated / at grade, span type, station
  layout, supply source, alignment variants) with the interactions the model already prices (shared
  beam plant and depots, the sibling-system corridor, phasing); anneal for the cheapest consistent set.
- In-kind trades with other parties: excavated spoil and taconite tailings to road and fill projects
  (Chuo's spoil alone cost 0.3 trillion yen), land swaps and MnDOT right-of-way, fusion surplus power,
  farm leasebacks or crossing rights; multi-party haves and wants, as in the laundromat.
Keep the reference-class cost growth on top of a value-engineered base, so the savings don't make the
expected cost optimistic again. Use CortenForge as an end user (published crates).
