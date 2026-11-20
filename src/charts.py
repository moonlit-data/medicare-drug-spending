"""Static charts for the README: light and dark PNG at 2x DPI.

Titles state the finding, not the topic. Money in $B on the axes.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from . import config

def out_dir():
    return config.RESULTS / "charts"


def _style(mode):
    s = config.SURFACES[mode]
    plt.rcParams.update({
        "figure.facecolor": s["bg"], "axes.facecolor": s["bg"],
        "axes.edgecolor": s["grid"], "axes.labelcolor": s["text"],
        "xtick.color": s["secondary"], "ytick.color": s["secondary"],
        "text.color": s["text"], "font.family": "DejaVu Sans", "font.size": 10,
        "axes.grid": True, "grid.color": s["grid"], "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.axisbelow": True,
    })
    return s


def _save(fig, name, mode):
    fig.savefig(out_dir() / f"{name}_{mode}.png", dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor(), metadata={"Software": None})
    plt.close(fig)


def _both(name, fn):
    for mode in ("light", "dark"):
        s = _style(mode)
        fig = fn(s, config.CAT_DARK if mode == "dark" else config.CAT_LIGHT)
        _save(fig, name, mode)


def _b(x):
    return x / 1e9


def _dmoney(v):
    """Signed money label with a real minus sign, no '+' on negatives."""
    return f"\u2212${abs(v) / 1e9:.1f}B" if v < 0 else f"+${v / 1e9:.1f}B"


def bridge_chart(kpis):
    dec = kpis["decomposition"]
    # correction steps first (bridging full RY21 2020 -> RY26 survivor 2020),
    # then the per-drug decomposition steps
    steps = []
    for key, lab in [("absent_from_ry26", "No longer\nlisted"),
                     ("restatement_2020", "2020\nrestatement"),
                     ("ry26_only_2020", "In RY26,\nnot RY21")]:
        if abs(dec.get(key, 0.0)) > 1:
            steps.append((lab, dec[key]))
    n_corr = len(steps)
    steps += [("New\ndrugs", dec["new_drugs"]),
              ("Patients\nper drug", dec["patients_per_drug"]),
              ("Claims\nper patient", dec["utilization"])]
    if abs(dec.get("claims_fallback", 0.0)) > 1:
        steps.append(("Claims\n(benes n/a)", dec["claims_fallback"]))
    steps.append(("Spend\nper unit", dec["price"]))
    if abs(dec["exited_drugs"]) > 1:
        steps.insert(n_corr + 1, ("Exited", dec["exited_drugs"]))
    if abs(dec["unattributed"]) > 1:
        steps.append(("Unattributed", dec["unattributed"]))

    s0, s_surv, s1 = (kpis["spend_2020"], kpis.get("spend_2020_survivors", 0),
                      kpis["spend_2024"])
    # a mid-total bar for the survivor baseline between correction and
    # decomposition steps (only when there are correction steps)
    mid_total_at = n_corr + 1 if n_corr else None

    def draw(s, cat):
        fig, ax = plt.subplots(figsize=(9.6, 4.0))
        n_bars = len(steps) + (2 if mid_total_at is None else 3)
        x = list(range(n_bars))
        pos_of_step = {}
        xi = 1
        for si in range(len(steps)):
            pos_of_step[si] = xi
            xi += 1
            if mid_total_at is not None and si + 1 == n_corr:
                xi += 1   # mid-total bar slot
        ax.bar(x[0], _b(s0), width=0.78, color=s["secondary"])
        bottom = s0
        for si, (lab, v) in enumerate(steps):
            i = pos_of_step[si]
            col = cat[0] if v >= 0 else cat[7]
            ax.bar(i, _b(v), bottom=_b(bottom), width=0.78, color=col)
            va = "bottom" if v >= 0 else "top"
            txt = f"+{_b(v):.1f}" if v >= 0 else f"\u2212{_b(abs(v)):.1f}"
            ax.text(i, _b(bottom + v), txt,
                    ha="center", va=va, fontsize=9, color=s["text"])
            bottom += v
            if mid_total_at is not None and si + 1 == n_corr:
                ax.bar(i + 1, _b(s_surv), width=0.78, color=s["secondary"])
                ax.text(i + 1, _b(s_surv), f"{_b(s_surv):.1f}", ha="center",
                        va="bottom", fontsize=9, color=s["text"])
        ax.bar(x[-1], _b(s1), width=0.78, color=s["secondary"])
        ax.text(x[0], _b(s0), f"{_b(s0):.1f}", ha="center", va="bottom", fontsize=9, color=s["text"])
        ax.text(x[-1], _b(s1), f"{_b(s1):.1f}", ha="center", va="bottom", fontsize=9, color=s["text"])
        # connectors at the running level between consecutive bars
        seq = [(x[0], None)] + [(pos_of_step[si], si) for si in range(len(steps))]
        if mid_total_at is not None:
            seq.append((pos_of_step[n_corr - 1] + 1, "mid"))
        seq.append((x[-1], None))
        seq.sort(key=lambda t: t[0])
        run = s0
        for k in range(len(seq) - 1):
            ax.plot([seq[k][0] + 0.39, seq[k + 1][0] - 0.39], [_b(run)] * 2,
                    color=s["grid"], lw=1, zorder=0)
            nxt = seq[k + 1][1]
            if nxt == "mid":
                run = s_surv
            elif nxt is not None:
                run += steps[nxt][1]
        ax.set_xticks(x)
        labels = ["2020\nall drugs"] + [s_ for s_, _ in steps]
        if mid_total_at is not None:
            labels.insert(1 + n_corr, "2020\nsurvivors")
        ax.set_xticklabels(labels + ["2024\ntotal"], fontsize=8)
        ax.set_ylabel("Gross spending ($B)")
        # title states the actual finding: the largest positive driver
        biggest = max(steps, key=lambda t: t[1])
        ax.set_title(f"{biggest[0].replace(chr(10), ' ')} ({_dmoney(biggest[1])}) "
                     f"drove most of the +${_b(kpis['delta_spending']):.1f}B increase",
                     fontsize=11, loc="left", pad=10, parse_math=False)
        ax.grid(axis="x", visible=False)
        return fig

    _both("decomposition_bridge", draw)


def group_chart(grp):
    piv = grp.pivot(index="group_name", columns="yr", values="spend")
    piv["delta"] = piv[config.END_YEAR] - piv[config.BASE_YEAR]
    # fold groups under $0.1B of change into 'Other' so no '-0.0' labels show
    tiny = piv.index[(piv["delta"].abs() < 0.1e9) & (piv.index != "Other")]
    if len(tiny):
        piv.loc["Other", "delta"] += piv.loc[tiny, "delta"].sum()
        piv = piv.drop(index=tiny)
    piv = piv.sort_values("delta", ascending=False)
    # 'Other' is an unnamed bucket, not a therapeutic group: always last
    if "Other" in piv.index:
        piv = pd.concat([piv.drop(index="Other"), piv.loc[["Other"]]])

    def draw(s, cat):
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        names = list(piv.index)
        vals = [_b(v) for v in piv["delta"]]
        # one series -> one colour; 'Other' drawn in muted grey
        cols = [s["secondary"] if n == "Other" else cat[0] for n in names]
        y = range(len(names))
        ax.barh(y, vals, height=0.72, color=cols)
        ax.set_yticks(y, names)
        ax.invert_yaxis()
        for i, v in enumerate(vals):
            txt = f"\u2212{abs(v):.1f}" if v < 0 else f"+{v:.1f}"
            # negative labels sit outside the bar's left end, clear of the
            # category labels thanks to the widened x-axis
            ax.text(v + 0.3 if v >= 0 else v - 0.3, i, txt,
                    va="center", ha="left" if v >= 0 else "right", fontsize=9,
                    color=s["text"])
        ax.axvline(0, color=s["grid"], lw=1)
        named = [n for n in names if n != "Other"]
        top_named = named[0]
        top_val = vals[names.index(top_named)]
        ax.set_title(f"{top_named} added ${top_val:.1f}B - the largest group "
                     f"contribution\nto the 2020-2024 change for drugs listed "
                     f"in 2024 (+${sum(vals):.1f}B total)",
                     fontsize=11, loc="left", pad=10, parse_math=False)
        ax.set_xlabel("Change in gross spending, 2020 to 2024, drugs listed in "
                      "2024 ($B)")
        ax.grid(axis="y", visible=False)
        lo, hi = min(vals), max(vals)
        ax.set_xlim(lo * 1.35 if lo < 0 else 0, hi * 1.25)
        return fig

    _both("group_growth", draw)


def negotiation_chart(kpis, neg_by_drug):
    s24 = kpis["spend_2024"]
    s26 = kpis["neg_2026_spend_2024"]
    s27 = kpis["neg_2027_spend_2024"]
    rest = s24 - s26 - s27
    share = 100.0 * (s26 + s27) / s24

    def draw(s, cat):
        fig, ax = plt.subplots(figsize=(7.2, 2.6))
        segs = [("Selected for 2026", s26, cat[0]),
                ("Selected for 2027", s27, cat[1]),
                ("All other drugs", rest, s["grid"])]
        left = 0.0
        for lab, v, c in segs:
            ax.barh([0], [v / 1e9], left=left / 1e9, height=0.5, color=c, label=lab)
            left += v
        for lab, v, c in segs:
            pass
        ax.set_xlim(0, s24 / 1e9)
        ax.set_yticks([])
        ax.set_xlabel("2024 gross spending ($B)")
        ax.set_title(f"Negotiation-selected drugs were {share:.0f}% of 2024 spending",
                     fontsize=11, loc="left", pad=10)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.42), ncol=3, frameon=False,
                  fontsize=9)
        ax.grid(axis="y", visible=False)
        return fig

    _both("negotiation_share", draw)


def concentration_chart(conc, pct_change):
    def draw(s, cat):
        fig, ax = plt.subplots(figsize=(7.2, 4.0))
        ax.plot(conc["yr"], conc["top10_share_pct"], marker="o", ms=4, lw=2,
                color=cat[0], label="Top 10 drugs")
        ax.plot(conc["yr"], conc["top50_share_pct"], marker="o", ms=4, lw=2,
                color=cat[1], label="Top 50 drugs")
        last = conc.iloc[-1]
        ax.annotate(f"{last['top10_share_pct']:.0f}%",
                    (last["yr"], last["top10_share_pct"]), textcoords="offset points",
                    xytext=(6, 4), fontsize=9, color=cat[0])
        ax.annotate(f"{last['top50_share_pct']:.0f}%",
                    (last["yr"], last["top50_share_pct"]), textcoords="offset points",
                    xytext=(6, -12), fontsize=9, color=cat[1])
        ax.set_xticks(conc["yr"])
        ax.set_ylabel("Share of gross spending (%)")
        first = conc.iloc[0]
        a, b = first["top10_share_pct"], last["top10_share_pct"]
        if abs(b - a) < 1:
            share_txt = f"held near {a:.0f}%"
        else:
            share_txt = f"{'rose' if b > a else 'fell'} from {a:.1f}% to {b:.1f}%"
        ax.set_title(f"The top 10 drugs' share {share_txt} while spending grew {pct_change:.0f}%",
                     fontsize=11, loc="left", pad=10)
        ax.legend(frameon=False, fontsize=9, loc="center left")
        ax.grid(axis="x", visible=False)
        return fig

    _both("concentration", draw)


def run():
    out_dir().mkdir(parents=True, exist_ok=True)
    kpis = json.loads((config.RESULTS / "kpis.json").read_text())
    grp = pd.read_csv(config.RESULTS / "group_growth.csv")
    neg = pd.read_csv(config.RESULTS / "negotiation_by_drug.csv")
    conc = pd.read_csv(config.RESULTS / "concentration.csv")

    bridge_chart(kpis)
    group_chart(grp)
    negotiation_chart(kpis, neg)
    concentration_chart(conc, kpis["pct_change"])
    print("wrote charts to results/charts/")


if __name__ == "__main__":
    run()
