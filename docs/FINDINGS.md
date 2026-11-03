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
- 2026-11-03, research pass 2 (three agents): found the FRA 2005 maglev Report to Congress cost
  tables via the National Transportation Library (rosap.ntl.bts.gov/view/dot/83590; FRA's own site
  blocks automated fetches). Pittsburgh's 100%-elevated guideway converts to ~$79 M/km 2026, so
  elevated went 60 -> 65. Stations, depot, switch, vehicle, crew and O&M now sourced; the maglev switch
  dropped 15 -> 7 (Berlin-Hamburg ~2 Mio DM each), crews rose 1.5 -> 2.5 M per train-year.
- 2026-11-03: my Nov-Mar temperatures were 3-4 C too cold (I had used Dec-Feb values from memory);
  NOAA normals fixed them. Two census populations were wrong (Virginia, Bemidji).
- 2026-11-03: the energy model was ~30% low against Transrapid figures (20.5 vs 28.1 Wh/seat-km for
  TR08 at 300 km/h). Wikipedia's Cd 0.26 can't describe a 128 m, 5-section train; an effective 0.41
  reproduces TR08 and gives ~44 Wh/seat-km at 400 km/h (TR07 simulation: 49). Spine energy is now
  ~21 kWh per train-km. Test `test_energy_matches_tr08_at_300_kmh` holds it.
- 2026-11-03: pre-2003 figures are now carried to 2003 with the ENR CCI (1990-2003), and 1993 DM
  convert at the Fed G.5A rate (1.6545 DM/USD). The Pittsburgh 2001 promoter figure rose 77 -> 81.
- 2026-11-03: after pass 2 the spine is $100.8 bn P50 ($87-116 bn), up from $99.0 bn (mostly elevated
  60 -> 65 and stations). 2 research agents of 3 hit sites that block automated fetches (FRA, Census
  QuickFacts); mirrors (ROSA P, Wikipedia lists) worked.
- 2026-11-03: I told Jon the spine would use ~22 GWh/yr (2.5 MW); that was my mental arithmetic
  off by 10x (I dropped a factor in the train-km). The model had it right all along: 216 GWh/yr,
  ~25 MW. Lesson: quote the model, not head math.
- 2026-11-03, power profile: every train on the timetable, second by second, both directions. Spine:
  24 MW average, 99 MW 1-minute peak, 123 MW 1-second peak; full network 132 MW average, 485 MW
  1-second peak (departures aligned on the hour, a peaky worst case). Building it exposed a small
  bias in the old energy formula (it billed drag during braking at 1/efficiency, though drag slows
  the train for free); energy and power now share one per-cell calculation and agree within 0.25%.
- 2026-11-03, fusion fleet: 4 units (200 MW) for the spine, 12 (600 MW) for everything, ~74-86%
  of output surplus. At $20,000/kW for the first unit (learning curve after), the spine's units
  cost ~$6.9 bn P50; at wholesale prices the surplus value plus avoided grid energy only just beats
  the fleet's O&M, so fusion is a strategic choice (carbon-free, energy security, Range industry),
  not a cost saving. Spine with fusion $107.8 bn P50, without $100.8 bn.

## OSRD

## Calliope

## cfsem

## CortenForge
