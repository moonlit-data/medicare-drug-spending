"""Build the interactive dashboard (docs/index.html) from results/*.csv.

One self-contained HTML file (Plotly from a pinned CDN); GitHub Pages can
serve it from docs/. Visual system follows the project style reference:
CSS variables, light/dark via prefers-color-scheme, hover tooltips,
table-view toggles, phone-friendly grid.
"""
import csv
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = ROOT / "docs" / "index.html"

# Test-only flag: point at a local plotly.min.js (e.g. the pip package's
# bundle) to render the page where the CDN is unreachable.
PLOTLY_SRC = os.environ.get(
    "MEDICARE_PLOTLY_SRC", "https://cdn.plot.ly/plotly-2.35.2.min.js")

YEARS = [2020, 2021, 2022, 2023, 2024]
# (key, table label, short two-line waterfall label)
BUCKETS = [
    ("absent_from_ry26", "No longer listed", "No longer<br>listed"),
    ("restatement_2020", "2020 restatement", "2020<br>restatement"),
    ("ry26_only_2020", "In RY26, not RY21", "Only in<br>RY26"),
    ("new_drugs", "New drugs", "New<br>drugs"),
    ("exited_drugs", "Drugs that left", "Drugs<br>that left"),
    ("patients_per_drug", "More patients per drug", "More patients<br>per drug"),
    ("utilization", "Claims / units per patient", "Claims per<br>patient"),
    ("claims_fallback", "Claims (no patient count)", "Claims<br>fallback"),
    ("price", "Gross spend per dosage unit", "Price<br>per unit"),
    ("unattributed", "Unattributed", "Un-<br>attributed"),
]
CORR_KEYS = {"absent_from_ry26", "restatement_2020", "ry26_only_2020"}


def read(name):
    with open(RESULTS / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(v):
    return float(v) if v not in ("", None) else None


def build_data():
    kpis = json.loads((RESULTS / "kpis.json").read_text())
    dec = read("decomposition_summary")
    grp = read("group_growth")
    top = read("top_drugs")
    conc = read("concentration")
    neg_sel = read("negotiation_by_drug")
    neg_sum = read("negotiation_summary")

    # decomposition waterfall steps
    d = {r["component"]: float(r["delta_spending"]) for r in dec}
    steps = [{"label": lab, "short": short, "value": d.get(k, 0.0),
              "corr": 1 if k in CORR_KEYS else 0} for k, lab, short in BUCKETS
             if abs(d.get(k, 0.0)) > 1]

    # group x year matrix
    groups = sorted({r["group_name"] for r in grp})
    gmat = {g: [0.0] * len(YEARS) for g in groups}
    for r in grp:
        gmat[r["group_name"]][YEARS.index(int(r["yr"]))] = num(r["spend"])

    drugs = [{
        "b": r["brnd_name"], "g": r["gnrc_name"], "grp": r["group_name"],
        "s20": num(r["spend_2020"]), "s24": num(r["spend_2024"]),
        "ch": num(r["spend_change"]),
    } for r in top]

    return {
        "kpis": kpis, "steps": steps, "years": YEARS,
        "groups": groups, "groupSpend": gmat,
        "drugs": drugs,
        "concentration": [{"yr": int(r["yr"]), "t10": num(r["top10_share_pct"]),
                           "t50": num(r["top50_share_pct"])} for r in conc],
        "negSelected": [{"cycle": int(r["cycle"]), "drug": r["selected_drug"],
                         "s24": num(r["spend_2024"]), "s20": num(r["spend_2020"]),
                         "n": int(r["n_matched_brands"])} for r in neg_sel],
        "negSummary": [{"cycle": int(r["cycle"]), "n": int(r["n_selected_drugs"]),
                        "s24": num(r["spend_2024"]),
                        "share": num(r["share_of_2024_pct"])} for r in neg_sum],
        "yearlyTotals": {str(int(r["yr"])): num(r["gross_spending"])
                         for r in read("yearly_totals")},
    }


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Medicare Part D drug spending 2020-2024</title>
<script src="__PLOTLY_SRC__" charset="utf-8"></script>
<style>
.viz-root {
  color-scheme: light;
  --page: #f9f9f7; --surface-1: #fcfcfb; --text-primary: #0b0b0b; --text-secondary: #52514e;
  --muted: #898781; --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --series-4: #eda100;
  --series-5: #e87ba4; --series-6: #008300; --series-7: #6250d6; --series-8: #e34948;
  --up: #2a78d6; --down: #e34948; --total: #52514e;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .viz-root {
    color-scheme: dark;
    --page: #0d0d0d; --surface-1: #1a1a19; --text-primary: #f0efec; --text-secondary: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
    --series-5: #d55181; --series-6: #008300; --series-7: #9085e9; --series-8: #e66767;
    --up: #3987e5; --down: #e66767; --total: #c3c2b7;
  }
}
:root[data-theme="dark"] .viz-root {
    color-scheme: dark;
    --page: #0d0d0d; --surface-1: #1a1a19; --text-primary: #f0efec; --text-secondary: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
    --series-5: #d55181; --series-6: #008300; --series-7: #9085e9; --series-8: #e66767;
    --up: #3987e5; --down: #e66767; --total: #c3c2b7;
}
body { margin: 0; }
.viz-root { background: var(--page); color: var(--text-primary); min-height: 100vh;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 1180px; margin: 0 auto; padding: 28px 24px 48px; }
h1 { font-size: 22px; font-weight: 600; margin: 0 0 4px; }
.sub { color: var(--text-secondary); font-size: 14px; margin: 0 0 18px; }
.note { font-size: 13px; color: var(--text-secondary); border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 12px; margin-bottom: 18px; background: var(--surface-1); }
.filters { display: flex; gap: 12px; align-items: center; margin-bottom: 18px; font-size: 14px; flex-wrap: wrap; }
.filters select { font: inherit; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface-1); color: var(--text-primary); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 18px; }
.tile { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.tile .label { font-size: 13px; color: var(--text-secondary); }
.tile .value { font-size: 26px; font-weight: 600; margin: 4px 0 2px; }
.tile .delta { font-size: 13px; color: var(--text-secondary); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(520px, 1fr)); gap: 12px; }
.grid > * { min-width: 0; }
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px 6px;
  min-width: 0; max-width: 100%; }
.card h2 { font-size: 15px; font-weight: 600; margin: 0 0 2px; }
.card p { font-size: 12.5px; color: var(--text-secondary); margin: 0 0 4px; }
.chart { height: 320px; min-width: 0; max-width: 100%; }
#c-group { height: 380px; }
.wide { grid-column: 1 / -1; }
details { margin-top: 18px; background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 10px 16px; }
summary { cursor: pointer; font-size: 14px; }
table { border-collapse: collapse; font-size: 12.5px; margin-top: 10px; width: 100%;
  font-variant-numeric: tabular-nums; }
th, td { padding: 4px 8px; text-align: right; border-bottom: 1px solid var(--grid); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--text-secondary); font-weight: 600; cursor: pointer; user-select: none; white-space: nowrap; }
th:hover { color: var(--text-primary); }
footer { margin-top: 18px; font-size: 12.5px; color: var(--text-secondary); }
a { color: var(--series-1); }
@media (max-width: 560px) { .grid { grid-template-columns: 1fr; } .chart { height: 260px; }
  #c-group { height: 430px; } .card { padding: 12px 12px 4px; } }
</style>
</head>
<body>
<div class="viz-root">
<div class="wrap">
  <h1>Medicare Part D drug spending, 2020-2024</h1>
  <p class="sub">What drove gross drug spending up - new drugs, more patients per drug, more fills per patient, or price?</p>
  <div class="note">Gross spending (before manufacturer rebates), per CMS
    "Medicare Part D Spending by Drug", release of 2026-06-25.
    <a href="https://github.com/moonlit-data/medicare-drug-spending">Method, data and checks</a>.</div>
  <div class="tiles" id="tiles"></div>
  <div class="grid">
    <div class="card"><h2>What drove the $__DELTA_B__B increase</h2><p>Per-drug decomposition 2020 &rarr; 2024, summed over all drugs (log-mean Divisia)</p><div class="chart" id="c-bridge"></div></div>
    <div class="card"><h2>Growth by therapeutic group</h2><p>Gross spending by year ($B); hover for values</p><div class="chart" id="c-group"></div></div>
    <div class="card"><h2>Concentration</h2><p>Share of each year's spending held by the top 10 and top 50 drugs</p><div class="chart" id="c-conc"></div></div>
    <div class="card"><h2>Negotiation-selected drugs</h2><p>Share of 2024 spending in the drugs CMS selected for price negotiation (10 for 2026, 15 for 2027)</p><div class="chart" id="c-neg"></div></div>
    <div class="card wide"><h2>Top drugs</h2><p>Top 25 drugs by spending change, 2020 &rarr; 2024; filter by group or rank year, click a column to sort</p>
      <div class="filters"><label for="grp">Group</label><select id="grp"></select>
        <label for="yrsel">Rank by change</label><select id="yrsel"><option value="ch">2020 &rarr; 2024</option></select>
      </div>
      <div id="drugtable" style="max-height:420px; overflow:auto"></div>
    </div>
    <div class="card wide"><h2>Selected drugs detail</h2><p>Each CMS selected drug and its spending in the dataset</p>
      <div id="negtable" style="max-height:420px; overflow:auto"></div>
    </div>
  </div>
  <details><summary>Table view: decomposition and group totals</summary><div id="table"></div></details>
  <footer>Built from the CSV files in <code>results/</code> by <code>src/build_dashboard.py</code>.</footer>
</div>
</div>
<script>
const DATA = __DATA__;
const css = n => getComputedStyle(document.querySelector('.viz-root')).getPropertyValue(n).trim();
const fmtB = v => v == null ? '-' : (v < 0 ? '-$' : '$') + (Math.abs(v) / 1e9).toFixed(1) + 'B';
const fmtB2 = v => v == null ? '-' : (v < 0 ? '-$' : '$') + (Math.abs(v) / 1e9).toFixed(2) + 'B';
const fmtPct = v => v == null ? '-' : v.toFixed(1) + '%';
const fmtSign = v => (v > 0 ? '+' : v < 0 ? '\u2212' : '') + '$' + (Math.abs(v) / 1e9).toFixed(1) + 'B';

function baseLayout(extra) {
  return Object.assign({
    paper_bgcolor: css('--surface-1'), plot_bgcolor: css('--surface-1'),
    font: { family: 'system-ui, -apple-system, "Segoe UI", sans-serif', size: 12, color: css('--text-secondary') },
    margin: { l: 56, r: 12, t: 8, b: 36 }, showlegend: false,
    hoverlabel: { bgcolor: css('--surface-1'), bordercolor: css('--axis'), font: { color: css('--text-primary') } },
    xaxis: { gridcolor: css('--grid'), linecolor: css('--axis'), tickcolor: css('--axis'), showgrid: false, ticks: '' },
    yaxis: { gridcolor: css('--grid'), gridwidth: 1, zerolinecolor: css('--axis'), linecolor: css('--axis'), ticks: '' },
  }, extra || {});
}
const CFG = { displayModeBar: false, responsive: true };
const PALETTE = ['--series-1','--series-2','--series-3','--series-4','--series-5','--series-6','--series-7','--series-8'];

function tile(labelText, value, deltaText) {
  const d = document.createElement('div'); d.className = 'tile';
  const l = document.createElement('div'); l.className = 'label'; l.textContent = labelText;
  const v = document.createElement('div'); v.className = 'value'; v.textContent = value;
  const de = document.createElement('div'); de.className = 'delta'; de.textContent = deltaText || '';
  d.append(l, v, de); return d;
}

function render() {
  const K = DATA.kpis;

  // KPI tiles
  const tiles = document.getElementById('tiles'); tiles.replaceChildren();
  tiles.append(
    tile('Gross spending, 2020', fmtB(K.spend_2020),
         'full market incl. drugs later unlisted'),
    tile('Gross spending, 2024', fmtB(K.spend_2024), K.n_drugs_2024.toLocaleString() + ' drugs in data'),
    tile('Change 2020-2024', fmtSign(K.delta_spending), '+' + K.pct_change.toFixed(0) + '%'),
    tile('Explained by top 10 growth drugs', fmtPct(K.top10_growth_drugs_share_of_increase_pct),
         'of the total increase'));

  // Waterfall, horizontal: labels sit on the y axis at full width, so they
  // cannot collide at any viewport size (values in $B so ticks read '$300B')
  const steps = DATA.steps;
  const cats = ['2020 all drugs', ...steps.map(s => s.label), '2024'];
  const measure = ['absolute', ...steps.map(() => 'relative'), 'total'];
  const vals = [K.spend_2020 / 1e9, ...steps.map(s => s.value / 1e9), K.spend_2024 / 1e9];
  // insert a survivor-total subtotal bar after the last correction step
  const nCorr = steps.filter(s => s.corr).length;
  if (nCorr) {
    cats.splice(1 + nCorr, 0, '2020 survivors');
    measure.splice(1 + nCorr, 0, 'absolute');
    vals.splice(1 + nCorr, 0, K.spend_2020_survivors / 1e9);
  }
  Plotly.react('c-bridge', [{
    type: 'waterfall', orientation: 'h', y: cats, x: vals, measure,
    connector: { line: { color: css('--axis'), width: 1 } },
    increasing: { marker: { color: css('--up') } },
    decreasing: { marker: { color: css('--down') } },
    totals: { marker: { color: css('--total') } },
    hovertemplate: '<b>%{x:$,.1f}B</b><extra></extra>',
  }], baseLayout({
    xaxis: Object.assign(baseLayout().xaxis,
      { tickprefix: '$', ticksuffix: 'B', showgrid: true, gridcolor: css('--grid') }),
    yaxis: Object.assign(baseLayout().yaxis,
      { autorange: 'reversed', automargin: true, tickfont: { size: 11 }, showgrid: false }),
    margin: { l: 10, r: 16, t: 8, b: 36 } }), CFG);

  // Group stacked bars: categorical year axis; up to 6 named groups in
  // categorical colours; every other group (incl. the catch-all 'Other')
  // merges into one grey 'Other' on top; each year stacks to the yearly total
  const yearLabels = DATA.years.map(String);
  const gnames = DATA.groups.filter(g => g !== 'Other');
  const tot = g => DATA.groupSpend[g].reduce((a, b) => a + b, 0);
  gnames.sort((a, b) => tot(b) - tot(a));
  const keep = gnames.slice(0, 6);
  const traces = keep.map((g, i) => ({
    x: yearLabels, y: DATA.groupSpend[g].map(v => v / 1e9), name: g, type: 'bar',
    marker: { color: css(PALETTE[i]) },
    hovertemplate: '<b>%{y:$,.1f}B</b> ' + g + '<extra></extra>',
  }));
  const collapsed = DATA.groups.filter(g => !keep.includes(g));
  const otherY = yearLabels.map((_, j) =>
    collapsed.reduce((a, g) => a + DATA.groupSpend[g][j] / 1e9, 0));
  traces.push({ x: yearLabels, y: otherY, name: 'Other', type: 'bar',
    marker: { color: css('--axis') }, hovertemplate: '<b>%{y:$,.1f}B</b> Other<extra></extra>' });
  Plotly.react('c-group', traces, baseLayout({ barmode: 'stack', bargap: 0.35,
    hovermode: 'x unified', showlegend: true,
    margin: { l: 56, r: 12, t: 8, b: 150 },
    xaxis: Object.assign(baseLayout().xaxis, { type: 'category' }),
    legend: { orientation: 'h', xanchor: 'left', x: 0, yanchor: 'top', y: -0.16,
      bgcolor: 'rgba(0,0,0,0)', font: { color: css('--text-secondary') } },
    yaxis: Object.assign(baseLayout().yaxis, { tickprefix: '$', ticksuffix: 'B' }) }), CFG);

  // Concentration lines
  const cy = DATA.concentration.map(r => r.yr);
  Plotly.react('c-conc', [
    { x: cy, y: DATA.concentration.map(r => r.t10), name: 'Top 10', type: 'scatter',
      mode: 'lines+markers', line: { color: css('--series-1'), width: 2 },
      hovertemplate: '<b>%{y:.1f}%</b> top 10<extra></extra>' },
    { x: cy, y: DATA.concentration.map(r => r.t50), name: 'Top 50', type: 'scatter',
      mode: 'lines+markers', line: { color: css('--series-2'), width: 2 },
      hovertemplate: '<b>%{y:.1f}%</b> top 50<extra></extra>' }],
    baseLayout({ showlegend: true, hovermode: 'x unified',
      margin: { l: 56, r: 12, t: 8, b: 72 },
      legend: { orientation: 'h', xanchor: 'left', x: 0, yanchor: 'top', y: -0.16,
        bgcolor: 'rgba(0,0,0,0)', font: { color: css('--text-secondary') } },
      yaxis: Object.assign(baseLayout().yaxis, { ticksuffix: '%', rangemode: 'tozero' }) }), CFG);

  // Negotiation stacked bar: one categorical column per year, direct labels
  const s26 = K.neg_2026_spend_2024 / 1e9, s27 = K.neg_2027_spend_2024 / 1e9,
        rest = K.spend_2024 / 1e9 - s26 - s27;
  Plotly.react('c-neg', [
    { x: ['2024'], y: [s26], name: 'prices 2026', type: 'bar',
      marker: { color: css('--series-1') },
      text: ['prices 2026<br>' + fmtB(s26 * 1e9)], textposition: 'inside',
      insidetextfont: { color: '#ffffff' },
      hovertemplate: '<b>%{y:$,.1f}B</b> selected for 2026 prices<extra></extra>' },
    { x: ['2024'], y: [s27], name: 'prices 2027', type: 'bar',
      marker: { color: css('--series-2') },
      text: ['prices 2027<br>' + fmtB(s27 * 1e9)], textposition: 'inside',
      insidetextfont: { color: '#ffffff' },
      hovertemplate: '<b>%{y:$,.1f}B</b> selected for 2027 prices<extra></extra>' },
    { x: ['2024'], y: [rest], name: 'all other drugs', type: 'bar',
      marker: { color: css('--axis') },
      text: ['all other drugs<br>' + fmtB(rest * 1e9)], textposition: 'inside',
      insidetextfont: { color: css('--text-primary') },
      hovertemplate: '<b>%{y:$,.1f}B</b> not selected<extra></extra>' }],
    baseLayout({ barmode: 'stack',
      xaxis: Object.assign(baseLayout().xaxis, { type: 'category' }),
      yaxis: Object.assign(baseLayout().yaxis, { tickprefix: '$', ticksuffix: 'B' }) }), CFG);

  renderDrugTable();
  renderNegTable();
  renderTableView();

  // Test hook: open the page with #legendcheck to dump legend-vs-plot bounds
  // as JSON into <pre id="legend-check-report"> for headless checks.
  if (location.hash === '#legendcheck') {
    setTimeout(() => {
      const out = {};
      document.querySelectorAll('.chart').forEach(el => {
        const fl = el._fullLayout;
        if (!fl) return;
        const size = fl._size || {};
        const rec = { plotTop: size.t, plotBottom: (size.t || 0) + (size.h || 0),
          divHeight: el.clientHeight };
        const lg = el.querySelector('g.legend');
        if (lg) {
          const r = lg.getBoundingClientRect();
          const svg = el.querySelector('.main-svg').getBoundingClientRect();
          rec.legendTop = Math.round(r.top - svg.top);
          rec.legendBottom = Math.round(r.bottom - svg.top);
          rec.overlapsPlot =
            rec.legendTop < rec.plotBottom && rec.legendBottom > rec.plotTop;
          const clip = el.querySelector('.legend clipPath rect');
          rec.legendH = Math.round(r.bottom - r.top);
          rec.clipH = clip ? Math.round(clip.getBBox().height) : null;
          rec.scrollable = !!el.querySelector('.legend .scrollbar');
          rec.legendClipped =
            rec.legendBottom > rec.divHeight ||
            (rec.clipH != null && rec.clipH < rec.legendH - 1);
        } else rec.legend = false;
        out[el.id] = rec;
      });
      out.__doc = { scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
        overflows: document.documentElement.scrollWidth > window.innerWidth };
      const pre = document.createElement('pre');
      pre.id = 'legend-check-report';
      pre.textContent = JSON.stringify(out);
      document.body.appendChild(pre);
    }, 1500);
  }
}

// --- top drugs table -------------------------------------------------------
let sortKey = 'ch', sortDir = -1;
function renderDrugTable() {
  const gsel = document.getElementById('grp');
  if (gsel.options.length === 0) {
    ['All groups', ...DATA.groups].forEach(g => {
      const o = document.createElement('option'); o.textContent = g; gsel.appendChild(o); });
  }
  const grp = gsel.value === 'All groups' ? null : gsel.value;
  let rows = DATA.drugs.filter(d => !grp || d.grp === grp);
  rows = rows.slice().sort((a, b) => (b[sortKey] - a[sortKey]) * -sortDir || a.b.localeCompare(b.b));
  rows = rows.slice(0, 25);
  const cols = [['b', 'Brand'], ['grp', 'Group'], ['s20', '2020'], ['s24', '2024'], ['ch', 'Change']];
  const table = document.createElement('table');
  const head = table.insertRow();
  cols.forEach(([k, h]) => {
    const th = document.createElement('th'); th.textContent = h + (k === sortKey ? (sortDir < 0 ? ' ▼' : ' ▲') : '');
    if (k === 'b' || k === 'grp') th.style.textAlign = 'left';
    th.addEventListener('click', () => { sortDir = (sortKey === k) ? -sortDir : -1; sortKey = k; renderDrugTable(); });
    head.appendChild(th);
  });
  for (const d of rows) {
    const r = table.insertRow();
    const c1 = r.insertCell(); c1.textContent = d.b.replace(/\*+$/, '');
    const c2 = r.insertCell(); c2.textContent = d.grp; c2.style.textAlign = 'left';
    r.insertCell().textContent = fmtB2(d.s20);
    r.insertCell().textContent = fmtB2(d.s24);
    r.insertCell().textContent = fmtSign(d.ch);
  }
  const note = document.createElement('p');
  note.style.cssText = 'font-size:12px;color:var(--text-secondary);margin:6px 0 2px';
  note.textContent = 'CMS marks brands with multiple routes of administration with a trailing *; it is stripped here.';
  document.getElementById('drugtable').replaceChildren(table, note);
}
document.getElementById('grp').addEventListener('change', renderDrugTable);

// --- negotiation table -----------------------------------------------------
function renderNegTable() {
  const tot = DATA.kpis.spend_2024;
  const rows = DATA.negSelected.slice().sort((a, b) => a.cycle - b.cycle || (b.s24 || 0) - (a.s24 || 0));
  const table = document.createElement('table');
  const head = table.insertRow();
  ['Cycle', 'Selected drug', '2024 spend', 'Share of 2024'].forEach((h, i) => {
    const th = document.createElement('th'); th.textContent = h;
    if (i < 2) th.style.textAlign = 'left';
    head.appendChild(th); });
  for (const d of rows) {
    const r = table.insertRow();
    const c0 = r.insertCell(); c0.textContent = 'prices ' + d.cycle; c0.style.textAlign = 'left';
    const c = r.insertCell(); c.textContent = d.drug; c.style.textAlign = 'left';
    r.insertCell().textContent = fmtB2(d.s24);
    r.insertCell().textContent = d.s24 == null ? '-' : (100 * d.s24 / tot).toFixed(2) + '%';
  }
  document.getElementById('negtable').replaceChildren(table);
}

// --- table view ------------------------------------------------------------
function renderTableView() {
  const t = document.createElement('div');
  const h = document.createElement('p');
  h.textContent = 'Decomposition of the 2020 -> 2024 change ($)';
  h.style.fontWeight = '600';
  const table = document.createElement('table');
  const head = table.insertRow();
  ['Component', 'Change ($)'].forEach(x => { const th = document.createElement('th'); th.textContent = x; head.appendChild(th); });
  for (const s of DATA.steps) {
    const r = table.insertRow();
    const c = r.insertCell(); c.textContent = s.label; c.style.textAlign = 'left';
    r.insertCell().textContent = s.value.toLocaleString('en-US', { maximumFractionDigits: 0 });
  }
  const r = table.insertRow();
  const c = r.insertCell(); c.textContent = 'Total change'; c.style.textAlign = 'left';
  c.style.fontWeight = '600';
  const cv = r.insertCell(); cv.textContent = DATA.kpis.delta_spending.toLocaleString('en-US', { maximumFractionDigits: 0 });
  cv.style.fontWeight = '600';
  t.append(h, table);
  document.getElementById('table').replaceChildren(t);
}

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', render);
render();
</script>
</body>
</html>
"""


def main():
    OUT.parent.mkdir(exist_ok=True)
    data = build_data()
    html = (PAGE
            .replace("__PLOTLY_SRC__", PLOTLY_SRC)
            .replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__DELTA_B__", f"{data['kpis']['delta_spending'] / 1e9:.1f}"))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    with open(OUT.parent / ".nojekyll", "w", newline="\n") as f:
        f.write("")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
