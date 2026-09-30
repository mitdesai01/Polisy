# -*- coding: utf-8 -*-
"""Organizations: large employers' partisan drift, AI and big-tech employers, and sorting."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ..core import read, finding, dataset, view, wls, log
from . import needs

RULES = [  # name-based groups; replace with industry codes once employers are linked to firms
    ("AI & big tech", r"\b(google|alphabet|microsoft|meta platforms|facebook|apple|amazon web services|nvidia|openai|anthropic|ibm|international business machines|intel|oracle|salesforce|adobe|cisco|qualcomm|advanced micro devices|micron|palantir|linkedin|netflix|uber|airbnb|tesla|spacex|dell|hewlett|vmware|servicenow|workday|snowflake|databricks|broadcom|texas instruments|applied materials)\b"),
    ("Defense & aerospace", r"\b(lockheed|northrop|raytheon|rtx|general dynamics|boeing|l3harris|leidos|science applications|booz allen|caci|bae systems|huntington ingalls|textron|mitre)\b"),
    ("Military & federal", r"\b(army|navy|air force|marine corps|coast guard|department of|veterans affairs|postal service|national guard|federal)\b"),
    ("Higher education", r"\b(university|college|institute of technology|school of medicine)\b"),
    ("Health care", r"\b(health|hospital|medical|clinic|kaiser|mayo|healthcare|pharmacy|cvs|walgreen)\b"),
    ("Finance & insurance", r"\b(bank|bancorp|financial|capital one|jpmorgan|goldman|morgan stanley|wells fargo|citigroup|insurance|mutual|fidelity|fmr|schwab|american express|visa|mastercard|state farm|allstate|progressive)\b"),
    ("Consulting & accounting", r"\b(deloitte|accenture|pricewaterhouse|ernst|kpmg|mckinsey|boston consulting|bain)\b"),
    ("Retail & hospitality", r"\b(walmart|target|home depot|lowe|kroger|costco|starbucks|mcdonald|restaurant|hotel|marriott|hilton|retail|stores)\b"),
    ("State & local government", r"\b(county of|city of|state of|school district|public schools|police|sheriff)\b"),
]


def tag(name):
    s = str(name).lower()
    return next((lab for lab, rx in RULES if re.search(rx, s)), "Other")


def run():
    e, srt = read("vr_employer_summary"), read("vr_sorting")
    if e is None and srt is None:
        return needs("org", "Employer drift and partisan sorting", "Organizations", "employer", "VRscores employer panel",
                     "Is workforce partisanship a stable organisational trait?")
    if e is not None and len(e) > 100:
        e = e.copy()
        e["group"] = e.employer.map(tag)
        dataset("employers", e[[c for c in ("employer", "group", "class", "avg_rep_share", "change_pp", "workers") if c in e]])
        view("emp-explorer", "scatter", "Large employers: average lean against change over the period", "employers",
             x=["avg_rep_share"], y=["change_pp"], size="workers", color="group", text="employer", filter=["group", "class"],
             labels={"avg_rep_share": "Average Republican share", "change_pp": "Change over the period (points)"})
        g = e.groupby("group").apply(lambda x: pd.Series({"employers": len(x), "workers": x.workers.sum(),
                                                         "rep_share": np.average(x.avg_rep_share, weights=x.workers),
                                                         "change_pp": np.average(x.change_pp, weights=x.workers),
                                                         "share_drift_rep": np.mean(x.change_pp >= 5), "share_drift_dem": np.mean(x.change_pp <= -5)}),
                                     include_groups=False).reset_index().sort_values("change_pp")
        dataset("employer_groups", g)
        view("emp-groups", "bar", "Average change in Republican share by employer group (points, weighted by workers)", "employer_groups",
             x="change_pp", y="group", orientation="h", color="rep_share")
        nd, nr = int((e.change_pp <= -5).sum()), int((e.change_pp >= 5).sum())
        e["log_workers"] = np.log10(e.workers)
        m = wls(e, "change_pp", ["avg_rep_share", "log_workers"], None)
        t_lean, t_size = m["terms"]["avg_rep_share"]["t"], m["terms"]["log_workers"]["t"]
        head = (f"Large employers drift Democratic {nd / max(nr, 1):.1f} times as often as Republican" if nd >= nr else
                f"Large employers drift Republican {nr / max(nd, 1):.1f} times as often as Democratic")
        way = lambda t: "towards the Democrats" if t < 0 else "towards the Republicans"  # noqa: E731  (change_pp > 0 = more Republican)
        if nd > nr and t_lean <= -2 and t_size <= -2:
            head += "; the most Republican and the largest drift most"
        else:
            parts = ([f"more Republican employers moved further {way(t_lean)}"] if abs(t_lean) >= 2 else []) + \
                    ([f"larger employers moved further {way(t_size)}"] if abs(t_size) >= 2 else [])
            head += ("; " + " and ".join(parts)) if parts else ""
        finding("emp-drift", head,
                f"Of {len(e):,} large employers present every year, {nd:,} moved 5+ points towards the Democrats and {nr:,} towards the Republicans "
                f"(ratio {nd / max(nr, 1):.1f} to 1). Employers that started more Republican moved further {way(t_lean)} (t = {t_lean:+.1f}), "
                f"larger ones further {way(t_size)} (t = {t_size:+.1f}); |t| below 2 means no clear difference.",
                theme="Organizations", level="employer", datasets=["VRscores"],
                strength="robust", stats={"n": len(e), "drift_dem": nd, "drift_rep": nr, "t_start_lean": t_lean, "t_size": t_size},
                question="Is drift hiring (new cohorts), attrition, or relocation? Which organisational events precede it?",
                next_data="Employer x year hires and exits by age; M&A events (SDC); locations", views=["emp-explorer"], rank=13)
        t = e[e.group == "AI & big tech"]
        if len(t) >= 8:
            other = e[e.group != "AI & big tech"]
            up = t[t.change_pp > 0].nlargest(6, "change_pp")
            cb, co = np.average(t.change_pp, weights=t.workers), np.average(other.change_pp, weights=other.workers)
            if co < 0 and co < cb < 0 and abs(cb) < abs(co) / 2:
                head = "AI and big-tech workforces barely joined the Democratic drift"
            elif cb > co + 1:
                head = "AI and big-tech workforces moved less towards the Democrats than other large employers"
            elif cb < co - 1:
                head = "AI and big-tech workforces moved further towards the Democrats than other large employers"
            else:
                head = "AI and big-tech workforces moved much like other large employers"
            head += ", and several moved Republican" if len(up) >= 3 else ""
            finding("emp-bigtech", head,
                    f"The {len(t)} large AI and big-tech employers (identified by name) changed {cb:+.1f} points "
                    f"on average, against {co:+.1f} for all others. Moving Republican: "
                    + ("; ".join(f"{a} ({b:+.1f})" for a, b in zip(up.employer, up.change_pp)) or "none") + ".",
                    theme="Political ideology x AI", level="employer", datasets=["VRscores"], strength="suggestive",
                    stats={"n_bigtech": len(t), "change_bigtech_pp": float(np.average(t.change_pp, weights=t.workers)),
                           "change_other_pp": float(np.average(other.change_pp, weights=other.workers))},
                    question="Did AI and cloud firms' expansion (data centres, new hubs in Texas, Virginia, Utah) or the 2022-24 layoffs shift their workforces' politics?",
                    next_data="Employer x metro x occupation headcounts; data-centre locations; layoff notices (WARN)", views=["emp-explorer", "emp-groups"], rank=4)
        top = e.reindex(e.change_pp.abs().sort_values(ascending=False).index).head(12)
        finding("emp-artifacts", "The largest employer drifts need checking for restructured firms",
                "The twelve largest absolute drifts: " + "; ".join(f"{a} ({b:+.0f})" for a, b in zip(top.employer, top.change_pp)) +
                ". In the first run most of the largest were spin-offs, mergers or rebrands after 2020, whose early years are rebuilt "
                "from today's profiles; check these names before using drift as an outcome.",
                theme="Anomalies", level="employer", datasets=["VRscores"], strength="artifact",
                question="Flag restructured employers before using drift as an outcome.", next_data="M&A and spin-off dates (SDC, Crunchbase)",
                views=["emp-explorer"], rank=21)
    if srt is not None and len(srt):
        m = srt[srt.measure.isin(["over_exposure", "dissimilarity_excess", "dissimilarity"])].copy()
        dataset("sorting", m)
        view("sorting", "line", "Partisan sorting by dimension over time", "sorting", x="year", y="value", group="dimension", facet="measure")
        ch = []
        for (dim, meas), gg in m.groupby(["dimension", "measure"]):
            gg = gg.sort_values("year")
            ch.append((dim, meas, gg.value.iloc[0], gg.value.iloc[-1]))
        ov = {d: (a, b) for d, meas, a, b in ch if meas == "over_exposure"}
        if "employer" in ov:
            txt = "; ".join(f"{d}: {(a - 1) * 100:.2f}% -> {(b - 1) * 100:.2f}%" for d, (a, b) in ov.items())
            up = [d for d, (a, b) in ov.items() if b > a]
            down = [d for d, (a, b) in ov.items() if b < a]
            jobs_down = [d for d in ("industry", "occupation") if d in down]
            plural = {"employer": "employers", "metro": "metros", "industry": "industries", "occupation": "occupations"}
            if "employer" in up and len(jobs_down) == 2:
                head = "Partisans are sorting into different employers while sorting across industries and occupations declines"
            elif "employer" in up:
                head = "Partisans are sorting into different employers" + (
                    f", and across {' and '.join(plural.get(d, d) for d in up if d != 'employer')} too" if len(up) > 1 else "")
            else:
                head = "Partisan sorting between employers did not rise" + (
                    f"; it rose across {' and '.join(plural.get(d, d) for d in up)}" if up else "")
            finding("sorting", head,
                    f"Same-party over-exposure (colleagues share one's party more often than by chance), first to last year: {txt}. "
                    f"Rising: {', '.join(up) or 'none'}; falling: {', '.join(down) or 'none'}. Employer sorting changed "
                    f"{(ov['employer'][1] - ov['employer'][0]) * 100:+.2f} points" + (f", metro sorting {(ov['metro'][1] - ov['metro'][0]) * 100:+.2f}" if "metro" in ov else "") +
                    (": most of the growth in workplace segregation happens between firms within the same kinds of jobs, not across occupations "
                     "or industries." if "employer" in up and len(jobs_down) == 2 else "."),
                    theme="Organizations", level="employer", datasets=["VRscores"], strength="suggestive",
                    stats={k: {"first": a, "last": b} for k, (a, b) in ov.items()},
                    question="Which organisational practices (hiring networks, location choice, mission statements, leadership politics) produce between-firm sorting?",
                    next_data="Firm-level leadership politics (DIPI), hiring sources, location histories", views=["sorting"], rank=3)
    log("organizations: done")
    return True
