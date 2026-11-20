import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
TINY_RAW = FIXTURES / "tiny_partd.csv"
TINY_GROUPS = FIXTURES / "tiny_groups.csv"
TINY_NEG = FIXTURES / "tiny_negotiation.csv"
TINY_PRIOR = FIXTURES / "tiny_prior_partd.csv"
