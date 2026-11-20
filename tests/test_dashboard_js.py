"""The generated docs/index.html must contain valid JavaScript and JSON.

Regression: a Python ``\\n`` inside a non-raw PAGE string produced a literal
newline inside a JS string literal ('2020<newline>(all drugs)') — a SyntaxError
that left every chart empty in a real browser.
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

DASH = pathlib.Path(__file__).resolve().parents[1] / "docs" / "index.html"

pytestmark = pytest.mark.skipif(
    not DASH.exists(), reason="run `python -m src.build_dashboard` first")


@pytest.fixture(scope="module")
def inline_scripts():
    src = DASH.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", src, re.S)
    assert scripts, "no inline <script> block found in docs/index.html"
    return scripts


def test_data_block_parses(inline_scripts):
    m = re.search(r"const DATA = (\{.*?\});\s*\n", inline_scripts[0], re.S)
    assert m, "const DATA = {...}; block not found"
    data = json.loads(m.group(1))
    for key in ("kpis", "steps", "groups", "groupSpend", "drugs",
                "concentration", "negSelected"):
        assert key in data
    assert data["kpis"]["spend_2024"] > data["kpis"]["spend_2020"]
    assert len(data["steps"]) >= 5


def test_inline_script_is_valid_javascript(inline_scripts):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; install Node.js to run `node --check`")
    js = "\n".join(inline_scripts)
    probe = pathlib.Path(__file__).parent / "_dashboard_probe.js"
    try:
        probe.write_text(js, encoding="utf-8")
        res = subprocess.run([node, "--check", str(probe)],
                             capture_output=True, text=True, timeout=60)
        assert res.returncode == 0, f"node --check failed:\n{res.stderr}"
    finally:
        probe.unlink(missing_ok=True)


def test_no_literal_newline_inside_js_strings(inline_scripts):
    """Pure-python guard for the same bug where node is unavailable: no raw
    newline may appear inside a '...' or \"...\" JS string literal."""
    js = "\n".join(inline_scripts)
    in_str = None
    esc = False
    for i, ch in enumerate(js):
        if esc:
            esc = False
            continue
        if in_str:
            if ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            elif ch == "\n":
                line = js.count("\n", 0, i) + 1
                pytest.fail(f"literal newline inside JS string at script line {line}")
        elif ch in "'\"`":
            in_str = ch


def test_no_si_tick_format_on_money_axes(inline_scripts):
    """Money axes must render '$300B', never Plotly's SI suffix '$300G'."""
    js = "\n".join(inline_scripts)
    bad = re.findall(r"tickformat\s*:\s*['\"][^'\"]*~s", js)
    assert not bad, f"SI tick formats on money axes: {bad}"


def test_negotiation_axis_is_categorical(inline_scripts):
    """'2024' as a bare x value parses as a number -> axis ticks like
    '2,023.6'; the negotiation axis must be explicitly categorical."""
    js = "\n".join(inline_scripts)
    m = re.search(r"Plotly\.react\('c-neg'.*?,\s*CFG\)", js, re.S)
    assert m, "c-neg Plotly.react call not found"
    assert re.search(r"type:\s*'category'", m.group(0)), \
        "negotiation x-axis is not declared categorical"


def test_group_stacks_sum_to_yearly_totals(inline_scripts):
    """Every year's plotted stack (top-6 named groups + folded 'Other') must
    equal the year's gross total from results/yearly_totals.csv to the cent."""
    m = re.search(r"const DATA = (\{.*?\});\s*\n", inline_scripts[0], re.S)
    data = json.loads(m.group(1))
    spend = data["groupSpend"]
    named = [g for g in data["groups"] if g != "Other"]
    keep = sorted(named, key=lambda g: sum(spend[g]), reverse=True)[:6]
    collapsed = [g for g in data["groups"] if g not in keep]
    for j, yr in enumerate(data["years"]):
        plotted = sum(spend[g][j] for g in keep) + \
                  sum(spend[g][j] for g in collapsed)
        expected = data["yearlyTotals"][str(yr)]
        assert abs(plotted - expected) < 0.01, \
            f"{yr}: stack sums to {plotted:.2f}, yearly total {expected:.2f}"


def test_legends_sit_outside_plot(inline_scripts):
    """Every showlegend chart must anchor its legend below the plot area
    (negative y) with a transparent background — a legend at y>1 in the
    top margin can cover the tallest bars at card widths."""
    blocks = re.findall(
        r"legend:\s*\{(.*?)\}", inline_scripts[0], re.S)
    assert len(blocks) >= 2, "expected legend blocks for group + concentration"
    for b in blocks:
        y = re.search(r"y:\s*(-?[\d.]+)", b)
        assert y and float(y.group(1)) < 0, \
            f"legend must be anchored below the plot: {b.strip()[:120]}"
        assert "rgba(0,0,0,0)" in b, "legend background must be transparent"


def test_mobile_layout_guards():
    """Phone-width guards: grid children must be allowed to shrink
    (min-width:0), cards must not exceed viewport, and Plotly must be
    responsive — otherwise cards overflow the viewport on phones."""
    dash_html = DASH.read_text(encoding="utf-8")
    assert re.search(r"\.grid\s*>\s*\*\s*\{[^}]*min-width:\s*0", dash_html), \
        "grid children lack min-width:0"
    assert re.search(r"\.card\s*\{[^}]*min-width:\s*0", dash_html), \
        ".card lacks min-width:0"
    assert "responsive: true" in dash_html, "Plotly config lost responsive:true"
