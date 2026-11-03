# Calliope integration (phase 5, planned)

[Calliope](https://calliope.readthedocs.io/) builds energy system optimisation models from YAML and CSV
(capacity expansion, dispatch). Here: how to power the maglev, and what that costs.

Plan:
1. Demand: hourly traction + levitation + hotel load per substation node, from OSRD runs (or
   `kinematics.py` per leg and the timetable), with winter and summer profiles.
2. Nodes: substations every few tens of km along each line, linked to MISO transmission nodes.
3. Supply options: grid import (MISO prices), contracted wind (SW/W Minnesota), solar, batteries at
   substations to shave train peaks.
4. Output: power supply capital, energy price per kWh -> back into `params/costs.yaml`
   (`operations.energy_price`, part of `systems.propulsion_power_control`).

Use Calliope 0.7 (check whether it's out of pre-release when starting). Log friction in docs/FINDINGS.md.
