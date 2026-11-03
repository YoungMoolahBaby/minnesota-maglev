# Findings

Friction and lessons while using the tools, logged as we go: type (bug, docs, API, perf, setup,
works), date, details. One section per tool.

## mnmaglev (this repo)

- 2026-11-03, works: first run. Most-likely values summed (P0) land below the Monte Carlo P10 for
  the spine ($58.7 bn vs P10 $62.8 bn): the triangular ranges are skewed high, so stacking modes is
  optimistic. Plan with P50/P90. Test `test_most_likely_values_are_optimistic` keeps this visible.
- 2026-11-03: winter vs summer energy on the spine differs ~9% (air density + heating), first
  physics-based climate effect.
- 2026-11-03: Midway hub vs downtown Minneapolis: spine P50 $68.9 bn vs $73.3 bn, tunnel 4.1 vs
  8.3 km, same Duluth - Rochester time (70 vs 71 min). The St. Cloud line costs $3.2 bn more from
  the hub (Mississippi crossing in the north metro); network through phase 2 is still $1.4 bn cheaper.
  The size of the saving rests on planner tunnel shares; the direction is solid.

## OSRD

## Calliope

## cfsem

## CortenForge
