"""Sourced cost benchmarks (reference/benchmarks.yaml), converted to 2026 USD."""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from . import ROOT
from .indices import to_2026_usd


@dataclass(frozen=True)
class Benchmark:
    id: str
    param: str
    value: float
    currency: str
    year: int
    unit: str
    scope: str
    source: str
    quote: str
    conf: str
    anchor: bool
    adjust: float = 1.0
    adjust_why: str = ""
    note: str = ""

    @property
    def usd_2026(self) -> float:
        """In 2026 USD, adjusted to the parameter's scope."""
        return to_2026_usd(self.value, self.currency, self.year) * self.adjust


def load_benchmarks() -> list[Benchmark]:
    data = yaml.safe_load((ROOT / "reference" / "benchmarks.yaml").read_text(encoding="utf-8"))
    out = []
    for b in data["benchmarks"]:
        adj = b.pop("adjust", None) or {}
        out.append(Benchmark(**b, adjust=float(adj.get("factor", 1.0)), adjust_why=adj.get("why", "")))
    return out


def benchmark_table(params) -> str:
    """Markdown table: each benchmark in 2026 USD next to its parameter's range."""
    rows = ["| Benchmark | Param | Original | 2026 USD (adj.) | Param value (low-high) | In range |",
            "|---|---|---|---|---|---|"]
    for b in load_benchmarks():
        p = params.get(b.param)
        rng = f"{p.value:g} ({p.low:g}-{p.high:g})" if p else "-"
        inr = ("yes" if p.low <= b.usd_2026 <= p.high else "NO") if p else "-"
        if not b.anchor:
            inr += " (context)"
        rows.append(f"| {b.id} | `{b.param}` | {b.value:g} {b.currency} {b.year} | {b.usd_2026:,.3g} {b.unit} "
                    f"| {rng} | {inr} |")
    return "\n".join(rows)
