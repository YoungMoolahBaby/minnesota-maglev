# Research queue

Ordered by the sensitivity table in `out/report.md` (first run 2026-11-03) and by risk.
When an item is done: update the parameter's value/range/conf/source, tick it here, rerun the report.

## Cost drivers (from the sensitivity table)

1. [ ] `costs.guideway.elevated` (+0.62): published Transrapid/CRRC elevated guideway costs per km,
   split civil vs systems. Sources to try: Munich and Berlin-Hamburg Transrapid studies (German
   federal reports), Shanghai project reports, Northeast Maglev / Baltimore-Washington SCMaglev DEIS
   (FRA, 2021: US numbers, different tech), Chuo Shinkansen. Convert with a construction cost index.
2. [ ] `costs.soft.contingency` (+0.44) and `costs.soft.engineering_admin`: FRA/FTA guidance on
   contingency at concept stage; US HSR soft-cost shares (CAHSR, Brightline West).
3. [ ] `costs.systems.propulsion_power_control` (+0.41): long stator + substations + control per km.
   Cross-check with the cfsem sizing (phase 6) and with any Transrapid cost split.
4. [ ] `costs.guideway.urban_viaduct`, `costs.guideway.tunnel`: US urban transit viaduct and
   twin-bore tunnel costs (Transit Costs Project database, NYU).
5. [ ] `costs.guideway.at_grade`: Transrapid at-grade vs elevated ratio (the Victoria quote is the
   only hint so far).

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
    (`land.reserve.width_rural`), cost of building city structures for two (`costs.reserve.urban_provision`),
    Minnesota law on acquiring land for a future system (Minn. Stat. ch. 117), corridor-preservation
    precedents (official mapping, rail banking, utility corridors).

## Benchmarks to add (params/benchmarks.yaml, phase 1)

- Shanghai maglev: 30.5 km, US$1.33 bn (2004), fully elevated, soft ground.
- Northern Lights Express (MnDOT): conventional 110 mph on BNSF track, $592 M construction (FY2026$).
- Zip Rail (Twin Cities - Rochester, studied ~2014-2016): what alignments and costs it found.
- California HSR, Brightline West: US high-speed rail per-km costs.
- Chuo Shinkansen (SCMaglev): maglev, mostly tunnel.
