"""Parameters with ranges and sources.

Every number the model uses lives in params/*.yaml as a leaf
{value, low, high, unit, conf, source, note}. Leaves are flattened to dotted names
prefixed by the file stem, e.g. ``costs.guideway.elevated`` or ``climate.north.snowfall``.

Monte Carlo draws are triangular(low, value, high). A leaf may instead give ``quantiles``, a
table {cumulative probability: value} from 0 to 1 (a reference-class curve); then draws follow
that curve (linear between the points), ``value`` is its median and low / high its ends.
"""

from __future__ import annotations

from dataclasses import dataclass
import zlib
from pathlib import Path

import numpy as np
import yaml

from . import PARAMS_DIR

CONFIDENCE = ("high", "medium", "low", "placeholder")


@dataclass(frozen=True)
class Param:
    name: str
    value: float
    low: float
    high: float
    unit: str
    conf: str
    source: str
    note: str = ""
    quantiles: tuple[tuple[float, float], ...] = ()  # ((p, value), ...), p from 0 to 1

    @property
    def varies(self) -> bool:
        return self.high > self.low

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        if not self.varies:
            return np.full(n, float(self.value))
        if self.quantiles:
            ps, qs = zip(*self.quantiles)
            return np.interp(rng.random(n), ps, qs)
        return rng.triangular(self.low, self.value, self.high, n)


def _is_leaf(node: object) -> bool:
    return isinstance(node, dict) and "value" in node


def _walk(node: dict, prefix: str, out: dict[str, Param]) -> None:
    for key, child in node.items():
        name = f"{prefix}.{key}"
        if _is_leaf(child):
            out[name] = Param(
                name=name,
                value=float(child["value"]),
                low=float(child.get("low", child["value"])),
                high=float(child.get("high", child["value"])),
                unit=str(child.get("unit", "")),
                conf=str(child.get("conf", "")),
                source=str(child.get("source", "")),
                note=str(child.get("note", "")),
                quantiles=tuple(sorted((float(k), float(v)) for k, v in (child.get("quantiles") or {}).items())),
            )
        elif isinstance(child, dict):
            _walk(child, name, out)
        else:
            raise ValueError(f"{name}: expected a leaf with 'value' or a group, got {child!r}")


def load_params(params_dir: Path = PARAMS_DIR) -> dict[str, Param]:
    out: dict[str, Param] = {}
    for path in sorted(params_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        _walk(data, path.stem, out)
    return out


def check_params(params: dict[str, Param]) -> list[str]:
    """Return a list of problems (empty = all good)."""
    problems = []
    for p in params.values():
        if not (p.low <= p.value <= p.high):
            problems.append(f"{p.name}: need low <= value <= high, got {p.low} / {p.value} / {p.high}")
        if p.conf not in CONFIDENCE:
            problems.append(f"{p.name}: conf must be one of {CONFIDENCE}, got {p.conf!r}")
        if not p.source.strip():
            problems.append(f"{p.name}: missing source")
        if not p.unit.strip():
            problems.append(f"{p.name}: missing unit")
        if p.quantiles:
            ps, qs = zip(*p.quantiles)
            if ps[0] != 0.0 or ps[-1] != 1.0:
                problems.append(f"{p.name}: quantiles must run from 0 to 1")
            if any(b < a for a, b in zip(qs, qs[1:])):
                problems.append(f"{p.name}: quantile values must not decrease")
            if (qs[0], qs[-1]) != (p.low, p.high) or abs(float(np.interp(0.5, ps, qs)) - p.value) > 1e-9:
                problems.append(f"{p.name}: with quantiles, low / value / high must be the 0 / 0.5 / 1 points")
    return problems


def nominal(params: dict[str, Param]) -> dict[str, float]:
    return {k: p.value for k, p in params.items()}


def sample(params: dict[str, Param], n: int, seed: int) -> dict[str, np.ndarray]:
    """n draws per parameter (triangular, or along its quantile table). Each parameter has its own random stream (seeded by the run
    seed and its name), so adding or removing a parameter doesn't reshuffle the others' draws and
    before / after comparisons show only the change itself."""
    return {k: p.sample(np.random.default_rng([seed, zlib.crc32(k.encode())]), n) for k, p in params.items()}
