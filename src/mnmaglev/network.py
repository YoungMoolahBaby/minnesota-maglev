"""Cities, lines and segments from network/*.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import NETWORK_DIR
from .geo import haversine_km

STATION_TYPES = ("terminal_major", "airport", "city")
POINT_TYPES = STATION_TYPES + ("waypoint",)
CORRIDOR = "existing_corridor"  # land class priced as a share of the land around it
STRUCTURES = ("elevated", "at_grade", "urban_viaduct")  # urban_viaduct here = built-up km outside the urban ends


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
    # measured (GIS): reference pier height (m) -> m x km of guideway standing above it
    pier_excess: dict[float, float] = field(default_factory=dict)
    # measured (GIS): buildings per km2 beside the takeable km, by group (residential,
    # nonresidential, agriculture) -> {n, side, area, aside} (count, sum sqrt(m2), sum m2, sum m2^1.5)
    buildings: dict[str, dict[str, float]] = field(default_factory=dict)
    # measured (GIS): share of the route with county parcel data, and its land EMV (USD/acre) there
    parcel_coverage: float = 0.0
    parcel_price: float = 0.0
    # measured (GIS): share of the route in Section 4(f) land (public parks, refuges, ...) and tribal land
    section_4f: float = 0.0
    tribal: float = 0.0

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
    offset_fwd_min: int = 0  # first departure, minutes after 06:00, from the first point
    offset_rev_min: int = 0  # first departure, minutes after 06:00, from the last point

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
SETTINGS_DEFAULTS = {"local_supply": False, "fusion": "none", "winter_heating": "none", "security": "none"}
FUSION_CHOICES = ("own", "none")
HEATING_CHOICES = ("targeted", "full", "none")
SECURITY_CHOICES = ("robots", "none")


def load_settings(path: Path = NETWORK_DIR / "lines.yaml") -> dict:
    """Network-wide policy settings (top-level `settings:` in lines.yaml)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {**SETTINGS_DEFAULTS, **(data.get("settings") or {})}
    unknown = set(out) - set(SETTINGS_DEFAULTS)
    if unknown:
        raise ValueError(f"unknown settings {unknown}; known: {sorted(SETTINGS_DEFAULTS)}")
    if out["fusion"] not in FUSION_CHOICES:
        raise ValueError(f"settings.fusion must be one of {FUSION_CHOICES}, got {out['fusion']!r}")
    if out["winter_heating"] not in HEATING_CHOICES:
        raise ValueError(f"settings.winter_heating must be one of {HEATING_CHOICES}, got {out['winter_heating']!r}")
    if out["security"] not in SECURITY_CHOICES:
        raise ValueError(f"settings.security must be one of {SECURITY_CHOICES}, got {out['security']!r}")
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
    use_measured: bool = True,
) -> list[Line]:
    """Lines from lines.yaml. A line with `use_measured: true` takes its points and segments from its
    GIS alignment (network/measured/<id>.yaml) when that exists, unless use_measured=False."""
    cities = cities or load_cities()
    lines = []
    for raw in _raw_lines(path, variant):
        pts = [cities[p] for p in raw["points"]]
        defaults = raw.get("defaults", {})
        overrides = {(s["from"], s["to"]): s for s in raw.get("segments", [])}
        unknown = set(overrides) - {(a.id, b.id) for a, b in zip(pts, pts[1:])}
        if unknown:
            raise ValueError(f"line {raw['id']}: segments not between neighbouring points: {unknown}")
        planner = {k: {**defaults, **v} for k, v in overrides.items()}
        measured = measured_specs(raw["id"], cities, defaults, planner) if (
            use_measured and raw.get("use_measured")) else None
        if measured:
            pts, mspecs = measured
            pairs = [(m.pop("_a"), m.pop("_b"), m) for m in mspecs]
        else:
            pairs = [(a, b, {**defaults, **overrides.get((a.id, b.id), {})}) for a, b in zip(pts, pts[1:])]
        segs = []
        for a, b, spec in pairs:
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
                    pier_excess={float(k): float(v) for k, v in spec.get("pier_excess", {}).items()},
                    buildings={g: {k: float(v) for k, v in d.items()}
                               for g, d in spec.get("buildings", {}).items()},
                    parcel_coverage=float(spec.get("parcel_coverage", 0.0)),
                    parcel_price=float(spec.get("parcel_price", 0.0)),
                    section_4f=float(spec.get("section_4f", 0.0)),
                    tribal=float(spec.get("tribal", 0.0)),
                )
            )
        lines.append(
            Line(id=raw["id"], name=raw["name"], phase=int(raw["phase"]),
                 points=pts, segments=segs, note=str(raw.get("note", "")).strip(),
                 reserve=bool(raw.get("reserve_second_system", False)))
        )
    offsets = load_timetable()
    for line in lines:
        if line.id in offsets:
            line.offset_fwd_min, line.offset_rev_min = offsets[line.id]
    return lines


TIMETABLE_PATH = NETWORK_DIR / "timetable.yaml"


def load_timetable(path: Path = TIMETABLE_PATH) -> dict[str, tuple[int, int]]:
    """Departure offsets per line (minutes after 06:00, forward / reverse), from `mnmaglev timetable`."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {k: (int(v["forward"]), int(v["reverse"])) for k, v in (data.get("offsets") or {}).items()}


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
                if cls != CORRIDOR and f"land.price_per_acre.{cls}" not in param_names:
                    problems.append(f"{tag}: land class {cls!r} has no price in params/land.yaml")
            if f"climate.{s.zone}.snowfall" not in param_names:
                problems.append(f"{tag}: climate zone {s.zone!r} not in params/climate.yaml")
            for name, v in (("floodplain", s.floodplain), ("peat", s.peat), ("urban_tunnel", s.urban_tunnel),
                            ("section_4f", s.section_4f), ("tribal", s.tribal), ("parcel_coverage", s.parcel_coverage)):
                if not 0 <= v <= 1:
                    problems.append(f"{tag}: {name} {v} outside 0..1")
            if s.detour < 1:
                problems.append(f"{tag}: detour {s.detour} < 1")
            if s.urban_km + s.bridge_km > s.length_km:
                problems.append(f"{tag}: urban + bridge km exceed the segment length")
    return problems


MEASURED_DIR = NETWORK_DIR / "measured"
OPEN_LAND = {"north": "cropland_central", "central": "cropland_central", "south": "cropland_south"}


def measured_specs(line_id: str, cities: dict, defaults: dict, planner: dict) -> tuple[list, list[dict]] | None:
    """Points and segment specs from network/measured/<line>.yaml (the GIS alignment), or None.

    Measured: detour, zone, land shares (incl. freeway right-of-way), urban km at each end, built-up
    share (priced as urban viaduct), bridges, floodplain where FEMA has maps, guideway height above
    reference pier heights (tall piers), peat (SSURGO Histosols where the soil survey is complete,
    the wetland share where it isn't), buildings beside the route (FEMA USA Structures), county
    parcel land value where counties publish it, Section 4(f) and tribal land shares. Inherited from the planner segment that starts or ends at the same
    station (else the line defaults): elevated / at-grade split, urban tunnel share.
    """
    path = MEASURED_DIR / f"{line_id}.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    points, specs = [], []

    def point(p):
        if isinstance(p, str):
            return cities[p]
        return City(id=f"{line_id}_{p['id']}", name="zone break (waypoint)", lat=p["lat"], lon=p["lon"],
                    pop=0, type="waypoint")

    for piece in data["pieces"]:
        a, b = point(piece["from"]), point(piece["to"])
        if not points:
            points.append(a)
        points.append(b)
        inherit = None
        for (fa, fb), spec in planner.items():
            if fa == a.id and fb == b.id:
                inherit = spec
                break
        if inherit is None:
            inherit = next((s for (fa, fb), s in planner.items() if fa == a.id or fb == b.id), {})
        base = {**defaults, **inherit}
        sh = piece["land_shares"]
        land = {"suburban": sh["suburban"], "urban_core": sh["urban"], "forest_north": sh["forest"],
                OPEN_LAND[piece["zone"]]: sh["open"], "wetland": sh["wetland"]}
        total = sum(land.values())
        land = {k: v / total for k, v in land.items() if v > 0}
        # beside a freeway: that share of the land is highway right-of-way
        c = piece.get("highway_corridor_share", 0.0)
        if c > 0:
            land = {**{k: v * (1 - c) for k, v in land.items()}, CORRIDOR: c}
        # built-up km outside the urban ends are priced as urban viaduct, the rest by the planner's mix
        built = piece.get("built_up_share", 0.0)
        structure = {k: v * (1 - built) for k, v in base["structure"].items() if k != "urban_viaduct"}
        if built > 0:
            structure["urban_viaduct"] = built
        specs.append({
            **base,
            "detour": piece["detour"],
            "zone": piece["zone"],
            "urban_start_km": piece["urban_start_km"],
            "urban_end_km": piece["urban_end_km"],
            "land": land,
            "structure": structure,
            # SSURGO Histosols where the soil survey is complete; wetland stands in where it isn't
            "peat": (piece["soil_survey_coverage"] * piece["peat_share"]
                     + (1 - piece["soil_survey_coverage"]) * sh["wetland"])
            if "peat_share" in piece else sh["wetland"],
            # measured where FEMA maps cover the piece, the estimate where they don't
            "floodplain": (piece["flood_map_coverage"] * piece["floodplain_share"]
                           + (1 - piece["flood_map_coverage"]) * float(base["floodplain"]))
            if "floodplain_share" in piece else base["floodplain"],
            "bridges": [{"name": f"water crossing {i + 1}", "length_m": m} for i, m in enumerate(piece["bridges_m"])],
            "pier_excess": piece.get("pier_excess_m_km", {}),
            "buildings": piece.get("buildings_per_km2", {}),
            "parcel_coverage": piece.get("parcel_coverage", 0.0),
            "parcel_price": piece.get("parcel_land_usd_per_acre", 0.0),
            "section_4f": piece.get("public_land_shares", {}).get("section_4f", 0.0),
            "tribal": piece.get("public_land_shares", {}).get("tribal", 0.0),
            "note": (f"measured (GIS); guideway up to {piece['guideway_max_height_m']} m high for <=10% grades"
                     + (f"; FEMA flood maps cover {piece['flood_map_coverage']:.0%}" if "flood_map_coverage" in piece else "")
                     + (f"; soil survey covers {piece['soil_survey_coverage']:.0%}" if "soil_survey_coverage" in piece else "")),
            "_a": a, "_b": b,
        })
    return points, specs
