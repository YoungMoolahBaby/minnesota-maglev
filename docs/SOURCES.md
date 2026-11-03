# Sources

Check every dataset's license before it goes into the repo. Raw downloads live in `data/`
(gitignored); only small derived files with compatible licenses get committed.

## Used for parameters so far

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
