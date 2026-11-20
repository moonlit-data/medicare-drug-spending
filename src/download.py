"""Download the raw CMS file and verify it.

Keeps the file untouched in data/raw/ and records a SHA-256 + row-count
manifest so a later run can prove it has the same bytes.
"""
import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone

from . import config


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def row_count(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return sum(1 for _ in csv.DictReader(f))


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "medicare-drug-spending/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)


def _ensure(path, url, expected_rows, expected_sha, label):
    if not path.exists():
        print(f"downloading {url}")
        download(url, path)
    digest = sha256_of(path)
    n = row_count(path)
    if n != expected_rows:
        sys.exit(f"{label} file has {n} rows, expected {expected_rows}")
    if digest != expected_sha:
        print(f"warning: {label} SHA-256 differs from the recorded release hash "
              "(CMS may have republished the file); continuing with the downloaded bytes")
    print(f"{label} data ok: {path.name} ({n} rows, sha256 {digest[:12]}...)")
    return digest, n


def ensure_data():
    """Return the path to the raw CSV, downloading it if missing."""
    digest, n = _ensure(config.RAW_CSV, config.DATASET_CSV_URL,
                        config.EXPECTED_ROWS, config.RAW_SHA256, "raw")
    manifest = {
        "url": config.DATASET_CSV_URL,
        "dataset_id": config.DATASET_ID,
        "landing_page": config.DATASET_LANDING_PAGE,
        "release_date": config.DATASET_RELEASE_DATE,
        "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": digest,
        "rows": n,
        "expected_sha256": config.RAW_SHA256,
        "expected_rows": config.EXPECTED_ROWS,
    }

    # The RY21 release (ends 2020) supplies the unbiased 2020 baseline used
    # by sql/09_survivor.sql.
    p_digest, p_rows = _ensure(config.PRIOR_CSV, config.PRIOR_CSV_URL,
                             config.PRIOR_EXPECTED_ROWS, config.PRIOR_SHA256,
                             "prior release")
    manifest["prior_release"] = {
        "url": config.PRIOR_CSV_URL,
        "release": config.PRIOR_RELEASE,
        "sha256": p_digest,
        "rows": p_rows,
        "expected_sha256": config.PRIOR_SHA256,
        "expected_rows": config.PRIOR_EXPECTED_ROWS,
    }
    with open(config.RAW / "MANIFEST.json", "w", newline="\n") as f:
        f.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return config.RAW_CSV


def main():
    ensure_data()


if __name__ == "__main__":
    main()
