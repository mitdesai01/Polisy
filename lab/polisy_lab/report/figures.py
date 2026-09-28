# -*- coding: utf-8 -*-
"""Figures for the report: static SVG drawn with matplotlib from the datasets in results.json.

Every figure function takes the results dict and returns (svg, caption, notes) or None when its data
are missing. Text stays text in the SVG (svg.fonttype = none) and takes the page's typeface.
"""
from __future__ import annotations

import io
import re

import numpy as np
import pandas as pd

INK, SLATE, RULE, GRID = "#1c2430", "#5a6472", "#c9cfd6", "#e7eaee"
DEM, REP, TEAL, OCHRE = "#2f5d9a", "#b3423a", "#1f6f78", "#9a6b12"
RAMP = ["#c3c9d1", "#9aa4b0", "#6f7b8a", "#434f60", "#1c2430"]     # fewer to more controls
WIDTH = 7.0                                                          # inches; every figure spans the text column


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "svg.fonttype": "none", "svg.hashsalt": "polisy", "font.family": "sans-serif",
        "font.sans-serif": ["Source Sans 3", "Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 9,
        "axes.edgecolor": SLATE, "axes.labelcolor": INK, "axes.linewidth": 0.6, "axes.spines.top": False,
        "axes.spines.right": False, "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.titlepad": 8, "xtick.color": SLATE, "ytick.color": SLATE, "xtick.labelcolor": INK, "ytick.labelcolor": INK,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 3, "ytick.major.size": 3,
        "legend.frameon": False, "legend.fontsize": 8.5, "lines.linewidth": 1.4, "figure.dpi": 100})
    return plt


def _svg(fig, label):
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.04, metadata={"Date": None, "Creator": None})
    import matplotlib.pyplot as plt
    plt.close(fig)
    s = buf.getvalue()
    s = s[s.index("<svg"):]
    s = re.sub(r"<metadata>.*?</metadata>", "", s, flags=re.S)
    s = re.sub(r'<svg([^>]*?) width="[^"]*" height="[^"]*"', r'<svg\1', s, count=1)
    s = s.replace("<svg", f'<svg role="img" aria-label="{label}" preserveAspectRatio="xMidYMid meet"', 1)
    s = re.sub(r"font-family: [^;\"]+", "font-family: var(--sans)", s)
    s = re.sub(r"\n\s*", "\n", s)
    return s


def _ds(res, did):
    d = (res.get("datasets") or {}).get(did)
    if not d or not d.get("rows"):
        return None
    return pd.DataFrame(d["rows"], columns=d["columns"])


def _stat(res, fid, key, default=None):
    for f in res.get("findings", []):
        if f["id"] == fid:
            return (f.get("stats") or {}).get(key, default)
    return default


# --------------------------------------------------------------------------- the seam (a diagram, not data)
def fig_seam(res):
    """Politics -> organisations -> innovation: what POLISY's first run linked, and the four seams at the level of the firm."""
    W, H = 760, 470
    L, M, R, bw, bh, top, gap = 24, 283, 542, 194, 66, 108, 32
    rows = lambda i: top + i * (bh + gap)  # noqa: E731
    cols = [("POLITICS", L, [("Workforce", "Partisanship at work (VRscores)"), ("Leaders", "CEO, top team, board (DIPI)"),
                             ("Environment", "State policy, local vote")]),
            ("ORGANISATIONS", M, [("Composition", "Lean, balance, sorting"), ("Incongruence", "Leaders against workforce"),
                                  ("Decisions", "What to adopt and invent")]),
            ("INNOVATION & TECHNOLOGY", R, [("Exposure", "Which tasks AI touches"), ("Adoption", "Who uses AI, how fast"),
                                            ("Direction", "What gets invented")])]
    sans, serif = "font-family: var(--sans)", "font-family: var(--serif)"
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="The research seam" xmlns="http://www.w3.org/2000/svg">',
         '<defs>'
         f'<marker id="sa" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{TEAL}"/></marker>'
         f'<marker id="sg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{SLATE}"/></marker>'
         '</defs>', f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    # the first run: links between the outer columns, at an aggregate level, bypassing organisations
    xa, xb, ya = L + bw / 2, R + bw / 2, 58
    o.append(f'<path d="M{xa},{top - 30} C{xa},{ya - 30} {xb},{ya - 30} {xb},{top - 30}" fill="none" stroke="{SLATE}" '
             f'stroke-width="1.1" stroke-dasharray="4 3" marker-end="url(#sg)"/>')
    o.append(f'<text x="{(xa + xb) / 2}" y="{ya - 28}" font-size="11.5" text-anchor="middle" fill="{SLATE}" style="{sans}">'
             f'first run: occupations, industries, counties and states</text>')
    for title, x, items in cols:
        o.append(f'<text x="{x}" y="{top - 12}" font-size="10.5" font-weight="700" letter-spacing="1.3" fill="{SLATE}" '
                 f'style="{sans}">{title}</text>')
        for i, (name, sub) in enumerate(items):
            y = rows(i)
            o.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="2" fill="#ffffff" stroke="{INK}" stroke-width="1"/>')
            o.append(f'<text x="{x + 12}" y="{y + 27}" font-size="15" font-weight="600" fill="{INK}" style="{serif}">{name}</text>')
            o.append(f'<text x="{x + 12}" y="{y + 48}" font-size="11.5" fill="{SLATE}" style="{sans}">{sub}</text>')

    def link(x1, y1, x2, y2, seam=None, thin=False):
        col, mk, w = (SLATE, "sg", 1) if thin else (TEAL, "sa", 2)
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{w}" marker-end="url(#{mk})"/>')
        if seam:
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            o.append(f'<circle cx="{cx}" cy="{cy}" r="10.5" fill="{TEAL}"/>')
            o.append(f'<text x="{cx}" y="{cy + 4}" font-size="11.5" font-weight="700" text-anchor="middle" fill="#ffffff" '
                     f'style="{sans}">{seam}</text>')
    mid = lambda i: rows(i) + bh / 2  # noqa: E731
    link(L + bw + 2, mid(0), M - 3, mid(0), "1")                        # workforce -> composition
    link(R - 2, mid(0), M + bw + 3, mid(0), "4")                        # technology reshapes composition
    link(L + bw + 2, mid(1), M - 3, mid(1), thin=True)                  # leaders -> incongruence
    link(L + bw + 2, mid(0) + 18, M - 3, mid(1) - 18, thin=True)        # workforce -> incongruence
    link(M + bw + 2, mid(1), R - 3, mid(1), "2")                        # who decides, who is exposed
    link(L + bw + 2, mid(1) + 18, M - 3, mid(2) - 18, thin=True)        # leaders -> decisions
    link(M + bw + 2, mid(2), R - 3, mid(2), "3")                        # direction of invention
    y = rows(2) + bh + 42
    o.append(f'<line x1="{L}" y1="{y}" x2="{L + 30}" y2="{y}" stroke="{TEAL}" stroke-width="2"/>'
             f'<text x="{L + 40}" y="{y + 4}" font-size="11.5" fill="{INK}" style="{sans}">the four research seams (Section 5), '
             f'all at the level of the firm</text>')
    o.append(f'<line x1="{L}" y1="{y + 22}" x2="{L + 30}" y2="{y + 22}" stroke="{SLATE}" stroke-width="1.1" stroke-dasharray="4 3"/>'
             f'<text x="{L + 40}" y="{y + 26}" font-size="11.5" fill="{INK}" style="{sans}">the first POLISY run, which linked politics '
             f'to AI directly and never reached the firm</text>')
    o.append("</svg>")
    caption = "The research seam: from politics, through organisations, to innovation and technology."
    notes = ("The dashed arc is what the first run linked: workforce partisanship and the political environment against AI exposure and "
             "migration, with occupations, industries, counties and states standing in for firms. The numbered arrows are the four seams of "
             "Section 5: (1) structural and elective partisanship; (2) who decides and who is exposed; (3) politics and the direction of AI "
             "invention; (4) technology reshaping the political composition of firms. Grey arrows are the links the seams build on.")
    return "\n".join(o), caption, notes


# --------------------------------------------------------------------------- stress test 1: migration
def fig_mig_models(res):
    d = _ds(res, "stress_mig_models")
    if d is None:
        return None
    plt = _plt()
    models = list(dict.fromkeys(d.model))
    periods = list(dict.fromkeys(d.period))
    fig, ax = plt.subplots(figsize=(WIDTH, 3.3))
    step = 0.15
    for j, m in enumerate(models):
        s = d[d.model == m]
        y = np.array([periods.index(p) for p in s.period]) + (j - (len(models) - 1) / 2) * step
        col = RAMP[min(j, len(RAMP) - 1)]
        ax.errorbar(s.coef, y, xerr=[s.coef - s.lo, s.hi - s.coef], fmt="o", color=col, ms=4.2, elinewidth=1.3, capsize=0, label=m)
    ax.axvline(0, color=SLATE, lw=0.8)
    ax.set_yticks(range(len(periods)), [f"{p}" for p in periods])
    ax.invert_yaxis()
    ax.set_xlabel("Change in net domestic migration (percentage points of households a year) per SD of AI exposure (AIGE)")
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), handletextpad=0.3, labelspacing=0.9)
    caption = "The county AI-exposure gradient of migration disappears once the rival explanations are held equal."
    base, full = _stat(res, "stress-mig", "coef_base"), _stat(res, "stress-mig", "coef_full")
    notes = ("Each dot is the coefficient on AIGE (z-scored) in a regression of net domestic migration on AIGE and the controls named in the "
             "legend, with state-by-year fixed effects, weighted by households (IRS returns), for county-years in each period; lines are "
             "95% intervals from errors clustered by county. Darker dots add more controls. "
             + (f"2020&ndash;22: {base:+.2f} with state-by-year effects only, {full:+.2f} with every control.".replace("-", "&minus;")
                if base is not None else ""))
    return _svg(fig, "Migration models"), caption, notes


def fig_mig_years(res):
    d = _ds(res, "stress_mig_years")
    if d is None:
        return None
    plt = _plt()
    style = {"AI exposure, state effects only": (SLATE, "--"), "AI exposure, all controls": (INK, "-"),
             "2016 Republican vote, all controls": (REP, "-"), "Telework, all controls": (TEAL, "-")}
    fig, ax = plt.subplots(figsize=(WIDTH, 3.4))
    ends = []
    for series, (col, ls) in style.items():
        s = d[d.series == series].sort_values("year")
        if s.empty:
            continue
        ax.fill_between(s.year, s.lo, s.hi, color=col, alpha=0.10, lw=0)
        ax.plot(s.year, s.coef, color=col, ls=ls, marker="o", ms=3)
        ends.append([s.coef.iloc[-1], series, col, s.year.iloc[-1]])
    span = float(d.hi.max() - d.lo.min()) or 1.0
    ends.sort(key=lambda e: e[0])
    ys = [e[0] for e in ends]
    for _ in range(50):                               # push end labels apart until they no longer overlap
        moved = False
        for i in range(1, len(ys)):
            if ys[i] - ys[i - 1] < 0.075 * span:
                shift = (0.075 * span - (ys[i] - ys[i - 1])) / 2
                ys[i - 1] -= shift
                ys[i] += shift
                moved = True
        if not moved:
            break
    for (v, series, col, x), y in zip(ends, ys):
        ax.annotate(series, (x, v), xytext=(x + 0.25, y), textcoords="data", va="center", color=col, fontsize=8.5)
    ax.axhline(0, color=SLATE, lw=0.8)
    ax.set_xlim(d.year.min() - 0.3, d.year.max() + 0.3)
    ax.set_ylabel("Points of households a year per SD")
    ax.set_xticks(sorted(d.year.unique()))
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    caption = "What grew after 2016 is the partisan and telework gradient of migration, not the AI gradient."
    notes = ("One regression per year (the second year of each IRS filing pair) with state fixed effects, weighted by households; shaded bands "
             "are 95% intervals clustered by county. The dashed line is AIGE with state effects only; the solid lines come from the model with "
             "every control (density, education, income, housing costs, January temperature, the 2016 Republican vote share and the share of "
             "the county's jobs that can be done at home).")
    return _svg(fig, "Migration by year"), caption, notes


# --------------------------------------------------------------------------- stress test 2: exposure measures
def fig_occ_models(res):
    d = _ds(res, "stress_occ_models")
    if d is None:
        return None
    plt = _plt()
    fam_order = ["Language models", "AI benchmarks", "Patents", "Routine automation"]
    meas = (d.drop_duplicates("measure").assign(f=lambda x: x.family.map({f: i for i, f in enumerate(fam_order)}))
            .sort_values(["f", "measure"]).measure.tolist())
    models = list(dict.fromkeys(d.model))
    fig, ax = plt.subplots(figsize=(WIDTH, 5.2))
    step = 0.14
    for j, m in enumerate(models):
        s = d[d.model == m]
        y = np.array([meas.index(x) for x in s.measure]) + (j - (len(models) - 1) / 2) * step
        ax.errorbar(s.coef, y, xerr=[s.coef - s.lo, s.hi - s.coef], fmt="o", color=RAMP[min(j, 4)], ms=3.8, elinewidth=1.1, capsize=0, label=m)
    ax.axvline(0, color=SLATE, lw=0.8)
    ax.set_yticks(range(len(meas)), meas)
    ax.invert_yaxis()
    fams = d.drop_duplicates("measure").set_index("measure").family
    prev = None
    for i, m in enumerate(meas):
        if prev is not None and fams[m] != prev:
            ax.axhline(i - 0.5, color=GRID, lw=0.8)
        prev = fams[m]
    ax.text(0, 1.012, "← more Democratic workforce", transform=ax.transAxes, color=DEM, fontsize=8.5, va="bottom")
    ax.text(1, 1.012, "more Republican workforce →", transform=ax.transAxes, color=REP, fontsize=8.5, va="bottom", ha="right")
    ax.set_xlabel("Republican share of an occupation's workers (percentage points) per SD of the measure")
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), handletextpad=0.3, labelspacing=0.9)
    caption = ("Generative-AI exposure leans Democratic only through who holds the jobs; routine-automation risk leans Republican "
               "under every set of controls.")
    notes = ("Each dot is the coefficient on one exposure measure (z-scored) in a regression of the Republican share of an occupation's VRscores "
             "workers on the measure and the controls in the legend, weighted by matched workers; lines are 95% intervals (HC1). Darker dots "
             "add more controls. Gender and race shares exist for about 300 occupations, so the last two models use that smaller sample. "
             "Measures are grouped by how they were built: language-model exposure, AI benchmark exposure, patent text, and routine automation.")
    return _svg(fig, "Exposure measures and partisanship"), caption, notes


# --------------------------------------------------------------------------- stress test 3: structure
def fig_structure(res):
    d = _ds(res, "stress_structure")
    if d is None:
        return None
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.35))
    w = d.workers / d.workers.max()
    for ax, x, y, lab, stat in ((axes[0], "rep_pred", "rep_share", "Republican share", "r2_share"),
                                (axes[1], "balance_pred", "balance", "Political balance (1 = evenly split)", "r2_balance")):
        ax.scatter(d[x], d[y], s=8 + 140 * w, facecolor="none", edgecolor=INK, linewidth=0.6, alpha=0.75)
        lo = min(d[x].min(), d[y].min()) - 0.02
        hi = max(d[x].max(), d[y].max()) + 0.02
        ax.plot([lo, hi], [lo, hi], color=SLATE, lw=0.8, ls="--")
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_xlabel("Predicted from the occupations employed")
        ax.set_ylabel("Actual")
        ax.set_title(lab)
        r2 = _stat(res, "stress-structure", stat)
        if r2 is not None:
            ax.text(0.04, 0.96, f"R² = {r2:.2f}", transform=ax.transAxes, va="top", color=INK)
        ax.grid(color=GRID, lw=0.5)
        ax.set_axisbelow(True)
    fig.tight_layout(w_pad=3)
    caption = "Industries' partisanship, and half of their political balance, follow from the occupations they employ."
    notes = ("Each circle is a four-digit industry with at least 70% of its jobs linked to VRscores occupations, sized by matched workers. "
             "Predicted = national Republican share of each occupation, weighted by the industry's staffing pattern (OES). Balance = "
             "1 &minus; |2p &minus; 1|, where p is the Republican share. R&sup2; from a regression weighted by workers; the dashed line is equality.")
    return _svg(fig, "Structural partisanship"), caption, notes


FIGURES = {"seam": fig_seam, "mig-models": fig_mig_models, "mig-years": fig_mig_years, "occ-models": fig_occ_models, "structure": fig_structure}
