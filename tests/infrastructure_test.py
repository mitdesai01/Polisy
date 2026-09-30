# -*- coding: utf-8 -*-
"""Infrastructure test: the patent, firm, IPUMS and task layers on stand-in files (tests/infra_fixtures.py).

What it does: writes a few rows of PatentsView (granted and pre-grant), the AI Patent Dataset, DISCERN 2.0 (Stata
files keyed by permno_adj), Compustat, an IPUMS USA extract and O*NET in their published layouts, runs the lab's
inventory, the patent-layer adapters, IPUMS, the task matching (when spaCy and an English model are installed) and
the panels, and checks each output against values worked out by hand.
Why: the real files are gigabytes; this checks every code path in seconds before a long run in Colab. It proves the
code handles the layouts, not that any result holds: the stand-in rows are made up.
Usage: python tests/infrastructure_test.py [workdir]
"""
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
WORK = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="polisy_infra_"))
os.environ["POLISY_ROOT"] = str(WORK / "polisy")
os.environ["POLISY_LAB_ROOT"] = str(WORK / "lab")
os.environ["POLISY_SCRATCH"] = str(WORK / "scratch")
sys.path[:0] = [str(HERE.parent / "POLISY_DA"), str(HERE.parent / "lab"), str(HERE)]

import infra_fixtures as fx  # noqa: E402


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    return bool(cond)


def main():
    D = WORK / "data"
    fx.build(D)
    fx.build_firms(D)
    fx.build_ipums(D)
    fx.build_onet(D)
    pd.DataFrame({"gvkey": [6066, 160329], "year": [2020, 2017], "empLiberalism_10yr": [0.4, 0.7], "ceoLiberalism": [0.1, 0.9]}
                 ).to_csv(D / "Organizational_Leadership_File.csv", index=False)
    import polisy_core as pc
    pc.CONFIG["SEARCH_DIRS"] = [str(D)]
    pc.CONFIG.update({k: None for k in pc.FILES})
    panels = Path(pc.CONFIG["PANELS"])
    panels.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"gvkey": ["006066", "184996"], "year": [2020, 2023], "n_vrids": [3, 1], "workers": [900.0, 50.0],
                  "dem": [500.0, 20.0], "rep": [400.0, 30.0], "rep_share": [0.444, 0.6]}).to_parquet(panels / "firm_year.parquet")
    from polisy_lab import run_all, LAB, PATENT_LAYER
    from polisy_lab.core import read
    from polisy_lab import sources as S
    try:
        import spacy
        spacy.load("en_core_web_sm")
        LAB["SETTINGS"].update(webb_run=True, webb_model="en_core_web_sm", webb_generic_share=0.5)
        have_nlp = True
    except Exception:
        have_nlp = False
    ok = []

    # discovery: every new source and role, including gzipped files, codebooks and a folder of Stata files
    roles = {(s, r): S.discover(s, r) for s in ("patentsview", "patentsview_pregrant", "aipd", "discern", "ipums", "onet_tasks")
             for r in S.SOURCES[s]["files"]}
    missing = [f"{s}/{r}" for (s, r), f in roles.items() if not f and r != "cpc_title" and not (s == "patentsview_pregrant" and r == "location")]
    ok.append(check(not missing, f"every new source and role found ({len(roles)} roles; missing: {missing or 'none'})"))
    ok.append(check(len(roles[("discern", "tables")]) == 4, "all four DISCERN files found through their folder"))
    ok.append(check(Path(roles[("ipums", "data")][0][0]).name == "usa_00001.csv.gz" and roles[("ipums", "ddi")],
                    "the IPUMS extract (.csv.gz) and its codebook (.xml) found"))

    run_all(stages=("adapt",), fetch=False, adapters=PATENT_LAYER + ["ipums", "patent_tasks"])
    pt = read("patents").set_index("patent_id")
    ok.append(check(sorted(pt.index) == ["10000001", "10000002", "10000005", "11000006", "11000007", "4000008"],
                    "utility patents only: the design and the withdrawn patent are dropped"))
    ok.append(check(pt.app_year.to_dict() == {"10000001": 2017, "10000002": 2018, "10000005": 2019, "11000006": 2020,
                                              "11000007": 2021, "4000008": 1975}, "filing years from g_application"))
    ok.append(check(pt.ai["10000001"] and not pt.ai["11000006"] and pt.ai_broad["10000002"] and not pt.ai["10000002"]
                    and pt.sub_language["11000007"], "CPC AI flags: G06N yes, quantum G06N10 no, vision and language broad only"))
    ok.append(check(pt.climate["10000002"] and pt.weapons["10000005"] and pt.weapons["4000008"] and not pt.climate["10000001"],
                    "climate (Y02) and weapons (F41/F42) flags"))
    ok.append(check(pt.ai_aipd["10000001"] and not pt.ai_aipd["10000005"] and pd.isna(pt.ai_aipd["11000007"])
                    and pt.ai_aipd_strict["10000002"], "AI Patent Dataset labels joined; empty where it has no row"))
    ok.append(check(pt.assignee_type["10000005"] == 3 and pt.n_inventors["10000002"] == 2 and pt.n_us_inventors["10000002"] == 1,
                    "assignee type from '3.0'; foreign inventors counted but not placed"))
    g = pd.read_parquet(Path(LAB["STAGED"]) / "patentsview" / "g_patent.parquet").set_index("patent_id")
    ok.append(check(g.title["10000002"] == 'System for "detecting" and classifying objects in images\twith solar panels',
                    "quoted text with doubled quotes and a tab survives staging"))
    pp = read("patent_places").set_index("patent_id")
    ok.append(check(pp.county_fips["10000001"] == "06085" and pp.share["10000002"] == 0.5 and pp.state_fips["11000006"] == "36",
                    "places: county from state 6 + county 85, share 1/2 with a foreign co-inventor, state from 'NY'"))
    ap = read("applications").set_index("pgpub_id")
    ok.append(check(sorted(ap.index) == ["20170000001", "20230000002", "20240000004"] and ap.granted_patent_id["20170000001"] == "10000001"
                    and ap.ai_aipd["20230000002"] and ap.climate["20240000004"],
                    "applications: a republication counted once, the granted one linked, AIPD and CPC flags"))
    iy = read("inventions_year").set_index("year")
    ok.append(check(iy.patents[2018] == 1 and iy.applications[2022] == 1 and iy.applications_granted[2017] == 1,
                    "inventions by filing year: patents and applications"))

    dp = read("discern_patents").set_index("patent_id")
    ok.append(check(dp.gvkey.to_dict() == {"10000001": "160329", "10000002": "006066", "5500000": "006066"},
                    "DISCERN: patent numbers stored as numbers, owners from permno_adj through the permno-gvkey file"))
    ag = read("assignee_gvkey").set_index("assignee_id")
    ok.append(check(ag.gvkey.get("as-ibm") == "006066" and ag.gvkey.get("as-goog") == "160329" and "as-oai" not in ag.index,
                    "names: IBM matched to Compustat's INTL BUSINESS MACHINES, Google to Alphabet through DISCERN's names"))
    pf = read("patent_firm").set_index("patent_id")
    ok.append(check(pf.link.to_dict() == {"10000001": "discern", "10000002": "discern", "11000006": "name"},
                    "patent -> firm: DISCERN first, the name match after DISCERN's last year"))
    fp = read("firm_patents_year", "PANELS").set_index(["gvkey", "year"])
    ibm18, ibm20 = fp.loc[("006066", 2018)], fp.loc[("006066", 2020)]
    ok.append(check(ibm18.pat_filed == 1 and ibm18.ai_filed == 1 and ibm18.climate_filed == 1 and ibm18.explore_filed == 1
                    and ibm20.explore_filed == 1 and ibm20.new_subclasses == 1 and ibm20.prior_patents == 1,
                    "firm panel: counts by filing year, a class new to the firm, the firm's history"))
    ok.append(check(abs(ibm20.search_depth - 0.5) < 1e-9 and abs(ibm20.search_scope - 0.5) < 1e-9 and ibm18.search_scope == 1,
                    "Katila-Ahuja: one of two 2020 citations repeats a 2018 one -> depth 0.5, scope 0.5"))
    ok.append(check(fp.loc[("184996", 2023)].apps_pending == 1 and fp.loc[("160329", 2017)].apps_filed == 1,
                    "published applications: a pending one by assignee name, a granted one through its patent"))
    tables = Path(LAB["RESULTS"]) / "tables"
    ok.append(check((tables / "firm_patents_year.csv").exists() and (tables / "firm_patents_year.dta").exists(),
                    "firm panel exported as CSV and Stata"))
    run_all(stages=("link",), fetch=False)
    pfy = read("panel_firm_year", "PANELS").set_index(["gvkey", "year"])
    ok.append(check(pfy.loc[("006066", 2020)].vr_workers == 900 and pfy.loc[("006066", 2020)].dipi_empLiberalism_10yr == 0.4,
                    "panel_firm_year joins the VRscores workforce (POLISY_DA) and DIPI"))

    occ = read("acs_occupation").set_index("occsoc")
    ok.append(check(abs(occ.female["151252"] - 2 / 3) < 1e-9 and abs(occ.graduate["151252"] - 1 / 3) < 1e-9
                    and occ.inferred_party_states["1191XX"] == 1, "IPUMS: weighted shares; Texas counts as an inferred-party state"))
    from polisy_lab.adapters.ipums import occsoc_for
    ok.append(check(occsoc_for("47-2061", occ.index) == "4720XX" and occsoc_for("15-1252", occ.index) == "151252",
                    "SOC 2018 codes find their OCCSOC code, X digits as wildcards"))
    from polisy_lab import link
    extra = link._occupation_extras(pd.DataFrame({"soc": ["15-1252", "29-1216", None], "workers": [10.0, 5.0, 1.0]}))
    ok.append(check(extra.acs_workers.iloc[0] == 150 and extra.soc_key.isna().iloc[2], "occupation panel gets the ACS profile"))

    if have_nlp:
        inc = read("patent_occ_incidence")
        hit = inc[inc.doc_id == "10000001"]
        ok.append(check(len(hit) and (hit.soc == "29-1216").any() and abs(inc.groupby("doc_id").incidence.sum() - 1).max() < 1e-9,
                        "task matching: the diagnosis patent targets physicians; each invention's incidence sums to one"))
        ok.append(check(read("occ_ai_invention") is not None and "webb_ai_invention" in extra,
                        "Webb exposure by period, joined to the occupation panel"))
    else:
        print("  skip task matching: spaCy or en_core_web_sm not installed")
    print(f"\n{sum(ok)} of {len(ok)} checks passed; files in {WORK}")
    return all(ok)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
