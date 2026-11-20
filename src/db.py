"""Run the numbered SQL files against DuckDB.

Each file may contain __RAW__, __REF_GROUPS__, __REF_NEG__ and __RESULTS__
placeholders, substituted before execution so the SQL stays portable.
"""
import duckdb

from . import config


def _substitute(sql_text, raw_csv=None, ref_groups=None, ref_neg=None,
                results_dir=None, raw_prior_csv=None):
    raw = str(raw_csv if raw_csv is not None else config.RAW_CSV)
    rg = str(ref_groups if ref_groups is not None else config.REFERENCE / "drug_groups.csv")
    rn = str(ref_neg if ref_neg is not None else config.REFERENCE / "negotiation_drugs.csv")
    res = str(results_dir if results_dir is not None else config.RESULTS)
    rp = str(raw_prior_csv if raw_prior_csv is not None else config.PRIOR_CSV)
    return (sql_text
            .replace("__RAW__", raw.replace("\\", "/"))
            .replace("__RAW_PRIOR__", rp.replace("\\", "/"))
            .replace("__REF_GROUPS__", rg.replace("\\", "/"))
            .replace("__REF_NEG__", rn.replace("\\", "/"))
            .replace("__RESULTS__", res.replace("\\", "/")))


def run_sql_file(con, name, raw_csv=None, ref_groups=None, ref_neg=None,
                 results_dir=None, raw_prior_csv=None):
    path = config.SQL_DIR / name
    con.execute(_substitute(path.read_text(encoding="utf-8"), raw_csv,
                            ref_groups, ref_neg, results_dir, raw_prior_csv))
    return con


def run_sql_files(con, names, raw_csv=None, ref_groups=None, ref_neg=None,
                  results_dir=None, raw_prior_csv=None):
    for name in names:
        run_sql_file(con, name, raw_csv, ref_groups, ref_neg, results_dir, raw_prior_csv)
        print(f"ran sql/{name}")


def connect():
    config.RESULTS.mkdir(exist_ok=True)
    con = duckdb.connect()
    # single-threaded: parallel floating-point aggregation order is not
    # guaranteed identical between runs, and we require byte-identical results
    con.execute("SET threads = 1")
    return con
