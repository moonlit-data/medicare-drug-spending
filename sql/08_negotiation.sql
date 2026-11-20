-- Question: what share of 2024 spending sits in the drugs CMS picked for
-- price negotiation (10 for 2026, 15 for 2027)?
-- Matches by brand name via the curated lists in
-- data/reference/negotiation_drugs.csv (brands normalized the same way as
-- the spending table). Every selected drug must match at least one row;
-- the test suite checks this.

CREATE OR REPLACE TABLE neg_brands AS
SELECT
    cycle,
    selected_drug,
    ingredient,
    lower(regexp_replace(trim(unnest(string_split(matched_brands, ';'))), '\*+$', '')) AS brnd_key
FROM ref_negotiation;

CREATE OR REPLACE TABLE neg_detail AS
SELECT
    n.cycle,
    n.selected_drug,
    n.brnd_key,
    MIN(l.brnd_name) AS dataset_brand_name,
    SUM(l.spend) FILTER (l.yr = 2024) AS spend_2024,
    SUM(l.spend) FILTER (l.yr = 2020) AS spend_2020
FROM neg_brands n
LEFT JOIN long_overall l USING (brnd_key)
GROUP BY n.cycle, n.selected_drug, n.brnd_key;

CREATE OR REPLACE TABLE neg_selected AS
SELECT
    cycle,
    selected_drug,
    SUM(spend_2024) AS spend_2024,
    SUM(spend_2020) AS spend_2020,
    COUNT(dataset_brand_name) AS n_matched_brands
FROM neg_detail
GROUP BY cycle, selected_drug;

CREATE OR REPLACE TABLE neg_summary AS
SELECT
    cycle,
    COUNT(*) AS n_selected_drugs,
    SUM(spend_2024) AS spend_2024,
    100.0 * SUM(spend_2024) / (SELECT SUM(spend) FROM long_overall WHERE yr = 2024) AS share_of_2024_pct
FROM neg_selected
GROUP BY cycle;

COPY (SELECT * FROM neg_detail ORDER BY cycle, selected_drug, brnd_key)
TO '__RESULTS__/negotiation_detail.csv' (HEADER, DELIMITER ',');

COPY (SELECT * FROM neg_selected ORDER BY cycle, spend_2024 DESC NULLS LAST, selected_drug)
TO '__RESULTS__/negotiation_by_drug.csv' (HEADER, DELIMITER ',');

COPY (SELECT * FROM neg_summary ORDER BY cycle)
TO '__RESULTS__/negotiation_summary.csv' (HEADER, DELIMITER ',');
