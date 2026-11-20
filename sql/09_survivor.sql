-- Survivor-bias correction: how much of the true 2020 spending is missing
-- from this release's 2020 baseline?
--
-- Every Overall row in the RY26 file has 2024 spending (the file only lists
-- drugs with >=11 claims in 2024), so drugs that exited or fell under the
-- threshold before 2024 never appear - the 2020 total is a survivors-only
-- number. The RY21 release (2016-2020) lists drugs with >=11 claims in
-- 2020, i.e. the complete 2020 universe. Comparing the two:
-- The bridge from the full RY21 2020 total to the RY26 survivor total
-- splits into three exact components:
--   RY21 total - spend of brands absent from RY26
--              + net 2020 restatement on shared brands
--              + 2020 spend of brands present in RY26 but not in RY21
-- The last bucket also catches renamed brands: a rename shows up as an
-- absent RY21 brand plus a new RY26 brand. Renames are estimated by a
-- generic-name match between the two sides.
--
-- Outputs: results/survivor_correction.csv (summary metrics) and
-- results/survivor_brand_reconciliation.csv (per-brand prior vs current).

CREATE OR REPLACE TABLE raw_prior AS
SELECT
    Brnd_Name,
    lower(regexp_replace(trim(Brnd_Name), '\*+$', '')) AS brnd_key,
    lower(trim(Gnrc_Name)) AS gnrc_key,
    Mftr_Name,
    TRY_CAST(Tot_Spndng_2020 AS DOUBLE) AS spend_2020
FROM read_csv('__RAW_PRIOR__', header = true, all_varchar = true, nullstr = '');

CREATE OR REPLACE TABLE prior_brand AS
SELECT brnd_key, SUM(spend_2020) AS spend_prior_2020
FROM raw_prior
WHERE Mftr_Name = 'Overall'
GROUP BY brnd_key;

-- generic names seen on prior-release brands (any row, for rename matching)
CREATE OR REPLACE TABLE prior_gnrc AS
SELECT DISTINCT brnd_key, gnrc_key
FROM raw_prior WHERE Mftr_Name = 'Overall';

CREATE OR REPLACE TABLE current_brand AS
SELECT brnd_key, SUM(spend) AS spend_current_2020
FROM (
    SELECT lower(regexp_replace(trim(Brnd_Name), '\*+$', '')) AS brnd_key,
           TRY_CAST(Tot_Spndng_2020 AS DOUBLE) AS spend
    FROM raw
    WHERE Mftr_Name = 'Overall'
)
GROUP BY brnd_key;

-- generic names seen on current-release brands (any row, for rename matching)
CREATE OR REPLACE TABLE current_gnrc AS
SELECT DISTINCT lower(regexp_replace(trim(Brnd_Name), '\*+$', '')) AS brnd_key,
       lower(trim(Gnrc_Name)) AS gnrc_key
FROM raw WHERE Mftr_Name = 'Overall';

-- per-brand reconciliation: every brand either release saw in 2020
CREATE OR REPLACE TABLE brand_recon AS
SELECT
    COALESCE(p.brnd_key, c.brnd_key) AS brnd_key,
    p.spend_prior_2020,
    c.spend_current_2020,
    CASE WHEN c.brnd_key IS NULL THEN 0 ELSE 1 END AS in_current_release,
    CASE WHEN p.brnd_key IS NULL THEN 0 ELSE 1 END AS in_prior_release
FROM prior_brand p
FULL OUTER JOIN current_brand c USING (brnd_key);

COPY (
    SELECT brnd_key,
           ROUND(spend_prior_2020, 2) AS spend_prior_2020,
           ROUND(spend_current_2020, 2) AS spend_current_2020,
           ROUND(COALESCE(spend_current_2020, 0) - COALESCE(spend_prior_2020, 0), 2)
               AS revision_2020,
           in_current_release,
           in_prior_release
    FROM brand_recon
    ORDER BY brnd_key
) TO '__RESULTS__/survivor_brand_reconciliation.csv' (HEADER, DELIMITER ',');

-- summary metrics
CREATE OR REPLACE TABLE survivor_metrics AS
SELECT * FROM (VALUES
    ('prior_release', 'RY21 (data through 2020): its drug list is based on >=11 claims in 2020',
     NULL),
    ('prior_release_total_2020', 'full 2020 gross spending over all drugs listed in RY21',
     (SELECT SUM(spend_prior_2020) FROM prior_brand)),
    ('prior_release_n_drugs_2020', 'count of brands with 2020 spend in RY21 (full-market drug count)',
     (SELECT COUNT(*) FROM prior_brand WHERE spend_prior_2020 > 0)),
    ('this_release_total_2020', '2020 gross spending over drugs still listed in RY26 (survivors only)',
     (SELECT SUM(spend_current_2020) FROM current_brand)),
    ('no_longer_listed', 'full 2020 total minus survivor 2020 total; subtracted in the decomposition',
     (SELECT SUM(spend_prior_2020) - SUM(spend_current_2020)
      FROM prior_brand p FULL OUTER JOIN current_brand c USING (brnd_key))),
    ('brands_absent_from_ry26', 'brands with 2020 spend in RY21 that do not appear in RY26 at all',
     (SELECT COUNT(*) FROM brand_recon WHERE in_current_release = 0
        AND spend_prior_2020 > 0)),
    ('spend_of_absent_brands_2020', 'their combined 2020 spend (RY21 values)',
     (SELECT SUM(spend_prior_2020) FROM brand_recon
        WHERE in_current_release = 0 AND spend_prior_2020 > 0)),
    ('brands_revised_2020', 'shared brands whose 2020 spend differs between releases by > $0.01 (a suppressed 2020 cell counts as 0)',
     (SELECT COUNT(*) FROM brand_recon WHERE in_current_release = 1
        AND in_prior_release = 1
        AND ABS(COALESCE(spend_current_2020, 0) - COALESCE(spend_prior_2020, 0)) > 0.01)),
    ('net_revision_2020', 'sum over shared brands of (RY26 2020 spend - RY21 2020 spend; suppressed cells as 0)',
     (SELECT SUM(COALESCE(spend_current_2020, 0) - COALESCE(spend_prior_2020, 0))
        FROM brand_recon WHERE in_current_release = 1 AND in_prior_release = 1)),
    ('largest_single_revision', 'largest absolute single-brand 2020 revision',
     (SELECT MAX(ABS(COALESCE(spend_current_2020, 0) - COALESCE(spend_prior_2020, 0)))
        FROM brand_recon WHERE in_current_release = 1 AND in_prior_release = 1)),
    ('brands_ry26_only_2020', 'brands with 2020 spend in RY26 that are not in RY21 at all',
     (SELECT COUNT(*) FROM brand_recon WHERE in_current_release = 1
        AND in_prior_release = 0 AND spend_current_2020 > 0)),
    ('spend_of_ry26_only_2020', 'their combined 2020 spend (RY26 values)',
     (SELECT SUM(spend_current_2020) FROM brand_recon
        WHERE in_current_release = 1 AND in_prior_release = 0
        AND spend_current_2020 > 0)),
    ('probable_renames_ry26_only', 'RY26-only brands sharing a generic name with an absent RY21 brand',
     (SELECT COUNT(DISTINCT c.brnd_key) FROM brand_recon r
        JOIN current_gnrc c ON r.brnd_key = c.brnd_key
        JOIN prior_gnrc p ON c.gnrc_key = p.gnrc_key
        JOIN brand_recon a ON a.brnd_key = p.brnd_key
        WHERE r.in_current_release = 1 AND r.in_prior_release = 0
          AND r.spend_current_2020 > 0 AND a.in_current_release = 0))
) AS t(check_name, detail, value);

COPY (SELECT * FROM survivor_metrics)
TO '__RESULTS__/survivor_correction.csv' (HEADER, DELIMITER ',');
