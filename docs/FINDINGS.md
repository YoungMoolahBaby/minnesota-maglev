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
- 2026-11-03, winter heating: targeted heating of 29 km of the spine (stations, bridges, 5% of the
  route) adds 18 MW during icing and one fusion unit (4 -> 5); the whole spine heated at once would
  be ~245 MW and 10 units. Overnight warming of the whole spine in rotation needs ~82 MW, well
  inside the 200 MW idle overnight. Heating energy ~17 GWh/yr on the spine (~8% of traction). Spine
  total $107.8 -> $110.0 bn P50 (one more unit, heaters along the line).
- 2026-11-03, staggered timetable: a coordinate search with restarts over whole-minute offsets per line
  and direction halves the network's 1-second peak (485 -> 237 MW); the spine alone 123 -> 75 MW, close
  to one train accelerating at a time. Requiring 5-12 minute connections at the Midway hub costs
  almost nothing (134 -> 137 MW at phase 2). The first, power-only run had the St. Cloud line leaving
  the hub at the same minute the spine arrived; the transfer rule fixed it. With fewer units,
  overnight ice warming stopped fitting in the idle capacity for phases 2-3, so the fleet is now sized
  to whichever is larger. Fleet 14 -> 10 units; spine $110.0 -> $108.5 bn, all $470.6 -> $465.6 bn.
- 2026-11-03, measured icing: 20 years of hourly ASOS reports (80 station-years, all ~8,760 h
  complete). Icing hours/yr: Duluth 224, MSP 124, St. Cloud 115, Rochester 166; freezing rain or
  drizzle only 35 / 18 / 4 / 21 (St. Cloud's sensor reports 'unknown precipitation' where MSP reports
  freezing rain, so central uses the MSP/STC average). My placeholders (150 h, 30 nights, statewide)
  were close overall. Spine heating energy 17.4 -> 14.4 GWh/yr; the fleet is unchanged, because the
  fleet is set by heating POWER (overnight warming time per km), not by how often it ices. I had
  told Jon the icing hours were the number that matters most for the fleet; that was wrong.
- 2026-11-03, GIS slice 1 (spine): first least-cost alignment on USGS elevation + NLCD land cover.
  The first run went 39% through wetland: priced only by land and mitigation, bogs looked cheap.
  Adding the peat adder for wetland cells (deep piles) brought it to ~18%, with forest taking the
  rest. Grades: the ground near Duluth reaches 14.6% over a km; the guideway profile stays within
  10% with piers up to ~44 m for ~1 km. Measured spine 354 km vs 389 estimated, $93.5 bn vs $108.1 bn
  P50, likely optimistic (water-only bridges, suburbs priced as rural, no buildings or corridors).
  The measured spine also changed the timetable (re-optimised: spine peak 91 -> 75 MW).
- 2026-11-03, GIS slice 2 (FEMA floodplains, spine): FEMA has digital flood maps for all of the
  spine's pieces. 5.7% of the measured route is in a 1% or 0.2% annual-chance zone, close to my ~6%
  estimate; what changed the cost is the floodways: pricing them as bridge makes the route cross
  the Mississippi on ~0.9 km and the Minnesota River on ~2.0 km of bridge instead of just the water
  width (bridge metres on the spine 2.6 -> 4.1 km). Line +$2.1 bn P50 (reserve +$0.5 bn of it).
  Re-optimising the timetable for the new route lowered the spine's 1-second peak 75 -> 65 MW, so
  phase 1 needs 3 fusion units instead of 4 (-$1.5 bn); spine with fusion $93.5 -> $94.0 bn, all
  $450 -> $452 bn. The transfer rule still holds, but the connections it found moved: Rochester ->
  St. Cloud now connects (9 min) and Duluth -> St. Cloud waits ~26 min (was the other way round).
  The FEMA server drops connections under load: the download is cached per page and retried, and
  took ~70 minutes for the spine. The TR08 energy test failed after the reroute (31.0 Wh/seat-km vs
  28.1 +-10%): it took 'segment 3 with detour 2', meant as ~230 km, which on the measured route is a
  79 km leg with more of its energy in accelerating. It now builds an explicit 230 km leg: 27.9.
- 2026-11-03, GIS slice 3 (suburbs and freeway corridors, spine): NLCD 2021 impervious surface on
  the spine grid, roads left out: developed-open-space cells median 11% (p90 19%), low-intensity
  (single-family) 36%, medium 55%, high 80%; farmland, forest and wetland ~0%. Pricing cells from 20%
  to 35% as built-up doubled the spine's urban-viaduct km (15 -> 33): line +$6.9 bn P50. Freeways:
  the old `existing_corridor` price ($50k/acre flat) was five times the farmland beside it, so the
  route would have avoided highways; it is now a share of the surrounding land (23 U.S.C. 142(f),
  23 CFR 810.212: free to a public transit authority). Even so the route follows freeways for only
  ~12 km, because in the model the land saved in the country (~$0.07 M/km) is tiny next to the cost
  of building beside traffic (~$3 M/km at a 5% adder). I had told Jon following I-35 would change the
  alignment through the north woods; at these prices it doesn't. The reasons lines like Brightline
  West use highway medians (permits, environmental review, public acceptance) are not in the model.
  The route north of Cannon Falls stayed within ~1 km; south of it, over flat farmland where many
  paths cost nearly the same, it moved up to 7 km. Fusion went back from 3 to 4 units: units come in
  50 MW steps, 3 need a phase-1 peak under ~73 MW, and with only the spine running every offset gets
  tried (60 restarts give the same 75 MW), so the ~$1.5 bn swing between slices is a step, not a
  trend. Spine with fusion $94.0 -> $102.8 bn (estimates: $109.1 bn); all phases $452 -> $462 bn. The
  planner lines moved by up to +$1.5 bn because of the new corridor adder on their assumed corridor
  shares.
- 2026-11-03, phase 2 lines routed (GIS slices 1-3): every measured line is shorter than my
  estimate (Duluth - Hibbing 126 vs 136 km, Midway - Moorhead 375 vs 386, MSP - Mankato 105 vs 111),
  but the first routing made the west line $10 bn dearer (P50 $79.0 -> 89.3 bn): 9.6 km of bridges
  against my 0.6. Nearly all were lakes (Sauk chain west of St. Cloud, Alexandria, the Otter Tail
  lakes near Fergus Falls), which the least-cost path had gone around. The cause was the curve
  fitting: one Douglas-Peucker tolerance for the whole line, raised until every curve fit, so one
  tight spot straightened everything (1.45 km on the west line). Local fitting (simplify each leg at
  300 m, drop the cheapest vertex where a curve doesn't fit) brings the west line's bridges to
  ~2.5 km and every smoothed route within 0-4% of its least-cost path's cost. It also fixed the
  spine, which had ~3 km of needless lake crossings north of the metro: spine line P50 $95.6 ->
  $89.9 bn, with fusion $102.8 -> $97.0 bn. Phase 2 (all measured) $234.3 bn (estimates $246.7),
  all $456.4 bn. Fleet still 4 / 6 / 10 units, but from phase 2 on overnight ice warming sets it,
  not the daytime peak. Following the terrain more closely, the Duluth climbs now cross the
  hillside's ravines on piers up to 73 m (spine) and 80 m (Iron Range), ~1 km each over 25 m,
  still priced as ordinary elevated guideway. The MRLC server answered one of three parallel
  downloads with a firewall captcha page, which the cache saved as a tile; downloads now keep only
  files that start like a TIFF and retry otherwise.

## OSRD

## Calliope

## cfsem

## CortenForge
