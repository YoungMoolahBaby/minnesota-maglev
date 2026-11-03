# Findings

Friction and lessons while using the tools, logged as we go: type (bug, docs, API, perf, setup,
works), date, details. One section per tool.

## mnmaglev (this repo)

- 2026-11-03, works: first run. Most-likely values summed (P0) land below the Monte Carlo P10 for
  the spine ($58.7 bn vs P10 $62.8 bn): the triangular ranges are skewed high, so stacking modes is
  optimistic. Plan with P50/P90. Test `test_most_likely_values_are_optimistic` keeps this visible.
- 2026-11-03: winter vs summer energy on the spine differs ~9% (air density + heating), first
  physics-based climate effect.
- 2026-11-03: Midway hub vs downtown Minneapolis: spine P50 $68.9 bn vs $73.3 bn, tunnel 4.1 vs
  8.3 km, same Duluth - Rochester time (70 vs 71 min). The St. Cloud line costs $3.2 bn more from
  the hub (Mississippi crossing in the north metro); network through phase 2 is still $1.4 bn cheaper.
  The size of the saving rests on planner tunnel shares; the direction is solid.
- 2026-11-03: second-system reserve on the spine: P50 $7.5 bn (10.9% of the line), not the ~0.5%
  I first estimated from land alone. Land is $0.43 bn nominal ($0.6 bn with contingency); the
  rest is build-for-two in cities (urban provision $1.84 bn nominal), stations ($0.41 bn), soft
  costs, review and contingency. With the reserve, downtown Minneapolis costs $6.2 bn more than
  Midway (was $4.4 bn): building downtown structures for two is expensive. Holding the reserve on
  every other line would add $21.1 bn P50.
- 2026-11-03: spacing made explicit: B's own right-of-way + 50 m construction separation (~70 m
  centre to centre, so building one needs no slow orders on the other). Spine reserve $7.5 -> $8.1 bn
  P50, land $0.43 -> $0.69 bn nominal; spine $76.5 -> $77.1 bn. Room to build freely costs ~$0.6 bn.
- 2026-11-03, research pass 1: sourced the top cost drivers (reference/benchmarks.yaml, three
  research agents + the FHWA NHCCI series). Elevated guideway 42 -> 60, at grade 30 -> 48, systems
  18 -> 27, urban viaduct 110 -> 150, tunnel 450 -> 500, bridges 0.16 -> 0.40 MUSD/m, soft 25 -> 24%,
  contingency stays 40%. Spine P50 $77.1 -> $100.7 bn ($259 M/km); network through phase 3 $336 ->
  $447 bn. Most of the rise is real US construction inflation: the highway construction index rose
  ~2x since 2007, so 2007 European figures land far above my CPI-ish placeholders. The at-grade
  guideway is only ~1.24x cheaper than elevated (it is still a beam on low piers), so at-grade buys
  little; elevated-by-default costs less extra than the placeholders implied.
- 2026-11-03: research agents could not fetch railroads.dot.gov (403) or the SCMaglev DEIS cost
  appendices; the FRA 2005 Report to Congress tables are the best missing US source.
- 2026-11-03: local supply policy (Jon's question: does using Minnesota's own mines bring costs
  down?). Materials bill = ~4.0% of construction across the network ($8.4 bn of materials,
  nominal); the raw ore is far less. Local supply saves the spine ~$1.66 bn P50 (1.7%), the network
  ~$8.1 bn: about half from the supply-contract hedge (1 contingency point), most of the rest from
  one beam plant; taconite aggregate ~$1 M per northern line (hauls eat the saving). Production tax
  on Minnesota pellets in the spine's steel ~$2.3 M. Answer: a supply-security and Range-economy
  case, not a cost cut.

## OSRD

## Calliope

## cfsem

## CortenForge
