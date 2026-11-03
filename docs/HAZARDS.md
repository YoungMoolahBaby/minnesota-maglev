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

## Shared corridor: both systems in one place

Jon's call (2026-11-03): sibling systems side by side, and the shared hazards go into the planning
instead of splitting the corridor. So the corridor is designed for the worst case once, for both:

| Shared risk | Design rule for the corridor |
|---|---|
| A flood takes out both | piers and stations of BOTH systems above the climate-adjusted 500-yr flood + freeboard (not yet priced for the reserve: add the floodplain adder to its bridge provisions) |
| An ice storm or blizzard stops both | heated switches and guideway de-icing on both; snow storage in the separation strip, never on the other guideway |
| One power failure stops both | each system fed from different substations and different grid nodes; the fusion fleet is sized N+1 (one spare 50 MW unit) with the grid as backup, so one unit or one outage can't drop both |
| A tornado, derecho or crash debris hits both | the 50 m separation keeps most crash debris from one off the other; tornado debris travels much farther, so both guideways and their power need wind and debris design, not distance |
| Construction on one hurts the other | the 50 m separation keeps crane and piling-rig fall zones off the live guideway, so works need no slow orders |
| Shared stations are a single point of failure | the Midway hub and end stations get two independent sets of platforms, power and access |
| Both age together | stagger the generations (build B while A is mid-life), so they are never both at end of life |

To price in phase 3: what each rule adds over a single-system corridor, as parameters with sources.
