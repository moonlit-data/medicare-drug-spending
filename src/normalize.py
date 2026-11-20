"""Cross-platform determinism for results/.

Normalizes every results/*.csv: LF line endings (not CRLF), and rounded
floats so last-bit differences between platforms cannot change the bytes:
money and counts to 2 decimals, percentages/shares to 4, integers stay
integers. kpis.json is written rounded and sorted by src/kpis.py.
"""
import csv
import math

from . import config

PCT_HINTS = ("pct", "share", "percent")


def _is_float(s):
    try:
        f = float(s)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def normalize_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    header, body = rows[0], rows[1:]
    # a column is numeric only if every non-empty cell parses as a float
    numeric = []
    for j in range(len(header)):
        vals = [r[j] for r in body if j < len(r) and r[j] != ""]
        numeric.append(bool(vals) and all(_is_float(v) for v in vals))
    pct_col = [numeric[j] and any(h in header[j].lower() for h in PCT_HINTS)
               for j in range(len(header))]

    def fmt(name_idx, cell):
        if cell == "" or not numeric[name_idx]:
            return cell
        # round FIRST, then decide integer formatting: last-bit noise like
        # 100 vs 100.00000000000001 must produce identical bytes
        f = round(float(cell), 4 if pct_col[name_idx] else 2)
        if f == 0:
            f = 0.0                  # normalize -0.0
        if f.is_integer() and abs(f) < 1e15:
            return str(int(f))
        return f"{f:.4f}" if pct_col[name_idx] else f"{f:.2f}"

    out = [header]
    for r in body:
        out.append([fmt(j, r[j]) if j < len(r) else r[j] for j in range(len(r))])
        if len(r) > len(header):
            out[-1].extend(r[len(header):])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerows(out)


def run():
    for path in sorted(config.RESULTS.glob("*.csv")):
        normalize_csv(path)
    print("normalized results/*.csv (LF endings, rounded floats)")


if __name__ == "__main__":
    run()
