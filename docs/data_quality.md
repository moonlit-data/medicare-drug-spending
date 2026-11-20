# Data quality notes

Counts below are produced by `sql/02_quality_checks.sql` during the pipeline run.

| Check | What it means | Count |
|---|---|---|
| `blank_benes_2020` | Overall rows with spending but beneficiary count suppressed in 2020 | 59 |
| `blank_benes_2024` | Overall rows with spending but beneficiary count suppressed in 2024 | 199 |
| `blank_spend_2020` | Overall rows with spending blank in 2020 (drug absent or <11 claims, redacted) | 738 |
| `blank_spend_2024` | Overall rows with spending blank in 2024 | 0 |
| `brands_star_suffix` | Overall rows whose brand name ends in '*' (multiple routes of administration flag) | 191 |
| `distinct_brands` | distinct brand names among Overall rows | 3508 |
| `gone_by_2024` | Overall rows with 2020 spending but none in 2024 (structurally zero: file only lists drugs with >=11 claims in 2024) | 0 |
| `mfr_rows_exceed_overall` | drug-years where summed manufacturer spending differs from the Overall row by more than $0.01 | 3 |
| `new_in_2024` | Overall rows present in 2024 with no 2020 spending | 738 |
| `outlier_flag_2020` | Overall rows flagged as price outliers in 2020 | 197 |
| `outlier_flag_2024` | Overall rows flagged as price outliers in 2024 | 395 |
| `rows_manufacturer` | manufacturer-level rows; summing ALL rows would double-count | 10911 |
| `rows_overall` | rows with Mftr_Name = 'Overall' (one per brand/generic combination) | 3625 |
| `rows_total` | all rows in the file (drug x manufacturer rows + Overall rows) | 14536 |

## Known traps and how the pipeline handles them

- **Double counting.** Each brand/generic has one `Overall` row plus one row per manufacturer. All analysis uses `Overall` rows only; the check `mfr_rows_exceed_overall` verifies manufacturer rows sum back to the Overall row.
- **Suppressed cells.** CMS redacts any drug-year with fewer than 11 claims and suppresses beneficiary counts it cannot publish. Blank spending is treated as 'not observed'; blank beneficiary counts force a 3-factor fallback in the decomposition (see docs/metric_definitions.md).
- **Outlier flags.** `Outlier_Flag_*` marks drugs whose unit prices look anomalous in a year. Totals include them (spending itself is real), but per-unit price comparisons for those drug-years should be read with care.
- **Survivor bias.** The release only lists drugs with >= 11 claims in 2024, so drugs that left the market or fell under the threshold before 2024 are absent. sql/09_survivor.sql measures it against the earlier RY21 release (whose 2020 list is complete): brands absent from RY26 ('No longer listed'), the 2020 restatement on shared brands, and 2020 spend RY26 reports for brands RY21 never listed together bridge the full 2020 market to the survivor total, and headline totals use the full 2020 market.
- **'Patients per drug' is not enrollment.** Tot_Benes counts the people using each drug; summed over drugs it counts one person several times. It measures adoption of each drug, not Part D enrollment.
- **Brand-name variants.** A trailing `*` marks multiple routes of administration; brand keys are normalized (lowercase, `*` stripped) before matching.
- **Units are not comparable across drugs** (tablets, grams, milliliters). We never average price across drugs.
- **Gross spending.** All figures are gross drug cost before manufacturer rebates. This is the single biggest limitation for cost questions.

## Reconciliation with a CMS-published total

From `results/reconciliation.csv`:
- **gross_part_d_spending_2024**: ours $288.7B vs CMS $292.9B - ours = calendar year 2024 sum of 'Overall' rows; cms = implied total from '15 drugs ~= $41B ~= 14%' (Nov 2023-Oct 2024 window)
- **cycle_2027_selected_share_pct**: ours 14.682 vs CMS 14 - same definition family (gross covered Part D cost), different time window
- **gross_part_d_spending_2020_full**: ours $198.7B vs CMS n/a - prior release RY21 (data through 2020) is the published source; survivor-only 2020 total in RY26 is $194.1B
- **revised_2020_spend_shared_brands**: ours −$3.7B vs CMS n/a - 940 brands present in both releases had their 2020 spend restated; net restatement shown (RY26 minus RY21)

The implied CMS total is a trailing-12-month figure (Nov 2023-Oct 2024) derived from the second-cycle fact sheet, so a gap of a few percent against the calendar-2024 sum is expected; the two series agree within that window's rounding.