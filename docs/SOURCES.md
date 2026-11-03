# Sources

Check every dataset's license before it goes into the repo. Raw downloads live in `data/`
(gitignored); only small derived files with compatible licenses get committed.

## Used for parameters so far

Cost benchmarks with exact quotes, price years and conversions: `reference/benchmarks.yaml`
(run `uv run mnmaglev benchmarks`). Price indices and exchange rates: `reference/indices.yaml`
(FHWA NHCCI from data.transportation.gov r94d-n4f9, BLS CPI-U, Federal Reserve G.5A).

- Transrapid technical and cost figures: [Wikipedia, Transrapid](https://en.wikipedia.org/wiki/Transrapid)
  (Shanghai US$43.6 M/km incl. trains and stations; Victoria quote A$34 M/km; 505 km/h cruise; ~1 m/s^2;
  Cd 0.26, 16 m^2; 1.7 kW/t levitation; 440 seats).
- Munich Transrapid financing EUR 1.85 bn for 37 km: [AFP via Solar Daily](https://www.solardaily.com/reports/Germany_to_build_first_commercial_Maglev_train_line_999.html).
- Northern Lights Express (Minneapolis - Duluth, conventional): [MnDOT NLX FAQ](https://dot.mn.gov/nlx/faq.html)
  ($592.3 M construction estimate incl. inflation, $18.9 M/yr operating).
- Frost depth rules: Minnesota Rules 1303.1600 ([Revisor](https://www.revisor.mn.gov/rules/1303/version/2021/full));
  DLI technical advisory group on frost zones ([DLI](https://dli.mn.gov/sites/default/files/pdf/TAG-structural-080124-notes.pdf)).
- Duluth Complex status: [mining.com on NewRange/NorthMet](https://www.mining.com/newrange-reviews-options-after-usace-decision-to-revoke-water-permit-for-northmet-project/),
  [Teck: NewRange](https://teck.com/operations/united-states/projects/newrange-copper-nickel).

## Data for the GIS phase

| Data | Source | Notes |
|---|---|---|
| Elevation | [Statewide Seamless 0.5 m Lidar DEM, 2025](https://gisdata.mn.gov/en/dataset/elev-lidar-statewide-gen2) (MN DNR / MnGeo); [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) | QL1; huge, resample for route search |
| Land cover | NLCD (USGS / MRLC); MN land cover (DNR) | public domain (NLCD) |
| Wetlands | National Wetlands Inventory (USFWS); MN NWI update (DNR) | |
| Floodplains | FEMA National Flood Hazard Layer | |
| Rainfall intensity | NOAA Atlas 14 (Atlas 15 coming) | |
| Climate normals | NOAA NCEI 1991-2020 normals; PRISM / nClimGrid | |
| Soils (peat) | NRCS SSURGO | |
| Parcels, land value | [MnGeo parcels](https://gisdata.mn.gov/) (counties opt in); U of MN Land Economics | coverage varies by county |
| Public and tribal land | DNR, USFS (Superior NF), BIA / tribal nations | consultation, not just data |
| Rail and roads | MnDOT, OpenStreetMap (ODbL) | ODbL is share-alike: keep OSM-derived data separate |
| Mines | MN DNR minerals, Iron Range pit maps | |

## Software

| Tool | Use | License |
|---|---|---|
| [OSRD](https://github.com/OpenRailAssociation/osrd) | running time, timetables, capacity | LGPL-3.0 (check current repo) |
| [Calliope](https://calliope.readthedocs.io/) | energy system optimisation (power supply) | Apache-2.0 |
| cfsem | magnetics (stator and magnet sizing) | check crate |
| CortenForge | simulation and 3D view | Jon's project |

## Fusion power (params/power.yaml)

- Böhnlein et al. (2026), review of 99 fusion cost estimates, DIW / TU Berlin: https://arxiv.org/abs/2606.26536
- Handley, Slesinski, Hsu (2021), ARPA-E-based fusion plant costing: https://arxiv.org/abs/2101.09150
- Helion Orion (Malaga, WA; Washington DOH licences, June 2026): https://www.helionenergy.com/newsroom/helion-clears-key-regulatory-milestone-on-the-path-to-building-and-operating-the-worlds-first-fusion-power-plant
- Helion and Nucor, 500 MWe plant for steelmaking (2023): https://www.helionenergy.com/newsroom/helion-nucor-collaboration-to-deploy-500-mw-fusion-power-plant
- Zap Energy 50 MWe modules: https://neimagazine.com/news/zap-energy-launches-fusion-prototype/
- NRC proposed fusion rule (Feb 2026): https://www.powermag.com/nrc-proposes-first-dedicated-regulatory-framework-for-commercial-fusion-machines/
- Minnesota as an NRC Agreement State: https://www.nrc.gov/agreement-states/minnesota.html
- Minn. Stat. 216B.243 (moratorium in subd. 3b): https://www.revisor.mn.gov/statutes/cite/216B.243 ; HF 387 (2023): https://www.revisor.mn.gov/bills/93/2023/0/HF/387
- MISO 2025 State of the Market (Potomac Economics): https://www.potomaceconomics.com/wp-content/uploads/2026/07/2025-State-of-the-Market-Report.pdf
- NRRI hydrogen DRI pre-FEED with U.S. Steel: https://nrri.umn.edu/news/doe-82m-industry-innovation

## Weather observations

- Hourly ASOS reports (NWS/FAA airport weather stations DLH, MSP, STC, RST), 2006-2025, from the
  Iowa Environmental Mesonet archive: https://mesonet.agron.iastate.edu/request/download.phtml
  (`scripts/icing_hours.py` downloads them to data/raw/noaa_asos, gitignored; the yearly summary is
  reference/icing.yaml). Public-domain US government observations.
