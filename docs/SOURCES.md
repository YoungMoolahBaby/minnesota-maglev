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
| Soils (peat) | NRCS gSSURGO via SoilWeb WCS + Soil Data Access | used, slice 4 |
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

## GIS slice 1 (src/mnmaglev/gis.py)

- USGS 3DEP elevation, ImageServer exportImage (public domain):
  https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer
- NLCD 2021 land cover, MRLC GeoServer WCS (public domain):
  https://www.mrlc.gov/geoserver/mrlc_download/NLCD_2021_Land_Cover_L48/wcs
- FEMA National Flood Hazard Layer, flood hazard zones (MapServer layer 28, public domain):
  https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28
- NLCD 2021 impervious surface and impervious descriptor, MRLC GeoServer WCS (public domain):
  coverages NLCD_2021_Impervious_L48 and NLCD_2021_Impervious_descriptor_L48 at
  https://www.mrlc.gov/geoserver/mrlc_download/wcs (descriptor codes: 20 primary road, 21 secondary
  road, 24 non-road non-energy impervious; roads from 2018 NavStreets, per the LANDFIRE data
  dictionary https://www.landfire.gov/sites/default/files/DataDictionary/LF2023/LF23_RoadsADD_240.pdf)
All are cached in data/raw/gis (gitignored); the alignment and measurements are committed.

## Highway right-of-way

- 23 U.S.C. 142(f), right-of-way of federal-aid highways available with or without charge:
  https://www.law.cornell.edu/uscode/text/23/142
- 23 CFR 810 subpart C (810.212), highway right-of-way for publicly owned mass transit, use may be
  without charge: https://www.ecfr.gov/current/title-23/chapter-I/subchapter-I/part-810/subpart-C
- Brightline West in I-15 right-of-way: Caltrans lease (2020)
  https://dot.ca.gov/caltrans-near-me/district-8/district-8-news/caltrans-and-xpresswest-complete-lease-agreement ;
  ENR https://enr.com/articles/49684-vegas-la-high-speed-rail-line-can-use-interstate-15-right-of-way
- Shared rail corridors (track centres 25-200 ft, set case by case): FRA catalog of common-use rail
  corridors https://rosap.ntl.bts.gov/view/dot/40227

## Tall piers (costs.guideway.pier_height_ref, tall_pier_per_m)

- Transrapid guideway gradient-height classes (at grade 1.25-3.5 m, elevated 3.5-20 m), Shanghai line
  paper in Promet - Traffic & Transportation: https://traffic.fpz.hr/index.php/PROMTT/article/download/877/728
- Same classes and the Berlin-Hamburg girder type for 2.2-20 m, Transrapid system document excerpt:
  https://1library.net/document/zxokdxvz-girder-guideway-hybrid-munich-optimization-shanghai-transrapid.html
- FRA (1992), influence of guideway flexibility on maglev vehicle dynamics, costs Transrapid guideway
  on 7.6 m piers (search-result summary; the PDF refused download):
  https://railroads.dot.gov/sites/fra.dot.gov/files/fra_net/16355/1992_INFLUENCE%20OF%20GUIDEWAY%20FLEXIBILITY%20ON%20MAGLEV%20VEHICL.PDF
- Martinez-Martin, Gonzalez-Vidosa, Hospitaler, Yepes (2013), A parametric study of optimum tall piers
  for railway bridge viaducts, Structural Engineering and Mechanics 45(6), doi:10.12989/sem.2013.45.6.723
  (40-100 m hollow RC piers; full text closed, no cost figures taken from it). The cost per metre
  itself is an engineering estimate (params/costs.yaml), not a benchmark.

## Soils (GIS slice 4: peat)

- gSSURGO 30 m map unit key grid (EPSG:5070), served by UC Davis / NRCS SoilWeb's WCS, the one
  soilDB's `mukey.wcs()` uses: http://casoilresource.lawr.ucdavis.edu/cgi-bin/mapserv?map=mukey-wcs
  (coverage `gssurgo`; request format from https://github.com/ncss-tech/soilDB/blob/master/R/mukey-WCS.R)
- USDA NRCS Soil Data Access, tabular SQL over SSURGO (component.taxorder, comppct_r):
  https://sdmdataaccess.sc.egov.usda.gov/tabular/post.rest
- Histosols = soils with >= 40 cm of organic material (peat, mucky peat, muck): USDA Keys to Soil
  Taxonomy, https://www.nrcs.usda.gov/resources/guides-and-instructions/keys-to-soil-taxonomy
