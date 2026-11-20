"""Unit tests for the LMDI decomposition: known answers on hand-made cases."""
import math

import pytest

from src.decompose import decompose_drug, log_mean, summarize
import pandas as pd


def test_log_mean():
    assert log_mean(100, 200) == pytest.approx(100 / math.log(2))
    assert log_mean(50, 50) == 50


def test_pure_beneficiary_growth():
    # spending doubles, benes double, everything else flat -> all to benes
    p = decompose_drug(100, 200, 10, 20, 20, 40, 40, 80)
    assert p["d_benes"] == pytest.approx(100, abs=1e-6)
    for k in ("d_new", "d_exit", "d_claims", "d_claims_fb", "d_units",
              "d_price", "d_unattrib"):
        assert p[k] == pytest.approx(0, abs=1e-6)


def test_pure_price_growth():
    p = decompose_drug(100, 200, 10, 10, 20, 20, 40, 40)
    assert p["d_price"] == pytest.approx(100, abs=1e-6)
    assert sum(p.values()) == pytest.approx(100, abs=1e-6)


def test_new_drug():
    p = decompose_drug(None, 50, None, 5, None, 10, None, 20)
    assert p["d_new"] == 50
    assert sum(p.values()) == 50


def test_exited_drug():
    p = decompose_drug(30, None, 3, None, 6, None, 12, None)
    assert p["d_exit"] == -30


def test_suppressed_benes_falls_back_to_claims():
    # benes blank both years; claims up 50%, price per unit up
    p = decompose_drug(100, 150, None, None, 20, 30, 40, 45)
    assert p["d_benes"] == 0
    assert p["d_claims"] == 0
    assert p["d_claims_fb"] > 0            # separate claims-fallback bucket
    assert p["used_claims_fallback"] == 1
    assert sum(v for k, v in p.items() if k != "used_claims_fallback") \
        == pytest.approx(50, abs=1e-6)


def test_missing_volume_data_unattributed():
    p = decompose_drug(60, 90, 10, 15, None, None, None, None)
    assert p["d_unattrib"] == pytest.approx(30, abs=1e-6)


def test_flat_drug_contributes_zero():
    p = decompose_drug(80, 80, 8, 8, 16, 16, 32, 32)
    assert all(v == 0 for k, v in p.items() if k != "used_claims_fallback")


def test_parts_add_to_the_cent():
    cases = [
        (100, 257.43, 10, 23, 20, 41, 40, 97),
        (1000.5, 777.25, 100, 66, 200, 140, 400, 301),
        (3.33, 9999.99, 1, 50, 2, 99, 4, 231),
    ]
    for s0, s1, b0, b1, c0, c1, u0, u1 in cases:
        p = decompose_drug(s0, s1, b0, b1, c0, c1, u0, u1)
        total = sum(v for k, v in p.items() if k != "used_claims_fallback")
        assert round(total - (s1 - s0), 2) == 0


def test_summarize_buckets():
    dec = pd.DataFrame({
        "d_new": [10.0], "d_exit": [-2.0], "d_benes": [30.0],
        "d_claims": [4.0], "d_claims_fb": [9.0], "d_units": [1.0],
        "d_price": [7.0], "d_unattrib": [0.0],
    })
    s = summarize(dec).set_index("component")
    assert s.loc["new_drugs", "delta_spending"] == 10
    assert s.loc["exited_drugs", "delta_spending"] == -2
    assert s.loc["patients_per_drug", "delta_spending"] == 30
    assert s.loc["utilization", "delta_spending"] == 5   # claims + units merged
    assert s.loc["claims_fallback", "delta_spending"] == 9
    assert s.loc["price", "delta_spending"] == 7
    assert s["delta_spending"].sum() == pytest.approx(59)
