-- Question: how do we get a tidy drug x manufacturer x year panel?
-- Reshapes the wide file to long format in SQL. Blank cells become NULL.
-- brnd_key normalizes the brand name for joining (lowercase, trimmed,
-- trailing '*' route-of-administration flag removed).

CREATE OR REPLACE TABLE long_all AS
SELECT
    Brnd_Name AS brnd_name,
    lower(regexp_replace(trim(Brnd_Name), '\*+$', '')) AS brnd_key,
    Gnrc_Name AS gnrc_name,
    Mftr_Name AS mftr_name,
    2020 AS yr,
    TRY_CAST(Tot_Spndng_2020 AS DOUBLE) AS spend,
    TRY_CAST(Tot_Dsg_Unts_2020 AS DOUBLE) AS units,
    TRY_CAST(Tot_Clms_2020   AS DOUBLE) AS claims,
    TRY_CAST(Tot_Benes_2020  AS DOUBLE) AS benes,
    TRY_CAST(Outlier_Flag_2020 AS INTEGER) AS outlier_flag
FROM raw
UNION ALL SELECT Brnd_Name, lower(regexp_replace(trim(Brnd_Name), '\*+$', '')), Gnrc_Name, Mftr_Name, 2021,
    TRY_CAST(Tot_Spndng_2021 AS DOUBLE), TRY_CAST(Tot_Dsg_Unts_2021 AS DOUBLE),
    TRY_CAST(Tot_Clms_2021 AS DOUBLE), TRY_CAST(Tot_Benes_2021 AS DOUBLE), TRY_CAST(Outlier_Flag_2021 AS INTEGER)
FROM raw
UNION ALL SELECT Brnd_Name, lower(regexp_replace(trim(Brnd_Name), '\*+$', '')), Gnrc_Name, Mftr_Name, 2022,
    TRY_CAST(Tot_Spndng_2022 AS DOUBLE), TRY_CAST(Tot_Dsg_Unts_2022 AS DOUBLE),
    TRY_CAST(Tot_Clms_2022 AS DOUBLE), TRY_CAST(Tot_Benes_2022 AS DOUBLE), TRY_CAST(Outlier_Flag_2022 AS INTEGER)
FROM raw
UNION ALL SELECT Brnd_Name, lower(regexp_replace(trim(Brnd_Name), '\*+$', '')), Gnrc_Name, Mftr_Name, 2023,
    TRY_CAST(Tot_Spndng_2023 AS DOUBLE), TRY_CAST(Tot_Dsg_Unts_2023 AS DOUBLE),
    TRY_CAST(Tot_Clms_2023 AS DOUBLE), TRY_CAST(Tot_Benes_2023 AS DOUBLE), TRY_CAST(Outlier_Flag_2023 AS INTEGER)
FROM raw
UNION ALL SELECT Brnd_Name, lower(regexp_replace(trim(Brnd_Name), '\*+$', '')), Gnrc_Name, Mftr_Name, 2024,
    TRY_CAST(Tot_Spndng_2024 AS DOUBLE), TRY_CAST(Tot_Dsg_Unts_2024 AS DOUBLE),
    TRY_CAST(Tot_Clms_2024 AS DOUBLE), TRY_CAST(Tot_Benes_2024 AS DOUBLE), TRY_CAST(Outlier_Flag_2024 AS INTEGER)
FROM raw;

-- One row per drug x year, all manufacturers combined.
CREATE OR REPLACE TABLE long_overall AS
SELECT * FROM long_all WHERE mftr_name = 'Overall';

-- Yearly program totals as reported by the dataset (Overall rows only).
CREATE OR REPLACE TABLE yearly_totals AS
-- a "drug" is one brand name: count brands, not brand x generic rows
SELECT yr,
       COUNT(DISTINCT brnd_name) FILTER (spend IS NOT NULL) AS n_drugs,
       SUM(spend) AS gross_spending
FROM long_overall
GROUP BY yr;

COPY (SELECT * FROM yearly_totals ORDER BY yr)
TO '__RESULTS__/yearly_totals.csv' (HEADER, DELIMITER ',');
