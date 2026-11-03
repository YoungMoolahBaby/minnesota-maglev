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

First run (2026-11-03, all numbers concept-stage, see the report for the caveats):

| | Route km | End to end | Capital P50 (P10 - P90) |
|---|---|---|---|
| Spine: Duluth - Midway hub - MSP - Rochester, incl. second-system reserve | 389 | 1 h 10 | $77 bn ($65 - 89 bn) |
| Network through phase 2 | 1,022 | | $175 bn ($150 - 204 bn) |
| Everything incl. Chicago | 1,997 | | $335 bn ($287 - 392 bn) |

The spine holds land for a **second system** beside it (build the next generation while this one
runs, then alternate): P50 $7.5 bn of the $77 bn. The land strip itself is cheap (~$0.6 bn with
contingency); most of it is building city structures and stations for two from day one. Every other
line shows what its reserve would cost in the report.

The spine works out to ~$197 M per route-km all-in. For scale: Shanghai's maglev cost US$43.6 M/km
in 2004 (incl. trains and stations); US megaprojects cost several times Chinese ones. The biggest
single driver of the range is the elevated guideway cost per km, so that's research item 1.

## How it fits together

| Piece | Role | Status |
|---|---|---|
| `src/mnmaglev` (Python) | parameters, network, costs, land, materials, Monte Carlo, report | working |
| GIS pipeline | measure the segment shares from MN lidar, land cover, NWI wetlands, FEMA floodplains, parcels; least-cost route search with maglev curve and grade limits | phase 2 |
| [OSRD](https://github.com/OpenRailAssociation/osrd) | running time, timetables and capacity on the real alignments (`integrations/osrd`) | planned |
| [Calliope](https://calliope.readthedocs.io/) | traction power supply: substations, MISO grid, winter peaks, renewables + storage (`integrations/calliope`) | planned |
| cfsem | long-stator and levitation magnet sizing, which replaces the placeholder stator steel and aluminium per km (`sim/`) | planned |
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
That variant (spine through downtown Minneapolis, St. Paul by Green Line) comes to $83 bn P50,
$6.2 bn more than the Midway hub: downtown tunnel, and building it for two systems downtown.

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
