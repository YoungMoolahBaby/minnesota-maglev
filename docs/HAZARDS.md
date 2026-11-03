# Hazards: snow, rain, floods, freezing and the rest

Minnesota is the hard case for an elevated maglev: deep cold, heavy snow up north, freezing rain
in the south, spring floods on big rivers, peat and wetlands, frost heave. This register lists each
hazard, what the model does about it today, and what it should do.

| Hazard | Where | What it does to a maglev | Modelled now | Next step |
|---|---|---|---|---|
| Extreme cold (-30 to -40 C) | north, all in cold snaps | denser air raises drag; electronics, seals, gap sensors; cabin heating | air density per zone in energy; winter hotel load | design cold limits; cold-snap frequency (NOAA daily data) |
| Snow (heavy, drifting) | Duluth ~220 cm/yr, lake effect; open farmland drifts | snow on the guideway top and in the stator area; at-grade sections drift in | winter O&M scaled by snowfall; elevated default | drift exposure from land cover + wind; clearance rules for at-grade |
| Freezing rain / ice storms | south and central more than north | ice on guidance rails and stator faces; ice on switches | switch heating in switch cost (placeholder) | ice-storm frequency per zone; heating power for the guideway (Calliope load) |
| Frost heave, frost depth | statewide, deeper north | pier footings must go below the frost line | frost-zone adder on guideway cost | county frost zones; foundation design per soil type |
| Freeze-thaw cycles | statewide | concrete scaling, de-icing salt damage on beams | no | cycles per year by zone; concrete spec cost (air entrainment, sealers) |
| River floods | Red River (1997, 2009), Minnesota River, Mississippi, St. Louis | scour at piers; flooded approaches; closed access roads | floodplain adder on km in floodplain; long bridges | FEMA NFHL per crossing; climate-adjusted 500-yr stage + freeboard |
| Flash floods, intense rain | Driftless Area (SE MN, WI), bluff descents | washouts at at-grade sections; slope failures | no | NOAA Atlas 14 intensities; drainage cost per km |
| Peat / soft ground | Arrowhead, Iron Range, Hinckley area | deep piles, settlement | peat adder | SSURGO organic soils along alignments |
| Wetlands (law, not physics) | everywhere, most in the north | WCA/Section 404 permits and replacement credits | fill acres x ratio x credit price | NWI polygons along alignments; avoidance in the route search |
| High wind | open prairie west, viaducts | speed restrictions on high viaducts | no | wind climatology; viaduct height; restriction rules |
| Tornadoes, derechos | south and west | debris, power loss, structure damage | no | frequency per km (NOAA SPC); downtime cost |
| Wildfire smoke and fire | northern forests | outages, access | no | low priority |
| Lightning | statewide | power and control electronics | no | standard protection in systems cost |
| Wildlife and crossings | north (deer, moose) | at-grade collisions | elevated default | fencing cost for at-grade sections |
| Mining ground | Iron Range pits, old underground workings | subsidence, routes around pits | detour factor | mine maps from DNR along the Iron Range line |

Design stance so far: **elevated by default** outside cities. The beams lift the vehicle above
drifting snow and farm and wildlife crossings, and the land under them stays farmable. That costs
more per km (`costs.guideway.elevated` vs `at_grade`), so the route search should decide it per
cell, not a fixed share.
