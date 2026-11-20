"""Regression tests for output normalization (rounding BEFORE integer check).

Review finding: the old order (is_integer first, then format) printed
100.00000000000001 as '100.00' while a platform computing exactly 100
printed '100' — byte differences across platforms. Rounding first must
collapse both to '100'.
"""
import csv

from src import normalize


def _write(tmp_path, header, rows):
    p = tmp_path / "t.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return p


def _read(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_last_bit_noise_becomes_integer(tmp_path):
    p = _write(tmp_path, ["spend"], [["100.00000000000001"], ["99.99999999999999"]])
    normalize.normalize_csv(p)
    rows = _read(p)
    assert rows[1] == ["100"]
    assert rows[2] == ["100"]


def test_rounding_before_format(tmp_path):
    # 200.49999999999999 rounds to 200.5, not 200
    p = _write(tmp_path, ["spend"], [["200.49999999999999"], ["0.0049999"]])
    normalize.normalize_csv(p)
    rows = _read(p)
    assert rows[1] == ["200.50"]
    assert rows[2] == ["0"]


def test_pct_column_four_decimals(tmp_path):
    p = _write(tmp_path, ["top10_share_pct"], [["28.499999999999996"], ["14.7"]])
    normalize.normalize_csv(p)
    rows = _read(p)
    assert rows[1] == ["28.5000"]
    assert rows[2] == ["14.7000"]


def test_minus_zero_normalized(tmp_path):
    p = _write(tmp_path, ["delta"], [["-0.0000001"], ["-0.0"]])
    normalize.normalize_csv(p)
    rows = _read(p)
    assert rows[1] == ["0"]
    assert rows[2] == ["0"]


def test_non_numeric_columns_untouched(tmp_path):
    p = _write(tmp_path, ["brand", "spend"], [["Drugg*", "abc"], ["Drugb", "12.3456789"]])
    normalize.normalize_csv(p)
    rows = _read(p)
    # column 'spend' isn't all-numeric -> left alone
    assert rows[1] == ["Drugg*", "abc"]
    assert rows[2] == ["Drugb", "12.3456789"]


def test_lf_endings(tmp_path):
    p = _write(tmp_path, ["a"], [["1.0"]])
    normalize.normalize_csv(p)
    data = p.read_bytes()
    assert b"\r" not in data


def test_kpis_rounding_order():
    from src.kpis import _round
    # float noise collapses to int identically on every platform
    assert _round("spend", 100.00000000000001) == 100
    assert _round("share_pct", 28.499999999999996) == 28.5
    assert _round("spend", 200.49999999999999) == 200.5
    assert _round("spend", -0.0000001) == 0
    assert type(_round("spend", 100.00000000000001)) is int
