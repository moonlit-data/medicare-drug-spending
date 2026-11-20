-- Question: what does the raw CMS file look like, loaded verbatim?
-- Loads the wide-format CSV (one row per brand x manufacturer, one set of
-- measure columns per year 2020-2024) plus the two reference CSVs.
-- Everything is read as VARCHAR with empty cells -> NULL; casting happens
-- in 03_long_format.sql so this layer stays a faithful copy of the file.

CREATE OR REPLACE TABLE raw AS
SELECT * FROM read_csv('__RAW__', header = true, all_varchar = true, nullstr = '');

CREATE OR REPLACE TABLE ref_groups AS
SELECT
    TRY_CAST(priority AS INTEGER) AS priority,
    "group" AS group_name,
    match_field,
    match_value,
    rule
FROM read_csv('__REF_GROUPS__', header = true);

CREATE OR REPLACE TABLE ref_negotiation AS
SELECT * FROM read_csv('__REF_NEG__', header = true);
