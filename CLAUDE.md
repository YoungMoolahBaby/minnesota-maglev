# minnesota-maglev

Planning model for a Transrapid-style maglev network in Minnesota. Read first:
- `README.md`: what it is, how to run.
- `docs/PLAN.md`: phases and status. **Start here.**
- `docs/RESEARCH.md`: the research queue, ordered by the sensitivity table.

## Rules

- Every number the model uses lives in `params/*.yaml` with value, low, high, unit, conf, source.
  No magic numbers in code. Placeholders are marked `conf: placeholder`, never passed off as sourced.
- Every number in docs comes from a real run (`uv run mnmaglev report`) or a cited source.
- Check physics against known results (closed forms, textbook values) in tests before building on it.
- `uv run mnmaglev check` and `uv run pytest` must pass before a commit.
- Log tool friction in `docs/FINDINGS.md` (OSRD, Calliope, cfsem, CortenForge) while building.
- Use CortenForge and cfsem as an end user (published crates).
- Commit and push only when Jon asks; ask before downloads over 1 GB (lidar!) and before deletes.
- Data licenses: record in docs/SOURCES.md; keep ODbL (OSM) derived data separate.
