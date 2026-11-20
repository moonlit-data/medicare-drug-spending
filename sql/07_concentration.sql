-- Question: how concentrated is spending - what share sit in the top 10
-- and top 50 drugs each year?

CREATE OR REPLACE TABLE concentration AS
WITH brand_year AS (
    -- a "drug" is one brand name: aggregate its generic-name rows first
    SELECT brnd_name, yr, SUM(spend) AS spend
    FROM long_overall
    GROUP BY brnd_name, yr
    HAVING SUM(spend) IS NOT NULL
),
ranked AS (
    SELECT brnd_name, yr, spend,
           ROW_NUMBER() OVER (PARTITION BY yr ORDER BY spend DESC, brnd_name) AS rnk
    FROM brand_year
),
agg AS (
    SELECT yr,
           SUM(spend) AS total,
           SUM(spend) FILTER (rnk <= 10) AS top10_spend,
           SUM(spend) FILTER (rnk <= 50) AS top50_spend
    FROM ranked GROUP BY yr
)
SELECT yr, total,
       top10_spend, 100.0 * top10_spend / total AS top10_share_pct,
       top50_spend, 100.0 * top50_spend / total AS top50_share_pct
FROM agg;

COPY (SELECT * FROM concentration ORDER BY yr)
TO '__RESULTS__/concentration.csv' (HEADER, DELIMITER ',');
