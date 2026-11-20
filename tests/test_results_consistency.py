"""Checks on the committed results/ artifacts produced by the real run."""
import json
import pathlib

import pandas as pd
import pytest

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"

pytestmark = pytest.mark.skipif(
    not (RESULTS / "kpis.json").exists(),
    reason="run `python -m src.run_all` first")


@pytest.fixture(scope="module")
def kpis():
    return json.loads((RESULTS / "kpis.json").read_text())


def test_decomposition_adds_to_the_cent(kpis):
    dec = pd.read_csv(RESULTS / "decomposition_summary.csv")
    assert round(dec["delta_spending"].sum() - kpis["delta_spending"], 2) == 0


def test_per_drug_parts_sum_to_change():
    d = pd.read_csv(RESULTS / "decomposition_by_drug.csv")
    parts = d[["d_new", "d_exit", "d_benes", "d_claims", "d_claims_fb",
               "d_units", "d_price", "d_unattrib"]].sum(axis=1)
    diff = (parts - d["spend_change"]).abs()
    assert (diff < 0.01).all()


def test_yearly_totals_reconcile(kpis):
    t = pd.read_csv(RESULTS / "yearly_totals.csv").set_index("yr")
    # the headline 2020 baseline is the full market; yearly_totals is the
    # survivor panel of the RY26 release
    assert t.loc[2020, "gross_spending"] == pytest.approx(kpis["spend_2020_survivors"], abs=0.005)
    assert t.loc[2024, "gross_spending"] == pytest.approx(kpis["spend_2024"], abs=0.005)
    assert t["gross_spending"].is_monotonic_increasing
    # n_drugs_2020 must use the same RY21 basis as spend_2020 (review #12):
    # the full-market count comes from the prior release, the survivor
    # count from this release's panel
    assert kpis["n_drugs_2020"] > kpis["n_drugs_2020_survivors"]
    assert int(t.loc[2020, "n_drugs"]) == kpis["n_drugs_2020_survivors"]


def test_survivor_correction_consistency(kpis):
    surv = pd.read_csv(RESULTS / "survivor_correction.csv").set_index("check_name")["value"]
    assert float(surv["prior_release_total_2020"]) == pytest.approx(kpis["spend_2020"], abs=0.005)
    assert float(surv["this_release_total_2020"]) == pytest.approx(kpis["spend_2020_survivors"], abs=0.005)
    # n_drugs_2020 is the RY21 full-market count (same basis as spend_2020)
    assert int(surv["prior_release_n_drugs_2020"]) == kpis["n_drugs_2020"]
    # gone brands + revisions explain the gap
    gap = kpis["spend_2020"] - kpis["spend_2020_survivors"]
    assert gap > 0
    assert kpis["survivor_gap_2020"] == pytest.approx(-gap)
    # the three correction steps sum to the gap to the cent
    dec = pd.read_csv(RESULTS / "decomposition_summary.csv").set_index("component")
    for c in ["absent_from_ry26", "restatement_2020", "ry26_only_2020"]:
        assert c in dec.index
    corr_sum = dec.loc[["absent_from_ry26", "restatement_2020",
                        "ry26_only_2020"], "delta_spending"].sum()
    assert corr_sum == pytest.approx(-gap, abs=0.005)
    # absent + restatement + only = gap, with no double counting between
    # the correction and the SQL cross-check columns
    assert dec.loc["absent_from_ry26", "delta_spending"] \
        == pytest.approx(-kpis["spend_of_absent_brands_2020"], abs=0.005)
    assert dec.loc["restatement_2020", "delta_spending"] \
        == pytest.approx(kpis["net_revision_2020"], abs=0.005)


def test_all_25_negotiation_drugs_matched():
    n = pd.read_csv(RESULTS / "negotiation_by_drug.csv")
    assert len(n) == 25
    assert (n["n_matched_brands"] >= 1).all()
    assert set(n["cycle"]) == {2026, 2027}
    assert (n["cycle"] == 2026).sum() == 10
    assert (n["cycle"] == 2027).sum() == 15


def test_concentration_bounds():
    c = pd.read_csv(RESULTS / "concentration.csv")
    assert ((c["top10_share_pct"] > 0) & (c["top10_share_pct"] <= 100)).all()
    assert (c["top50_share_pct"] >= c["top10_share_pct"]).all()


def _line_with(doc, needle):
    """All lines containing `needle` — used to bind a number to its metric."""
    return [ln for ln in doc.splitlines() if needle in ln]


def test_key_numbers_bound_to_metrics(kpis):
    """Each displayed number must sit on the line of ITS OWN metric — so a
    transposition (e.g. the claims-fallback value printed on the utilization
    line) fails. Values are distinct, so a swap is caught."""
    dec = pd.read_csv(RESULTS / "decomposition_summary.csv").set_index("component")
    # README prints negatives as a real minus sign before the dollar sign
    fmt = lambda x: f"\u2212${abs(x) / 1e9:.1f}B" if x < 0 else f"${x / 1e9:.1f}B"
    bindings = [  # (line that must contain the value, metric value)
        ("Gross spending 2020 (full market", kpis["spend_2020"]),
        ("Gross spending 2020 (drugs still listed", kpis["spend_2020_survivors"]),
        ("Gross spending 2024", kpis["spend_2024"]),
        ("Change 2020", kpis["delta_spending"]),
        ("patients per drug |", dec.loc["patients_per_drug", "delta_spending"]),
        ("new drugs on the list |", dec.loc["new_drugs", "delta_spending"]),
        ("utilization per patient |", dec.loc["utilization", "delta_spending"]),
        ("claims (patient count n/a) |", dec.loc["claims_fallback", "delta_spending"]),
        ("gross spend per dosage unit |", dec.loc["price", "delta_spending"]),
        ("No longer listed", dec.loc["absent_from_ry26", "delta_spending"]),
        ("2020 restatement", dec.loc["restatement_2020", "delta_spending"]),
        ("In RY26 2020 but not RY21", dec.loc["ry26_only_2020", "delta_spending"]),
    ]
    # all values must be distinct, otherwise a swap couldn't be detected
    vals = [round(v / 1e9, 1) for _, v in bindings]
    assert len(vals) == len(set(vals))
    readme = (RESULTS.parent / "README.md").read_text()
    for label, val in bindings:
        lines = _line_with(readme, label)
        assert lines, f"label missing from README: {label}"
        assert any(fmt(val) in ln for ln in lines), \
            f"{label}: expected {fmt(val)} on its own line"


def test_report_numbers_bound_to_metrics(kpis):
    dec = pd.read_csv(RESULTS / "decomposition_summary.csv").set_index("component")
    fmt = lambda x: f"\u2212${abs(x) / 1e9:.1f}B" if x < 0 else f"${x / 1e9:.1f}B"
    report = (RESULTS.parent / "reports" / "management_report.md").read_text()
    head = _line_with(report, "gross Part D drug spending")
    assert any(fmt(kpis["delta_spending"]) in ln for ln in head)
    # each bucket's formatted value must appear on a line naming that bucket
    assert any(fmt(dec.loc["patients_per_drug", "delta_spending"]) in ln
               for ln in _line_with(report, "More patients per drug"))
    assert any(fmt(dec.loc["utilization", "delta_spending"]) in ln
               for ln in _line_with(report, "more claims/units per patient"))
    assert any(fmt(dec.loc["claims_fallback", "delta_spending"]) in ln
               for ln in _line_with(report, "multi-row brands) added"))
    assert any(fmt(dec.loc["price", "delta_spending"]) in ln
               for ln in _line_with(report, "gross spend per dosage unit"))
    assert any(fmt(dec.loc["new_drugs", "delta_spending"]) in ln
               for ln in _line_with(report, "Newly listed drugs added"))
    # the RY26 2020 total must be labelled restated, not "surviving"
    restated = _line_with(report, "own 2020 total") + _line_with(report, "restated")
    assert any(fmt(kpis["spend_2020_survivors"]) in ln for ln in restated)
    assert not any("survives into" in ln for ln in report.splitlines())


def test_key_numbers_in_docs(kpis):
    readme = (RESULTS.parent / "README.md").read_text()
    report = (RESULTS.parent / "reports" / "management_report.md").read_text()
    fmt = lambda x: f"${x / 1e9:.1f}B"
    for doc in (readme, report):
        assert fmt(kpis["spend_2020"]) in doc
        assert fmt(kpis["spend_2024"]) in doc
        assert fmt(kpis["delta_spending"]) in doc
    html = (RESULTS.parent / "docs" / "index.html").read_text()
    for k in ("spend_2020", "spend_2024", "delta_spending"):
        assert json.dumps(kpis[k]) in html


def test_claims_fallback_consistency(kpis):
    dec = pd.read_csv(RESULTS / "decomposition_summary.csv").set_index("component")
    d = pd.read_csv(RESULTS / "decomposition_by_drug.csv")
    fb = d[d["used_claims_fallback"] == 1]
    assert len(fb) > 0
    # claims_fallback sums the d_claims_fb column over fallback brands only
    assert fb["d_claims_fb"].sum() == pytest.approx(
        dec.loc["claims_fallback", "delta_spending"], abs=0.005)
    # and utilization contains only the per-patient claims/units factors
    assert d["d_claims"].sum() + d["d_units"].sum() == pytest.approx(
        dec.loc["utilization", "delta_spending"], abs=0.005)
    # every fallback brand actually lacks a usable patient count somewhere
    assert fb["brnd_name"].is_unique
