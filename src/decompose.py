"""Exact additive decomposition of the 2020 -> 2024 spending change.

Method: per-drug log-mean Divisia (LMDI). For a drug active in both years,

    spend = benes * (claims / benes) * (units / claims) * (spend / units)

and the change decomposes exactly as

    spend_1 - spend_0 = w * [ dln(benes) + dln(claims/benes)
                              + dln(units/claims) + dln(spend/units) ]

with w = L(spend_1, spend_0), the logarithmic mean. The four terms are the
"more patients per drug", "more claims per patient", "more units per claim"
and "price" effects; their sum equals the spending change. A residual below
1e-6 dollars (floating-point noise) is folded into the largest component so
the parts add up to the cent.

Special cases:
  * spend_0 missing, spend_1 present -> "new drugs" contribution.
  * spend_0 present, spend_1 missing -> "exited drugs" (structurally zero in
    this release: the file only lists drugs with >= 11 claims in 2024).
  * patient counts suppressed (claims and units present) -> 3-factor split
    claims x units/claim x spend/unit; the claims term substitutes for the
    per-patient volume terms and lands in "utilization".
  * any further missing factor -> "unattributed".
"""
import math

import pandas as pd

from . import config

PART_COLS = ["d_new", "d_exit", "d_benes", "d_claims", "d_claims_fb", "d_units",
             "d_price", "d_unattrib"]


def log_mean(a, b):
    if a == b:
        return a
    return (b - a) / (math.log(b) - math.log(a))


def _split(a1, a0, b1, b0, w):
    """w * (ln(b1/a1) - ln(b0/a0)) computed as w * (ln b1 - ln a1 - ln b0 + ln a0)."""
    return w * (math.log(b1) - math.log(a1) - math.log(b0) + math.log(a0))


def _f(v):
    """Blank cells arrive as None/NaN; treat them as not observed."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return 0.0
    return float(v)


def decompose_drug(s0, s1, benes0, benes1, claims0, claims1, units0, units1):
    """Return dict of contribution components for one drug."""
    parts = dict.fromkeys(PART_COLS, 0.0)
    s0 = _f(s0)
    s1 = _f(s1)
    delta = s1 - s0
    if s0 == 0.0 and s1 == 0.0:
        return parts
    if s0 == 0.0:
        parts["d_new"] = delta
        return parts
    if s1 == 0.0:
        parts["d_exit"] = delta
        return parts

    have_b = _f(benes0) > 0 and _f(benes1) > 0
    have_c = _f(claims0) > 0 and _f(claims1) > 0
    have_u = _f(units0) > 0 and _f(units1) > 0
    benes0, benes1 = _f(benes0), _f(benes1)
    claims0, claims1 = _f(claims0), _f(claims1)
    units0, units1 = _f(units0), _f(units1)
    w = log_mean(s0, s1)

    if have_b and have_c and have_u:
        parts["d_benes"] = w * (math.log(benes1) - math.log(benes0))
        parts["d_claims"] = _split(benes1, benes0, claims1, claims0, w)
        parts["d_units"] = _split(claims1, claims0, units1, units0, w)
        parts["d_price"] = _split(units1, units0, s1, s0, w)
    elif have_c and have_u:
        # Beneficiary counts unusable (suppressed, or multi-row brand where
        # summing rows could double-count people): total claims growth
        # carries volume and is reported in its own bucket.
        parts["used_claims_fallback"] = 1
        parts["d_claims_fb"] = w * (math.log(claims1) - math.log(claims0))
        parts["d_units"] = _split(claims1, claims0, units1, units0, w)
        parts["d_price"] = _split(units1, units0, s1, s0, w)
    else:
        parts["d_unattrib"] = delta
        return parts

    # Fold the floating-point residual into the largest component so the
    # decomposition is exact to the cent.
    residual = delta - sum(parts[k] for k in PART_COLS)
    if residual != 0.0:
        biggest = max(PART_COLS, key=lambda k: (abs(parts[k]), -PART_COLS.index(k)))
        parts[biggest] += residual
    return parts


def decompose_panel(panel):
    """panel: one row per drug with 2020/2024 measures. Returns a DataFrame
    with the contribution columns appended."""
    out = panel.copy()
    for col in PART_COLS:
        out[col] = 0.0
    out["used_claims_fallback"] = 0
    for i, r in out.iterrows():
        p = decompose_drug(r["spend_2020"], r["spend_2024"],
                           r["benes_2020"], r["benes_2024"],
                           r["claims_2020"], r["claims_2024"],
                           r["units_2020"], r["units_2024"])
        for k, v in p.items():
            out.at[i, k] = v
    out["used_claims_fallback"] = out["used_claims_fallback"].fillna(0).astype(int)
    out["spend_change"] = out["spend_2024"].fillna(0) - out["spend_2020"].fillna(0)
    return out


def summarize(dec):
    """Fold the per-drug parts into the reported buckets (survivor panel)."""
    s = pd.DataFrame({
        "component": config.PANEL_BUCKETS,
        "delta_spending": [
            dec["d_new"].sum(),
            dec["d_exit"].sum(),
            dec["d_benes"].sum(),
            dec["d_claims"].sum() + dec["d_units"].sum(),
            dec["d_claims_fb"].sum(),
            dec["d_price"].sum(),
            dec["d_unattrib"].sum(),
        ],
    })
    total = s["delta_spending"].sum()
    s["share_of_change_pct"] = 100.0 * s["delta_spending"] / total
    return s


def add_survivor_correction(summ, out_dir):
    """Prepend the correction steps bridging the FULL RY21 2020 total down
    to this release's survivor 2020 total:
      absent_from_ry26  - brands missing from the RY26 release (negative)
      restatement_2020  - net 2020 revision on brands present in both
      ry26_only_2020    - 2020 spend of brands in RY26 but not in RY21
    All three are measured in sql/09_survivor.sql and must reproduce the
    survivor gap to the cent (asserted below).
    Returns summ unchanged if the prior-release comparison was not run."""
    path = out_dir / "survivor_correction.csv"
    if not path.exists():
        return summ
    corr = pd.read_csv(path).set_index("check_name")["value"]
    gap = round(float(corr["this_release_total_2020"])
                - float(corr["prior_release_total_2020"]), 2)          # <= 0
    absent = round(-float(corr["spend_of_absent_brands_2020"]), 2)     # <= 0
    restate = round(float(corr["net_revision_2020"]), 2)               # signed
    only = round(float(corr["spend_of_ry26_only_2020"]), 2)            # >= 0
    # the three measured steps must reproduce the gap to the cent
    assert abs(absent + restate + only - gap) < 0.005, \
        f"survivor steps {absent+restate+only} != gap {gap}"
    rows = pd.DataFrame({
        "component": ["absent_from_ry26", "restatement_2020", "ry26_only_2020"],
        "delta_spending": [absent, restate, only]})
    out = pd.concat([rows, summ], ignore_index=True)
    total = out["delta_spending"].sum()
    out["share_of_change_pct"] = 100.0 * out["delta_spending"] / total
    return out


def run(con, out_dir=None):
    """Read the drug-year panel from DuckDB, decompose, write results/."""
    out_dir = out_dir or config.RESULTS
    # A "drug" is one brand name: spend, benes, claims and units are summed
    # over its generic-name variants (e.g. salt forms) so nothing is counted
    # twice.
    panel = con.execute(f"""
        SELECT l.brnd_name, g.gnrc_name, g.group_name,
               SUM(CASE WHEN l.yr = {config.BASE_YEAR} THEN l.spend  END) AS spend_2020,
               -- benes are kept only when the brand has exactly one spend-
               -- bearing row that year: summing benes over several generic-
               -- name rows can double-count people who used two forms, and
               -- a NULL on any row would silently drop patients.
               CASE WHEN COUNT(*) FILTER (l.yr = {config.BASE_YEAR} AND l.spend > 0) = 1
                    THEN MAX(CASE WHEN l.yr = {config.BASE_YEAR} AND l.spend > 0
                                  THEN l.benes END)
               END AS benes_2020,
               SUM(CASE WHEN l.yr = {config.BASE_YEAR} THEN l.claims END) AS claims_2020,
               SUM(CASE WHEN l.yr = {config.BASE_YEAR} THEN l.units  END) AS units_2020,
               SUM(CASE WHEN l.yr = {config.END_YEAR} THEN l.spend  END) AS spend_2024,
               CASE WHEN COUNT(*) FILTER (l.yr = {config.END_YEAR} AND l.spend > 0) = 1
                    THEN MAX(CASE WHEN l.yr = {config.END_YEAR} AND l.spend > 0
                                  THEN l.benes END)
               END AS benes_2024,
               SUM(CASE WHEN l.yr = {config.END_YEAR} THEN l.claims END) AS claims_2024,
               SUM(CASE WHEN l.yr = {config.END_YEAR} THEN l.units  END) AS units_2024
        FROM long_overall l
        JOIN drug_group g USING (brnd_name)
        GROUP BY ALL
        ORDER BY l.brnd_name
    """).df()

    dec = decompose_panel(panel)
    # round to cents, then re-fold the rounding residual into the largest
    # component so the published parts still sum to spend_change exactly
    dec["spend_2020"] = dec["spend_2020"].fillna(0).round(2)
    dec["spend_2024"] = dec["spend_2024"].fillna(0).round(2)
    dec["spend_change"] = (dec["spend_2024"] - dec["spend_2020"]).round(2)
    dec[PART_COLS] = dec[PART_COLS].round(2)
    resid = (dec["spend_change"] - dec[PART_COLS].sum(axis=1)).round(2)
    for i, r in dec.iterrows():
        if resid[i] != 0.0:
            biggest = max(PART_COLS,
                          key=lambda k: (abs(r[k]), -PART_COLS.index(k)))
            dec.at[i, biggest] = round(r[biggest] + resid[i], 2)
    cols = ["brnd_name", "gnrc_name", "group_name", "spend_2020", "spend_2024",
            "spend_change", "used_claims_fallback"] + PART_COLS
    dec[cols].to_csv(out_dir / "decomposition_by_drug.csv", index=False,
                     lineterminator="\n")

    summ = add_survivor_correction(summarize(dec), out_dir)
    summ.to_csv(out_dir / "decomposition_summary.csv", index=False,
                lineterminator="\n")

    n_supp = int(dec["used_claims_fallback"]
                 .where((dec["spend_2020"] > 0) & (dec["spend_2024"] > 0), 0)
                 .sum())
    print(f"decomposed {len(dec)} drugs; {n_supp} on the claims-based form "
          "(no trustworthy patient count)")
    return dec, summ
