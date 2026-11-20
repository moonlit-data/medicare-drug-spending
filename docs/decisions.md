# Decisions

Every non-obvious choice made while building this project, and why. (The task brief said: do not ask questions — pick the simplest reasonable option and record it.)

## 1. Data acquisition: checked-in CSV, not the API

The task offers the CMS data API. I downloaded the release CSV once (`src/download.py` URL), verified it (14,536 rows, SHA-256 `5dcc9d7b…4c2a55`), and committed it to `data/raw/` — it is 5.3 MB, well under the 50 MB cap. This makes the repo self-contained, reproducible offline, and immune to API drift. `src/download.py` still exists and re-downloads + verifies if the file is deleted; the raw file is never modified by the pipeline.

## 2. "Drug" = brand name

One brand name can appear with several generic-name variants (e.g. salt forms, and 71 brands have more than one `Gnrc_Name`). Every count, ranking and aggregate keys on `Brnd_Name` (normalised by stripping the trailing `*` "multiple routes of administration" flag for matching only). Spend, claims and units are *summed* over a brand's generic rows — events and dollars add cleanly. Patient counts are **not** summed: a person who used two forms of one brand in a year would be counted twice, and a suppressed count on one row would silently lose patients. A brand-year therefore gets a patient count only when exactly one spend-bearing row exists with `Tot_Benes` disclosed; every other case uses the claims-based fallback (see #4).

## 3. Decomposition method: per-drug LMDI with residual folding

`S = benes × (claims/benes) × (units/claims) × (spend/units)`. The log-mean Divisia index gives each drug `w·Δln(factor)` with `w` = the log mean of its 2020/2024 spending. LMDI is chosen because it is *additive*: summing drug contributions reproduces the aggregate change. Any residual (floating-point or a drug with incomplete factors) is folded into that drug's largest component, so per-drug parts sum to the change to the cent — a test enforces `round(sum(parts) − ΔS, 2) == 0`.

## 4. Patient counts: only single-row brands get a 4-factor split; the rest get a separate claims bucket

Two problems with `Tot_Benes`: it is blank when redacted, and summing it over a multi-row brand double-counts people who used two forms (see #2). A brand-year therefore uses the 4-factor form only when it has exactly one spend-bearing row with benes disclosed; all others decompose as `S = claims × units/claims × spend/units`. Because the fallback's claims term is *total* claims growth — which mixes patient growth with per-patient volume — it is reported in its own **`claims_fallback`** bucket ($1.6B over 188 brands), not inside `utilization`. Drugs with no usable volume data at all go to `unattributed` (0 in the real data; tested on the fixture).

The main bucket is named **"patients per drug"**, deliberately not "beneficiaries" or "enrollment": `Tot_Benes` is users-of-that-drug summed over drugs, and it now covers only the brands whose patient count is trustworthy.

## 5. Exited drugs are structurally invisible — corrected via the RY21 release

The file lists only drugs with ≥11 claims in 2024, so no drug can "leave" the dataset and its 2020 total is survivors-only. Rather than accept the inflated baseline, the pipeline pulls the earlier **RY21 release** (list = drugs with ≥11 claims in 2020, the complete 2020 universe) and bridges its 2020 total down to the RY26 survivor total in three labelled steps: `absent_from_ry26` (−$3.5B, the 547 brand identifiers RY26 drops entirely — the "no longer listed" step, though an unknown share of those names are renames rather than exits (the rename candidates show up on the other side, in `ry26_only_2020`)), `restatement_2020` (−$3.7B net revision across 940 shared brands, blank cells counted as 0), and `ry26_only_2020` (+$2.7B on 26 brands only RY26 reports for 2020, of which 22 are probable renames by generic-name match). The steps sum to the −$4.6B gap to the cent (asserted in code and tested). RY21 was chosen over RY24/RY25 (ends 2022/2023) because only the 2020-ending release captures *every* drug that was on the market in 2020 — later releases drop drugs that left between 2021 and their own end year. Per-brand detail lives in `results/survivor_brand_reconciliation.csv`. The per-drug `exited_drugs` path stays for completeness (fixture-tested), still zero on this panel.

## 6. Drug groups: rule-based matching on generic name, first-hit priority

`data/reference/drug_groups.csv` carries one row per rule: `group, match_field, match_value, rule, priority`. Rules are `gnrc_contains` matches against `Gnrc_Name` or `brnd_contains` matches against `Brnd_Name`, applied at the *brand* level: a brand takes the lowest-priority-number rule matching ANY of its names; brands with no match go to `Other`. This fixes the earlier bug where a brand whose generics hit both a rule and nothing could land in two groups. The respiratory group is restricted to inhaled products: `brnd_contains` whitelists the inhaler brands of budesonide, fluticasone, mometasone, glycopyrrolate and ipratropium (Pulmicort, Flovent, Arnuity, Asmanex, Breo, Symbicort, Advair, Bevespi, Duaklir, Seebri, Alvesco, Atrovent, Spiriva, Combivent…) so oral/nasal/topical forms (Budesonide EC/DR/ER, Uceris, Tarpeyo, Dymista, Xhance…) fall to `Other`, and the few multi-route brands end in `Respiratory (mixed/unknown)`. Groups cover the task-required classes (GLP-1/incretin, DOACs, SGLT2i, insulins, top oncology) plus DPP-4 inhibitors and immunology for context.

## 7. Negotiation matching: brand-name match, exclusions explicit

`data/reference/negotiation_drugs.csv` lists all 25 selections (10 for 2026, 15 for 2027) with the CMS fact-sheet `source_url` per row and a `match_note`. Matching strips the `*` suffix and lowercases; `matched_brands` records the exact dataset spellings. The 2026 selection covers the six listed products Fiasp/Fiasp FlexTouch/Fiasp PenFill/NovoLog/NovoLog FlexPen/NovoLog PenFill — *NovoLog Mix 70-30* is a different drug (insulin aspart protamine/aspart) never selected, and *Fiasp Pumpcart* and the *Inpen* device are not on the selected list, so they do not match. *Otezla XR* does not exist in the file — only `Otezla`. Note the exposure metric is 2024 spending of the *selected cohort* as published at analysis time, not spend while under negotiated prices.

## 8. Reconciliation target: CMS's own implied total

CMS publishes no headline "total Part D drug spending 2024" for this file. The 2027-cycle press release says the 15 selected drugs were ≈$41B ≈14% of Part D covered-drug spending (Nov 2023–Oct 2024 window), implying ≈$292.9B. Our calendar-2024 total is $288.7B and the same 15 drugs are 14.7% — inside the expected window-difference gap, written into `results/reconciliation.csv`.

## 9. Determinism: single-threaded DuckDB + normalized outputs

DuckDB's parallel floating-point aggregation produced ~1e-5 differences and unstable tie-ordering between runs. `src/db.connect()` sets `threads = 1`. For **cross-platform** determinism `src/normalize.py` rewrites every `results/*.csv` with LF endings and rounded floats (money to cents, percentages to 4 decimals, integers kept); `kpis.json` is written with sorted keys and the same rounding; charts save with `metadata={'Software': None}`. The determinism test (`run_all` twice → byte-identical `results/`) passes.

## 10. Skipped: optional state-level GLP-1 analysis

The task marks it optional ("skip it rather than do it badly"). The national file has no state dimension, so the analysis would need a second dataset and a different join — skipped deliberately rather than half-done.

## 11. "Gross spending" wording

Every number is gross (pre-rebate) Medicare Part D spending. The README and report say "gross spending" explicitly; the term "cost" is reserved for the CMS column name itself.
