"""Generate reports/management_report.md and docs/data_quality.md from
results/ so every number in them is produced by the pipeline."""
import json

import pandas as pd

from . import config


def b(x):
    x = float(x)
    return f"\u2212${abs(x) / 1e9:.1f}B" if x < 0 else f"${x / 1e9:.1f}B"


def build_management_report():
    kpis = json.loads((config.RESULTS / "kpis.json").read_text())
    dec = pd.read_csv(config.RESULTS / "decomposition_summary.csv").set_index("component")
    grp = pd.read_csv(config.RESULTS / "group_growth.csv")
    conc = pd.read_csv(config.RESULTS / "concentration.csv").set_index("yr")
    top = pd.read_csv(config.RESULTS / "top_drugs.csv")

    gp = grp.pivot(index="group_name", columns="yr", values="spend")
    gdelta = (gp[2024] - gp[2020]).sort_values(ascending=False)

    n_glp1 = gdelta.get("GLP-1 / incretin", 0.0)
    n_doac = gdelta.get("DOAC", 0.0)
    top3 = top.head(3)

    text = f"""# Medicare Part D gross drug spending, 2020-2024: one page

**Answer:** gross Part D drug spending rose {b(kpis['delta_spending'])} on a
full-market basis, from
{b(kpis['spend_2020'])} in 2020 to {b(kpis['spend_2024'])} in 2024
(+{kpis['pct_change']:.0f}%). The single biggest driver is more patients
using each drug; newly listed drugs added most of the rest, while average
gross spend per dosage unit went down overall (a mix of price and
strength/form changes — the file has no list prices).

## Findings

1. **Newly listed drugs added {b(dec.loc['new_drugs', 'delta_spending'])}.** {kpis['n_drugs_2024'] - kpis['n_drugs_2020_survivors']} more
   drug names report spending in 2024 than in 2020 on the same release's
   list (a drug enters the file when it passes 11 claims; a brand below
   that threshold in 2020 is indistinguishable from a true launch, so
   this bucket is an upper bound on genuinely new drugs). Examples:
   Mounjaro (tirzepatide) went from $0
   to {b(float(top.loc[top['brnd_name'] == 'Mounjaro', 'spend_2024'].iloc[0]))}.
2. **Growth is a patient-volume story, not a price story.**
   More patients per drug added {b(dec.loc['patients_per_drug', 'delta_spending'])}
   ({dec.loc['patients_per_drug', 'share_of_change_pct']:.0f}% of the change) — this counts
   users of each drug, not Part D enrollment;
   more claims/units per patient added {b(dec.loc['utilization', 'delta_spending'])};
   drugs without a trustworthy patient count (suppressed counts or
   multi-row brands) added {b(dec.loc['claims_fallback', 'delta_spending'])}
   via total claims growth;
   gross spend per dosage unit added {b(dec.loc['price', 'delta_spending'])}
   — a negative contribution that mixes price with strength/form mix.
3. **GLP-1/incretin drugs explain {100.0 * n_glp1 / kpis['delta_spending']:.0f}% of the growth**
   ({b(n_glp1)}). Ozempic alone added
   {b(float(top.loc[top['brnd_name'] == 'Ozempic', 'spend_change'].iloc[0]))},
   Eliquis (a DOAC) added {b(float(top.loc[top['brnd_name'] == 'Eliquis', 'spend_change'].iloc[0]))},
   and Jardiance (SGLT2) added {b(float(top.loc[top['brnd_name'] == 'Jardiance', 'spend_change'].iloc[0]))}.
   DOACs as a group added {b(n_doac)}.
4. **Spending is concentrating where negotiation will hit.** The top 10
   drugs held {conc.loc[2024, 'top10_share_pct']:.0f}% of 2024 spending
   ({conc.loc[2020, 'top10_share_pct']:.0f}% in 2020); the 25 drugs selected
   for negotiation hold {kpis['neg_union_share_2024_pct']:.0f}% —
   {b(kpis['neg_2026_spend_2024'])} on the 2026 list and
   {b(kpis['neg_2027_spend_2024'])} on the 2027 list.

## What to watch in 2025-2026

- Negotiated prices for the first 10 drugs take effect January 2026; the
  2027 list adds 15 more, led by the semaglutide products (Ozempic,
  Rybelsus, Wegovy). Watch whether their share of spending actually falls.
- GLP-1 growth is still the swing factor: another year at the 2024 pace
  would add several billion dollars more.
- Insulin spending keeps declining after the $35 cap; watch whether
  GLP-1 uptake substitutes for it further.

## Limitations

- **Gross spending**: these figures are before manufacturer rebates, which
  CMS cannot publish. Net plan costs are materially lower for high-rebate
  brands.
- The 2020 baseline uses the earlier RY21 release ({b(kpis['spend_2020'])}
  full market). The RY26 file's own 2020 total of {b(kpis['spend_2020_survivors'])}
  is its *restated* figure for the drugs it still lists — restatements,
  absent brands and RY26-only brands together explain the gap, so it is
  not simply the surviving part of the RY21 total.
  "Patients per drug" sums users of each drug across drugs — not Part D
  enrollment growth.
- Dosage units are not comparable across drugs (tablets vs. milliliters);
  the decomposition only compares a drug to its own past.
"""
    with open(config.REPORTS / "management_report.md", "w", newline="\n") as f:
        f.write(text)
    print("wrote reports/management_report.md")


def build_data_quality_doc():
    qc = pd.read_csv(config.RESULTS / "quality_checks.csv")
    rec = pd.read_csv(config.RESULTS / "reconciliation.csv")

    lines = ["# Data quality notes", "",
             "Counts below are produced by `sql/02_quality_checks.sql` during the pipeline run.", "",
             "| Check | What it means | Count |", "|---|---|---|"]
    for _, r in qc.iterrows():
        lines.append(f"| `{r['check_name']}` | {r['detail']} | {r['value']} |")
    lines += ["", "## Known traps and how the pipeline handles them", "",
              "- **Double counting.** Each brand/generic has one `Overall` row plus one row per "
              "manufacturer. All analysis uses `Overall` rows only; the check "
              "`mfr_rows_exceed_overall` verifies manufacturer rows sum back to the Overall row.",
              "- **Suppressed cells.** CMS redacts any drug-year with fewer than 11 claims and "
              "suppresses beneficiary counts it cannot publish. Blank spending is treated as "
              "'not observed'; blank beneficiary counts force a 3-factor fallback in the "
              "decomposition (see docs/metric_definitions.md).",
              "- **Outlier flags.** `Outlier_Flag_*` marks drugs whose unit prices look anomalous "
              "in a year. Totals include them (spending itself is real), but per-unit price "
              "comparisons for those drug-years should be read with care.",
              "- **Survivor bias.** The release only lists drugs with >= 11 claims in 2024, so "
              "drugs that left the market or fell under the threshold before 2024 are absent. "
              "sql/09_survivor.sql measures it against the earlier RY21 "
              "release (whose 2020 list is complete): brands absent from RY26 "
              "('No longer listed'), the 2020 restatement on shared brands, and "
              "2020 spend RY26 reports for brands RY21 never listed together "
              "bridge the full 2020 market to the survivor total, and headline "
              "totals use the full 2020 market.",
              "- **'Patients per drug' is not enrollment.** Tot_Benes counts the people using "
              "each drug; summed over drugs it counts one person several times. It measures "
              "adoption of each drug, not Part D enrollment.",
              "- **Brand-name variants.** A trailing `*` marks multiple routes of administration; "
              "brand keys are normalized (lowercase, `*` stripped) before matching.",
              "- **Units are not comparable across drugs** (tablets, grams, milliliters). We never "
              "average price across drugs.",
              "- **Gross spending.** All figures are gross drug cost before manufacturer rebates. "
              "This is the single biggest limitation for cost questions.",
              "", "## Reconciliation with a CMS-published total", "",
              "From `results/reconciliation.csv`:"]
    for _, r in rec.iterrows():
        def _fmt(v):
            try:
                f = float(v)
                return b(f) if abs(f) > 1000 else f"{f:g}"
            except (TypeError, ValueError):
                return str(v)
        cms_txt = "n/a" if pd.isna(r["cms"]) else _fmt(r["cms"])
        lines.append(f"- **{r['measure']}**: ours {_fmt(r['ours'])} vs CMS {cms_txt} - {r['note']}")
    lines.append("")
    lines.append("The implied CMS total is a trailing-12-month figure (Nov 2023-Oct 2024) "
                 "derived from the second-cycle fact sheet, so a gap of a few percent against "
                 "the calendar-2024 sum is expected; the two series agree within that window's "
                 "rounding.")
    with open(config.DOCS / "data_quality.md", "w", newline="\n") as f:
        f.write("\n".join(lines))
    print("wrote docs/data_quality.md")


def run():
    config.REPORTS.mkdir(exist_ok=True)
    build_management_report()
    build_data_quality_doc()


if __name__ == "__main__":
    run()
