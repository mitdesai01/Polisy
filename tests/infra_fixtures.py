# -*- coding: utf-8 -*-
"""Stand-in files in the published layouts of PatentsView (granted and pre-grant), the USPTO AI Patent Dataset,
DISCERN 2.0, Compustat, IPUMS USA and O*NET, for tests/infrastructure_test.py.

They exercise code paths only: a few made-up rows per table, with the real file names, column names, quoting and
formats (PatentsView's quoted TSV zips, DISCERN's CSV files keyed by permno_adj, an IPUMS CSV and a fixed-width extract with
its codebook). No result is ever computed from them.
"""
import gzip
import io
import zipfile
import pandas as pd


def pv_zip(path, header, rows):
    """A PatentsView table: tab-separated, text fields in double quotes (doubled inside), numbers bare."""
    buf = io.StringIO()
    def cell(v):
        if v is None: return ""
        if isinstance(v, (int, float)): return str(v)
        return '"' + str(v).replace('"', '""') + '"'
    buf.write("\t".join(cell(h) for h in header) + "\n")
    for r in rows:
        buf.write("\t".join(cell(v) for v in r) + "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(path.name[:-4], buf.getvalue())


def build(D):
    pv, pg = D / "patentsview", D / "patentsview"
    pv_zip(pv / "g_patent.tsv.zip", ["patent_id", "patent_type", "patent_date", "patent_title", "wipo_kind", "num_claims", "withdrawn", "filename"], [
        ["10000001", "utility", "2019-06-18", "Method for diagnosing diseases using neural networks", "B2", 20, 0, "ipg190618.xml"],
        ["10000002", "utility", "2020-01-07", 'System for "detecting" and classifying objects in images\twith solar panels', "B2", 12, 0, "ipg200107.xml"],
        ["D900000", "design", "2020-01-07", "Ornamental design for a lamp", "S1", 1, 0, "ipg200107.xml"],
        ["10000004", "utility", "2020-02-04", "Withdrawn thing", "B1", 3, 1, "ipg200204.xml"],
        ["10000005", "utility", "2021-03-02", "Recoil mechanism for a rifle", "B2", 8, 0, "ipg210302.xml"],
        ["11000006", "utility", "2022-05-10", "Quantum error correction with qubits", "B2", 15, 0, "ipg220510.xml"],
        ["11000007", "utility", "2023-08-01", "Systems and methods for generating text with language models", "B1", 30, 0, "ipg230801.xml"],
        ["4000008", "utility", "1977-02-01", "Rifle sight", "A", 5, 0, "pftaps.txt"],
        ["10000009", "utility", "2019-10-01", "Intrusion detection for industrial control networks", "B2", 9, 0, "ipg191001.xml"],
    ])
    pv_zip(pv / "g_application.tsv.zip", ["application_id", "patent_id", "patent_application_type", "filing_date", "series_code", "rule_47_flag"], [
        ["15/000001", "10000001", "15", "2017-03-01", "15", "FALSE"], ["16/000002", "10000002", "16", "2018-05-05", "16", "FALSE"],
        ["29/000003", "D900000", "29", "2019-01-01", "29", "FALSE"], ["16/000005", "10000005", "16", "2019-07-07", "16", "FALSE"],
        ["17/000006", "11000006", "17", "2020-10-10", "17", "FALSE"], ["17/000007", "11000007", "17", "2021-12-12", "17", "FALSE"],
        ["05/000008", "4000008", "05", "1975-04-04", "05", "FALSE"], ["15/000009", "10000009", "15", "2016-02-02", "15", "FALSE"],
    ])
    pv_zip(pv / "g_cpc_current.tsv.zip", ["patent_id", "cpc_sequence", "cpc_section", "cpc_class", "cpc_subclass", "cpc_group", "cpc_type"], [
        ["10000001", 0, "G", "G06", "G06N", "G06N3/08", "inventional"], ["10000001", 1, "G", "G16", "G16H", "G16H50/20", "additional"],
        ["10000002", 0, "G", "G06", "G06V", "G06V10/82", "inventional"], ["10000002", 1, "Y", "Y02", "Y02E", "Y02E10/50", "additional"],
        ["10000005", 0, "F", "F41", "F41A", "F41A3/00", "inventional"],
        ["11000006", 0, "G", "G06", "G06N", "G06N10/40", "inventional"],
        ["11000007", 0, "G", "G06", "G06F", "G06F40/56", "inventional"], ["11000007", 1, "G", "G06", "G06N", "G06N3/0455", "inventional"],
        ["4000008", 0, "F", "F41", "F41G", "F41G1/00", "inventional"], ["10000009", 0, "H", "H04", "H04L", "H04L63/14", "inventional"],
    ])
    pv_zip(pv / "g_location_disambiguated.tsv.zip", ["location_id", "disambig_city", "disambig_state", "disambig_country", "latitude", "longitude", "county", "state_fips", "county_fips"], [
        ["loc-ca", "Mountain View", "CA", "US", 37.39, -122.08, "Santa Clara", "6", "85"],
        ["loc-tx", "Austin", "TX", "US", 30.27, -97.74, "Travis", "48", "48453"],
        ["loc-de", "Berlin", None, "DE", 52.52, 13.40, None, None, None],
        ["loc-ny", "New York", "NY", "US", 40.71, -74.0, "New York", None, None],
    ])
    pv_zip(pv / "g_inventor_disambiguated.tsv.zip", ["patent_id", "inventor_sequence", "inventor_id", "disambig_inventor_name_first", "disambig_inventor_name_last", "gender_code", "location_id"], [
        ["10000001", 0, "inv-a", "Ada", "L", "F", "loc-ca"], ["10000002", 0, "inv-a", "Ada", "L", "F", "loc-tx"],
        ["10000002", 1, "inv-b", "Bo", "K", "M", "loc-de"], ["10000005", 0, "inv-c", "Cy", "Z", "M", "loc-tx"],
        ["11000006", 0, "inv-d", "Di", "Q", "F", "loc-ny"], ["11000007", 0, "inv-a", "Ada", "L", "F", "loc-ca"],
        ["4000008", 0, "inv-e", "Ed", "R", "M", "loc-tx"],
    ])
    pv_zip(pv / "g_assignee_disambiguated.tsv.zip", ["patent_id", "assignee_sequence", "assignee_id", "disambig_assignee_individual_name_first", "disambig_assignee_individual_name_last", "disambig_assignee_organization", "assignee_type", "location_id"], [
        ["10000001", 0, "as-goog", None, None, "Google LLC", "2.0", "loc-ca"],
        ["10000002", 0, "as-ibm", None, None, "International Business Machines Corporation", "2.0", "loc-ny"],
        ["10000005", 0, "as-hk", None, None, "Heckler & Koch GmbH", "3.0", "loc-de"],
        ["11000006", 0, "as-ibm", None, None, "International Business Machines Corporation", "2.0", "loc-ny"],
        ["11000007", 0, "as-oai", None, None, "OpenAI OpCo, LLC", "2.0", "loc-ca"],
        ["4000008", 0, "as-colt", None, None, "Colt's Manufacturing Company", "2", "loc-tx"],
        ["10000009", 0, "as-cs", None, None, "Cyber Systems Inc", "2.0", "loc-ca"],
    ])
    pv_zip(pv / "g_patent_abstract.tsv.zip", ["patent_id", "patent_abstract"], [
        ["10000001", "A neural network analyzes medical images and diagnoses diseases. The system predicts patient outcomes, "
                     "risks, and costs, and it ranks, filters, and sorts cases, using a processor, a memory, and a display."],
        ["10000002", "The system detects objects and classifies images captured by cameras."],
        ["10000005", "A rifle with a recoil spring."], ["11000006", "Qubits are corrected."],
        ["11000007", "A language model generates text and answers questions from customers."],
    ])
    pv_zip(pv / "g_us_patent_citation.tsv.zip", ["patent_id", "citation_sequence", "citation_patent_id", "citation_date", "record_name", "wipo_kind", "citation_category"], [
        ["10000002", 0, "10000001", "2019-06-18", "Smith", "B2", "cited by applicant"],
        ["11000006", 0, "10000002", "2020-01-07", "Doe", "B2", "cited by examiner"],
        ["11000006", 1, "10000001", "2019-06-18", "Smith", "B2", "cited by examiner"],
        ["11000007", 0, "10000001", "2019-06-18", "Smith", "B2", "cited by applicant"],
        ["11000007", 1, "9000000", "2018-01-01", "Roe", "B1", "cited by applicant"],
    ])
    # pre-grant publications
    pv_zip(pg / "pg_published_application.tsv.zip", ["pgpub_id", "application_id", "filing_date", "patent_application_type", "published_date", "wipo_kind", "application_title", "rule_47_flag", "filename"], [
        ["20170000001", "15/000001", "2017-03-01", "utility", "2017-09-01", "A1", "Diagnosing diseases with neural networks", "0", "ipa170901.xml"],
        ["20230000002", "17/999999", "2022-11-01", "utility", "2023-05-01", "A1", "Generating images from text prompts", "0", "ipa230501.xml"],
        ["20230000003", "17/999999", "2022-11-01", "utility", "2023-08-01", "A2", "Generating images from text prompts", "0", "ipa230801.xml"],
        ["20240000004", "18/000004", "2023-01-15", "utility", "2024-07-15", "A1", "Battery cooling", "0", "ipa240715.xml"],
    ])
    pv_zip(pg / "pg_cpc_current.tsv.zip", ["pgpub_id", "cpc_sequence", "cpc_section", "cpc_class", "cpc_subclass", "cpc_group", "cpc_type"], [
        ["20170000001", 0, "G", "G06", "G06N", "G06N3/08", "inventional"], ["20230000002", 0, "G", "G06", "G06T", "G06T11/00", "inventional"],
        ["20230000002", 1, "G", "G06", "G06N", "G06N3/0475", "additional"], ["20230000003", 0, "G", "G06", "G06T", "G06T11/00", "inventional"],
        ["20240000004", 0, "H", "H01", "H01M", "H01M10/613", "inventional"], ["20240000004", 1, "Y", "Y02", "Y02E", "Y02E60/10", "additional"],
    ])
    pv_zip(pg / "pg_inventor_disambiguated.tsv.zip", ["pgpub_id", "inventor_sequence", "inventor_id", "disambig_inventor_name_first", "disambig_inventor_name_last", "gender_code", "location_id"], [
        ["20170000001", 0, "inv-a", "Ada", "L", "F", "loc-ca"], ["20230000002", 0, "inv-f", "Fa", "M", "F", "loc-ca"],
        ["20230000003", 0, "inv-f", "Fa", "M", "F", "loc-ca"], ["20240000004", 0, "inv-g", "Gi", "N", "M", "loc-tx"],
    ])
    pv_zip(pg / "pg_assignee_disambiguated.tsv.zip", ["pgpub_id", "assignee_sequence", "assignee_id", "disambig_assignee_individual_name_first", "disambig_assignee_individual_name_last", "disambig_assignee_organization", "assignee_type", "location_id"], [
        ["20170000001", 0, "as-goog", None, None, "Google LLC", "2", "loc-ca"],
        ["20230000002", 0, "as-oai", None, None, "OpenAI OpCo, LLC", "2", "loc-ca"],
        ["20240000004", 0, "as-tsla", None, None, "Tesla, Inc.", "2", "loc-tx"],
    ])
    pv_zip(pg / "pg_granted_pgpubs_crosswalk.tsv.zip", ["pgpub_id", "application_id", "patent_id", "current_pgpub_id_flag", "current_patent_id_flag"], [
        ["20170000001", "15/000001", "10000001", "1", "1"],
    ])
    pv_zip(pg / "pg_published_application_abstract.tsv.zip", ["pgpub_id", "pg_published_application_abstract"], [
        ["20230000002", "A diffusion model generates images from text prompts written by users."],
        ["20240000004", "Coolant cools battery cells."],
    ])
    # AI Patent Dataset
    (D / "aipd").mkdir(parents=True, exist_ok=True)
    rows = [("10000001", 1, 1, 1, 0, 1, 0.97), ("10000002", 1, 1, 0, 1, 1, 0.91), ("10000005", 1, 0, 0, 0, 0, 0.02),
            ("11000006", 1, 0, 0, 0, 0, 0.30), ("20230000002", 0, 1, 1, 0, 1, 0.99), ("20240000004", 0, 0, 0, 0, 0, 0.01)]
    df = pd.DataFrame(rows, columns=["doc_id", "flag_patent", "predict50_any_ai", "predict50_ml", "predict50_vision", "predict93_any_ai", "ai_score_ml"])
    for p in ("evo", "nlp", "speech", "kr", "planning", "hardware"):
        df[f"predict50_{p}"] = 0
    with zipfile.ZipFile(D / "aipd" / "ai_model_predictions.csv.zip", "w") as z:
        z.writestr("ai_model_predictions.csv", df.to_csv(index=False))
    return D



def build_firms(D):
    """DISCERN 2.0 in its published layout: CSV files keyed by permno_adj (the granted patents, the publications, the
    subsidiary and ultimate-owner names with their owner spells spread over columns, a firm panel), a Stata
    permno-gvkey file, WRDS's CRSP/Compustat Merged link table, and a Compustat extract carrying CRSP's LPERMNO."""
    d = D / "discern"
    d.mkdir(parents=True, exist_ok=True)
    ibm = "INTERNATIONAL BUSINESS MACHINES CORPORATION"
    cols = ["patent_id", "patent_date", "assignee_name", "fyear", "name_std", "id_name", "sample", "permno_adj"]
    # owner at grant; 10000009 was bought by Alphabet (90319) between its filing in 2016 and its grant in 2019
    pd.DataFrame([["10000001", "2019-06-18", "GOOGLE LLC", 2019, "GOOGLE", 11, "U", 90319.0],
                  ["10000002", "2020-01-07", ibm, 2020, "INTERNATIONAL BUSINESS MACHINES", 12, "U", 12490.0],
                  ["5500000", "1996-03-05", ibm, 1996, "INTERNATIONAL BUSINESS MACHINES", 12, "U", 12490.0],
                  ["4000008", "1977-02-01", "COLT INDUSTRIES INC", 1977, "COLT INDUSTRIES", 13, "U", 11111.0],
                  ["10000009", "2019-10-01", "CYBER SYSTEMS INC", 2019, "CYBER SYSTEMS", 14, "S", 90319.0]],
                 columns=cols).to_csv(d / "discern_pat_grant_1980_2021.csv", index=False)
    # owner at filing, for patents applied for in 1980-2021 (10000005 was granted in 2021, after the grant file's last year)
    pd.DataFrame([["10000001", "2017-03-01", "GOOGLE LLC", 2017, "GOOGLE", 11, "U", 90319.0],
                  ["10000009", "2016-02-02", "CYBER SYSTEMS INC", 2016, "CYBER SYSTEMS", 14, "U", 55555.0],
                  ["10000005", "2019-07-07", "HECKLER & KOCH GMBH", 2019, "HECKLER & KOCH", 22, "S", 88888.0],
                  ["", "2021-05-05", "GOOGLE LLC", 2021, "GOOGLE", 11, "U", 90319.0]],
                 columns=cols).to_csv(d / "discern_pat_app_1980_2021.csv", index=False)
    pd.DataFrame({"openalex_id": ["W100", "W200"], "earliest_pub_date": ["2019-01-01", "2020-01-01"],
                  "openalex_date": ["2019-01-01", "2020-01-01"], "crossref_date": ["2019-01-02", "2020-01-02"],
                  "fyear": [2019, 2020], "name_std": ["GOOGLE", "INTERNATIONAL BUSINESS MACHINES"], "id_name": [11, 12],
                  "sample": ["compustat", "compustat"], "permno_adj": [90319, 12490], "doi": ["10.1/a", "10.1/b"]}
                 ).to_csv(d / "discern_pub_1980_2021.csv", index=False)
    # owner spells: Heckler & Koch held by one firm from 1991 for 24 years, then by another from 2015 (nyear a count here,
    # a last year in the owner file: both are read)
    pd.DataFrame({"id_name": [21, 22], "sample": ["compustat", "compustat"], "name_std": ["GOOGLE LLC", "HECKLER & KOCH GMBH"],
                  "country_code": ["US", "DE"], "subdiv_code": ["US-CA", None], "fyear1": [2015, 1991], "nyear1": [7, 24],
                  "permno_adj1": [90319, 77777], "fyear2": [None, 2015], "nyear2": [None, 7], "permno_adj2": [None, 88888]}
                 ).to_csv(d / "discern_sub_names.csv", index=False)
    pd.DataFrame({"id_name": [31, 32], "sample": ["compustat", "compustat"], "name_std": ["ALPHABET INC", "IBM"],
                  "fyear1": [2015, 1980], "nyear1": [2021, 2021], "permno_adj1": [90319, 12490], "name_acq1": [None, None]}
                 ).to_csv(d / "discern_uo_names.csv", index=False)
    pd.DataFrame({"permno_adj": [90319, 12490], "gvkey": [160329, 6066], "fyear": [2019, 2020], "n_patents": [3000, 9000],
                  "n_pubs": [100, 200]}).to_csv(d / "discern_firm_panel_1980_2021.csv", index=False)
    pd.DataFrame({"permno_adj": [90319, 12490, 12490, 77777, 88888, 55555, 11111],
                  "gvkey": ["160329", "006066", "006066", "100001", "100002", "100003", "002993"],
                  "fyear": [2019, 2020, 1996, 2000, 2019, 2016, 1977]}).to_stata(d / "permno_gvkey.dta", write_index=False)
    pd.DataFrame({"gvkey": ["160329", "006066", "006066"], "linkprim": ["P", "P", "J"], "liid": ["01", "01", "02"],
                  "linktype": ["LC", "LC", "LU"], "lpermno": [90319, 12490, 99999], "lpermco": [45483, 20990, 99999],
                  "linkdt": ["20040819", "19620131", "19900101"], "linkenddt": ["E", "E", "19951231"]}
                 ).to_csv(D / "ccmxpf_lnkhist.csv", index=False)
    pd.DataFrame({"gvkey": ["160329", "160329", "006066", "184996", "002993"], "fyear": [2019, 2023, 2022, 2023, 1977],
                  "conm": ["ALPHABET INC", "ALPHABET INC", "INTL BUSINESS MACHINES CORP", "TESLA INC", "COLT INDUSTRIES INC"],
                  "LPERMNO": [90319, 90319, 12490, 93436, None], "sale": [1, 2, 3, 4, 5]}).to_csv(D / "Compustat_Final.csv", index=False)
    return D


IPUMS_ROWS = [  # MULTYEAR, STATEFIP, MET2013, PERWT, SEX, AGE, RACE, HISPAN, EDUC, EDUCD, EMPSTAT, CLASSWKR, CLASSWKRD, OCCSOC, INDNAICS, INCWAGE, UHRSWORK, TRANWORK
    (2019, 6, 41940, 100.00, 2, 29, 4, 0, 10, 101, 1, 2, 22, "151252", "5415", 150000, 40, 80),
    (2020, 6, 41940, 50.00, 1, 41, 1, 0, 11, 116, 1, 2, 22, "151252", "5415", 200000, 45, 10),
    (2021, 48, 12420, 80.00, 1, 58, 1, 1, 6, 63, 1, 2, 25, "1191XX", "92M1", 60000, 40, 10),
    (2022, 48, 0, 40.00, 2, 35, 2, 0, 7, 71, 1, 1, 13, "4720XX", "23", 0, 50, 10),      # self-employed: no wage
    (2023, 36, 35620, 60.00, 2, 22, 1, 0, 10, 101, 2, 2, 22, "151252", "5415", 0, 0, 0),
    (2023, 17, 16980, 70.00, 1, 45, 1, 0, 10, 101, 1, 2, 23, "252021", "6111", 55000, 40, 10),
]
IPUMS_COLS = ["MULTYEAR", "STATEFIP", "MET2013", "PERWT", "SEX", "AGE", "RACE", "HISPAN", "EDUC", "EDUCD", "EMPSTAT", "CLASSWKR",
              "CLASSWKRD", "OCCSOC", "INDNAICS", "INCWAGE", "UHRSWORK", "TRANWORK"]
WIDTHS = {"MULTYEAR": 4, "STATEFIP": 2, "MET2013": 5, "PERWT": 10, "SEX": 1, "AGE": 3, "RACE": 1, "HISPAN": 1, "EDUC": 2, "EDUCD": 3,
          "EMPSTAT": 1, "CLASSWKR": 1, "CLASSWKRD": 2, "OCCSOC": 6, "INDNAICS": 8, "INCWAGE": 6, "UHRSWORK": 2, "TRANWORK": 2}


def build_ipums(D, fixed=False):
    d = D / "ipums"
    d.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(IPUMS_ROWS, columns=IPUMS_COLS)
    if not fixed:
        with gzip.open(d / "usa_00001.csv.gz", "wt") as f:
            df.to_csv(f, index=False)
        (d / "usa_00001.xml").write_text("<codeBook/>")
        return d / "usa_00001.csv.gz"
    lines, pos, xml = [], 1, ['<?xml version="1.0"?><codeBook xmlns="ddi:codebook:2_5"><dataDscr>']
    for v in IPUMS_COLS:
        w = WIDTHS[v]
        dec = 2 if v == "PERWT" else 0
        xml.append(f'<var ID="{v}" files="F1" dcml="{dec}"><location StartPos="{pos}" EndPos="{pos + w - 1}" width="{w}"/></var>')
        pos += w
    xml.append("</dataDscr></codeBook>")
    for r in IPUMS_ROWS:
        s = ""
        for v, x in zip(IPUMS_COLS, r):
            w = WIDTHS[v]
            if v == "PERWT":
                x = int(round(x * 100))
            s += (str(x).ljust(w) if isinstance(x, str) else str(x).rjust(w, "0"))
        lines.append(s)
    with gzip.open(d / "usa_00002.dat.gz", "wt") as f:
        f.write("\n".join(lines) + "\n")
    (d / "usa_00002.xml").write_text("".join(xml))
    return d / "usa_00002.dat.gz"


def build_onet(D):
    """O*NET's text database zip with Task Statements and Task Ratings (a handful of real-looking rows)."""
    tasks = [("29-1216.00", "General Internal Medicine Physicians", 1, "Diagnose and treat diseases of patients.", "Core"),
             ("29-1216.00", "General Internal Medicine Physicians", 2, "Analyze medical images to detect diseases.", "Core"),
             ("29-1216.00", "General Internal Medicine Physicians", 3, "Predict patient outcomes from records.", "Supplemental"),
             ("15-1252.00", "Software Developers", 4, "Write computer programs and test software.", "Core"),
             ("15-1252.00", "Software Developers", 5, "Generate text documentation for users.", "Supplemental"),
             ("43-4051.00", "Customer Service Representatives", 6, "Answer questions from customers.", "Core"),
             ("43-4051.00", "Customer Service Representatives", 7, "Resolve complaints of customers.", "Core"),
             ("33-3011.00", "Bailiffs", 8, "Maintain order in courtrooms.", "Core"),
             ("47-2061.00", "Construction Laborers", 9, "Operate machines to move materials.", "Core"),
             ("27-1024.00", "Graphic Designers", 10, "Generate images for advertisements.", "Core")]
    ts = pd.DataFrame(tasks, columns=["O*NET-SOC Code", "Title", "Task ID", "Task", "Task Type"])
    ts["Incumbents Responding"] = 20
    ts["Date"] = "08/2023"
    ts["Domain Source"] = "Incumbent"
    rt = []
    for code, title, tid, task, _ in tasks:
        for scale, name, val in (("IM", "Importance", 4.2 if tid % 2 else 3.1), ("RT", "Relevance of Task", 95.0)):
            rt.append((code, title, tid, task, scale, name, "n/a", val, 20, 0.2, 3.8, 4.5, "N", "08/2023", "Incumbent"))
    rt = pd.DataFrame(rt, columns=["O*NET-SOC Code", "Title", "Task ID", "Task", "Scale ID", "Scale Name", "Category", "Data Value", "N",
                                   "Standard Error", "Lower CI Bound", "Upper CI Bound", "Recommend Suppress", "Date", "Domain Source"])
    with zipfile.ZipFile(D / "db_29_0_text.zip", "w") as z:
        z.writestr("db_29_0_text/Task Statements.txt", ts.to_csv(sep="\t", index=False))
        z.writestr("db_29_0_text/Task Ratings.txt", rt.to_csv(sep="\t", index=False))
        z.writestr("db_29_0_text/Job Zones.txt", "O*NET-SOC Code\tTitle\tJob Zone\n29-1216.00\tX\t5\n")
    return D
