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

8. [ ] NOAA 1991-2020 normals for Duluth, MSP, Rochester, St. Cloud (`params/climate.yaml`).
9. [ ] MN Rules 1303.1600 frost zones by county, and DLI's proposed air-freezing-index zones.
10. [ ] 2020 Census populations (`network/cities.yaml`).
11. [ ] U of MN Land Economics county land values (cropland south/central, forest).
12. [ ] BWSR wetland bank credit prices by bank service area; WCA replacement ratios.
13. [ ] Transrapid guideway geometry: 12 deg max cant, max gradient, unbalanced lateral limit,
    beam cross-sections (concrete per km), stator pack mass per metre, winding material.
14. [ ] Duluth Complex grades (NewRange NorthMet technical report; Twin Metals); Mesabi pellet Fe
    and taconite ratios; Minnesota annual pellet output, for scale.
15. [ ] Minnesota industrial electricity rates and MISO interconnection costs.

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
