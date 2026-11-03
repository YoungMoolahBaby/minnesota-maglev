import pytest

from mnmaglev.benchmarks import load_benchmarks
from mnmaglev.indices import inflate, to_2026_usd, to_usd
from mnmaglev.params import load_params


def test_anchor_benchmarks_fall_inside_their_parameter_range():
    params = load_params()
    for b in load_benchmarks():
        if not b.anchor:
            continue
        p = params[b.param]
        assert p.low <= b.usd_2026 <= p.high, f"{b.id}: {b.usd_2026:.3g} outside {b.param} {p.low}-{p.high}"


def test_every_benchmark_is_sourced():
    for b in load_benchmarks():
        assert b.source.strip() and b.quote.strip() and b.scope.strip(), b.id
        assert b.conf in ("high", "medium", "low"), b.id
        assert b.adjust == 1.0 or b.adjust_why, f"{b.id}: adjustment without a reason"


def test_conversion_arithmetic():
    # EUR 2007 at the Fed annual rate, then NHCCI 2007 -> 2026 Q1
    assert to_usd(1.0, "EUR", 2007) == pytest.approx(1.3711)
    assert inflate(1.0, 2007) == pytest.approx(3.1348 / 1.5442)
    assert to_2026_usd(10.0, "USD", 2026) == pytest.approx(10.0)
    # before the index starts (2003), 2003 is used
    assert inflate(1.0, 2001) == pytest.approx(3.1348 / 1.0138)
