"""Shared paths and constants for the pipeline."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
REFERENCE = DATA / "reference"
RESULTS = ROOT / "results"
SQL_DIR = ROOT / "sql"
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports"

# CMS "Medicare Part D Spending by Drug" dataset, RY26 release (data through
# 2024), published 2026-06-25. The CSV distribution is the canonical file;
# the JSON API endpoint serves identical rows.
DATASET_ID = "7e0b4365-fd63-4a29-8f5e-e0ac9f66a81b"
DATASET_CSV_URL = (
    "https://data.cms.gov/sites/default/files/2026-06/"
    "98218f98-166c-4723-8438-c344a4ef96a6/"
    "DSD_PTD_RY26_P04_V10_DY24_BGM.csv"
)
DATASET_API_URL = f"https://data.cms.gov/data-api/v1/dataset/{DATASET_ID}/data"
DATASET_LANDING_PAGE = (
    "https://data.cms.gov/summary-statistics-on-use-and-payments/"
    "medicare-medicaid-spending-by-drug/medicare-part-d-spending-by-drug"
)
DATASET_RELEASE_DATE = "2026-06-25"
EXPECTED_ROWS = 14536
RAW_CSV = RAW / "DSD_PTD_RY26_P04_V10_DY24_BGM.csv"
RAW_SHA256 = "5dcc9d7bd7d7f88d9f6b24485c06d961ed6d70f9aa6deffa50dd47a6854c2a55"

# Prior release RY21 (data through 2020): the drug list is based on
# >=11 claims in 2020, so its 2020 total covers every drug that was on the
# market then - including the ones absent from the RY26 release. Used to
# correct the survivor bias in the 2020 baseline.
PRIOR_CSV_URL = (
    "https://data.cms.gov/sites/default/files/2022-01/"
    "bdc2d0f7-fcdb-4429-9304-f97dfdc3c7ab/"
    "DSD_PTD_R21_P04_V21_D20_BGM.csv"
)
PRIOR_CSV = RAW / "DSD_PTD_R21_P04_V21_D20_BGM.csv"
PRIOR_EXPECTED_ROWS = 13570
PRIOR_SHA256 = "76f42332c464c2d856b6603e10878e29869e4e5afd8d558acf56b24480a75df0"
PRIOR_RELEASE = "RY21 (data through 2020)"

YEARS = [2020, 2021, 2022, 2023, 2024]
BASE_YEAR, END_YEAR = 2020, 2024

# Fixed categorical palette (task spec): never cycle, >6 categories -> "Other".
CAT_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4",
             "#008300", "#6250d6", "#e34948"]
CAT_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181",
            "#008300", "#9085e9", "#e66767"]

SURFACES = {
    "light": {"bg": "#fcfcfb", "text": "#0b0b0b", "secondary": "#52514e", "grid": "#e1e0d9"},
    "dark": {"bg": "#1a1a19", "text": "#f0efec", "secondary": "#c3c2b7", "grid": "#2c2c2a"},
}

BLUE_RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
             "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]

# Decomposition components in display order. 'patients_per_drug' is the
# Tot_Benes factor: the number of people using each drug, summed over
# drugs - NOT Medicare Part D enrollment growth (one person taking five
# drugs is counted five times).
# aggregate survivor-bias correction steps, applied before the per-drug
# decomposition (in bridge order): RY21 total -> absent -> restatement ->
# RY26-only -> survivor total
CORRECTION_BUCKETS = ["absent_from_ry26", "restatement_2020", "ry26_only_2020"]
BUCKETS = CORRECTION_BUCKETS + ["new_drugs", "exited_drugs", "patients_per_drug",
           "utilization", "price", "unattributed"]
BUCKET_LABELS = {
    "absent_from_ry26": "No longer listed",
    "restatement_2020": "2020 restatement",
    "ry26_only_2020": "In RY26, not RY21",
    "new_drugs": "New drugs",
    "exited_drugs": "Drugs that left",
    "patients_per_drug": "More patients per drug",
    "utilization": "Claims / units per patient",
    "claims_fallback": "Claims (patient count n/a)",
    "price": "Spend per unit",
    "unattributed": "Unattributed",
}
# Components produced by the per-drug LMDI panel itself (the survivor
# panel); the CORRECTION_BUCKETS are added afterwards from the prior release.
PANEL_BUCKETS = ["new_drugs", "exited_drugs", "patients_per_drug",
                 "utilization", "claims_fallback", "price", "unattributed"]

