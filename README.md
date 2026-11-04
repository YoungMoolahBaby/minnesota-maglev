# minnesota-maglev

A planning model for a Transrapid-style high-speed maglev network in Minnesota. You lay out lines
like in a city builder, and the model prices them as close to reality as it can: the guideway and
what it's built on, land and wetlands, floods, frost and snow, trains, power, operations, and the
iron and copper you'd have to mine to build it.

**Priority corridor:** Duluth - Twin Cities - Rochester (phase 1), with one Twin Cities hub in the
Midway area between Minneapolis and St. Paul, fed by light rail and buses. Then the Iron Range, St. Cloud -
Fargo/Moorhead and Mankato (phase 2). Later: Brainerd/Bemidji, a southern link, and Rochester - La Crosse -
Madison - Milwaukee - Chicago (phase 3, needs partner states), and Twin Cities - Des Moines - Omaha -
Denver (phase 4, needs partner states).

## What it does today (phase 0)

```
uv sync
uv run mnmaglev check            # validate every parameter and the network
uv run mnmaglev report           # -> out/report.md, out/results.json, out/map.html
uv run mnmaglev report --phase 1 # just the spine
uv run mnmaglev benchmarks       # sourced cost benchmarks in 2026 USD vs the parameter ranges
uv run mnmaglev report --local-supply off   # the same without the Minnesota local-supply policy
uv run mnmaglev report --fusion none            # the same without the fusion fleet (grid power only)
uv run mnmaglev report --winter-heating full    # heat the whole guideway during icing (vs targeted / none)
uv run mnmaglev report --security none          # without the robot and drone patrols
uv run mnmaglev timetable --write               # stagger departures to cut the power peak, keep hub connections
uv sync --extra gis && uv run mnmaglev gis spine # route a line on elevation + land cover (downloads ~85 MB, cached)
uv run pytest
```

- **Every number has a range and a source.** `params/*.yaml`: value, low, high, unit, confidence
  (high / medium / low / placeholder), source. The report counts how many are still placeholders.
- **Monte Carlo cost ranges** (P10 / P50 / P90) per line and per phase, and a **sensitivity table**
  that ranks which unknowns move the total most, so research goes where it counts.
- **Running times and energy from physics**: speed profile with acceleration and urban speed limits;
  drag uses the air density of each climate zone, so a -10 C Duluth winter costs energy through the
  physics, not a guessed factor.
- **Land and wetlands**: right-of-way acres by structure type, land price by class, acquisition
  premium, wetland fill and Minnesota Wetland Conservation Act replacement credits.
- **Climate and ground**: floodplain, peat and frost-zone foundation adders, snow-scaled winter O&M.
- **Materials and ore**: concrete, cement, aggregate, rebar, electrical steel, aluminium, copper,
  and back to iron pellets, crude taconite (Mesabi Range) and copper ore (Duluth Complex grades).
- **Map**: `out/map.html`, the network on OpenStreetMap with costs and times in the popups.

After research passes 1-2 (2026-11-03; cost, Minnesota and Transrapid parameters sourced, see
`reference/benchmarks.yaml`; still concept-stage, see the report for the caveats):

| | Route km | End to end | Capital P50 (P10 - P90) |
|---|---|---|---|
| Spine (GIS-measured route): Duluth - Midway hub - MSP - Rochester, with reserve, local supply, winter heating, robot security patrols, staggered timetable and 3 fusion units | 359 | 1 h 02 | $94.3 bn ($82 - 109 bn) |
| Network through phase 2, all GIS-measured (6 fusion units) | 966 | | $231 bn ($200 - 268 bn) |
| Through phase 3, incl. Chicago, all GIS-measured (9 fusion units) | 1,881 | | $448 bn ($387 - 518 bn) |
| Through phase 4, incl. Denver via Des Moines and Omaha (planner estimates, 16 fusion units) | 3,364 | MSP - Denver 4 h 26 | $759 bn ($655 - 881 bn) |

(2026-11-04: GIS slices 1-6, i.e. elevation, land cover, floods, suburbs and freeways, peat,
buildings and parcels, public and tribal land; the Denver line isn't routed yet.)

The spine holds room for a **sibling system** right beside it, so the next generation can be
built while this one runs, then they alternate. The two sit ~70 m apart centre to centre (a 50 m
construction separation), far enough that work on one needs no slow orders on the other; the
shared hazards are designed for once, for both (docs/HAZARDS.md). P50 $9.0 bn of the spine. The
land is cheap (~$1.3 bn with contingency); most of it is building city structures and stations
for two from day one. Every other line shows what its reserve would cost in the report.

**Local supply** (on by default): Minnesota-made guideway beams and stator packs, taconite aggregate
near the Range, and long-term supply contracts with Minnesota mines and mills. It saves the spine
~$1.5 bn P50 (~1.6%), mostly from the price hedge of supply contracts (1 contingency point) and one
beam plant serving the whole network; taconite aggregate saves little. Materials are only ~4% of
construction (the report's materials bill), so cheap ore can't move the total much; the ore
pays ~$2.3 M of production tax to the Range on the spine. `--local-supply off` shows it without.

**Fusion power** (on by default): the megaproject builds its own small fusion units (~50 MWe, the
Helion / Zap Energy class), more than the trains need, instead of batteries. The model simulates
every train on the timetable second by second (braking trains feed pulling ones) and sizes the
fleet to cover the 1-second peak plus 10% and one spare unit: the spine averages 25 MW but peaks
at 67 MW with staggered departures (94 MW if every train left on the hour), plus 17 MW of ice
heating during storms: 92 MW with the 10% margin, under the 100 MW two working units give, so it
gets 3 units (150 MW, one spare) for ~$5.4 bn P50 (re-optimise the timetable after every re-route:
on stale offsets the peak can jump past 100 MW and add a unit), and
~80% of their output (~0.9 TWh/yr) is surplus for neighbouring users (hydrogen steelmaking on the Range needs ~1 GW, data centres, the
Midway hub district) or the grid. Through phase 3 the network gets 9 units (450 MW), through phase 4 16. At wholesale prices the
surplus and the grid power the trains no longer buy only just beat the plant's O&M, so the case is
strategic (carbon-free, energy security, Range industry), not cost. Every fusion number is a target
or projection: no fusion plant has made net electricity yet, a first Minnesota unit is ~2035 at the
earliest, and Minnesota's nuclear moratorium may cover fusion (unresolved). Until then the trains
run on grid power, which is what each line's opex shows. `--fusion none` drops the fleet.

**Winter ice** (targeted by default), the way cold railways do it plus one new idea: (1) heat only
the critical spots during icing (stations and their switches, river bridges, ~5% more for grades,
shaded cuts and drifts: 26 km of the spine, 16 MW), the way Shinkansen, Boston and St. Louis heat
switches; (2) storm trains and sweepers through icing nights (St. Louis); (3) clearing vehicles,
slow orders and bus backup for the worst storms (Emsland, Metro Transit); (4) new: warm the whole
guideway overnight on icing nights, in rotation, with fusion units the trains aren't using (74 MW
vs 100 MW idle on the spine). The magnets and stator sit under the deck where ice can't form; the
heated parts are the side guidance rails (10 mm magnet gap) and gliding strips. Heating the whole
line during storms instead would more than double the fusion fleet (8 units for the spine instead of 3). How often it
ices is measured: 20 years of hourly airport weather reports give 224 icing hours a year at Duluth,
~120 in the Twin Cities and St. Cloud, 166 at Rochester (`scripts/icing_hours.py`). The heated
surface, heater cost and overnight warming time are still placeholders (docs/RESEARCH.md 24b-26).

**Staggered timetable** (`network/timetable.yaml`): every line still runs every 30 minutes each way,
but `mnmaglev timetable --write` shifts each direction's departures by whole minutes so trains
don't accelerate at the same moment. It cuts the network's 1-second power peak about in half
(on the measured spine 95 -> 75 MW, everything 648 -> 225 MW), and with it the fusion fleet
(to 3 / 5 / 9 units by phase), while keeping Midway hub connections of 5-12 minutes: trains from
Duluth reach the hub at :01/:31 and the St. Cloud line leaves 10 minutes later (:11/:41); trains from
Moorhead arrive at :23/:53, 10 minutes before the spine leaves for Rochester. Rochester -> St. Cloud
riders wait 16 minutes and Moorhead -> Duluth ~34 (the rule asks for one good connection per
direction, not every pair, and which pairs get it changes whenever the timetable is re-optimised).
The spine sits right on a step (see Fusion power): 0.2 MW more peak and it needs a fourth unit. With
the fleet that lean, overnight ice warming sets the full network's fleet, not the daytime peak.

**Measured routes (GIS slices 1-4; every line)**: `mnmaglev gis <line>` routes a
line on USGS 3DEP elevation, NLCD 2021 land cover and impervious surface, FEMA flood maps and
gSSURGO soils (210 m cells, each priced with the model's own parameters), fits curves of at least
the minimum radius and measures it. The spine is 353 km (my estimates said 389), Duluth to the
Midway hub in 34 minutes, 1 h 01 end to end; mostly forest and wetland north of Hinckley, cropland south of Cannon Falls.
Climbing out of Duluth the guideway crosses the hillside's ravines on piers up to ~70-80 m (about
1 km of each line over 25 m) to stay within 10%. Piers above 20 m (the top of Transrapid's standard
elevated guideway) pay ~$0.6 M per km for every metre above it (a placeholder engineering
estimate): +$50 M P50 on the spine and +$59 M on the Iron Range line. The Chicago line needs
them more: it drops off the bluffs to the Mississippi at Winona and La Crosse and crosses the
Driftless Area's ridges, on piers up to ~86 m (~430 m x km above 20 m, +$0.65 bn P50). Almost
everywhere else the 10% grade limit needs no lift at all.

| Line (GIS-measured) | Route km (estimate) | End to end | Line P50 (estimate) |
|---|---|---|---|
| Spine | 353 (389) | 1 h 01 | $88.8 bn ($102.5 bn) |
| Duluth - Virginia - Hibbing | 124 (136) | 24 min | $28.3 bn ($30.9 bn) |
| Midway hub - St. Cloud - Alexandria - Moorhead | 370 (386) | 1 h 04 | $80.6 bn ($79.4 bn) |
| MSP - Mankato | 104 (111) | 17 min | $23.8 bn ($25.0 bn) |
| St. Cloud - Brainerd - Bemidji | 233 (250) | 39 min | $47.2 bn ($51.4 bn) |
| Rochester - Owatonna - Mankato | 125 (132) | 24 min | $25.7 bn ($28.0 bn) |
| Rochester - La Crosse - Madison - Milwaukee - Chicago | 556 (593) | 1 h 42 | $137.5 bn ($138.5 bn) |

Every measured line is shorter than my straight-line-plus-detour estimate. The west line costs
more anyway: it starts with ~15 km of north-metro suburbs priced as built-up viaduct, and lake
country around Alexandria and Fergus Falls still takes ~2.1 km of bridges (I had 0.6 km). The
Chicago line is 37 km shorter but costs about the same: ~68 km of Madison, Milwaukee and Chicago
suburbs priced as built-up viaduct (I had 49), 3.6 km of bridges (2.5) and land at $1.7 bn (0.7),
with Wisconsin and Illinois land still priced at Minnesota rates.
Curves are fitted locally: each station-to-station leg of the least-cost path is simplified to
300 m, and where a curve doesn't fit, the vertex whose removal adds the least cost goes. The first
version straightened the whole line by one tolerance (up to 1.45 km on the west line) and cut
straight across lakes the least-cost path went around: 9.6 km of bridges on the west line, ~3 km
of needless lake crossings on the spine. Deleting corners alone still failed where the least-cost
path threads gaps between lakes too tight for 4 km curves (with the soil data the west line's
bridges went 2.4 -> 6.9 km), so the fitted line is then refined: corners nudged sideways and gentle
bends added on long straights wherever that lowers the cost and every curve still fits. Smoothed
routes now cost within 2% of the least-cost path, either way (the path's cell-by-cell staircase
costs a little more than a straight chord through the same cells).
- Floods (slice 2): 5.7% of the spine is in a 1% or 0.2% annual-chance flood zone (my estimate was
  ~6%); regulatory floodways are bridged, so river crossings are as long as the floodway, not
  just the water (the Minnesota River ~1.7 km).
- Peat (slice 4): the soil survey (gSSURGO, 30 m) gives each cell's share of Histosols, the
  organic soils (peat and muck, >= 40 cm of organic matter) that need deep piles; where the survey
  isn't complete (5% of the spine) the wetland share still stands in. I had used wetland for
  peat everywhere, and up north only about 40% of wetland is peat: the spine is 5% peat (13%
  wetland), the Iron Range line 16% (38%), Bemidji 11% (22%). In the southern farm belt it runs
  the other way: drained muck fields are cropland now, so Owatonna - Mankato is 6% peat on 5%
  wetland. Network -$3.5 bn P50 (same routes, peat vs the wetland proxy); the spine -$0.8 bn.
- Suburbs (slice 3): a cell is priced as built-up (urban viaduct) by how much of it is paved or
  built, interstates left out, on a ramp from 20% (parks and lawns stay rural) to 35% (a typical
  single-family suburb). Built-up viaduct on the spine went from 15 to 33 km: +$6.9 bn P50.
- Freeways (slice 3): the route may run in interstate right-of-way (NLCD's primary roads), where
  land costs a quarter of the land around it (federal law lets a state lend it to a public
  transit authority free) but building beside traffic costs 5% more. It uses only ~12 km: in the
  country the land it saves is worth ~$0.07 M/km against ~$3 M/km of extra building. What really
  pulls lines like Brightline West into highway medians (permits, environmental review on land
  already disturbed, public acceptance) isn't priced yet. Rail corridors are left out: freight
  railroads set the separation case by case.

Spine P50 $94.3 bn vs $109.5 bn on my estimates (`--no-measured`); through phase 2 $230 bn vs
$248 bn. Monte Carlo noise at 5,000 samples is about +-$0.3 bn on the spine (seeds 1-5:
$97.3-97.7 bn); each parameter has its own random stream, so adding one doesn't reshuffle the rest. Still not seen: buildings and parcels one by one,
public and tribal land.

The spine works out to ~$251 M per route-km for the line itself (with 24% soft costs, 40% contingency and the
second-system reserve). For scale, in 2026 USD: Shanghai's maglev ~$123 M/km (2004, Chinese costs,
incl. trains and stations); the 2001 Baltimore-Washington Transrapid estimate ~$187 M/km (incl. 40%
contingency); FRA's 2005 range for US maglev ~$59-147 M/km. Early estimates of rail projects have
overrun ~45% on average, which closes most of the gap. The biggest single driver of the range is
still the elevated guideway cost per km.

## How it fits together

| Piece | Role | Status |
|---|---|---|
| `src/mnmaglev` (Python) | parameters, network, costs, land, materials, Monte Carlo, report | working |
| `gis.py` (`mnmaglev gis <line>`) | route a line on USGS elevation + NLCD land cover and impervious surface + FEMA flood zones + gSSURGO peat soils: least-cost path priced with the model's own parameters, floodways bridged, suburbs as built-up, interstate right-of-way, curves >= the minimum radius, pier heights for <=10% grades (tall piers priced by height), peat; measured shares feed the model (`use_measured: true`). Next: parcels, public and tribal land | slices 1-4 (all lines) |
| [OSRD](https://github.com/OpenRailAssociation/osrd) | running time, timetables and capacity on the real alignments (`integrations/osrd`) | planned |
| `power.py`, `fusion.py` | second-by-second traction demand from the timetable; the fusion fleet sized from its peak, surplus and costs | working |
| [Calliope](https://calliope.readthedocs.io/) | optimise the power mix (fusion units, grid, surplus users) hour by hour (`integrations/calliope`) | planned |
| cfsem | long-stator and levitation magnet sizing (replaces the derived stator steel per km), and the fusion units' pulsed air-core coils (`sim/`) | planned |
| CortenForge | the 3D city-builder view: lidar terrain, guideway, trains running the OSRD timetable, hazard overlays (`sim/`) | planned |

See [docs/PLAN.md](docs/PLAN.md) for the phases, [docs/RESEARCH.md](docs/RESEARCH.md) for what to firm
up first, [docs/HAZARDS.md](docs/HAZARDS.md) for snow, rain, floods and freezing, and
[docs/SOURCES.md](docs/SOURCES.md) for data sources and their licenses.

## Edit the network

`network/lines.yaml` is the city-builder part: add a line through ids from `network/cities.yaml`,
set its structure mix (elevated / at grade / urban viaduct / tunnel), land classes, floodplain and
peat shares, and long bridges. `mnmaglev check` tells you if anything doesn't add up.

Alternatives live in `network/variants/` (lines there replace the same ids):
`uv run mnmaglev report --variant downtown_minneapolis` writes `out/downtown_minneapolis/`.
That variant (spine through downtown Minneapolis, St. Paul by Green Line) comes to $116.7 bn P50 with fusion,
$7.2 bn more than the Midway hub on the same planner estimates (`--no-measured`: $109.5 bn); the
GIS-measured Midway spine is $97.7 bn. The difference is downtown tunnel, and building it for two
systems downtown.

## Honest caveats

- **Concept stage** (AACE class 5: -50% / +100%). Most cost parameters are benchmarks or placeholders.
- **Who would build it.** Transrapid technology is largely dormant in Germany; China's CRRC has the
  live high-speed maglev programme. US rules on federal funding for Chinese-built rail vehicles may
  matter. Vendor and procurement risk is research item 2.
- **The mines.** Mesabi taconite is mined today, but Minnesota pellets are made into steel in mills
  out of state, and electrical steel comes from a few specialised mills. Duluth Complex copper-nickel
  is not in production, and its permits are contested and in court. Aluminium has no Minnesota source.
  The model counts the ore; where it can really come from is a research question, not an assumption.
- **Land.** Corridors cross tribal lands (e.g. near Cloquet and Hinckley), state and national forest.
  These need consultation, not a price per acre.

## License

Apache-2.0. Data you download into `data/` keeps its own license (see docs/SOURCES.md).
