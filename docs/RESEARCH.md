# Research queue

Ordered by the sensitivity table in `out/report.md` (first run 2026-11-03) and by risk.
When an item is done: update the parameter's value/range/conf/source, tick it here, rerun the report.

## Cost drivers (from the sensitivity table)

Research pass 1 (2026-11-03) did items 1-5: figures in reference/benchmarks.yaml, converted with
reference/indices.yaml, checked by tests/test_benchmarks.py. Spine P50 went $77.1 -> $100.7 bn.

1. [x] `costs.guideway.elevated`: 42 -> **60** (40-95). Transrapid Munich itemised estimate
   (Vieregg-Rössler 2007) ~60 after removing planning/contingency, SCMaglev DEIS viaduct ~76,
   Pittsburgh maglev 2001 ~77 (2026 USD). Still the top driver (+0.58): next step is an official
   (not critic) itemised Transrapid estimate and the FRA 2005 Report to Congress cost tables
   (railroads.dot.gov blocked automated fetches; try by hand).
2. [x] `costs.soft.engineering_admin` 25% -> **24%** (MnDOT MWRRI method: 10+2+4+6+2), and
   `costs.soft.contingency` kept at **40%** (30-70): AACE class 5, MnDOT 30% of direct construction,
   rail overruns average 44.7% (Flyvbjerg 2003). Open: FRA's own contingency table; P65 vs P50.
3. [x] `costs.systems.propulsion_power_control`: 18 -> **27** (17-45). Munich itemised ~27; official
   Berlin-Hamburg planning ~0.57x civil. Cross-check with the cfsem stator sizing (phase 6).
4. [x] `costs.guideway.urban_viaduct` 110 -> **150** (90-280): Honolulu guideway contracts ~139,
   CA HSR viaduct ~174. `costs.guideway.tunnel` 450 -> **500** (280-1000): Hudson tunnel 1C ~584,
   CA HSR Palmdale-Burbank structures <= ~545. `costs.guideway.bridge_per_m` 0.16 -> **0.40**
   (0.22-0.75): St. Croix ~0.47, Hastings ~0.42 (Minnesota river bridges, 2026 USD).
5. [x] `costs.guideway.at_grade`: 30 -> **48** (32-78). Munich ~50; "at grade" Transrapid is still a
   beam on low piers, so it is only ~1.22-1.26x cheaper than elevated.

Method note: older figures are brought to 2026 with the FHWA highway construction index (NHCCI),
which rose ~2x since 2007 and ~3x since 2003 (CPI rose ~1.6x and ~1.8x). Using CPI would make the
older benchmarks 25-40% lower; the parameter low ends allow for that. The index choice is itself
one of the bigger judgment calls in the estimate.

Next in this queue (by the new sensitivity table): the elevated guideway again (official sources),
then the segment shares (elevated vs at grade, urban km), which are planner estimates not sampled
by Monte Carlo: the GIS phase measures them. Then stations (`costs.stations.*`, placeholders),
trains per hour (needs the demand model) and the second-system urban provision.

## Vendor and procurement (risk, not in the numbers yet)

6. [ ] Who could supply a long-stator high-speed maglev today: Transrapid IP holders, CRRC
   (600 km/h), others. Buy America and the federal restrictions on Chinese state-owned rail
   suppliers: do they apply to an intercity maglev with FRA money?
7. [ ] Federal maglev programme history (MAGLEV Deployment Program) and FRA safety rules for
   maglev (none specific? Northeast Maglev went through the FRA).

## Verify items flagged in the YAML

Research pass 2 (2026-11-03) did items 8-15 with three research agents; figures and sources are in
the parameter `source` fields and reference/benchmarks.yaml.

8. [x] NOAA 1991-2020 normals: my Nov-Mar temperatures were 3-4 C too cold (they matched Dec-Feb).
   Now Duluth -6.6 / 12.9 C / 229 cm, MSP -3.7 / 16.8 / 130, Rochester -4.5 / 15.4 / 135.
   Not found: freezing-rain days per station (NCEI normals don't carry them).
9. [x] Frost zones (Minn. R. 1303.1600): Zone I 5 ft (St. Louis, Carlton, Pine, Douglas, Clay, ...),
   Zone II 3.5 ft (metro, south). Pine (Hinckley), Douglas (Alexandria) and Clay (Moorhead) are Zone I
   but sit in segments with the central zone: the GIS phase should assign zones by county.
   DLI's air-freezing-index zones are proposed, not adopted.
10. [x] 2020 Census: Virginia 8,421 (was 8,354), Bemidji 14,574 (was 15,434), Brainerd/Baxter 23,007.
11. [x] Land values (UMN Land Economics 2024): south ~10-11.5k/acre, central 2.7-7k, northern
    timber 1.3-2.9k (was 3k). NASS cash rent $200 (was 250). Downtown Minneapolis ~3 M/acre (1-10).
    Still open: suburban land per acre, MnDOT right-of-way unit costs.
12. [x] BWSR 2025 average cost per credit by service area ($18k-120k; metro $120k) and the WCA
    ratios (Minn. R. 8420.0522: 2.5:1 base, 2:1 same service area, 1:1-1.5:1 in >80% areas).
13. [x] Transrapid geometry from the German design rules (12 deg cant, 10% grade, 1.5 m/s2
    unbalanced -> 3,980 m minimum radius at 430 km/h); beams (Shanghai 2,551 girders of ~175 t),
    Gers 1997 material totals, stator pack size, aluminium windings. Energy: the model was ~30% low;
    drag coefficient calibrated to TR08 (28.1 Wh/seat-km at 300 km/h), test added.
    Still open: stator pack mass, concrete in piers and footings, substation rating.
14. [x] NorthMet 0.290% Cu reserves (2022 feasibility update, 91% recovery), Twin Metals Maturi
    0.63% Cu; EPA AP-42 taconite grades; Minnesota pellets 34.5 Mt (2023), 34.6 (2024), ~28.6 (2025).
15. [x] EIA: Minnesota industrial power 9.78 c/kWh (Jan-Aug 2026), transportation sector 13.51 c.

Also from pass 2: the FRA 2005 Report to Congress cost tables (rosap.ntl.bts.gov/view/dot/83590),
used for guideway, systems, stations and vehicles; stations, depot, switch, vehicle, O&M and crew
costs sourced (CA HSR 2024 Basis of Estimate, Berlin-Hamburg planning, Union Depot, Brightline).

## Second-system reserve

16. [ ] Second-system reserve: construction separation needed beside a live maglev
    (`land.reserve.construction_separation`, crane and piling-rig fall zones, launching gantries), cost of building city structures for two (`costs.reserve.urban_provision`),
    Minnesota law on acquiring land for a future system (Minn. Stat. ch. 117), corridor-preservation
    precedents (official mapping, rail banking, utility corridors).

## Benchmarks to add (params/benchmarks.yaml, phase 1)

- Shanghai maglev: 30.5 km, US$1.33 bn (2004), fully elevated, soft ground.
- Northern Lights Express (MnDOT): conventional 110 mph on BNSF track, $592 M construction (FY2026$).
- Zip Rail (Twin Cities - Rochester, studied ~2014-2016): what alignments and costs it found.
- California HSR, Brightline West: US high-speed rail per-km costs.
- Chuo Shinkansen (SCMaglev): maglev, mostly tunnel.

## Local supply and materials

17. [ ] Local-supply savings (`costs.local_supply.*`, placeholders): what a dedicated guideway-beam
    plant saves vs shipped beams (Shanghai girder factory, Emsland), stator-pack assembly economics,
    and how far taconite aggregate can travel before local gravel is cheaper (haul cost per t-km).
    Whether MnDOT specifications allow taconite aggregate in structural/precast concrete.
18. [ ] Material prices (`materials.prices.*`): NOES electrical steel base price (Cleveland-Cliffs
    quote or CRU/Fastmarkets), PC strand, fabricated guidance rails, aggregate (USGS MCS).
19. [ ] Where the steel really comes from: which mills make rebar, strand, plate and electrical
    steel from Minnesota pellets (Cleveland-Cliffs, U.S. Steel), Buy America rules for FRA money.

## Fusion power

20. [x] Small fusion units, costs, operations, timelines (fusion research pass 2026-11-03): sizes
    (Helion/Zap ~50 MWe, others 85-400), capital (DIW review of 99 estimates: first-of-a-kind
    ~$12,600/kW, nth ~$7,000, 2018 USD, "rather optimistic"), O&M (~78-106 $/kW-yr), capacity
    factor (design targets 85-90%), MISO 2025 prices ($43 day-ahead, $53 all-in). All targets and
    projections; nothing has made net electricity yet.
21. [ ] Minnesota law: does Minn. Stat. 216B.243 subd. 3b ("new nuclear-powered electric generating
    plant") cover fusion? HF 387 (2023) would have exempted it and died; a state study of the
    moratorium is due January 2027. Certificate of need starts at 50 MW combined per site
    (216B.2421): could sub-50 MW units at separate sites (substations, depots) avoid it? Needs counsel.
    Minnesota is an NRC Agreement State (MDH), so it would license fusion under the NRC's fusion
    rule (proposed Feb 2026, final pending).
22. [ ] Surplus users: an H2-DRI plant on the Range (NRRI pre-FEED with U.S. Steel; ~1 GW of power),
    data centres near the Midway hub or the Range, district heat; what they would pay per MWh.
23. [x] Peak shaving by timetable (2026-11-03): staggered departures with 5-12 minute hub connections
    cut the network peak 485 -> 237 MW and the fleet 14 -> 10 units (`mnmaglev timetable`).

## Winter ice

24. [x] Icing frequency (2026-11-03): 20 years (2006-2025) of hourly ASOS reports for Duluth, MSP,
    St. Cloud and Rochester (`scripts/icing_hours.py` -> reference/icing.yaml), now per climate zone
    (`climate.<zone>.icing_hours`, `icing_nights`). Icing hours/yr (all conditions): DLH 224, MSP
    124, STC 115, RST 166; freezing rain or drizzle only: 35 / 18 / 4 / 21 (STC's sensor reports
    unknown precipitation instead). Icing nights: 27 / 16 / 19 / 26.
24b. [ ] How long each km must be warmed per icing night (`winter.heating.warm_hours_per_km`, 2 h,
    placeholder): this, not the icing hours, sets the overnight warming power and so the full
    network's fleet size. Heat-transfer estimate for steel guidance rails from -10 C to above 0 C
    under wind, or field data from rail and road anti-icing systems.
25. [ ] Heated surfaces and power: Transrapid guidance rail and gliding strip dimensions
    (`winter.heating.area_per_m`), anti-icing (keep above 0 C) vs snow melting heat flux for steel
    rails, rail switch heater ratings (DB, Trafikverket, nVent), installed cost of rail and deck
    heating per metre (`heater_capex_per_km`), any Transrapid or Chinese maglev de-icing studies.
26. [ ] Lessons from Metro Transit's Blue Line freezing-rain shutdowns and St. Louis MetroLink's
    storm trains: how fast ice builds on exposed steel, what kept or failed to keep service running.
27. [ ] Highway corridors: what MnDOT would charge for interstate right-of-way (`land.corridor.price_factor`,
    0.25 placeholder; 23 CFR 810.212 allows free use by a public transit authority), what building
    beside traffic adds (`costs.adders.highway_corridor`, 5% placeholder: pier protection, lane
    closures), and a price for what following a highway saves in permitting and environmental review
    (not in the model, the main reason Brightline West uses I-15). Freight-rail separation rules from
    BNSF / CPKC / UP for a guideway beside their main lines.

28. [ ] Tall piers: cost per metre of pier height for double-track maglev or HSR viaducts
    (`costs.guideway.tall_pier_per_m`, 0.6 MUSD per km per m, placeholder engineering estimate) and
    the height the elevated benchmarks already cover (`pier_height_ref`, 20 m: Transrapid's standard
    elevated class). Candidates: Martinez-Martin et al. 2013 (tall RC piers, 40-100 m), Chinese HSR
    viaduct cost by pier height, MnDOT/WSDOT bridge cost data for tall substructure. Small at today's
    routes (~$70 M a line on the Duluth hillside, $0.6 bn on the Chicago line's bluffs and Driftless ridges).

29. [ ] Out of state (great_lakes past Winona): Wisconsin and Illinois cropland and suburban land
    prices (USDA NASS land values, county assessors; the model uses Minnesota's), the Chicago and
    Milwaukee approaches' urban tunnel shares (planner 40% on the Chicago urban km), and climate
    zones (the line takes `south`, Minnesota's warmest). The line costs $139 bn P50, so a 2x error
    on its land is ~$1-2 bn.

30. [ ] Peat foundations: what deep piles through peat and muck add to elevated guideway
    (`costs.adders.peat_soft_ground`, 20% of the guideway cost on peat km, 8-45%, placeholder), and
    whether depth matters enough to split shallow (Terric, 40-130 cm over mineral soil) from deep
    Histosols (SSURGO taxsubgrp). Sources: MnDOT foundation practice on peat (I-35 and US-2
    through bogs), Shanghai maglev piling on soft soil, Dutch and Finnish rail on peat.

31. [ ] Buildings in the right-of-way (GIS slice 5): business relocation per building
    (`land.buildings.business_relocation`, 0.15 MUSD, placeholder: 49 CFR 24 moving costs are
    uncapped and machinery dominates; MnDOT or Met Council relocation records for the Southwest and
    Blue Line LRT takings would give real figures), the depreciated value of commercial and farm
    buildings per m2 of footprint (`nonresidential_value_per_m2`, `farm_value_per_m2`: the parcels
    have emv_bldg, but tying it to footprints needs parcel polygons), demolition and abatement per m2,
    and apartment buildings (one USA Structures footprint, many households to relocate).

32. [ ] Parcels where MnGeo has none: the 28 counties that don't publish open parcels (on our
    routes Pine, Goodhue, Dodge, Blue Earth, Nicollet, Beltrami, Kandiyohi, Todd, Wadena) via a data
    request to the counties or the internal MnGeo compilation (state agencies only), and Wisconsin
    (statewide parcel layer V10 from the Wisconsin State Cartographer's Office, with assessed
    values) and Illinois (county by county) for the Chicago line.

33. [ ] Public and tribal land (GIS slice 6): how much more a route may cost to stay out of
    Section 4(f) land (`land.public.section_4f_avoidance_km`, placeholder; 23 CFR 774.17 'cost of
    an extraordinary magnitude' is judged case by case: FHWA's Section 4(f) Policy Paper and
    rejected-avoidance cases would bound it), which parks carry Land and Water Conservation Fund
    (6(f)) money (replacement land of equal value), and what crossing tribal land takes: consent
    and compensation under 25 CFR 169 (`land.tribal.*`, placeholders; precedents: Enbridge Line 3
    and Line 5 easements with Fond du Lac, Leech Lake and Bad River, transmission lines across
    reservations), trust vs fee land inside reservation boundaries (BIA land records). Also county
    tax-forfeit land (2.8 M acres, DNR land portfolio; not in PAD-US's fee layer) and the PAD-US
    easement layer (RIM and other conservation easements bind private land the route may take).

34. [ ] The Denver line (phase 4, planner estimates): Iowa, Nebraska and Colorado land prices (Iowa
    State's land value survey, UNL's Nebraska farm real estate report, Colorado dryland and range;
    the model prices them as southern and central Minnesota cropland), a climate zone for the high
    plains (wind and ground blizzards that close I-80 and I-76, thinner air at Denver's ~1,600 m
    cuts drag), the Platte crossings and floodplain (braided channels; the central Platte between
    Grand Island and Kearney is designated whooping crane critical habitat and the sandhill crane
    staging area, so expect a hard environmental review there), the Missouri at Omaha / Council
    Bluffs, and station sites (Des Moines, the Omaha riverfront, DEN, Denver Union Station with RTD).
    Then GIS routing. Demand: MSP - Denver at 4 h 26 against ~2 h flights plus airport time, and
    what the Iowa and Nebraska stops add (phase 7).

35. [ ] Robot security patrols (params/security.yaml, mostly placeholders): what a magnetic
    gradiometer can find on a Transrapid guideway, whose laminated stator packs are steel every
    metre (smallest ferrous object seen against a baseline map, at what robot speed; whether the
    robot rides the beam or the access road), a guideway robot's price (no product: Spot launched at
    $74,500 in 2020), drone revisit interval and fleet per km from rail and pipeline practice
    (BNSF's dock-based program), FAA Part 108 (proposed 2025-08-07) and its final form, airspace
    near the MSP and DEN airport stations, who may counter hostile drones (federal agencies only),
    and the threat list the patrols answer (sabotage, metal theft, vandalism, debris, animals).
