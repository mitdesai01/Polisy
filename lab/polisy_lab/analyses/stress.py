# -*- coding: utf-8 -*-
"""Stress tests: do the headline findings survive the first alternative explanations a referee would raise?

Each test re-estimates a headline finding with the controls that stand for its obvious rival
explanation, registers the models, and re-grades the finding it tests (core.regrade):

stress-mig        households leaving AI-exposed counties (mig-ai-exodus) vs density, education, income,
                  housing costs, climate, the 2016 vote and telework
stress-occ        the partisan lean of AI exposure measures (occ-waves) vs education, pay, telework,
                  gender, race and occupation group
stress-structure  industry partisanship and political balance vs the occupations industries employ
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..core import read, finding, dataset, view, wls, wcorr, regrade, log, leaning
from . import needs
from .exposure import MEASURES

PERIODS = {"2013-16": range(2013, 2017), "2017-19": range(2017, 2020), "2020-22": range(2020, 2023)}
MIG_SPECS = [
    ("AIGE, state × year effects", []),
    ("+ population density", ["log_density"]),
    ("+ education and income", ["log_density", "ba_share", "log_income"]),
    ("+ housing costs, January temperature, 2016 vote", ["log_density", "ba_share", "log_income", "log_housing", "temp_jan", "rep16"]),
    ("+ telework (industry mix)", ["log_density", "ba_share", "log_income", "log_housing", "temp_jan", "rep16", "telework"]),
]
MIG_PHRASES = {"log_density": "population density", "ba_share": "the bachelor's degree share", "log_income": "average income",
               "log_housing": "housing costs", "temp_jan": "January temperature", "rep16": "the county's 2016 Republican vote share",
               "telework": "the share of jobs that can be done at home"}
MIG_LABELS = {"aige": "AI exposure (AIGE)", "log_density": "Population density (log)", "ba_share": "Bachelor's degree share",
              "log_income": "Average income (log)", "log_housing": "Housing costs (log)", "temp_jan": "January temperature",
              "rep16": "Republican vote share, 2016", "telework": "Jobs that can be done at home"}
OCC_SPECS = [
    ("Measure alone", []),
    ("+ education, wage", ["req_education", "log_salary"]),
    ("+ telework", ["req_education", "log_salary", "teleworkable"]),
    ("+ gender, race", ["req_education", "log_salary", "teleworkable", "female", "black", "hispanic", "asian"]),
    ("+ occupation group", ["req_education", "log_salary", "teleworkable", "female", "black", "hispanic", "asian", "FE"]),
]


def run():
    ran = [_migration(), _exposure(), _structure()]
    return any(ran)


# --------------------------------------------------------------------------- migration
def _county_controls():
    cc = read("county_context")
    if cc is None:
        return None
    cc = cc.copy()
    it = read("ind_telework")
    if it is not None:                      # telework share of the county's jobs, from its sector mix (CBP x Dingel & Neiman)
        tw = dict(zip(it.naics2.astype(str).str.strip(), it.teleworkable_emp))
        num, den = pd.Series(0.0, index=cc.index), pd.Series(0.0, index=cc.index)
        for c in [c for c in cc if c.startswith("emp_")]:
            share = tw.get(c[4:])
            if share is None or pd.isna(share):
                continue
            num += cc[c].fillna(0) * share
            den += cc[c].fillna(0)
        cc["telework"] = (num / den).where(den > 0)
    v = read("votes_county_year")
    if v is not None and (v.year == 2016).any():
        cc = cc.merge(v[v.year == 2016][["county_fips", "rep_vote_share"]].rename(columns={"rep_vote_share": "rep16"}), on="county_fips", how="left")
        cc["rep16"] = cc.rep16.fillna(cc.rep_share_2016)
    else:
        cc["rep16"] = cc.rep_share_2016
    return cc


def _migration():
    p = read("panel_county_year", "PANELS")
    cc = _county_controls()
    if p is None or "aige" not in p or cc is None:
        return needs("stress-mig", "Stress test: AI exposure and county migration with county controls", "Stress tests", "county",
                     "county context (counties.json) and telework shares (Dingel & Neiman); module fetch downloads both",
                     "Does AI exposure still predict out-migration once density, education, income, housing costs, climate, "
                     "politics and telework are held equal?", rank=91)
    d = p[p.net_migration_rate.notna() & p.aige.notna() & (p.base_returns > 0)].merge(cc, on="county_fips", how="left")
    d["net_pp"] = 100 * d.net_migration_rate
    d["state_year"] = d.state_fips.astype(str) + "_" + d.year.astype(str)
    full = MIG_SPECS[-1][1] if "telework" in d else MIG_SPECS[-2][1]
    specs = [(n, xs) for n, xs in MIG_SPECS if set(xs) <= set(d.columns)]
    rows, full_rows = [], []
    for per, yrs in PERIODS.items():
        s = d[d.year.isin(yrs)].dropna(subset=["aige"] + full)
        for name, xs in specs:
            m = wls(s, "net_pp", ["aige"] + xs, "base_returns", fe="state_year", cluster="county_fips")
            if not m:
                continue
            t = m["terms"]["aige"]
            rows.append({"period": per, "model": name, "coef": t["coef"], "lo": t["coef"] - 1.96 * t["se"], "hi": t["coef"] + 1.96 * t["se"],
                         "t": t["t"], "n": m["n"], "r2": m["r2"]})
            if xs == full:
                for term, tt in m["terms"].items():
                    full_rows.append({"period": per, "term": MIG_LABELS.get(term, term), "variable": term, "coef": tt["coef"],
                                      "lo": tt["coef"] - 1.96 * tt["se"], "hi": tt["coef"] + 1.96 * tt["se"], "t": tt["t"], "n": m["n"]})
    if not rows:
        return False
    models, fullm = pd.DataFrame(rows), pd.DataFrame(full_rows)
    years = []
    for y in sorted(d.year.unique()):
        s = d[d.year == y].dropna(subset=["aige"] + full)
        m0 = wls(s, "net_pp", ["aige"], "base_returns", fe="state_fips", cluster="county_fips")
        m1 = wls(s, "net_pp", ["aige"] + full, "base_returns", fe="state_fips", cluster="county_fips")
        for series, m, term in (("AI exposure, state effects only", m0, "aige"), ("AI exposure, all controls", m1, "aige"),
                                ("2016 Republican vote, all controls", m1, "rep16"), ("Telework, all controls", m1, "telework")):
            if m and term in m["terms"]:
                t = m["terms"][term]
                years.append({"year": int(y), "series": series, "coef": t["coef"], "lo": t["coef"] - 1.96 * t["se"],
                              "hi": t["coef"] + 1.96 * t["se"], "t": t["t"], "n": m["n"]})
    yrs = pd.DataFrame(years)
    dataset("stress_mig_models", models, note="Net domestic migration (% of households a year) per SD of AIGE; WLS by households; "
                                              "state x year effects; errors clustered by county.")
    dataset("stress_mig_full", fullm, note="Full model, every term per SD.")
    dataset("stress_mig_years", yrs, note="One regression per year with state effects.")
    view("stress-mig-models", "coef", "Net migration per SD of AI exposure, as controls are added (points of households a year)", "stress_mig_models",
         x="coef", y="period", group="model", lo="lo", hi="hi", xlabel="Percentage points of households a year per SD of AIGE, 95% interval")
    view("stress-mig-years", "line", "Year by year: AI exposure with and without controls, and the 2016 vote", "stress_mig_years",
         x="year", y=["coef"], group="series", labels={"coef": "Points of households a year per SD"})
    last = models[models.period == "2020-22"].set_index("model")
    base, fin = last.iloc[0], last.iloc[-1]
    att = 1 - fin.coef / base.coef if base.coef else np.nan
    fl = fullm[fullm.period == "2020-22"].set_index("variable")
    ff = fullm[fullm.period == "2013-16"].set_index("variable")
    top = fl.drop(index="aige").assign(a=lambda x: x.t.abs()).sort_values("a", ascending=False)
    r16 = fl.loc["rep16"] if "rep16" in fl.index else None
    mostly = np.isfinite(att) and att >= 0.5
    lead = top.index[0]
    if mostly and lead in ("rep16", "telework"):
        head = "The 'AI exodus' is mostly the partisan and telework geography of migration"
    elif mostly:
        head = f"The 'AI exodus' is mostly other county traits, led by {MIG_PHRASES.get(lead, lead)}"
    else:
        head = "Most of the 'AI exodus' survives density, education, income, housing, climate, politics and telework"
    ser = lambda s: yrs[yrs.series == s].sort_values("year") if len(yrs) else yrs  # noqa: E731
    ctrl_y, raw_y = ser("AI exposure, all controls"), ser("AI exposure, state effects only")
    trend = ""
    if len(ctrl_y) > 2 and len(raw_y) > 2:
        small = ctrl_y.coef.abs().max() < 0.5 * raw_y.coef.abs().max()
        grows = abs(raw_y.coef.iloc[-1]) > abs(raw_y.coef.iloc[0])
        trend = (f" Year by year the controlled AI coefficient {'stays small' if small else 'does not stay small'} while the unadjusted one "
                 f"{'grows' if grows else 'does not grow'} ({raw_y.coef.iloc[0]:+.2f} in {int(raw_y.year.iloc[0])}, {raw_y.coef.iloc[-1]:+.2f} in "
                 f"{int(raw_y.year.iloc[-1])}).")
    finding("stress-mig", head,
            f"In 2020-22, one SD more AI exposure meant {base.coef:+.2f} points of households a year within the same state "
            f"(t = {base.t:.1f}). With density, education, income, housing costs, January temperature, the 2016 vote and telework held "
            f"equal it is {fin.coef:+.2f} (t = {fin.t:.1f}): {att:.0%} of the gradient goes.{trend} The strongest predictor in the full model is "
            f"{MIG_PHRASES.get(top.index[0], top.index[0])} ({top.coef.iloc[0]:+.2f}, t = {top.t.iloc[0]:.1f})"
            + (f"; the coefficient on the 2016 vote grew from {ff.loc['rep16'].coef:+.2f} (2013-16) to {r16.coef:+.2f} (2020-22)."
               if r16 is not None and "rep16" in ff.index else "."),
            theme="Stress tests", level="county", datasets=["IRS SOI migration", "AIOE (AIGE)", "County context", "Dingel & Neiman telework"],
            strength="robust",
            stats={"coef_base": base.coef, "t_base": base.t, "coef_full": fin.coef, "t_full": fin.t, "attenuation": att,
                   "rep16_2013_16": ff.loc["rep16"].coef if "rep16" in ff.index else None, "rep16_2020_22": r16.coef if r16 is not None else None,
                   "telework_2020_22": fl.loc["telework"].coef if "telework" in fl.index else None, "n": int(fin.n)},
            question="Once AI exposure is read as a proxy for dense, Democratic, telework-intensive counties, the open question is the political "
                     "one: do movers carry their workplace politics into destination firms?",
            next_data="Movers' occupations and party (ACS migration microdata; L2 voter-file moves); county-pair flows across state borders",
            caveats=["County context is a 2019 cross-section (ACS 2019, CBP); telework comes from the county's industry mix, not its occupations.",
                     "The 2016 vote is fixed before the flows it predicts, but it stands for everything that differs between red and blue counties."],
            views=["stress-mig-models", "stress-mig-years"], rank=1)
    if mostly:
        note = (f"Stress test (stress-mig): with county controls the 2020-22 gradient falls from {base.coef:+.2f} to {fin.coef:+.2f} points per SD; "
                "AIGE mostly stands for dense, Democratic, telework-intensive counties.")
        regrade("mig-ai-exodus", "fragile", note, title="Households are leaving AI-exposed counties, but the gradient is mostly density, politics and telework")
        for fid in ("mig-income", "mig-exposure-gap"):
            regrade(fid, "descriptive", "AIGE stands for dense, Democratic, telework-intensive counties (see stress-mig); read as a description, not an AI effect.")
    else:
        regrade("mig-ai-exodus", "robust", f"Stress test (stress-mig): with county controls the 2020-22 gradient is {fin.coef:+.2f} points per SD "
                                           f"(from {base.coef:+.2f}); most of it survives.")
    log(f"stress-mig: AIGE {base.coef:+.2f} -> {fin.coef:+.2f} with controls (2020-22)")
    return True


# --------------------------------------------------------------------------- exposure measures
def _exposure():
    o = read("panel_occupation", "PANELS")
    tw = read("occ_telework")
    if o is None or tw is None:
        return needs("stress-occ", "Stress test: the partisan lean of AI exposure with demographic controls", "Stress tests", "occupation",
                     "telework shares by occupation (Dingel & Neiman; module fetch downloads them)",
                     "Does AI exposure lean Democratic once education, pay, telework, gender and race are held equal?", rank=91)
    o = o.copy()
    o["soc_key"] = o.soc_link.fillna(o.soc2018) if "soc2018" in o else o.soc_link
    o = o.merge(tw.rename(columns={"soc": "soc_key"}), on="soc_key", how="left")
    o["rep_pp"] = 100 * o.rep_share
    have = [m for m in MEASURES if m in o and o[m].notna().sum() > 100]
    rows = []
    for m in have:
        lab, fam = MEASURES[m]
        for name, xs in OCC_SPECS:
            ctrl = [c for c in xs if c != "FE" and c in o]
            if len(ctrl) < len([c for c in xs if c != "FE"]):
                continue
            r = wls(o, "rep_pp", [m] + ctrl, "workers", fe="soc2" if "FE" in xs else None)
            if r:
                t = r["terms"][m]
                rows.append({"measure": lab, "variable": m, "family": fam, "model": name, "coef": t["coef"], "lo": t["coef"] - 1.96 * t["se"],
                             "hi": t["coef"] + 1.96 * t["se"], "t": t["t"], "n": r["n"]})
    if not rows:
        return False
    x = pd.DataFrame(rows)
    pairs = []
    for a, b in (("exp_cumul_genai", "fo17_p_computerisation"), ("exp_cumul_genai", "webb19_ai_score"),
                 ("open24_human_E1_E2", "fo17_p_computerisation")):
        if a not in have or b not in have:
            continue
        for name, xs in OCC_SPECS[1:]:
            ctrl = [c for c in xs if c != "FE" and c in o]
            r = wls(o, "rep_pp", [a, b] + ctrl, "workers", fe="soc2" if "FE" in xs else None)
            if r:
                for v in (a, b):
                    t = r["terms"][v]
                    pairs.append({"pair": f"{MEASURES[a][0]} vs {MEASURES[b][0]}", "model": name, "measure": MEASURES[v][0], "variable": v,
                                  "coef": t["coef"], "lo": t["coef"] - 1.96 * t["se"], "hi": t["coef"] + 1.96 * t["se"], "t": t["t"], "n": r["n"]})
    dataset("stress_occ_models", x, note="Republican share of an occupation's workers (points) per SD of each measure; WLS by matched workers; HC1 errors.")
    dataset("stress_occ_pairs", pd.DataFrame(pairs), note="Two measures in the same model.")
    view("stress-occ-models", "coef", "Republican share (points) per SD of each exposure measure, as controls are added", "stress_occ_models",
         x="coef", y="measure", group="model", lo="lo", hi="hi", xlabel="Points of Republican share per SD, 95% interval")
    get = lambda v, mdl: x[(x.variable == v) & (x.model == mdl)].iloc[0] if ((x.variable == v) & (x.model == mdl)).any() else None  # noqa: E731
    g0, g1 = get("exp_cumul_genai", OCC_SPECS[0][0]), get("exp_cumul_genai", OCC_SPECS[-1][0])
    c0, c1 = get("fo17_p_computerisation", OCC_SPECS[0][0]), get("fo17_p_computerisation", OCC_SPECS[-1][0])
    g3 = get("exp_cumul_genai", OCC_SPECS[3][0])
    flips = sorted({r.measure for r in x[x.model == OCC_SPECS[-1][0]].itertuples()
                    if abs(r.t) >= 2 and np.sign(r.coef) != np.sign(x[(x.variable == r.variable) & (x.model == OCC_SPECS[0][0])].coef.iloc[0])})
    lean_g = leaning(g0.t if g0 is not None else np.nan, "Democratic", "Republican", None, cut=2)   # generative AI, alone
    gone_g = g1 is not None and abs(g1.t) < 2                                                        # ... and with every control
    lean_c = leaning(c1.t if c1 is not None else np.nan, "Democratic", "Republican", None, cut=2)   # automation risk, every control
    claim = []
    if g0 is not None and g1 is not None:
        s = (f"Generative-AI exposure (DAIOE) {'leans ' + lean_g if lean_g else 'has no clear lean'} on its own ({g0.coef:+.1f} points per SD, "
             f"t = {g0.t:.1f}, {int(g0.n)} occupations)")
        s += f"; with gender and race held equal it is {g3.coef:+.1f} (t = {g3.t:.1f})" if g3 is not None else ""
        s += f"; with occupation-group effects too, {g1.coef:+.1f} (t = {g1.t:.1f})"
        s += (": the lean disappears once composition is held equal." if gone_g else ": the lean survives the controls.") if lean_g else "."
        claim.append(s)
    if c0 is not None and c1 is not None:
        other = lean_g and lean_c and lean_c != lean_g
        claim.append(f"Computerisation risk (Frey & Osborne) {'goes the other way' if other else 'for comparison'}: {c0.coef:+.1f} (t = {c0.t:.1f}) "
                     f"alone, {c1.coef:+.1f} (t = {c1.t:.1f}) with education, pay, telework, gender, race and occupation group held equal.")
    if flips:
        claim.append("Measures whose sign flips and becomes clear (|t| of 2 or more) with every control: " + ", ".join(flips) + ".")
    if lean_g and gone_g:
        head = f"AI exposure's {lean_g} lean is composition" + (f"; automation risk's {lean_c} lean is not" if lean_c else
                                                                  ", and automation risk shows no clear lean with every control")
    elif lean_g:
        head = f"AI exposure's {lean_g} lean survives every control" + (f", and so does automation risk's {lean_c} lean" if lean_c else
                                                                          "; automation risk shows no clear lean")
    else:
        head = ("AI exposure shows no clear partisan lean" + (f"; automation risk leans {lean_c} with every control" if lean_c else
                                                              ", and neither does automation risk with controls"))
    finding("stress-occ", head,
            " ".join(claim), theme="Stress tests", level="occupation",
            datasets=["VRscores", "DAIOE (SOC 2018 panel)", "AIOE inputs (CPS demographics)", "Dingel & Neiman telework"], strength="robust",
            stats={"genai_raw": g0.coef if g0 is not None else None, "genai_raw_t": g0.t if g0 is not None else None,
                   "genai_demog": g3.coef if g3 is not None else None, "genai_full": g1.coef if g1 is not None else None,
                   "genai_full_t": g1.t if g1 is not None else None, "comp_raw": c0.coef if c0 is not None else None,
                   "comp_full": c1.coef if c1 is not None else None, "comp_full_t": c1.t if c1 is not None else None,
                   "n_full": int(c1.n) if c1 is not None else None},
            question="If exposure's partisan face is who holds the jobs (educated women, teleworkers), does political conflict over AI inside "
                     "firms run along occupational and gender lines rather than party lines?",
            next_data="Worker-level panels with party, occupation and AI use (Cooperative Election Study; Gallup Workforce Panel); occupation "
                      "x metro partisanship to hold geography equal",
            caveats=["Gender and race shares exist for about 300 occupations, so the last two models use a smaller sample.",
                     "Occupation partisanship is national; occupations concentrated in Republican regions look Republican for that reason alone."],
            views=["stress-occ-models"], rank=2)
    if lean_g and gone_g:
        regrade("occ-waves", "fragile", f"Stress test (stress-occ): the {lean_g} lean of generative-AI exposure disappears once gender and race are "
                                        "held equal" + (f"; the {lean_c} lean of computerisation risk survives every control." if lean_c else "."))
    elif lean_g:
        regrade("occ-waves", "robust", f"Stress test (stress-occ): the {lean_g} lean of generative-AI exposure survives education, pay, telework, "
                                       "gender, race and occupation group.")
    a0, a3 = get("frs21_aioe", OCC_SPECS[0][0]), get("frs21_aioe", OCC_SPECS[3][0])     # AIOE alone; with gender and race
    if a0 is not None and a3 is not None:
        if abs(a3.t) < 2:
            regrade("occ-ai-education", "robust", f"Stress test (stress-occ): gender and race account for the rest of the lean ({a3.coef:+.1f}, t = {a3.t:.1f}).")
        elif np.sign(a3.coef) != np.sign(a0.coef):
            regrade("occ-ai-education", "robust", f"Stress test (stress-occ): with gender and race held equal the lean reverses ({a3.coef:+.1f}, t = {a3.t:.1f}).")
        else:
            regrade("occ-ai-education", "fragile", f"Stress test (stress-occ): the lean survives gender and race ({a3.coef:+.1f}, t = {a3.t:.1f}), so "
                                                   "education is not the whole story.")
    log(f"stress-occ: {len(have)} measures x {len(OCC_SPECS)} models")
    return True


# --------------------------------------------------------------------------- structure
def _structure():
    ind = read("panel_industry", "PANELS")
    if ind is None or "rep_pred" not in ind:
        return False
    s = ind.dropna(subset=["rep_share", "rep_pred", "workers"])
    s = s[s.occ_coverage >= 0.7].copy()
    if len(s) < 30:
        return False
    s["balance"] = 1 - (2 * s.rep_share - 1).abs()
    s["balance_pred"] = 1 - (2 * s.rep_pred - 1).abs()
    r_share, r_bal = wcorr(s.rep_pred, s.rep_share, s.workers), wcorr(s.balance_pred, s.balance, s.workers)
    keep = [c for c in ("naics4", "title", "sector", "workers", "rep_share", "rep_pred", "balance", "balance_pred", "ind_education") if c in s]
    dataset("stress_structure", s[keep], note="Industries with 70%+ of jobs linked to VRscores occupations.")
    view("stress-structure", "scatter", "Industries: Republican share predicted from occupation mix against the actual share", "stress_structure",
         x=["rep_pred", "balance_pred"], y=["rep_share", "balance"], size="workers", color="sector", text="title",
         labels={"rep_pred": "Predicted from occupation mix", "rep_share": "Actual Republican share", "balance_pred": "Predicted political balance",
                 "balance": "Actual political balance (1 = evenly split)"})
    how_much = lambda r2: ("most" if r2 >= 0.6 else "half" if r2 >= 0.4 else f"{r2:.0%}")  # noqa: E731
    r2s, r2b = (r ** 2 if np.isfinite(r) and r > 0 else 0.0 for r in (r_share, r_bal))
    finding("stress-structure", f"{how_much(r2s).capitalize()} of an industry's partisanship, and {how_much(r2b)} of its political balance, "
                                "is the occupations it employs",
            f"Across {len(s)} industries, the Republican share predicted from national occupation shares and each industry's staffing pattern "
            f"explains {r_share ** 2:.0%} of the variance in the actual share (r = {r_share:.2f}, weighted by workers) and {r_bal ** 2:.0%} of the "
            f"variance in political balance (how evenly split the workforce is; r = {r_bal:.2f}). Workforce 'ideology' and 'balance' measured at "
            "the organisation level therefore mix the occupational structure of the work with any organisational sorting.",
            theme="Stress tests", level="industry", datasets=["VRscores", "OES staffing"], strength="robust",
            stats={"n": len(s), "r2_share": r_share ** 2, "r2_balance": r_bal ** 2},
            question="Does the part of workforce partisanship and balance that occupations do not explain (the elective part) predict "
                     "innovation, where the structural part does not?",
            next_data="Employer x occupation headcounts (Revelio positions behind VRscores) matched to firms; DIPI leadership ideology",
            caveats=["National occupation partisanship is applied to every industry, so the prediction ignores where industries are located."],
            views=["stress-structure"], rank=3)
    return True
