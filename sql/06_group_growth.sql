-- Question: how much of the growth came from each therapeutic group?
-- results/group_growth.csv: spending by group x year.

CREATE OR REPLACE TABLE group_growth AS
SELECT
    g.group_name,
    l.yr,
    SUM(l.spend) AS spend
FROM long_overall l
JOIN drug_group g USING (brnd_name)
GROUP BY g.group_name, l.yr;

COPY (SELECT * FROM group_growth ORDER BY group_name, yr)
TO '__RESULTS__/group_growth.csv' (HEADER, DELIMITER ',');
