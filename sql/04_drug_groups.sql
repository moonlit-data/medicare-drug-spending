-- Question: which therapeutic group does each drug belong to?
-- Applies the hand-maintained rules in data/reference/drug_groups.csv.
-- A "drug" here is one brand name; a few brands appear with several generic
-- names (e.g. Calquence with two salt forms). Each brand gets exactly one
-- group: the lowest-priority-number rule matching ANY of its generic names
-- (ties on generic name). Anything unmatched is 'Other'.
-- Adding a drug to a group = adding one CSV row.

CREATE OR REPLACE TABLE drug_group AS
WITH per_pair AS (
    SELECT
        d.brnd_name,
        d.gnrc_name,
        g.group_name,
        MIN(g.priority) AS priority
    FROM (SELECT DISTINCT brnd_name, gnrc_name FROM long_overall) d
    JOIN ref_groups g
        ON (g.match_field = 'gnrc_contains'
            AND position(lower(g.match_value) IN lower(d.gnrc_name)) > 0)
        OR (g.match_field = 'brnd_contains'
            AND position(lower(g.match_value) IN lower(d.brnd_name)) > 0)
    GROUP BY ALL
),
best_per_brand AS (
    SELECT brnd_name, group_name,
           ROW_NUMBER() OVER (PARTITION BY brnd_name
                              ORDER BY priority, gnrc_name) AS rn
    FROM per_pair
)
SELECT brnd_name,
       (SELECT MIN(d.gnrc_name) FROM long_overall d WHERE d.brnd_name = b.brnd_name) AS gnrc_name,
       group_name
FROM best_per_brand b WHERE rn = 1
UNION ALL
-- brands with no matching rule at all on any of their generic names
SELECT brnd_name, MIN(gnrc_name), 'Other'
FROM long_overall
WHERE brnd_name NOT IN (SELECT brnd_name FROM best_per_brand)
GROUP BY brnd_name;

-- coverage check: how many drugs land in Other?
CREATE OR REPLACE TABLE group_coverage AS
SELECT
    COUNT(*) AS n_drugs_other,
    (SELECT COUNT(DISTINCT brnd_name) FROM long_overall) AS n_drugs_total
FROM drug_group WHERE group_name = 'Other';
