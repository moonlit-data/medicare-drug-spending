# Walkthrough

A plain-English tour of the repo in the order the code runs, the hardest decisions, and interview Q&A.

## The pipeline in run order

**`python -m src.run_all`** is the only command. It calls, in order:

1. **`src/download.py`** — checks `data/raw/DSD_PTD_RY26_P04_V10_DY24_BGM.csv` exists, counts its rows (must be 14,536), verifies SHA-256, writes `data/raw/MANIFEST.json`. Downloads the file from CMS only if missing. The raw file is never modified.
2. **`src/db.py` + `sql/01_load.sql`** — opens DuckDB (single-threaded for determinism), loads the raw CSV with every column as varchar (`all_varchar=true`, `nullstr=''` so blanks stay missing rather than becoming `0`), plus the two reference tables.
3. **`sql/02_quality_checks.sql`** — writes `results/quality_checks.csv`: 15 named checks (double-counting risk, suppressed cells, outlier flags, star-suffix brands, structural absenteeism). These numbers feed `docs/data_quality.md`.
4. **`sql/03_long_format.sql`** — the file is wide: `Tot_Spndng_2020`…`Tot_Spndng_2024` etc. A 5×`UNION ALL` reshapes it to long (`brnd_name, gnrc_name, mftr_name, yr, spend, benes, claims, units, outlier_flag`), casting blank-safe (`NULLIF`/empty→NULL), and adds `brnd_key` = brand name lowered with trailing `*` stripped. Writes `results/yearly_totals.csv` and `results/group_coverage.csv`.
5. **`sql/04_drug_groups.sql`** — one row per brand: the lowest-priority rule in `drug_groups.csv` that matches any of the brand's generic names (`position(lower(match_value) IN lower(gnrc_name))`), else `Other`. Exclusive: a brand cannot be in two groups.
6. **`sql/05_top_drugs.sql`** → `results/top_drugs.csv` — per-year rank by spend plus growth columns.
7. **`sql/06_group_growth.sql`** → `results/group_growth.csv` — group × year spending.
8. **`sql/07_concentration.sql`** → `results/concentration.csv` — top-10/top-50 share per year (`ROW_NUMBER` ordered by spend, brand name for deterministic ties).
9. **`sql/08_negotiation.sql`** → `negotiation_detail/by_drug/summary.csv` — splits the `;`-separated `matched_brands`, normalises, joins, aggregates per selection and per cycle.
10. **`sql/09_survivor.sql`** → `survivor_correction.csv` + `survivor_brand_reconciliation.csv` — loads the RY21 release (complete 2020 drug list), totals 2020 per brand in both releases, and measures the survivor gap + per-brand restatements.
11. **`src/decompose.py`** — pulls the per-brand 2020/2024 panel, runs the LMDI decomposition per drug, prepends the `no_longer_listed` component, writes `decomposition_by_drug.csv` and `decomposition_summary.csv` (parts sum to the full-market change to the cent).
12. **`src/normalize.py`** — rewrites every `results/*.csv` with LF endings and consistent rounding (money to cents, percentages to 4dp) so outputs are byte-identical across OSes.
13. **`src/kpis.py`** — every headline number → `results/kpis.json` (sorted keys), plus `results/reconciliation.csv` comparing our totals to the CMS-implied ~$292.9B.
14. **`src/charts.py`** — 4 charts × light/dark → `results/charts/*.png` (matplotlib, `metadata={'Software': None}`).
15. **`src/build_dashboard.py`** — self-contained `docs/index.html` (Plotly CDN only; data baked in as JSON).
16. **`src/build_report.py`** — `reports/management_report.md` and `docs/data_quality.md`, both generated from `results/` so no number is typed by hand.

## Every other file

- `src/config.py` — all constants: paths, palette, dataset metadata, expected SHA/rows.
- `data/reference/drug_groups.csv` — 69 substring rules with a `rule` explanation per row.
- `data/reference/negotiation_drugs.csv` — 25 selections with source URL + match note per row.
- `tests/` — 25 tests over unit cases, a 7-drug hand-made fixture (plus a prior-release fixture for the survivor check), real-results invariants, determinism, and README-number tracing.
- `docs/decisions.md`, `docs/metric_definitions.md` — the *why* and the *formulas*.
- `LICENSE` (MIT, moonlit-data), `requirements.txt` (pinned), `.gitignore`.

## The hardest decisions

1. **Additive-exact decomposition.** LMDI was chosen specifically because per-drug contributions sum to the aggregate change; the residual is folded into the largest component so the sum holds *to the cent* — and a test enforces it.
2. **"Drug" = brand name.** 71 brands carry multiple generic names; grouping by brand–generic would split products and break additivity. Panel aggregates per brand.
3. **Double-counting trap.** The file has Overall + manufacturer rows (10,911 of 14,536 rows). Every aggregate uses Overall only; a QC check verifies mfr rows sum back to Overall within $0.01 (3 drug-years exceed it — documented, tiny).
4. **Usable patient counts.** 199 rows have blank 2024 benes, and many brands span several generic-name rows where summing patient counts would double-count users who took two forms. Only a brand-year with exactly one spend-bearing row and a disclosed count gets the 4-factor split; the other 188 brands take the claims-based 3-factor form whose claims term lands in its own `claims_fallback` bucket — keeps every drug decomposable without pretending total-claims growth is per-patient utilization.
5. **Survivor bias.** The release only lists drugs with ≥11 claims in 2024, so its 2020 total ($194.1B) misses $4.6B of real 2020 spend. The RY21 release (list complete through 2020) supplies the full baseline ($198.7B), and the gap splits into three exact steps: −$3.5B on brands absent from RY26, −$3.7B net restatement of shared brands, +$2.7B on 26 brands only RY26 reports (22 probable renames).
6. **Group exclusivity.** A brand's generics can match a rule *and* match nothing; the 'Other' branch must anti-join on the brand, not the row — otherwise brands land in two groups.
7. **Negotiation edge cases.** 25 selections, 25 matched — but only after handling `Stelara*` star suffixes, nonexistent `Otezla XR`, kit/pack brand spellings, and the NovoLog/Fiasp deselection.
8. **Determinism.** DuckDB parallel float aggregation differs run-to-run in the last digits; `threads=1` makes results byte-identical (tested).
9. **Reconciliation.** No published headline total exists, so we reconcile against the CMS press-release implied total (~$292.9B TTM vs our $288.7B CY24; 14% vs our 14.7%).
10. **CSV over API.** Committing the 5.3 MB CSV makes the whole repo offline-reproducible; the API caps pages at 5,000 rows and can drift.

## Interview Q&A

**Q: How much did Part D drug spending grow?**
$198.7B (2020, full market) → $288.7B (2024): +$90.0B, +45.3%. The survivor-only panel (drugs still listed in 2024) would say +$94.6B, +48.7% — we use the full basis.

**Q: What drove it?**
More patients per drug +$60.6B (67.3%), new drugs +$29.6B (32.9%), utilization +$4.0B (4.4%), claims fallback +$1.6B (1.7%), gross spend per dosage unit −$1.2B (−1.3%); baseline correction: no longer listed −$3.5B, 2020 restatement −$3.7B, RY26-only +$2.7B. "Patients per drug" counts users of each drug — *not* Part D enrollment.

**Q: How do you decompose it?**
Per-drug LMDI over `S = B × C/B × U/C × S/U`; each factor contributes `w·Δln(factor)`, `w` = log mean of spend. Additive to the cent — enforced by a test.

**Q: Biggest data-quality trap?**
Overall + manufacturer rows in the same file — naive `SUM(Tot_Spndng)` over 14,536 rows counts most spend twice. We filter `Mftr_Name='Overall'` (3,625 rows) and verify mfr rows reconcile.

**Q: Which drug class grew fastest?**
GLP-1/incretin: $7.2B → $27.9B (+$20.7B) — about 22% of the entire increase alone.

**Q: Anything shrink?**
Insulins: $15.4B → $7.7B — roughly halved, consistent with the $35 insulin cap and list-price resets.

**Q: How concentrated is spending?**
Top-10 drugs: 20.3% (2020) → 28.5% (2024); top-50: 45.4% → 54.8%. Ten drugs alone produced 59.7% of the increase.

**Q: Negotiation exposure?**
2026 cycle (10 drugs): $61.2B, 21.2% of 2024 spend. 2027 cycle (15): $42.4B, 14.7%. Union: $103.6B, 35.9% — matches CMS's own ~14% figure for the 2027 list.

**Q: Why does the decomposition sum to exactly $90.02B?**
LMDI is additive by construction; leftover residual per drug is folded into its largest component and asserted in tests.

**Q: How do you handle suppressed patient counts?**
199 blank-in-2024 drugs switch to a 3-factor claims-based form; the claims term lands in utilization. ~124 continuing drugs affected; flagged in `quality_checks.csv`.

**Q: Could a drug leave the dataset?**
Not inside the RY26 file — it only lists drugs with ≥11 claims in 2024, so per-drug exits are structurally impossible (QC-verified). But 547 brands present in the RY21 release's 2020 list are gone by RY26 ($3.5B of 2020 spend); the `absent_from_ry26` step corrects the baseline for them.

**Q: How is it reproducible?**
`python -m src.run_all` end-to-end; `python -m pytest` runs 25 tests offline; `test_determinism` runs the pipeline twice and diffs `results/` byte-for-byte (LF-only, rounded CSV/JSON for cross-OS equality).
