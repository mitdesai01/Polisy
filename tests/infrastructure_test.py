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
    ok.append(check(len(roles[("discern", "tables")]) == 6, "all six DISCERN files found through their folder"))
    from polisy_lab.adapters import firms as F
    sub = ["id_name", "sample", "name_std", "country_code", "subdiv_code"] + [f"{x}{k}" for k in range(1, 9) for x in ("fyear", "nyear", "permno_adj")]
    uo = ["id_name", "sample", "name_std"] + [f"{x}{k}" for k in range(1, 7) for x in ("fyear", "nyear", "permno_adj", "name_acq")]
    kinds = [F._classify(c, f)[0] for c, f in [
        (["patent_id", "patent_date", "assignee_name", "fyear", "name_std", "id_name", "sample", "permno_adj"], "discern_pat_grant_1980_2021.csv"),
        (["openalex_id", "earliest_pub_date", "openalex_date", "crossref_date", "fyear", "name_std", "id_name", "sample", "permno_adj"], "discern_pub_1980_2021.csv"),
        (sub, "discern_sub_names.csv"), (uo, "discern_uo_names.csv"),
        (["gvkey", "linkprim", "liid", "linktype", "lpermno", "lpermco", "linkdt", "linkenddt", "conm"], "ccmxpf_lnkhist.csv")]]
    ok.append(check(kinds == ["patents", "publications", "names", "names", "crosswalk"] and len(F._classify(sub)[1]["spells"]) == 8,
                    "DISCERN 2.0's real layouts: patents, publications (skipped), names with 8 owner spells, WRDS link table"))
    ok.append(check(F._by_years(["100001", "100002"], 1995, 2023, {"100001": (1980, 2014), "100002": (2015, 2021)}) == "100002"
                    and F._by_years(["a", "b"], 2000, 2005, {"a": (1990, 2010), "b": (2011, 2020)}) == "a",
                    "a name two firms held goes to the one that held it last within the assignee's years"))
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
                    "DISCERN: owners from permno_adj (stored as 90319.0) through the permno-gvkey file, by year"))
    fy = read("discern_firm_year").set_index(["gvkey", "year"])
    ok.append(check(sorted(fy.index) == [("006066", 2020), ("160329", 2019)] and fy.n_patents[("006066", 2020)] == "9000",
                    "DISCERN's firm panel keyed by permno_adj gets its gvkey"))
    dn = pd.read_parquet(Path(LAB["STAGED"]) / "discern" / "names.parquet").set_index(["gvkey", "name"])
    ok.append(check(tuple(dn.loc[("100001", "HECKLER & KOCH GMBH")]) == (1991, 2014) and tuple(dn.loc[("100002", "HECKLER & KOCH GMBH")]) == (2015, 2021)
                    and tuple(dn.loc[("160329", "ALPHABET INC")]) == (2015, 2021),
                    "DISCERN names: every owner spell, its years from a count (sub names) or a last year (owner names)"))
    ag = read("assignee_gvkey").set_index("assignee_id")
    ok.append(check(ag.gvkey.get("as-ibm") == "006066" and ag.gvkey.get("as-goog") == "160329" and "as-oai" not in ag.index
                    and ag.gvkey.get("as-hk") == "100002",
                    "names: IBM matched to Compustat's INTL BUSINESS MACHINES, Google through DISCERN's names, Heckler & Koch "
                    "to its later owner"))
    pf = read("patent_firm").set_index("patent_id")
    ok.append(check(pf.link.to_dict() == {"10000001": "discern", "10000002": "discern", "10000005": "name", "11000006": "name"},
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

    # DISCERN without a permno-gvkey file: WRDS's link table (primary links, by year), else Compustat's LPERMNO
    import polisy_core as pc
    d = D / "discern"
    only = [d / "discern_pat_grant_1980_2021.csv", d / "discern_pub_1980_2021.csv", d / "discern_sub_names.csv", d / "discern_uo_names.csv"]
    want = {"10000001": "160329", "10000002": "006066", "5500000": "006066"}
    pc.CONFIG.update(LAB_DISCERN_TABLES=only, LAB_DISCERN_LINKS=[D / "ccmxpf_lnkhist.csv"])
    F.adapt_discern()
    via_ccm = read("discern_patents").set_index("patent_id").gvkey.to_dict()
    pc.CONFIG.update(LAB_DISCERN_LINKS=[only[1]])           # no link table: only Compustat's LPERMNO is left
    F.adapt_discern()
    via_comp = read("discern_patents").set_index("patent_id").gvkey.to_dict()
    bare = WORK / "elsewhere" / "Compustat_Final.csv"          # a Compustat extract without LPERMNO, outside the search folders
    bare.parent.mkdir(exist_ok=True)
    pd.read_csv(D / "Compustat_Final.csv").drop(columns="LPERMNO").to_csv(bare, index=False)
    pc.CONFIG["COMPUSTAT"] = str(bare)
    F.adapt_discern()
    kept = (Path(LAB["CANONICAL"]) / "discern_patents.parquet").exists()
    for k in ("LAB_DISCERN_TABLES", "LAB_DISCERN_LINKS", "COMPUSTAT"):
        pc.CONFIG[k] = None
    ok.append(check(via_ccm == want and via_comp == want and not kept,
                    "no permno-gvkey file: WRDS's link table, else Compustat's LPERMNO; with neither, no DISCERN table is kept"))

    occ = read("acs_occupation").set_index("occsoc")
    ok.append(check(abs(occ.female["151252"] - 2 / 3) < 1e-9 and abs(occ.graduate["151252"] - 1 / 3) < 1e-9
                    and occ.inferred_party_states["1191XX"] == 1, "IPUMS: weighted shares; Texas counts as an inferred-party state"))
    import numpy as np
    ok.append(check(abs(occ.log_wage_ft["151252"] - (100 * np.log(150000) + 50 * np.log(200000)) / 150) < 1e-9
                    and pd.isna(occ.log_wage_ft["4720XX"]), "IPUMS: log wage of full-time workers; a worker with no wage is left out"))
    from polisy_lab.adapters.ipums import occsoc_for
    ok.append(check(occsoc_for("47-2061", occ.index) == "4720XX" and occsoc_for("15-1252", occ.index) == "151252",
                    "SOC 2018 codes find their OCCSOC code, X digits as wildcards"))
    grouped = ["112030", "1120XX", "151252", "4750YY", "13102X"]
    ok.append(check([occsoc_for(s, grouped) for s in ("11-2032", "15-1252", "47-5041", "13-1023", "15-1132")]
                    == ["112030", "151252", "4750YY", "13102X", None],
                    "OCCSOC groups: a broad SOC code (trailing zero), X or Y; a SOC 2010 code alone finds none"))
    from polisy_lab.adapters.politics import THEMES
    import re as _re
    tags = {d: [t for t, rx in THEMES.items() if _re.search(rx, d.lower())] for d in (
        "frent rent control law", "gayempnondisc employment nondiscrimination for sexual orientation",
        "citizen_ig number of citizen interest groups", "citi6013 citizen ideology (berry et al.)",
        "hs_dem_prop share of house seats held by democrats", "gsp gross state product")}
    ok.append(check([tags[d] for d in tags] == [[], [], [], ["ideology"], ["party control"], ["economy"]],
                    "CSPP themes: rent control is not party control, nondiscrimination law not economy"))
    from polisy_lab import link
    extra = link._occupation_extras(pd.DataFrame({"soc": ["15-1252", "29-1216", None], "workers": [10.0, 5.0, 1.0]}))
    ok.append(check(extra.acs_workers.iloc[0] == 150 and extra.soc_key.isna().iloc[2], "occupation panel gets the ACS profile"))
    old = link._occupation_extras(pd.DataFrame({"soc": ["15-1132"], "soc2018": ["15-1252"], "workers": [1.0]}))
    ok.append(check(old.acs_workers.iloc[0] == 150, "a code the ACS lacks (SOC 2010) falls back to its SOC 2018 link"))

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
