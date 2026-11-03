"""Bring benchmark costs to 2026 USD (reference/indices.yaml)."""

from __future__ import annotations

from functools import lru_cache

import yaml

from . import ROOT


@lru_cache(maxsize=1)
def _data() -> dict:
    return yaml.safe_load((ROOT / "reference" / "indices.yaml").read_text(encoding="utf-8"))


def to_usd(amount: float, currency: str, year: int) -> float:
    if currency == "USD":
        return amount
    rates = _data()["usd_per"][currency]
    if year not in rates:
        raise KeyError(f"no {currency} rate for {year} in reference/indices.yaml")
    return amount * rates[year]


def inflate(amount_usd: float, year: int, index: str = "nhcci") -> float:
    d = _data()
    series = d[index]["annual"]
    if index == "nhcci" and year < min(series):
        # before NHCCI starts (2003): carry to 2003 with the ENR CCI, then NHCCI onwards
        enr = d["enr_cci"]["annual"]
        if year not in enr:
            raise KeyError(f"no ENR CCI value for {year} in reference/indices.yaml")
        start = min(series)
        return amount_usd * enr[start] / enr[year] * d["target"][index] / series[start]
    if year not in series:
        raise KeyError(f"no {index} value for {year} in reference/indices.yaml")
    return amount_usd * d["target"][index] / series[year]


def to_2026_usd(amount: float, currency: str, year: int, index: str = "nhcci") -> float:
    return inflate(to_usd(amount, currency, year), year, index)
