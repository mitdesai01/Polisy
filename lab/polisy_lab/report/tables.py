# -*- coding: utf-8 -*-
"""Tables for the report, built from results.json. Each returns (html, caption, notes) or None."""
from __future__ import annotations

import html

import pandas as pd

from .audit import AUDIT, VERDICTS
from .references import REFS
from .figures import _ds

GRADE_LABEL = {"robust": "Robust", "suggestive": "Suggestive", "fragile": "Fragile", "descriptive": "Descriptive",
               "artifact": "Artefact", "needs data": "Needs data"}


def _e(s):
    return html.escape(str(s), quote=False)


def _num(v, fmt="{:+.2f}"):
    try:
        return fmt.format(float(v)).replace("-", "&minus;")
    except (TypeError, ValueError):
        return "&ndash;"


def _cites(keys):
    return "; ".join(f'<a href="#ref-{k}">{REFS[k]["cite"]} {REFS[k]["year"]}</a>' for k in keys if k in REFS) or "&ndash;"


def tab_audit(res):
    order = list(VERDICTS)
    rows = []
    for f in res.get("findings", []):
        v, keys, why = AUDIT.get(f["id"], ("Descriptive", [], ""))
        rows.append((order.index(v) if v in order else 99, f.get("rank") or 99, f, v, keys, why))
    rows.sort(key=lambda r: (r[0], r[1]))
    body = []
    for _, _, f, v, keys, why in rows:
        body.append(f'<tr><td class="fid"><span class="t">{_e(f["title"])}</span><span class="id">{_e(f["id"])} &middot; {_e(f["level"])}</span></td>'
                    f'<td>{GRADE_LABEL.get(f["strength"], f["strength"])}</td>'
                    f'<td><span class="verdict v-{v.lower().replace(" ", "-")}">{v}</span></td>'
                    f'<td class="lit">{_cites(keys)}</td><td class="why">{_e(why)}</td></tr>')
    n = pd.Series([r[3] for r in rows]).value_counts()
    counts = ", ".join(f"{k.lower()} {n[k]}" for k in order if k in n)
    table = ('<table class="audit"><thead><tr><th>Finding</th><th>Lab grade</th><th>Verdict</th><th>Closest literature</th>'
             '<th>Why</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>")
    caption = "Every finding of the first run, against the literature."
    notes = (f"Lab grade: how well the pattern holds in POLISY's own data (after the stress tests). Verdict: how it stands against published "
             f"and working-paper evidence checked in September 2026. Counts: {counts}.")
    return table, caption, notes


def tab_mig_models(res):
    d = _ds(res, "stress_mig_models")
    if d is None:
        return None
    periods = list(dict.fromkeys(d.period))
    models = list(dict.fromkeys(d.model))
    head = "<tr><th>Controls</th>" + "".join(f'<th class="num">{_e(p)}</th>' for p in periods) + "</tr>"
    body = []
    for m in models:
        cells = []
        for p in periods:
            r = d[(d.model == m) & (d.period == p)]
            if r.empty:
                cells.append('<td class="num">&ndash;</td>')
                continue
            r = r.iloc[0]
            se = (r.hi - r.lo) / (2 * 1.96)
            cells.append(f'<td class="num">{_num(r.coef)}<span class="se">({se:.2f})</span></td>')
        body.append(f"<tr><td>{_e(m)}</td>{''.join(cells)}</tr>")
    last = d[d.model == models[-1]].set_index("period")
    body.append('<tr class="foot"><td>Counties &times; years (last model)</td>' +
                "".join(f'<td class="num">{int(last.loc[p].n):,}</td>' if p in last.index else "<td></td>" for p in periods) + "</tr>")
    body.append('<tr class="foot"><td>R&sup2; (last model)</td>' +
                "".join(f'<td class="num">{last.loc[p].r2:.2f}</td>' if p in last.index else "<td></td>" for p in periods) + "</tr>")
    table = f'<table class="reg"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table>'
    caption = "Net domestic migration per SD of AI exposure (AIGE), as the rival explanations are added."
    notes = ("Coefficient on AIGE with its standard error in parentheses (clustered by county). Dependent variable: net domestic migration, "
             "percentage points of households a year (IRS SOI county flows, year = second year of the filing pair). WLS weighted by "
             "households; state-by-year fixed effects in every model. Controls are cumulative from top to bottom.")
    return table, caption, notes


def tab_mig_full(res):
    d = _ds(res, "stress_mig_full")
    if d is None:
        return None
    periods = list(dict.fromkeys(d.period))
    terms = list(dict.fromkeys(d.term))
    head = "<tr><th>Per SD of</th>" + "".join(f'<th class="num">{_e(p)}</th>' for p in periods) + "</tr>"
    body = []
    for t in terms:
        cells = []
        for p in periods:
            r = d[(d.term == t) & (d.period == p)]
            if r.empty:
                cells.append('<td class="num">&ndash;</td>')
                continue
            r = r.iloc[0]
            cells.append(f'<td class="num">{_num(r.coef)}<span class="se">[t = {_num(r.t, "{:.1f}")}]</span></td>')
        body.append(f"<tr><td>{_e(t)}</td>{''.join(cells)}</tr>")
    table = f'<table class="reg"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table>'
    caption = "The full migration model: which county traits predict net migration."
    notes = ("Same models as the last row of the previous table, every term shown (z-scored). The 2016 vote comes from the county returns; "
             "telework is the share of the county's jobs (by sector) that can be done at home, after Dingel &amp; Neiman (2020).")
    return table, caption, notes


def tab_occ_pairs(res):
    d = _ds(res, "stress_occ_pairs")
    if d is None or d.empty:
        return None
    models = list(dict.fromkeys(d.model))
    head = "<tr><th>Measures in the same model</th>" + "".join(f'<th class="num">{_e(m)}</th>' for m in models) + "</tr>"
    body = []
    for pair in dict.fromkeys(d.pair):
        s = d[d.pair == pair]
        for meas in dict.fromkeys(s.measure):
            cells = []
            for m in models:
                r = s[(s.model == m) & (s.measure == meas)]
                cells.append(f'<td class="num">{_num(r.coef.iloc[0], "{:+.1f}")}<span class="se">[{_num(r.t.iloc[0], "{:.1f}")}]</span></td>'
                             if not r.empty else '<td class="num">&ndash;</td>')
            body.append(f'<tr><td>{_e(meas)}<span class="pair">{_e(pair)}</span></td>{"".join(cells)}</tr>')
    table = f'<table class="reg"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table>'
    caption = "Two exposure measures side by side: generative AI against routine automation and AI patents."
    notes = ("Republican share (points) per SD of each measure when both enter the same model; t statistics in brackets (HC1). Controls are "
             "cumulative from left to right, as in the figure above.")
    return table, caption, notes


def tab_findings(res):
    body = []
    for f in sorted(res.get("findings", []), key=lambda x: (x.get("rank") or 99, x["id"])):
        cav = "".join(f"<li>{_e(c)}</li>" for c in f.get("caveats") or [])
        body.append(f'<tr><td class="fid"><span class="t">{_e(f["title"])}</span><span class="id">{_e(f["id"])} &middot; {_e(f["level"])} '
                    f'&middot; {GRADE_LABEL.get(f["strength"], f["strength"])}</span></td>'
                    f'<td class="claim">{_e(f["claim"])}{f"<ul>{cav}</ul>" if cav else ""}</td>'
                    f'<td class="q">{_e(f.get("question") or "")}</td></tr>')
    table = ('<table class="findings"><thead><tr><th>Finding</th><th>What the data show</th><th>Question it raises</th></tr></thead><tbody>'
             + "".join(body) + "</tbody></table>")
    return table, "All findings of the first run, in the lab's reading order.", "Text as generated by the lab from the data."


TABLES = {"audit": tab_audit, "mig-models": tab_mig_models, "mig-full": tab_mig_full, "occ-pairs": tab_occ_pairs, "findings": tab_findings}
