# -*- coding: utf-8 -*-
"""Smoke test: the whole pipeline on small synthetic downloads with realistic file names.

What it does: writes fake inputs under the names they really arrive with ("(1)" copies,
renamed and unzipped dataverse_files zips, a WRDS random name, a .tab county file, the
Census list with its title rows, an unzipped OEWS folder), runs modules 01 to 10 on them,
and checks that every input was found and that DIPI and the CBSA reference made it into
the outputs.
Why: the file finder in polisy_core is only worth something if it survives the names
people actually end up with. Run this after changing FILES, locate() or a module.
Usage: python tests/smoke_test.py [workdir]      (needs pandas, duckdb, openpyxl, rapidfuzz,
matplotlib, pyarrow; no network)
"""
import json
import os
import random
import runpy
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORK = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="polisy_smoke_"))
DL = WORK / "downloads"
os.environ["POLISY_ROOT"] = str(WORK / "polisy")
os.environ["POLISY_LAB_ROOT"] = str(WORK / "lab")
sys.path[:0] = [str(HERE.parent / "POLISY_DA"), str(HERE.parent / "lab")]

rng = np.random.default_rng(7)
random.seed(7)
YEARS = [2012, 2013, 2014, 2015]
CITIES = ["Springfield", "Riverton", "Lakewood", "Fairview", "Greenville", "Madison", "Clayton",
          "Georgetown", "Salem", "Franklin", "Ashland", "Burlington", "Dover", "Milton", "Oxford",
          "Clinton", "Kingston", "Newport", "Arlington", "Bristol", "Auburn", "Dayton", "Lexington",
          "Hudson", "Marion", "Jackson", "Monroe", "Chester", "Warren", "Ontario"]
TOWNS = ["Oakdale", "Pinehurst", "Brookfield", "Elmwood", "Westfield", "Hillcrest", "Maplewood",
         "Stonebridge", "Rosedale", "Fairmont", "Glendale", "Ridgeway", "Belmont", "Bayside",
         "Crestview", "Northgate", "Southport", "Easton", "Weston", "Highland", "Lakeside",
         "Parkside", "Riverside", "Woodland", "Meadow", "Summit", "Valley", "Harbor", "Mill", "Grove"]
STATES = [("AL", "01", "Alabama"), ("TX", "48", "Texas"), ("OH", "39", "Ohio"), ("CA", "06", "California"),
          ("NY", "36", "New York"), ("GA", "13", "Georgia")]
METROS = []
for i, (city, town) in enumerate(zip(CITIES, TOWNS)):
    st, sfips, sname = STATES[i % len(STATES)]
    METROS.append({"cbsa": f"{10020 + 20 * i}", "city": city, "town": town, "st": st, "sfips": sfips,
                   "sname": sname, "counties": [f"{3 + 2 * i:03d}", f"{5 + 2 * i:03d}"]})
# a VRscores metro named after a place that is a principal city (List 2) but in no CBSA title,
# like Anderson, IN, which is part of Indianapolis today
PORT = METROS[2]
PORT_MSA = f"Port {PORT['city']} {PORT['st']} MSA"
OCCS = [f"{g}-{1000 + 11 * k}" for g in ("11", "13", "15", "17", "19", "25", "29", "41", "43", "47", "51", "53")
        for k in range(4)]
FIRMS = [f"{a} {b}" for a in ("Acme", "Globex", "Initech", "Umbrella", "Stark", "Wayne", "Wonka", "Tyrell",
                              "Cyberdyne", "Soylent") for b in ("Widgets", "Energy", "Foods", "Systems",
                                                                "Logistics", "Media", "Health", "Motors")]


def zip_dir(members, dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def counts(n):
    dem = rng.integers(10, 400, n)
    rep = rng.integers(10, 400, n)
    return dem, rep


def vr_frame(key_col, keys, year, extra=None):
    dem, rep = counts(len(keys))
    df = pd.DataFrame({key_col: keys, "dem_workers_raw": dem - 3, "rep_workers_raw": rep - 3,
                       "dem_workers_imp": dem, "rep_workers_imp": rep})
    df["republican_pct_two_party_imp"] = rep / (dem + rep)
    for k, v in (extra or {}).items():
        df[k] = v
    return df


def build():
    DL.mkdir(parents=True, exist_ok=True)
    raw = WORK / "polisy" / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    firm_dem = {}

    # VRscores: four downloads that are all called dataverse_files.zip
    msa_names = ([f"{m['city']}-{m['town']} {m['st']} MSA" for m in METROS]
                 + [PORT_MSA, "Atlantis-Ocean ZZ MSA"])  # a metro known only from List 2; one with no CBSA
    msa = {f"msa_panel_year_{y}.tab": vr_frame("msa", msa_names, y)
           .to_csv(index=False) for y in YEARS}
    zip_dir({**msa, "codebook.md": "# VRscores MSA panel"}, DL / "dataverse_files.zip")
    emp = {}
    for y in YEARS:
        names = FIRMS + [f"Private Employer {k}" for k in range(120)]
        df = vr_frame("vrid", [f"VR{k:05d}" for k in range(len(names))], y,
                      {"company_name": names, "employee_count": rng.integers(30, 3000, len(names)),
                       "avg_match_quality": rng.random(len(names))})
        for k, name in enumerate(FIRMS):
            firm_dem[(k, y)] = 1 - df.republican_pct_two_party_imp.iloc[k]
        ext = "tab" if y < 2015 else "csv"
        emp[f"employer_panel_year_{y}.{ext}"] = df.to_csv(index=False)
    zip_dir({**emp, "codebook.md": "# VRscores employer panel"}, DL / "dataverse_files (1).zip")
    zip_dir({f"naics_panel_year_{y}.csv": vr_frame("naics_code", ["541511", "541512", "336411", "622110", "445110"], y)
             .to_csv(index=False) for y in YEARS}, DL / "dataverse_files (2).zip")
    occ_dir = DL / "dataverse_files (3)"                     # unzipped by the browser
    occ_dir.mkdir(exist_ok=True)
    for y in YEARS:
        vr_frame("onet_code", [o + ".00" for o in OCCS] + ["Retired"], y).to_csv(
            occ_dir / f"occupation_panel_year_{y}.csv", index=False)

    # Compustat under a WRDS random name, gvkeys without leading zeros
    comp = pd.DataFrame([{"gvkey": 1000 + k, "datadate": f"{y}1231", "fyear": y, "indfmt": "INDL",
                          "conm": name.upper() + " INC", "state": "TX", "emp": 0.9}
                         for k, name in enumerate(FIRMS) for y in YEARS])
    comp.to_csv(DL / "rq8xk2mz1vbdqpf3.csv", index=False)

    # DIPI: spaces instead of underscores, a "(1)" copy, GVKEY in capitals, unpadded
    dipi = pd.DataFrame([{"GVKEY": 1000 + k, "year": y, "conm": name.upper() + " INC",
                          "empLiberalism_10yr": float(np.clip(firm_dem[(k, y)] + rng.normal(0, .05), 0, 1)),
                          "empLiberalism_5yr": rng.random(), "tmtLiberalism_10yr": rng.random(),
                          "ceoLiberalism_10yr": rng.random()}
                         for k, name in enumerate(FIRMS) for y in YEARS])
    dipi.to_csv(DL / "Organizational Leadership File (1).csv", index=False)

    # Census List 1 with its two title rows and footnotes, saved as a "(1)" copy
    head = ["CBSA Code", "Metropolitan Division Code", "CSA Code", "CBSA Title",
            "Metropolitan/Micropolitan Statistical Area", "Metropolitan Division Title", "CSA Title",
            "County/County Equivalent", "State Name", "FIPS State Code", "FIPS County Code",
            "Central/Outlying County"]
    rows = [["List 1. Core Based Statistical Areas (CBSAs), Metropolitan Divisions, and Combined "
             "Statistical Areas (CSAs)"] + [None] * 11, ["July 2023"] + [None] * 11, head]
    for m in METROS:
        for j, cty in enumerate(m["counties"]):
            rows.append([m["cbsa"], None, None, f"{m['city']}-{m['town']}, {m['st']}",
                         "Metropolitan Statistical Area", None, None, f"County {cty}", m["sname"],
                         m["sfips"], cty, "Central" if j == 0 else "Outlying"])
    rows += [[None] * 12, ["Note: synthetic delineation for tests"] + [None] * 11,
             ["Source: File prepared by U.S. Census Bureau, Population Division"] + [None] * 11]
    pd.DataFrame(rows).to_excel(DL / "list1_2023 (1).xlsx", header=False, index=False)
    # Census List 2: principal cities, more of them than the titles name
    rows = [["List 2. Principal Cities of Metropolitan and Micropolitan Statistical Areas"] + [None] * 5,
            ["July 2023"] + [None] * 5,
            ["CBSA Code", "CBSA Title", "Metropolitan/Micropolitan Statistical Area", "Principal City Name",
             "FIPS State Code", "FIPS Place Code"]]
    for m in METROS:
        for k, place in enumerate((m["city"], m["town"], f"Port {m['city']}")):
            rows.append([m["cbsa"], f"{m['city']}-{m['town']}, {m['st']}", "Metropolitan Statistical Area", place,
                         m["sfips"], f"{1000 + k:05d}"])
    rows += [[None] * 6, ["Note: synthetic principal cities for tests"] + [None] * 5]
    pd.DataFrame(rows).to_excel(DL / "list2_2023.xlsx", header=False, index=False)

    # MIT county returns as Dataverse's default .tab; 2020 has TOTAL rows plus mode rows
    votes = []
    for m in METROS:
        for cty in m["counties"]:
            fips = str(int(m["sfips"] + cty))                  # "01003" -> "1003", as MIT writes it
            for y in (2012, 2016, 2020):
                d, r = int(rng.integers(1000, 9000)), int(rng.integers(1000, 9000))
                for party, v in (("DEMOCRAT", d), ("REPUBLICAN", r), ("OTHER", 50)):
                    votes.append({"year": y, "state": m["sname"].upper(), "state_po": m["st"],
                                  "county_name": f"COUNTY {cty}", "county_fips": fips, "office": "US PRESIDENT",
                                  "candidate": party, "party": party, "candidatevotes": v, "totalvotes": d + r + 50,
                                  "version": 20250101, "mode": "TOTAL"})
                    if y == 2020:
                        votes += [dict(votes[-1], mode="ABSENTEE", candidatevotes=v // 2),
                                  dict(votes[-1], mode="ELECTION DAY", candidatevotes=v - v // 2)]
    pd.DataFrame(votes).to_csv(DL / "countypres_2000-2024.tab", sep="\t", index=False)

    # OEWS: national zip, metro area folder unzipped by the browser, industry as a "(1)" copy
    def oews(area, title, atype, naics="000000", igroup="cross-industry"):
        out = [{"AREA": area, "AREA_TITLE": title, "AREA_TYPE": atype, "NAICS": naics, "I_GROUP": igroup,
                "OCC_CODE": "00-0000", "OCC_TITLE": "All", "O_GROUP": "total", "TOT_EMP": "999999",
                "A_MEAN": "60000", "A_MEDIAN": "50000"}]
        for o in OCCS:
            out.append({"AREA": area, "AREA_TITLE": title, "AREA_TYPE": atype, "NAICS": naics, "I_GROUP": igroup,
                        "OCC_CODE": o, "OCC_TITLE": f"Occ {o}", "O_GROUP": "detailed",
                        "TOT_EMP": f"{int(rng.integers(6000, 90000)):,}", "A_MEAN": "70000",
                        "A_MEDIAN": "#" if o.endswith("1033") else str(int(rng.integers(30000, 150000)))})
        return out

    def xlsx(rows_):
        buf = __import__("io").BytesIO()
        pd.DataFrame(rows_).to_excel(buf, index=False)
        return buf.getvalue()

    zip_dir({"oesm24nat/national_M2024_dl.xlsx": xlsx(oews("99", "U.S.", "1")),
             "oesm24nat/file_descriptions.xlsx": xlsx([{"Field": "AREA"}])}, DL / "oesm24nat.zip")
    (DL / "oesm24ma").mkdir(exist_ok=True)
    pd.DataFrame([r for m in METROS for r in oews(m["cbsa"], f"{m['city']}-{m['town']}, {m['st']}", "4")]
                 + oews("0100001", "Northwest Alabama nonmetropolitan area", "6")).to_excel(
        DL / "oesm24ma" / "MSA_M2024_dl.xlsx", index=False)
    zip_dir({"oesm24in4/nat4d_M2024_dl.xlsx": xlsx([r for n in ("541500", "336400", "622100", "445100")
                                                    for r in oews("99", "U.S.", "1", n, "4-digit")])},
            DL / "oesm24in4 (1).zip")

    # O*NET job zones and AIOE, as module 05 would have saved them
    jz = "O*NET-SOC Code\tJob Zone\tDate\tDomain Source\n" + "".join(
        f"{o}.00\t{random.randint(1, 5)}\t08/2024\tAnalyst\n" for o in OCCS)
    zip_dir({"db_29_0_text/Job Zones.txt": jz, "db_29_0_text/Read Me.txt": "O*NET"}, raw / "db_29_0_text.zip")
    with pd.ExcelWriter(raw / "AIOE_DataAppendix.xlsx") as xw:
        pd.DataFrame({"Read me": ["This file holds the AIOE, AIIE and AIGE scores."]}).to_excel(xw, sheet_name="Read Me", index=False)
        pd.DataFrame({"SOC Code": OCCS, "Occupation Title": OCCS, "AIOE": rng.normal(0, 1, len(OCCS))}).to_excel(
            xw, sheet_name="Appendix A", index=False)
        pd.DataFrame({"NAICS": ["5415"], "Industry Title": ["x"], "AIIE": [0.3]}).to_excel(xw, sheet_name="Appendix B", index=False)

    # ACS metro json, as module 05 would have saved it
    acs = [["NAME", "B01003_001E", "B19013_001E", "B23025_004E", "B15003_022E", "B15003_001E", "B01002_001E",
            "metropolitan statistical area/micropolitan statistical area"]]
    acs += [[f"{m['city']}-{m['town']}, {m['st']} Metro Area", "500000", "60000", "250000", "90000", "330000",
             "38.5", m["cbsa"]] for m in METROS]
    (raw / "acs1_2015.json").write_text(json.dumps(acs))
    (raw / "acs1_2022.json").write_text("error: You included a key with this request, however, it is not valid.")
    # ACS saved by hand as one CSV for two years, in an older delineation: METROS[1] under an old
    # code, and a separate "Port" metro that is part of PORT's CBSA today
    old = [{"NAME": f"{m['city']}-{m['town']}, {m['st']} Metro Area", "CBSA": "99901" if m is METROS[1] else m["cbsa"],
            "B01003_001E": 400000 + k, "B19013_001E": 50000, "B23025_004E": 200000, "B15003_022E": 60000,
            "B15003_001E": 260000, "B01002_001E": 37.0, "year": y}
           for y in (2012, 2013) for k, m in enumerate(METROS)]
    old.append({"NAME": f"Port {PORT['city']}, {PORT['st']} Metro Area", "CBSA": "99902", "B01003_001E": 100000,
                "B19013_001E": 40000, "B23025_004E": 50000, "B15003_022E": 10000, "B15003_001E": 65000,
                "B01002_001E": 42.0, "year": 2012})
    pd.DataFrame(old).to_csv(DL / "ACS_MSA_2012_2013.csv", index=False)

    # noise a real downloads folder has
    (DL / "notes.txt").write_text("to do: thesis chapter 3")
    pd.DataFrame({"a": [1], "b": [2]}).to_csv(DL / "sample.csv", index=False)


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    return bool(cond)


def main():
    build()
    import polisy_core as pc
    pc.CONFIG["SEARCH_DIRS"] = [DL]                                # only the fake downloads, whatever this machine has
    pc.CONFIG.update({key: None for key in pc.FILES})              # no preset paths either
    pc.CONFIG["VR_EMPLOYER"] = str(DL / "dataverse_files.zip")    # a wrong path on purpose: holds the MSA panel
    results = {step: pc.run(step) for step in ("01", "02", "03", "04")}
    results.update({step: pc.run(step) for step in ("06", "07", "08", "09", "10")})

    out, keys = Path(pc.CONFIG["OUT"]) / "tables", Path(pc.CONFIG["KEYS"])
    files = pd.read_csv(out / "01_files.csv").set_index("input")
    ok = [check((files.status == "ok").all(), f"every input found: {files.status.to_dict()}")]
    ok.append(check(files.loc["VR_EMPLOYER", "path"].endswith("dataverse_files (1).zip")
                    and "ignored" in files.loc["VR_EMPLOYER", "note"],
                    "a CONFIG path holding the wrong panel is ignored and the right zip found"))
    ok.append(check(files.loc["VR_OCCUPATION", "path"].endswith("dataverse_files (3)"), "unzipped VRscores folder used"))
    ok.append(check(files.loc["COMPUSTAT", "found_by"] == "file contents", "Compustat found under a WRDS random name"))
    ok.append(check(files.loc["DIPI", "path"].endswith("Organizational Leadership File (1).csv"), "DIPI found"))
    ok.append(check(files.loc["CBSA_REFERENCE", "path"].endswith("list1_2023 (1).xlsx"), "CBSA List 1 found, List 2 ignored"))
    dipi = pd.read_parquet(Path(pc.CONFIG["CANONICAL"]) / "dipi.parquet")
    ok.append(check(dipi.gvkey.str.fullmatch(r"\d{6}").all() and not dipi.duplicated(["gvkey", "year"]).any(),
                    f"dipi.parquet at (gvkey, year) with 6-digit gvkeys ({len(dipi)} rows)"))
    county = pd.read_csv(keys / "cw_cbsa_county.csv", dtype=str)
    ok.append(check(len(county) == 2 * len(METROS) and county.county_fips.str.fullmatch(r"\d{5}").all()
                    and county.county_fips.str.startswith("01").any(), "county links with zero-padded FIPS"))
    cw = pd.read_csv(keys / "cw_msa_cbsa.csv", dtype=str)
    ok.append(check(cw.cbsa.notna().sum() == len(METROS) + 1 and cw.loc[cw.cbsa.isna(), "msa"].tolist() == ["Atlantis-Ocean ZZ MSA"],
                    "every real VRscores metro matched to a CBSA, the made-up one left unmatched"))
    port = cw.set_index("msa").loc[PORT_MSA]
    ok.append(check(port.cbsa == PORT["cbsa"] and port.match_method == "principal city",
                    "a metro named after a principal city in no title found through List 2"))
    ok.append(check(files.loc["CBSA_PRINCIPAL_CITIES", "path"].endswith("list2_2023.xlsx")
                    and files.loc["ACS_METRO", "status"] == "ok", "List 2 and the ACS tables found"))
    metro = pd.read_parquet(Path(pc.CONFIG["PANELS"]) / "metro_year.parquet")
    ok.append(check(metro.loc[metro.cbsa.notna(), "rep_vote_share"].notna().all() and metro.cbsa.isna().any()
                    and metro.population.notna().any(), "metro panel carries vote shares and ACS; unmatched metro kept"))
    real = metro[metro.msa.isin([f"{m['city']}-{m['town']} {m['st']} MSA" for m in METROS])]
    ok.append(check((real.acs_year == real.year.clip(upper=2013).where(real.year < 2015, 2015)).all(),
                    "each metro-year gets the latest ACS year at or before it (CSV 2012-13, API download 2015)"))
    acs = pd.read_parquet(Path(pc.CONFIG["CANONICAL"]) / "acs_metro.parquet").set_index(["cbsa", "year"])
    ok.append(check(acs.loc[(METROS[1]["cbsa"], 2012), "population"] == 400001,
                    "an ACS area under an older code matched to today's CBSA by name"))
    ok.append(check(acs.loc[(PORT["cbsa"], 2012), "acs_areas"] == 2 and acs.loc[(PORT["cbsa"], 2012), "population"] == 400002 + 100000,
                    "older areas that are one CBSA today are added up"))
    ok.append(check(2022 not in set(acs.reset_index().year), "an API reply that is not a data table is skipped, not read"))
    one = pd.read_csv(DL / "countypres_2000-2024.tab", sep="\t", dtype=str)
    one = one[(one.year == "2020") & (one["mode"] == "TOTAL") & one.party.isin(["DEMOCRAT", "REPUBLICAN"])]
    cbsa0 = county[county.cbsa == METROS[0]["cbsa"]].county_fips.str.lstrip("0")
    want = one[one.county_fips.isin(cbsa0)].candidatevotes.astype(int).sum()
    votes = runpy.run_path(str(HERE.parent / "POLISY_DA" / "06_merging.py"), run_name="smoke")["load_votes"](pc.paths())
    got = votes[(votes.cbsa == METROS[0]["cbsa"]) & (votes.year == 2020)][["DEMOCRAT", "REPUBLICAN"]]
    ok.append(check(len(got) == 1 and int(got.iloc[0].sum()) == int(want),
                    f"2020 votes counted once despite TOTAL plus mode rows ({int(want):,})"))
    val = pd.read_csv(out / "07_validation.csv")
    ok.append(check(val.gate.str.contains("DIPI").any(), "module 07 ran the DIPI gates"))
    occ = pd.read_parquet(Path(pc.CONFIG["PANELS"]) / "occupation_year.parquet")
    ok.append(check(occ.tot_emp.notna().all() and occ.job_zone.notna().all() and occ.aioe.notna().all(),
                    "occupation panel carries OEWS, O*NET job zones and AIOE"))
    ok.append(check((out / "10_metro_inventive.csv").exists(), "module 10 metro correlation ran"))

    # the lab on POLISY_DA's panels: the path a full-data run takes (and a table left over from a report-based run)
    from polisy_lab.adapters.politics import adapt_vrscores
    from polisy_lab.core import LAB
    canon = Path(LAB["CANONICAL"])
    canon.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"employer": ["from the report"], "source": ["report"]}).to_parquet(canon / "vr_employer_summary.parquet")
    ran = adapt_vrscores()
    want = ("vr_occupation_year", "vr_industry_year", "vr_metro_year", "vr_employer_summary", "vr_sorting")
    tabs = {t: pd.read_parquet(canon / f"{t}.parquet") for t in want if (canon / f"{t}.parquet").exists()}
    ok.append(check(ran and len(tabs) == len(want) and all((t.source == "panels").all() and len(t) for t in tabs.values()),
                    f"the lab's VRscores adapter builds every table from the panels, replacing report leftovers ({sorted(tabs)})"))
    print(f"\n{sum(ok)} of {len(ok)} checks passed; files in {WORK}")
    return all(ok)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
