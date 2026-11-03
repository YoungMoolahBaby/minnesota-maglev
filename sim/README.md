# sim/ (Rust, phase 6, planned)

Two parts, both as a Cargo workspace here when they start:

## Magnetics with cfsem
Size the long stator and the levitation magnets for this vehicle:
- thrust needed: drag at cruise (from `kinematics.py`, winter air) + grade + acceleration margin;
- stator geometry and current -> iron (electrical steel) and aluminium winding mass per km, replacing
  the placeholders `materials.guideway.stator_steel` / `stator_aluminium`;
- levitation: EMS against the stator iron. cfsem has no magnetic materials (found in
  [cortenforge-cfsem](https://github.com/YoungMoolahBaby/cortenforge-cfsem) maglev-train), so
  use the image method for the iron or treat it as a magnetic circuit, and check against
  published Transrapid gap/force figures.

## The city-builder view with CortenForge
- terrain from the MN lidar DEM (heightfield), alignment as guideway beams on piers, stations;
- trains moving on the OSRD timetable;
- overlays: land cost, floodplain, wetlands, snow, the cost surface the route search used;
- later: edit the alignment in the view and send it back to the Python model.

Use CortenForge and cfsem as an end user (published crates); log friction in docs/FINDINGS.md.
