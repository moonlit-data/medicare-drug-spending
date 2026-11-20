# Metric definitions

All figures are **gross Medicare Part D spending** (`Tot_Spndng` in the CMS file) before rebates and manufacturer discounts, summed over `Mftr_Name = 'Overall'` rows only. Manufacturer-level rows exist alongside Overall rows and are *never* added on top — they would double-count (a QC test checks that manufacturer rows sum back to the Overall row for every drug-year, allowing a $0.01 rounding tolerance).

**Baseline.** The headline 2020 total is the *full market*: the RY21 release's 2020 sum ($198.7B), because that release lists every drug with >=11 claims in 2020. The RY26 release's own 2020 total ($194.1B) covers only drugs still listed in 2024 — the *survivor panel*.

**"Patients per drug" is not enrollment.** `Tot_Benes` counts the people who used each drug; summed over drugs it counts a person once per drug they take. It measures per-drug adoption — it cannot and does not claim that Part D enrollment grew.

## The survivor-correction steps

```
absent_from_ry26 = -(2020 spend of brands in RY21 but not RY26)   <= 0
restatement_2020 = sum over shared brands of (RY26 2020 - RY21 2020; blanks = 0)
ry26_only_2020   = 2020 spend of brands in RY26 but not RY21       >= 0
```

The three steps, computed in `sql/09_survivor.sql`, bridge the RY21 2020 total down to the RY26 survivor 2020 total and sum to it exactly: −$3.54B of 2020 spend sat on 547 brand identifiers absent from RY26 entirely ("no longer listed"; most are brands that left the market or fell below the threshold, but an unknown share are *renames* — the matching generic-name evidence is on the other side of the bridge, so the step is best read as 2020 spend on unmatched legacy identifiers), shared brands' 2020 values were restated down by −$3.72B net (940 brands; blank 2020 cells count as 0), and +$2.70B is 2020 spend RY26 reports for 26 brands RY21 never listed — 22 of them share a generic name with an absent brand (a rename lead, not proof). Per-brand detail: `results/survivor_brand_reconciliation.csv`. The steps are prepended to the decomposition so the parts sum to the change against the true 2020 total.

## Spending, counts, and the identity

A **drug is one brand name**: spend, claims and units are summed over the brand's generic-name rows (e.g. salt forms). Beneficiaries are **not** summed over those rows — a person who used two forms of one brand in a year would be counted twice, and a suppressed count on one row would silently drop patients. A brand-year therefore has a patient count only when it has *exactly one* spend-bearing row with `Tot_Benes` disclosed; otherwise it uses the claims-based form below.

For each drug *d* and year *y*:

```
spend   = Tot_Spndng_{y}
benes   = Tot_Benes_{y}   (single spend-bearing row only, else unusable)
claims  = Tot_Clms_{y}
units   = Tot_Dsg_Unts_{y}
```

The multiplicative identity used everywhere:

```
S = B × C/B × U/C × S/U
  = beneficiaries × (claims per beneficiary) × (units per claim) × (spend per unit)
```

## LMDI decomposition (per drug)

For each drug, define the log mean of spending between the base year (2020) and end year (2024):

```
w = (S₁ − S₀) / (ln S₁ − ln S₀)     (w = S₀ when S₀ = S₁)
```

Each factor f contributes `w · (ln f₁ − ln f₀)`. With four factors:

```
ΔS = w·ln(B₁/B₀)      → patients per drug (users of that drug)
   + w·ln((C/B)₁/(C/B)₀) → claims per patient   } reported together as
   + w·ln((U/C)₁/(U/C)₀) → units per claim      } "utilization"
   + w·ln((S/U)₁/(S/U)₀) → gross spend per dosage unit  → "price"
```

The `price` factor is *gross spend per dosage unit*, not a list price: when a brand's mix of strengths or forms shifts, this factor moves even if every unit price is unchanged. A pure price-effect read needs cells defined at constant strength/form/route, which this file does not give.

Expanding `w·Δln` for each factor uses the equivalent pair-difference form `w·(ln b₁ − ln a₁ − ln b₀ + ln a₀)` for ratio factors, computed with `math.log` on the raw counts.

**Special cases** (implemented in `src/decompose.py`, exercised by `tests/fixtures/`):

- *New drug* (`S₀` empty): whole `S₁` to `new_drugs`. Empty means *undisclosed in 2020* — either a true launch or a brand below the 11-claim disclosure threshold; there is no launch-date evidence in the file, so the bucket is an upper bound on genuinely new drugs.
- *Exited drug* (`S₁` empty): whole `−S₀` to `exited_drugs` (always 0 in this release — the file only lists drugs with ≥11 claims in 2024).
- *Patient count unusable* (suppressed, or multi-row brand) but claims and units present: 3-factor form `S = C × U/C × S/U`; the total-claims contribution is reported in its own `claims_fallback` bucket — not inside `utilization`, because total claims growth can reflect more patients, not just use per patient. Coverage: 188 brands on the real data.
- *No usable volume data*: whole `ΔS` to `unattributed`.
- *Residual*: after the factors are computed, `ΔS − Σparts` is folded into the largest absolute component so each drug's parts sum to its change to the cent.

## Derived metrics

- **Concentration** (`results/concentration.csv`): share of yearly spending held by the 10 and 50 drugs with the highest spend that year (ties broken by brand name for determinism).
- **Group spending** (`results/group_growth.csv`): yearly spend summed by drug group (see `data/reference/drug_groups.csv`).
- **Negotiation exposure** (`results/negotiation_*.csv`): 2024 spending of drugs whose brand name (lowered, trailing `*` stripped) matches a selected drug in `data/reference/negotiation_drugs.csv`; `share_of_2024_pct` divides by total 2024 spending.
- **Share of increase**: each component or drug's `ΔS ÷ ΣΔS × 100`.
- **Rounding:** money in prose is rounded to $0.1B; percentages to 0.1 pt. All displayed numbers come from `results/` files — verified by `tests/test_results_consistency.py`.
