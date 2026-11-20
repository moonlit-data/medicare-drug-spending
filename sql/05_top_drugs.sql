-- Question: which individual drugs moved most between 2020 and 2024?
-- results/top_drugs.csv: every drug, its group, 2020/2024 spending, change,
-- and its rank by growth (ties broken by brand name for determinism).

CREATE OR REPLACE TABLE top_drugs AS
-- endpoint spend summed over a brand's generic-name rows; stays NULL
-- only when every row of that endpoint year is undisclosed
WITH p AS (
    SELECT brnd_name, yr, spend FROM long_overall
),
piv AS (
    SELECT brnd_name,
           SUM(CASE WHEN yr = 2020 THEN spend END) AS spend_2020,
           SUM(CASE WHEN yr = 2024 THEN spend END) AS spend_2024
    FROM p GROUP BY brnd_name
)
SELECT
    piv.brnd_name,
    g.gnrc_name,
    g.group_name,
    piv.spend_2020,
    piv.spend_2024,
    COALESCE(piv.spend_2024, 0) - COALESCE(piv.spend_2020, 0) AS spend_change,
    ROW_NUMBER() OVER (
        ORDER BY COALESCE(piv.spend_2024, 0) - COALESCE(piv.spend_2020, 0) DESC,
                 piv.brnd_name
    ) AS growth_rank
FROM piv
JOIN drug_group g USING (brnd_name);

COPY (SELECT * FROM top_drugs ORDER BY growth_rank)
TO '__RESULTS__/top_drugs.csv' (HEADER, DELIMITER ',');
