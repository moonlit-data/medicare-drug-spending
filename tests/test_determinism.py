"""Determinism: running the pipeline twice must give byte-identical results/."""
import hashlib
import pathlib

import pytest

from src import config, run_all

pytestmark = pytest.mark.skipif(
    not config.RAW_CSV.exists(), reason="raw data not downloaded")


def _snapshot():
    files = sorted(config.RESULTS.glob("*.csv")) + sorted(config.RESULTS.glob("*.json"))
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def test_results_are_deterministic():
    run_all.run()
    first = _snapshot()
    run_all.run()
    second = _snapshot()
    assert first == second
    assert len(first) >= 8
