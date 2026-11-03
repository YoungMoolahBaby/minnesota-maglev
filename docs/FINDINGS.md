# Findings

Friction and lessons while using the tools, logged as we go: type (bug, docs, API, perf, setup,
works), date, details. One section per tool.

## mnmaglev (this repo)

- 2026-11-03, works: first run. Most-likely values summed (P0) land below the Monte Carlo P10 for
  the spine ($58.7 bn vs P10 $62.8 bn): the triangular ranges are skewed high, so stacking modes is
  optimistic. Plan with P50/P90. Test `test_most_likely_values_are_optimistic` keeps this visible.
- 2026-11-03: winter vs summer energy on the spine differs ~9% (air density + heating), first
  physics-based climate effect.

## OSRD

## Calliope

## cfsem

## CortenForge
