"""End-to-end test on the hand-made fixture: SQL + decomposition, known answers."""
import csv

import duckdb
import pandas as pd
import pytest

from src import config, db, decompose
from conftest import TINY_RAW, TINY_GROUPS, TINY_NEG, TINY_PRIOR

SQL_ALL = [f"0{i}_{n}.sql" for i, n in enumerate(
    ["load", "quality_checks", "long_format", "drug_groups",
     "top_drugs", "group_growth", "concentration", "negotiation",
     "survivor"], start=1)]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("res")
    con = duckdb.connect()
    db.run_sql_files(con, SQL_ALL, raw_csv=TINY_RAW, ref_groups=TINY_GROUPS,
                     ref_neg=TINY_NEG, results_dir=out, raw_prior_csv=TINY_PRIOR)
    dec, summ = decompose.run(con, out_dir=out)
    return con, out, dec, summ


def _read(out, name):
    with open(out / name, newline="") as f:
        return list(csv.DictReader(f))


def test_long_format_counts(run):
    con, out, _, _ = run
    assert con.execute("SELECT COUNT(*) FROM long_overall").fetchone()[0] == 7 * 5
    totals = {int(r["yr"]): float(r["gross_spending"]) for r in _read(out, "yearly_totals.csv")}
    assert totals[2020] == pytest.approx(100 + 100 + 30 + 100 + 80 + 60)  # 470
    assert totals[2024] == pytest.approx(200 + 200 + 50 + 150 + 80 + 90)  # 770


def test_no_double_counting(run):
    con, _, _, _ = run
    # manufacturer rows must sum back to the Overall row per brand
    bad = con.execute("""
        WITH m AS (SELECT brnd_name, yr, SUM(spend) s FROM long_all
                   WHERE mftr_name <> 'Overall' GROUP BY ALL)
        SELECT COUNT(*) FROM m JOIN long_overall o USING (brnd_name, yr)
        WHERE ABS(COALESCE(m.s,0) - COALESCE(o.spend,0)) > 0.01
    """).fetchone()[0]
    assert bad == 0


def test_group_assignment(run):
    con, _, _, _ = run
    g = dict(con.execute("SELECT brnd_name, group_name FROM drug_group").fetchall())
    assert g["Druga"] == "DOAC"
    assert g["Drugb"] == "GLP-1 / incretin"
    assert g["Druge"] == "Oncology"
    assert g["Drugg*"] == "Other"          # 'Stelara Generic' matches no rule


def test_decomposition_known_answers(run):
    _, _, dec, _ = run
    d = dec.set_index("brnd_name")
    assert d.loc["Druga", "d_benes"] == pytest.approx(100, abs=1e-4)
    assert d.loc["Drugb", "d_price"] == pytest.approx(100, abs=1e-4)
    assert d.loc["Drugc", "d_new"] == pytest.approx(50, abs=1e-4)
    assert d.loc["Drugd", "d_exit"] == pytest.approx(-30, abs=1e-4)
    assert d.loc["Druge", "d_claims_fb"] > 0     # suppressed benes -> claims fallback
    assert d.loc["Druge", "used_claims_fallback"] == 1
    assert d.loc["Drugg*", "d_unattrib"] == pytest.approx(30, abs=1e-4)
    # total adds to the cent
    total_delta = dec["spend_change"].sum()
    assert round(dec[decompose.PART_COLS].sum().sum() - total_delta, 2) == 0


def test_negotiation_matching(run):
    _, out, _, _ = run
    sel = _read(out, "negotiation_by_drug.csv")
    assert len(sel) == 3                              # every listed drug matched
    assert all(int(r["n_matched_brands"]) >= 1 for r in sel)
    by_name = {r["selected_drug"]: r for r in sel}
    assert float(by_name["Druga"]["spend_2024"]) == pytest.approx(200)
    assert float(by_name["Drugb; Drugc"]["spend_2024"]) == pytest.approx(250)
    # ref lists 'Drugg' but the dataset brand is 'Drugg*': only the
    # star-stripped brnd_key join makes this match
    assert float(by_name["Drugg"]["spend_2024"]) == pytest.approx(90)


def test_concentration_fixture(run):
    _, out, _, _ = run
    conc = _read(out, "concentration.csv")
    assert len(conc) == 5
    c24 = [r for r in conc if r["yr"] == "2024"][0]
    assert float(c24["top50_share_pct"]) == pytest.approx(100.0)  # only 6 drugs


def test_survivor_correction(run):
    _, out, _, summ = run
    corr = {r["check_name"]: r["value"] for r in _read(out, "survivor_correction.csv")}
    # fixture prior: Druga 90 (vs 100 now), Druge removed, Drugold 25 absent
    assert float(corr["prior_release_total_2020"]) == pytest.approx(385)
    assert float(corr["this_release_total_2020"]) == pytest.approx(470)
    assert float(corr["brands_absent_from_ry26"]) == 1
    assert float(corr["spend_of_absent_brands_2020"]) == pytest.approx(25)
    assert float(corr["brands_revised_2020"]) == 1          # Druga 90 -> 100
    assert float(corr["net_revision_2020"]) == pytest.approx(10)
    assert float(corr["brands_ry26_only_2020"]) == 1       # Druge
    assert float(corr["spend_of_ry26_only_2020"]) == pytest.approx(100)
    assert float(corr["probable_renames_ry26_only"]) == 1  # Drugold/Druge share 'lenalidomide'
    # the three correction steps sum to the gap to the cent, and the whole
    # summary sums to the FULL-basis change: 770 - 385 = 385
    s = summ.set_index("component")
    assert s.loc["absent_from_ry26", "delta_spending"] == pytest.approx(-25)
    assert s.loc["restatement_2020", "delta_spending"] == pytest.approx(10)
    assert s.loc["ry26_only_2020", "delta_spending"] == pytest.approx(100)
    corr_sum = s.loc[["absent_from_ry26", "restatement_2020",
                      "ry26_only_2020"], "delta_spending"].sum()
    assert corr_sum == pytest.approx(470 - 385, abs=1e-4)
    assert s["delta_spending"].sum() == pytest.approx(770 - 385, abs=1e-4)
