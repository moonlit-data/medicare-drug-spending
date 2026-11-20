-- Question: what is wrong with this file, and how much of it is there?
-- Produces results/quality_checks.csv: one row per check. These counts are
-- quoted in docs/data_quality.md.

CREATE OR REPLACE TABLE qc_rows AS
SELECT * FROM (VALUES
    ('rows_total', 'all rows in the file (drug x manufacturer rows + Overall rows)', (SELECT COUNT(*)::VARCHAR FROM raw)),
    ('rows_overall', 'rows with Mftr_Name = ''Overall'' (one per brand/generic combination)', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall')),
    ('rows_manufacturer', 'manufacturer-level rows; summing ALL rows would double-count', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name <> 'Overall')),
    ('distinct_brands', 'distinct brand names among Overall rows', (SELECT COUNT(DISTINCT Brnd_Name)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall')),
    ('brands_star_suffix', 'Overall rows whose brand name ends in ''*'' (multiple routes of administration flag)', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall' AND Brnd_Name LIKE '%*')),
    ('blank_spend_2020', 'Overall rows with spending blank in 2020 (drug absent or <11 claims, redacted)', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall' AND Tot_Spndng_2020 IS NULL)),
    ('blank_spend_2024', 'Overall rows with spending blank in 2024', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall' AND Tot_Spndng_2024 IS NULL)),
    ('blank_benes_2020', 'Overall rows with spending but beneficiary count suppressed in 2020', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall' AND Tot_Spndng_2020 IS NOT NULL AND Tot_Benes_2020 IS NULL)),
    ('blank_benes_2024', 'Overall rows with spending but beneficiary count suppressed in 2024', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall' AND Tot_Spndng_2024 IS NOT NULL AND Tot_Benes_2024 IS NULL)),
    ('outlier_flag_2020', 'Overall rows flagged as price outliers in 2020', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall' AND Outlier_Flag_2020 = '1')),
    ('outlier_flag_2024', 'Overall rows flagged as price outliers in 2024', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall' AND Outlier_Flag_2024 = '1')),
    ('new_in_2024', 'Overall rows present in 2024 with no 2020 spending', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall' AND Tot_Spndng_2020 IS NULL AND Tot_Spndng_2024 IS NOT NULL)),
    ('gone_by_2024', 'Overall rows with 2020 spending but none in 2024 (structurally zero: file only lists drugs with >=11 claims in 2024)', (SELECT COUNT(*)::VARCHAR FROM raw WHERE Mftr_Name = 'Overall' AND Tot_Spndng_2020 IS NOT NULL AND Tot_Spndng_2024 IS NULL))
) AS t(check_name, detail, value);

-- Do manufacturer rows sum back to the Overall row? (double-counting check)
CREATE OR REPLACE TABLE qc_mfr_vs_overall AS
WITH mfr AS (
    SELECT Brnd_Name, Gnrc_Name,
           SUM(TRY_CAST(Tot_Spndng_2020 AS DOUBLE)) AS mfr_2020,
           SUM(TRY_CAST(Tot_Spndng_2024 AS DOUBLE)) AS mfr_2024
    FROM raw WHERE Mftr_Name <> 'Overall'
    GROUP BY ALL
),
ov AS (
    SELECT Brnd_Name, Gnrc_Name,
           TRY_CAST(Tot_Spndng_2020 AS DOUBLE) AS ov_2020,
           TRY_CAST(Tot_Spndng_2024 AS DOUBLE) AS ov_2024
    FROM raw WHERE Mftr_Name = 'Overall'
)
SELECT COUNT(*) AS n_diff
FROM ov JOIN mfr USING (Brnd_Name, Gnrc_Name)
WHERE ABS(COALESCE(ov_2020, 0) - COALESCE(mfr_2020, 0)) > 0.01
   OR ABS(COALESCE(ov_2024, 0) - COALESCE(mfr_2024, 0)) > 0.01;

INSERT INTO qc_rows
SELECT 'mfr_rows_exceed_overall',
       'drug-years where summed manufacturer spending differs from the Overall row by more than $0.01',
       (SELECT n_diff::VARCHAR FROM qc_mfr_vs_overall);

COPY (SELECT * FROM qc_rows ORDER BY check_name)
TO '__RESULTS__/quality_checks.csv' (HEADER, DELIMITER ',');
