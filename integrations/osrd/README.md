# OSRD integration (phase 4, planned)

[OSRD](https://github.com/OpenRailAssociation/osrd) (OpenRail Association) is an open-source web app for
railway infrastructure design, timetabling, running-time simulation and capacity. It runs as a Docker
Compose stack; infrastructure and rolling stock are loaded from RailJSON files.

Plan:
1. Run OSRD locally (docker compose, per its README); load its example infra to learn the workflow.
2. Export our alignments (phase 2 GeoJSON) as RailJSON infrastructure: track sections, speed limits
   (cruise / urban), stations as operational points, gradients and curves from the lidar profile.
3. Describe the maglev as rolling stock: mass, length, a tractive-effort curve from the long stator
   (no adhesion limit, thrust set by the stator, see sim/), drag from Cd and frontal area.
4. Run the spine, compare running times with `kinematics.py` (expect agreement within a few %; if not,
   find out which model is wrong).
5. Timetable and capacity: trains per hour the spine can carry, station track layouts.

Log friction (setup, RailJSON gaps for maglev, API) in docs/FINDINGS.md under OSRD.
