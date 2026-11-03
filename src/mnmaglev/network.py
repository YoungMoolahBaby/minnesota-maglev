"""Cities, lines and segments from network/*.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import NETWORK_DIR
from .geo import haversine_km

STATION_TYPES = ("terminal_major", "airport", "city")
POINT_TYPES = STATION_TYPES + ("waypoint",)
STRUCTURES = ("elevated", "at_grade")


@dataclass(frozen=True)
class City:
    id: str
    name: str
    lat: float
    lon: float
    pop: int
    type: str

    @property
    def is_station(self) -> bool:
        return self.type in STATION_TYPES


@dataclass(frozen=True)
class Bridge:
    name: str
    length_m: float


@dataclass
class Segment:
    line_id: str
    a: City
    b: City
    detour: float
    zone: str
    urban_start_km: float
    urban_end_km: float
    urban_tunnel: float
    structure: dict[str, float]
    land: dict[str, float]
    floodplain: float
    peat: float
    bridges: list[Bridge] = field(default_factory=list)
    note: str = ""

    @property
    def crow_km(self) -> float:
        return haversine_km(self.a.lat, self.a.lon, self.b.lat, self.b.lon)

    @property
    def length_km(self) -> float:
        return self.crow_km * self.detour

    @property
    def urban_km(self) -> float:
        return min(self.urban_start_km + self.urban_end_km, self.length_km)

    @property
    def bridge_km(self) -> float:
        return sum(b.length_m for b in self.bridges) / 1000.0

    @property
    def rural_guideway_km(self) -> float:
        """Rural km that are ordinary guideway (bridges are costed separately)."""
        return max(self.length_km - self.urban_km - self.bridge_km, 0.0)


@dataclass
class Line:
    id: str
    name: str
    phase: int
    points: list[City]
    segments: list[Segment]
    note: str = ""
    reserve: bool = False  # hold land and build-for-two provisions for a second system

    @property
    def length_km(self) -> float:
        return sum(s.length_km for s in self.segments)

    @property
    def stations(self) -> list[City]:
        return [p for p in self.points if p.is_station]


def load_cities(path: Path = NETWORK_DIR / "cities.yaml") -> dict[str, City]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {k: City(id=k, **v) for k, v in data.items()}


SEGMENT_KEYS = (
    "detour", "zone", "urban_start_km", "urban_end_km", "urban_tunnel",
    "structure", "land", "floodplain", "peat", "bridges",
)


VARIANTS_DIR = NETWORK_DIR / "variants"
SETTINGS_DEFAULTS = {"local_supply": False, "fusion": "none"}
FUSION_CHOICES = ("own", "none")


def load_settings(path: Path = NETWORK_DIR / "lines.yaml") -> dict:
    """Network-wide policy settings (top-level `settings:` in lines.yaml)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {**SETTINGS_DEFAULTS, **(data.get("settings") or {})}
    unknown = set(out) - set(SETTINGS_DEFAULTS)
    if unknown:
        raise ValueError(f"unknown settings {unknown}; known: {sorted(SETTINGS_DEFAULTS)}")
    if out["fusion"] not in FUSION_CHOICES:
        raise ValueError(f"settings.fusion must be one of {FUSION_CHOICES}, got {out['fusion']!r}")
    return out


def list_variants() -> list[str]:
    return sorted(p.stem for p in VARIANTS_DIR.glob("*.yaml"))


def _raw_lines(path: Path, variant: str | None) -> list[dict]:
    """Lines from the main file; a variant's lines replace those with the same id."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["lines"]
    if variant:
        vpath = VARIANTS_DIR / f"{variant}.yaml"
        if not vpath.exists():
            raise ValueError(f"no variant {variant!r}; have {list_variants()}")
        replace = {l["id"]: l for l in yaml.safe_load(vpath.read_text(encoding="utf-8"))["lines"]}
        unknown = set(replace) - {l["id"] for l in raw}
        if unknown:
            raise ValueError(f"variant {variant}: lines {unknown} not in {path.name}")
        raw = [replace.get(l["id"], l) for l in raw]
    return raw


def load_lines(
    path: Path = NETWORK_DIR / "lines.yaml",
    cities: dict[str, City] | None = None,
    variant: str | None = None,
) -> list[Line]:
    cities = cities or load_cities()
    lines = []
    for raw in _raw_lines(path, variant):
        pts = [cities[p] for p in raw["points"]]
        defaults = raw.get("defaults", {})
        overrides = {(s["from"], s["to"]): s for s in raw.get("segments", [])}
        unknown = set(overrides) - {(a.id, b.id) for a, b in zip(pts, pts[1:])}
        if unknown:
            raise ValueError(f"line {raw['id']}: segments not between neighbouring points: {unknown}")
        segs = []
        for a, b in zip(pts, pts[1:]):
            spec = {**defaults, **overrides.get((a.id, b.id), {})}
            missing = [k for k in SEGMENT_KEYS if k not in spec]
            if missing:
                raise ValueError(f"line {raw['id']} {a.id}->{b.id}: missing {missing}")
            segs.append(
                Segment(
                    line_id=raw["id"], a=a, b=b,
                    detour=float(spec["detour"]), zone=spec["zone"],
                    urban_start_km=float(spec["urban_start_km"]),
                    urban_end_km=float(spec["urban_end_km"]),
                    urban_tunnel=float(spec["urban_tunnel"]),
                    structure={k: float(v) for k, v in spec["structure"].items()},
                    land={k: float(v) for k, v in spec["land"].items()},
                    floodplain=float(spec["floodplain"]), peat=float(spec["peat"]),
                    bridges=[Bridge(**b_) for b_ in spec["bridges"]],
                    note=str(spec.get("note", "")),
                )
            )
        lines.append(
            Line(id=raw["id"], name=raw["name"], phase=int(raw["phase"]),
                 points=pts, segments=segs, note=str(raw.get("note", "")).strip(),
                 reserve=bool(raw.get("reserve_second_system", False)))
        )
    return lines


def check_network(lines: list[Line], cities: dict[str, City], param_names: set[str]) -> list[str]:
    """Problems with the network against the parameter set (empty = all good)."""
    problems = []
    for c in cities.values():
        if c.type not in POINT_TYPES:
            problems.append(f"city {c.id}: type {c.type!r} not in {POINT_TYPES}")
    for line in lines:
        if not line.points[0].is_station or not line.points[-1].is_station:
            problems.append(f"line {line.id}: must start and end at a station")
        for s in line.segments:
            tag = f"{line.id} {s.a.id}->{s.b.id}"
            if abs(sum(s.structure.values()) - 1) > 1e-6:
                problems.append(f"{tag}: structure shares sum to {sum(s.structure.values()):.3f}")
            if set(s.structure) - set(STRUCTURES):
                problems.append(f"{tag}: unknown structure {set(s.structure) - set(STRUCTURES)}")
            if abs(sum(s.land.values()) - 1) > 1e-6:
                problems.append(f"{tag}: land shares sum to {sum(s.land.values()):.3f}")
            for cls in s.land:
                if f"land.price_per_acre.{cls}" not in param_names:
                    problems.append(f"{tag}: land class {cls!r} has no price in params/land.yaml")
            if f"climate.{s.zone}.snowfall" not in param_names:
                problems.append(f"{tag}: climate zone {s.zone!r} not in params/climate.yaml")
            for name, v in (("floodplain", s.floodplain), ("peat", s.peat), ("urban_tunnel", s.urban_tunnel)):
                if not 0 <= v <= 1:
                    problems.append(f"{tag}: {name} {v} outside 0..1")
            if s.detour < 1:
                problems.append(f"{tag}: detour {s.detour} < 1")
            if s.urban_km + s.bridge_km > s.length_km:
                problems.append(f"{tag}: urban + bridge km exceed the segment length")
    return problems
