# minnesota-maglev

A planning model for a Transrapid-style high-speed maglev network in Minnesota. You lay out lines
like in a city builder, and the model prices them as close to reality as it can: the guideway and
what it's built on, land and wetlands, floods, frost and snow, trains, power, operations, and the
iron and copper you'd have to mine to build it.

**Priority corridor:** Duluth - Twin Cities - Rochester (phase 1), with one Twin Cities hub in the
Midway area between Minneapolis and St. Paul, fed by light rail and buses. Then the Iron Range, St. Cloud -
Fargo/Moorhead and Mankato (phase 2). Later: Brainerd/Bemidji, a southern link, and Rochester - La Crosse -
Madison - Milwaukee - Chicago (phase 3, needs partner states).

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
| Spine (GIS-measured route): Duluth - Midway hub - MSP - Rochester, with reserve, local supply, winter heating, staggered timetable and 4 fusion units | 354 | 1 h 01 | $93.5 bn ($81 - 109 bn) |
| Network through phase 2 (6 fusion units) | 987 | | $230 bn ($199 - 268 bn) |
| Everything incl. Chicago (10 fusion units) | 1,962 | | $450 bn ($389 - 524 bn) |

The spine holds room for a **sibling system** right beside it, so the next generation can be
built while this one runs, then they alternate. The two sit ~70 m apart centre to centre (a 50 m
construction separation), far enough that work on one needs no slow orders on the other; the
shared hazards are designed for once, for both (docs/HAZARDS.md). P50 $9.9 bn of the spine. The
land is cheap (~$1.3 bn with contingency); most of it is building city structures and stations
for two from day one. Every other line shows what its reserve would cost in the report.

**Local supply** (on by default): Minnesota-made guideway beams and stator packs, taconite aggregate
near the Range, and long-term supply contracts with Minnesota mines and mills. It saves the spine
~$1.7 bn P50 (~1.7%), mostly from the price hedge of supply contracts (1 contingency point) and one
beam plant serving the whole network; taconite aggregate saves little. Materials are only ~4% of
construction (the report's materials bill), so cheap ore can't move the total much; the ore
pays ~$2.6 M of production tax to the Range on the spine. `--local-supply off` shows it without.

**Fusion power** (on by default): the megaproject builds its own small fusion units (~50 MWe, the
Helion / Zap Energy class), more than the trains need, instead of batteries. The model simulates
every train on the timetable second by second (braking trains feed pulling ones) and sizes the
fleet to cover the 1-second peak plus 10% and one spare unit: the spine averages 24 MW but peaks
at 75 MW with staggered departures (91 MW if every train left on the hour), plus 18 MW of ice
heating during storms, so it gets 4 units (200 MW) for ~$6.9 bn P50, and ~84% of their output (~1.3 TWh/yr) is
surplus for neighbouring users (hydrogen steelmaking on the Range needs ~1 GW, data centres, the
Midway hub district) or the grid. The full network gets 10 units (500 MW). At wholesale prices the
surplus and the grid power the trains no longer buy only just beat the plant's O&M, so the case is
strategic (carbon-free, energy security, Range industry), not cost. Every fusion number is a target
or projection: no fusion plant has made net electricity yet, a first Minnesota unit is ~2035 at the
earliest, and Minnesota's nuclear moratorium may cover fusion (unresolved). Until then the trains
run on grid power, which is what each line's opex shows. `--fusion none` drops the fleet.

**Winter ice** (targeted by default), the way cold railways do it plus one new idea: (1) heat only
the critical spots during icing (stations and their switches, river bridges, ~5% more for grades,
shaded cuts and drifts: 29 km of the spine, 18 MW), the way Shinkansen, Boston and St. Louis heat
switches; (2) storm trains and sweepers through icing nights (St. Louis); (3) clearing vehicles,
slow orders and bus backup for the worst storms (Emsland, Metro Transit); (4) new: warm the whole
guideway overnight on icing nights, in rotation, with fusion units the trains aren't using (82 MW
vs 150 MW idle on the spine). The magnets and stator sit under the deck where ice can't form; the
heated parts are the side guidance rails (10 mm magnet gap) and gliding strips. Heating the whole
line during storms instead would more than double the fusion fleet (9 units for the spine instead of 4). How often it
ices is measured: 20 years of hourly airport weather reports give 224 icing hours a year at Duluth,
~120 in the Twin Cities and St. Cloud, 166 at Rochester (`scripts/icing_hours.py`). The heated
surface, heater cost and overnight warming time are still placeholders (docs/RESEARCH.md 24b-26).

**Staggered timetable** (`network/timetable.yaml`): every line still runs every 30 minutes each way,
but `mnmaglev timetable --write` shifts each direction's departures by whole minutes so trains
don't accelerate at the same moment. It cuts the network's 1-second power peak about in half
(on the measured spine 91 -> 75 MW, everything 524 -> 238 MW), and with it the fusion fleet
(to 4 / 6 / 10 units by phase), while keeping Midway hub connections of 5-12 minutes: trains from
Duluth reach the hub at :19/:49 and the St. Cloud line leaves 6 minutes later (:25/:55); trains from
Moorhead arrive at :21/:51, 6 minutes before the spine leaves for Duluth. Rochester -> St. Cloud riders
still wait ~30 minutes (the rule asks for one good connection per direction, not every pair). With the fleet that lean, overnight ice warming sets
the full network's fleet size, not the daytime peak.

**Measured route (GIS slice 1)**: `mnmaglev gis spine` routes the spine on USGS 3DEP elevation and
NLCD 2021 land cover (210 m cells, each priced with the model's own parameters), smooths it to the
minimum curve radius and measures it. The real route is 354 km (my estimates said 389), Duluth to
the Midway hub in 35 minutes, 1 h 01 end to end; mostly forest (59%) and wetland (21%) north of
Hinckley, cropland (78%) south of Cannon Falls; the Duluth descent needs piers up to ~44 m for a
km to stay within 10%. Spine P50 $93.5 bn vs $108.1 bn on my estimates (`--no-measured`). Treat that
drop as optimistic for now: slice 1 counts only open water as bridge (river valleys and their
floodplains come with FEMA data in slice 2), only dense development as urban (suburbs are priced as
rural), and doesn't see buildings, parcels or highway and rail corridors yet.

The spine works out to ~$259 M per route-km for the line itself (with 24% soft costs, 40% contingency and the
second-system reserve). For scale, in 2026 USD: Shanghai's maglev ~$123 M/km (2004, Chinese costs,
incl. trains and stations); the 2001 Baltimore-Washington Transrapid estimate ~$187 M/km (incl. 40%
contingency); FRA's 2005 range for US maglev ~$59-147 M/km. Early estimates of rail projects have
overrun ~45% on average, which closes most of the gap. The biggest single driver of the range is
still the elevated guideway cost per km.

## How it fits together

| Piece | Role | Status |
|---|---|---|
| `src/mnmaglev` (Python) | parameters, network, costs, land, materials, Monte Carlo, report | working |
| `gis.py` (`mnmaglev gis <line>`) | route a line on USGS elevation + NLCD land cover: least-cost path priced with the model's own parameters, curves >= the minimum radius, pier heights for <=10% grades; measured shares feed the model (`use_measured: true`). Next: floodplains, peat soils, parcels, existing corridors | slice 1 (spine) |
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
That variant (spine through downtown Minneapolis, St. Paul by Green Line) comes to $116.5 bn P50 with fusion,
$8.4 bn more than the Midway hub on the same planner estimates (`--no-measured`: $108.1 bn); the
GIS-measured Midway spine is $93.5 bn. The difference is downtown tunnel, and building it for two
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
