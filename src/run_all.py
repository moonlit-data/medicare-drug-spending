"""One command reproduces everything:  python -m src.run_all

Steps: download raw data -> SQL pipeline (load, QC, reshape, groups,
per-drug results) -> decomposition -> KPIs -> static charts -> dashboard
-> generated docs.
"""
from . import (build_dashboard, build_report, charts, config, db, decompose,
               download, kpis, normalize)

SQL_ORDER = [
    "01_load.sql",
    "02_quality_checks.sql",
    "03_long_format.sql",
    "04_drug_groups.sql",
    "05_top_drugs.sql",
    "06_group_growth.sql",
    "07_concentration.sql",
    "08_negotiation.sql",
    "09_survivor.sql",
]


def run(raw_csv=None, raw_prior_csv=None):
    config.RESULTS.mkdir(exist_ok=True)
    if raw_csv is None:
        raw_csv = download.ensure_data()
    con = db.connect()
    db.run_sql_files(con, SQL_ORDER, raw_csv, raw_prior_csv=raw_prior_csv)
    decompose.run(con)
    # normalize CSVs before downstream steps so charts/dashboard/report all
    # read the same rounded values that ship in results/
    normalize.run()
    kpis.run()
    charts.run()
    build_dashboard.main()
    build_report.run()
    print("done.")


def main():
    run()


if __name__ == "__main__":
    main()
