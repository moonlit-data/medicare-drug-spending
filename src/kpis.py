"""Compute results/kpis.json and results/reconciliation.csv.

Every headline number used in the README, the management report and the
dashboard comes from this file or the results CSVs - nothing is typed twice.

Headline basis: FULL 2020 spending from the prior release (RY21), so the
change covers the complete 2020 drug universe, not just drugs still listed
in 2024. The survivor-panel decomposition (drugs present in this release)
is kept alongside for comparison.
"""
import csv
import json

import pandas as pd

from . import config

# CMS press release, 2025-01-17: the 15 drugs selected for the second
# negotiation cycle "accounted for about $41 billion in total gross covered
# prescription drug costs under Medicare Part D, or about 14%" between
# November 2023 and October 2024.
CMS_RELEASE_URL = ("https://www.cms.gov/newsroom/press-releases/"
                   "hhs-announces-15-additional-drugs-selected-medicare-drug"
                   "-price-negotiations-continued-effort-lower")
CMS_SELECTED_SPEND = 41e9       # $41B, trailing 12 months Nov 2023-Oct 2024
CMS_SELECTED_SHARE = 14.0       # "about 14%" -> implied total ~ $293B
PRIOR_CSV_PAGE = config.PRIOR_CSV_URL


def _df(name):
    return pd.read_csv(config.RESULTS / f"{name}.csv")


def _round(name, v):
    """Money -> 2 decimals, percentages/shares -> 4, integers stay int.

    Round FIRST, then decide integer formatting, so last-bit float noise
    (100 vs 100.00000000000001) produces identical output across platforms.
    """
    if v is None:
        return None
    f = float(v)
    if any(h in name for h in ("pct", "share", "percent")):
        f = round(f, 4)
    else:
        f = round(f, 2)
    if f == 0:
        f = 0.0                     # normalize -0.0
    if f.is_integer() and abs(f) < 1e15:
        return int(f)
    return f


def _round_obj(name, v):
    if isinstance(v, dict):
        return {k: _round_obj(k, x) for k, x in v.items()}
    if isinstance(v, float):
        return _round(name, v)
    return v


def run():
    totals = _df("yearly_totals").set_index("yr")
    conc = _df("concentration").set_index("yr")
    dec = _df("decomposition_summary").set_index("component")
    top = _df("top_drugs")
    neg = _df("negotiation_summary").set_index("cycle")
    grp = _df("group_growth")
    surv = _df("survivor_correction").set_index("check_name")["value"]

    s20_surv = float(totals.loc[config.BASE_YEAR, "gross_spending"])
    s24 = float(totals.loc[config.END_YEAR, "gross_spending"])
    s20_full = float(surv["prior_release_total_2020"])
    no_longer_listed = s20_surv - s20_full          # negative
    delta_full = s24 - s20_full                   # headline change
    delta_panel = s24 - s20_surv                  # survivor-panel change

    grp_piv = grp.pivot(index="group_name", columns="yr", values="spend")
    grp_delta = (grp_piv[config.END_YEAR] - grp_piv[config.BASE_YEAR]).sort_values(ascending=False)
    glp1_delta = float(grp_delta.get("GLP-1 / incretin", 0.0))

    top10_change = float(top.sort_values(
        ["spend_change", "brnd_name"], ascending=[False, True]).head(10)["spend_change"].sum())

    neg26 = float(neg.loc[2026, "spend_2024"]) if 2026 in neg.index else 0.0
    neg27 = float(neg.loc[2027, "spend_2024"]) if 2027 in neg.index else 0.0
    det = pd.read_csv(config.RESULTS / "negotiation_detail.csv")
    union_spend = float(det.groupby("brnd_key")["spend_2024"].max().sum())

    kpis = {
        "spend_2020": s20_full,
        "spend_2024": s24,
        "delta_spending": delta_full,
        "pct_change": 100.0 * delta_full / s20_full,
        # survivor-panel comparison numbers (RY26 release only)
        "spend_2020_survivors": s20_surv,
        "delta_spending_survivors": delta_panel,
        "pct_change_survivors": 100.0 * delta_panel / s20_surv,
        "survivor_gap_2020": no_longer_listed,
        "brands_absent_from_ry26": float(surv["brands_absent_from_ry26"]),
        "spend_of_absent_brands_2020": float(surv["spend_of_absent_brands_2020"]),
        "brands_revised_2020": float(surv["brands_revised_2020"]),
        "net_revision_2020": float(surv["net_revision_2020"]),
        "brands_ry26_only_2020": float(surv["brands_ry26_only_2020"]),
        "spend_of_ry26_only_2020": float(surv["spend_of_ry26_only_2020"]),
        "probable_renames_ry26_only": float(surv["probable_renames_ry26_only"]),
        # full-market (RY21) drug count matches the spend_2020 basis;
        # the RY26 panel count is kept separately
        "n_drugs_2020": int(surv["prior_release_n_drugs_2020"]),
        "n_drugs_2020_survivors": int(totals.loc[config.BASE_YEAR, "n_drugs"]),
        "n_drugs_2024": int(totals.loc[config.END_YEAR, "n_drugs"]),
        "top10_share_2024_pct": float(conc.loc[config.END_YEAR, "top10_share_pct"]),
        "top50_share_2024_pct": float(conc.loc[config.END_YEAR, "top50_share_pct"]),
        "top10_growth_drugs_share_of_increase_pct": 100.0 * top10_change / delta_full,
        "decomposition": {r["component"]: float(r["delta_spending"])
                          for _, r in dec.reset_index().iterrows()},
        "glp1_delta": glp1_delta,
        "neg_2026_spend_2024": neg26,
        "neg_2027_spend_2024": neg27,
        "neg_union_spend_2024": union_spend,
        "neg_union_share_2024_pct": 100.0 * union_spend / s24,
    }
    rounded = {k: _round_obj(k, v) for k, v in kpis.items()}
    with open(config.RESULTS / "kpis.json", "w", newline="\n") as f:
        f.write(json.dumps(rounded, indent=2, sort_keys=True) + "\n")

    # Reconciliation: CMS's own implied total AND the prior-release cross-check.
    cms_implied = CMS_SELECTED_SPEND / (CMS_SELECTED_SHARE / 100.0)
    our_share_check = 100.0 * float(neg.loc[2027, "spend_2024"]) / s24 if 2027 in neg.index else None
    rows = [
        {"measure": "gross_part_d_spending_2024", "ours": s24, "cms": cms_implied,
         "cms_source": CMS_RELEASE_URL,
         "note": ("ours = calendar year 2024 sum of 'Overall' rows; "
                  "cms = implied total from '15 drugs ~= $41B ~= 14%' (Nov 2023-Oct 2024 window)")},
        {"measure": "cycle_2027_selected_share_pct", "ours": our_share_check or "",
         "cms": CMS_SELECTED_SHARE, "cms_source": CMS_RELEASE_URL,
         "note": "same definition family (gross covered Part D cost), different time window"},
        {"measure": "gross_part_d_spending_2020_full",
         "ours": s20_full, "cms": "",
         "cms_source": PRIOR_CSV_PAGE,
         "note": ("prior release RY21 (data through 2020) is the published source; "
                  f"survivor-only 2020 total in RY26 is ${s20_surv / 1e9:.1f}B")},
        {"measure": "revised_2020_spend_shared_brands",
         "ours": float(surv["net_revision_2020"]), "cms": "",
         "cms_source": PRIOR_CSV_PAGE,
         "note": (f"{int(surv['brands_revised_2020'])} brands present in both releases had their "
                  "2020 spend restated; net restatement shown (RY26 minus RY21)")},
    ]
    with open(config.RESULTS / "reconciliation.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["measure", "ours", "cms", "cms_source", "note"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print(f"kpis: 2020 ${s20_full/1e9:.1f}B -> 2024 ${s24/1e9:.1f}B "
          f"(+${delta_full/1e9:.1f}B; survivors-only {s20_surv/1e9:.1f}B -> +${delta_panel/1e9:.1f}B)")
    return kpis


if __name__ == "__main__":
    run()
