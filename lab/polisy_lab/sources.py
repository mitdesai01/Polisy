# -*- coding: utf-8 -*-
"""sources: the lab's dataset registry, file discovery, downloads and schema profiles.

Adding a dataset = one SOURCES entry (what it is, where it comes from, how to recognise its
files) + one adapter (adapters/) that turns the files into canonical tables. Everything else
(discovery, download, profiling, the data catalog on the site) works from this entry.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import os
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .core import LAB, log, pc, squash, RESULTS, dirs

UA = {"User-Agent": "Mozilla/5.0 (academic research; POLISY lab)"}
PV_KINDS = (".zip", ".tsv", ".csv", ".parquet")

# Each source: title, theme, publisher, url (landing page), access, terms, grain, keys, and
# `files`: {role: {"names": regex on the cleaned file name, "kinds": extensions,
#                  "tokens": header cells that must all be present ("~x" = contained),
#                  "folders": regex on the name of the folder holding the file (any file name then fits),
#                  "many": several files (e.g. one per year)}}.
SOURCES = {
    "aioe": {
        "title": "AI Occupational, Industry and Geographic Exposure (AIOE, AIIE, AIGE)",
        "theme": "AI exposure", "publisher": "Felten, Raj & Seamans (2021, Strategic Management Journal)",
        "url": "https://github.com/AIOE-Data/AIOE", "access": "open; module fetch clones the GitHub repository",
        "grain": "occupation (6-digit SOC), industry (4-digit NAICS), county (FIPS)", "keys": ["soc", "naics4", "county_fips"],
        "files": {
            "appendix": {"names": r"aioe_dataappendix", "kinds": (".xlsx",), "tokens": ("~aioe",)},
            "lm": {"names": r"language_modeling_aioe", "kinds": (".xlsx",), "tokens": ("~languagemodelingaioe",)},
            "ig": {"names": r"image_generation_aioe", "kinds": (".xlsx",), "tokens": ("~imagegenerationaioe",)},
            "abilities": {"names": r"abilities", "kinds": (".dta", ".csv"), "tokens": ("onetsoccode", "elementname", "scaleid")},
            "mturk": {"names": r"mturk", "kinds": (".dta", ".csv"), "tokens": ("applications", "oralcomprehension")},
            "salary": {"names": r"salary", "kinds": (".dta", ".csv"), "tokens": ("occcode", "~salary")},
            "education": {"names": r"education", "kinds": (".dta", ".csv"), "tokens": ("occcode", "~education")},
            "creative": {"names": r"creative", "kinds": (".dta", ".csv"), "tokens": ("occcode", "~creative")},
            "representation": {"names": r"representation", "kinds": (".dta", ".csv"), "tokens": ("occcode", "~female")},
            "oes_staffing": {"names": r"oes_4dig", "kinds": (".dta", ".zip", ".csv"), "tokens": ("naics", "occcode", "totemp")},
            "qcew": {"names": r"county_naics", "kinds": (".dta", ".csv"), "tokens": ("areafips", "agglvlcode", "~emplvl")},
        }},
    "dynamic_aioe": {
        "title": "Dynamic AI Occupational Exposure (DAIOE)", "theme": "AI exposure", "publisher": "DAIOE v1.0.0, Zenodo record 21873968",
        "url": "https://zenodo.org/records/21873968", "access": "open; module fetch lists the record's files through the Zenodo API",
        "grain": "occupation (SOC 2010, SOC 2018) x year, 2010-2024", "keys": ["soc", "soc2018", "year"],
        "files": {
            # DAIOE v1.0.0 (Zenodo 21873968): occupation x year panels on several classifications. The US SOC 2010
            # panel links to AIOE and VRscores; the SOC 2018 panel adds other published exposure measures.
            "soc2010": {"names": r"daioe_soc2010", "kinds": pc.TABLES, "tokens": ("occcodesoc2010", "year"), "many": True},
            "soc2018": {"names": r"daioe_panel_soc2018|daioe.*soc2018", "kinds": pc.TABLES, "tokens": ("soc2018code", "year"), "many": True},
            # anything else that looks like an occupation x time exposure table
            "data": {"names": r"dynamic_?ai|dyn_?aioe|aioe_?dyn|time_?varying", "kinds": pc.TABLES + (".zip",),
                     "tokens": ("~soc",), "many": True}}},
    "btos": {
        "title": "Business Trends and Outlook Survey (AI use)", "theme": "AI adoption", "publisher": "US Census Bureau",
        "url": "https://www.census.gov/hfp/btos/data_downloads", "access": "open; module fetch reads the download page for file links",
        "grain": "geography (national, sector, state, MSA, size) x question x answer x biweekly period", "keys": ["naics2", "state_fips", "period"],
        "files": {"data": {"names": r"btos|business_?trends|response_?estimates|^(national|sector|subsector|state|msa|"
                                    r"employment_?size.*|empsize|state_?by_?sector|state_?sector|top_?25.*)$",
                           "kinds": (".xlsx", ".csv", ".zip"), "tokens": ("~question", "~answer"), "many": True}}},
    "cspp": {
        "title": "Correlates of State Policy", "theme": "policy & politics", "publisher": "IPPSR, Michigan State University (Jordan & Grossmann)",
        "url": "https://ippsr.msu.edu/public-policy/correlates-state-policy", "access": "open; module fetch reads the project page for file links",
        "grain": "state x year", "keys": ["state_fips", "year"],
        "files": {"data": {"names": r"correlates|cspp|state_?policy", "kinds": (".csv", ".dta", ".xlsx", ".zip"), "tokens": ("year",)},
                  "codebook": {"names": r"codebook|variable", "kinds": (".xlsx", ".csv"), "tokens": ("~variable",)}}},
    "irs_migration": {
        "title": "IRS SOI migration data (state and county flows)", "theme": "migration", "publisher": "IRS Statistics of Income",
        "url": "https://www.irs.gov/statistics/soi-tax-stats-migration-data", "access": "open; module fetch tries the yearly CSV links",
        "grain": "origin x destination x year pair (households = returns, people = exemptions, AGI)", "keys": ["state_fips", "county_fips", "year"],
        "files": {"state": {"names": r"^state_?(in|out)_?flow_?\d{4}", "kinds": (".csv",), "tokens": ("~y1statefips", "~y2statefips"), "many": True},
                  "county": {"names": r"^county_?(in|out)_?flow_?\d{4}", "kinds": (".csv",), "tokens": ("~y1countyfips", "~y2countyfips"), "many": True}}},
    "patentsview": {
        "title": "PatentsView granted patents (patents, filing dates, CPC classes, inventors, places, assignees, abstracts, citations)",
        "theme": "innovation", "publisher": "USPTO PatentsView",
        "url": "https://patentsview.org/download/data-download-tables",
        "access": "open, large; the notebook's download step saves the tables you choose (or use your own copies)",
        "grain": "patent; patent x CPC class; patent x inventor; patent x assignee; location; citation",
        "keys": ["patent_id", "state_fips", "county_fips", "year"],
        "files": {"patent": {"names": r"^g_patent(_tsv)?$", "kinds": PV_KINDS, "tokens": ("patentid", "~patentdate")},
                  "application": {"names": r"^g_application(_tsv)?$", "kinds": PV_KINDS, "tokens": ("patentid",)},
                  "cpc": {"names": r"^g_cpc_current(_tsv)?$", "kinds": PV_KINDS, "tokens": ("patentid", "~cpc")},
                  "inventor": {"names": r"^g_inventor_disambiguated(_tsv)?$", "kinds": PV_KINDS, "tokens": ("patentid", "~locationid")},
                  "location": {"names": r"^g_location_disambiguated(_tsv)?$", "kinds": PV_KINDS, "tokens": ("locationid", "~latitude")},
                  "assignee": {"names": r"^g_assignee_disambiguated(_tsv)?$", "kinds": PV_KINDS, "tokens": ("patentid",)},
                  "abstract": {"names": r"^g_patent_abstract(_tsv)?$", "kinds": PV_KINDS, "tokens": ("patentid",)},
                  "citation": {"names": r"^g_us_patent_citation(_tsv)?$", "kinds": PV_KINDS, "tokens": ("patentid",)},
                  "cpc_title": {"names": r"^g_cpc_title(_tsv)?$", "kinds": PV_KINDS, "tokens": ()}}},
    "patentsview_pregrant": {
        "title": "PatentsView pre-grant publications (published applications: filing dates, CPC classes, inventors, "
                 "assignees, abstracts, and which were later granted)",
        "theme": "innovation", "publisher": "USPTO PatentsView",
        "url": "https://patentsview.org/download/pg-download-tables",
        "access": "open, large; the notebook's download step saves the tables you choose",
        "grain": "published application (pgpub_id); application x CPC class, inventor, assignee",
        "keys": ["pgpub_id", "patent_id", "state_fips", "county_fips", "year"],
        # the key column is found by pattern in the adapter (pgpub_id), so only the names are required here
        "files": {"application": {"names": r"^pg_published_application(_tsv)?$", "kinds": PV_KINDS, "tokens": ()},
                  "cpc": {"names": r"^pg_cpc_current(_tsv)?$", "kinds": PV_KINDS, "tokens": ()},
                  "inventor": {"names": r"^pg_inventor_disambiguated(_tsv)?$", "kinds": PV_KINDS, "tokens": ()},
                  "location": {"names": r"^pg_location_disambiguated(_tsv)?$", "kinds": PV_KINDS, "tokens": ()},
                  "assignee": {"names": r"^pg_assignee_disambiguated(_tsv)?$", "kinds": PV_KINDS, "tokens": ()},
                  "crosswalk": {"names": r"^pg_granted_pgpubs_crosswalk(_tsv)?$", "kinds": PV_KINDS, "tokens": ()},
                  "abstract": {"names": r"^pg_published_application_abstract(_tsv)?$", "kinds": PV_KINDS, "tokens": ()}}},
    "aipd": {
        "title": "USPTO Artificial Intelligence Patent Dataset (AIPD): model-based AI labels for patents and published applications",
        "theme": "innovation", "publisher": "USPTO Office of the Chief Economist (Giczy, Pairolero & Toole 2022; 2023 update)",
        "url": "https://www.uspto.gov/ip-policy/economic-research/research-datasets/artificial-intelligence-patent-dataset",
        "access": "open; module fetch looks for the download links on the page, otherwise save the predictions file by hand",
        "grain": "patent or pre-grant publication (doc_id, flag_patent)", "keys": ["patent_id", "pgpub_id"],
        "files": {"predictions": {"names": r"ai_model_predictions|^aipd|ai_patent_dataset|artificial_intelligence_patent",
                                  "folders": r"^aipd$", "kinds": (".zip", ".csv", ".tsv", ".dta", ".parquet", ".gz"), "tokens": (),
                                  "many": True}}},
    "discern": {
        "title": "DISCERN 2.0: which Compustat firm owns each patent (subsidiaries and ownership changes included), 1980-2021",
        "theme": "innovation", "publisher": "Arora, Belenzon & Sheer (Duke); DISCERN 2.0",
        "url": "https://zenodo.org/search?q=DISCERN%20Duke%20Innovation",
        "access": "your copy (the thesis used it); put the whole download in POLISY/data/discern. Every file in that folder is "
                  "read and recognized by its columns",
        "grain": "patent -> firm (gvkey or permno_adj); firm-year panel; firm names", "keys": ["patent_id", "gvkey", "year"],
        "files": {"tables": {"names": r"discern", "folders": r"discern", "kinds": (".dta", ".csv", ".tsv", ".parquet", ".zip", ".txt"),
                             "tokens": (), "many": True}}},
    "ipums": {
        "title": "IPUMS USA: American Community Survey microdata (age, gender, race, education, sector, wages, work from "
                 "home and location of every occupation and industry)",
        "theme": "controls", "publisher": "IPUMS USA, University of Minnesota (Ruggles et al.)",
        "url": "https://usa.ipums.org/usa/",
        "access": "free registration; the notebook requests the extract with your IPUMS API key (or save an extract made on "
                  "the website, the data file and its .xml codebook, in POLISY/data/ipums)",
        "grain": "person (weighted) -> occupation, industry, occupation x state, occupation x metro, industry x occupation",
        "keys": ["soc", "naics4", "state_fips", "cbsa"],
        "files": {"data": {"names": r"^usa_\d+$|ipums", "folders": r"ipums", "kinds": (".gz", ".csv", ".dat", ".parquet"), "tokens": ()},
                  "ddi": {"names": r"^usa_\d+$|ipums", "folders": r"ipums", "kinds": (".xml",), "tokens": ()}}},
    "onet_tasks": {
        "title": "O*NET task statements and task ratings", "theme": "AI exposure",
        "publisher": "O*NET Resource Center (US Department of Labor), database 29.0",
        "url": "https://www.onetcenter.org/database.html",
        "access": "open; POLISY_DA module 05 or module fetch downloads the text zip",
        "grain": "occupation (O*NET-SOC) x task", "keys": ["soc"],
        "files": {"tasks": {"names": r"^task_statements$", "kinds": (".txt", ".xlsx", ".csv"), "tokens": ("~onetsoccode", "~task")},
                  "ratings": {"names": r"^task_ratings$", "kinds": (".txt", ".xlsx", ".csv"), "tokens": ("~onetsoccode", "~scaleid")}}},
    "vrscores": {
        "title": "VRscores workforce partisanship (employer, metro, industry, occupation panels)", "theme": "politics at work",
        "publisher": "Kagan, Frake & Hurst (Organization Science 2026)", "url": "https://dataverse.harvard.edu",
        "access": "run POLISY_DA modules 01-04 first (their canonical Parquet files are read), or supply the VRscores HTML report",
        "grain": "employer/metro/industry/occupation x year", "keys": ["soc", "naics6", "msa", "cbsa", "year"],
        "files": {"report": {"names": r"vrscores|report", "kinds": (".html",), "tokens": ()}}},
    "elections": {
        "title": "County presidential returns", "theme": "politics",
        "publisher": "MIT Election Data and Science Lab (2000-2024); otherwise the county results compiled by T. McGovern (2016-2024)",
        "url": "https://doi.org/10.7910/DVN/VOQCHQ",
        "access": "the MIT file is found by POLISY_DA (COUNTYPRES); without it, module fetch downloads the McGovern files from GitHub",
        "grain": "county x election year", "keys": ["county_fips", "year"],
        "files": {"county_results": {"names": r"us_county_level_presidential_results|county_level_presidential",
                                     "kinds": (".csv",), "tokens": ("~fips", "~pergop"), "many": True}}},
    "county_context": {
        "title": "County context: land area, population, education, income, housing costs, climate, industry mix",
        "theme": "controls", "publisher": "JsonOfCounties (E. Gambit), compiled from the Census ACS 2019, BEA, NOAA, "
                                          "County Business Patterns and the MIT Living Wage Calculator",
        "url": "https://github.com/evangambit/JsonOfCounties", "access": "open; module fetch downloads counties.json from GitHub",
        "grain": "county", "keys": ["county_fips"],
        "files": {"data": {"names": r"^(json_?of_?)?counties$", "kinds": (".json",), "tokens": ()}}},
    "telework": {
        "title": "Jobs that can be done at home (occupations, industries, metro areas)", "theme": "controls",
        "publisher": "Dingel & Neiman (2020, Journal of Public Economics)",
        "url": "https://github.com/jdingel/DingelNeiman-workathome", "access": "open; module fetch downloads the result files from GitHub",
        "grain": "occupation (O*NET-SOC), 2-digit NAICS, metro area", "keys": ["soc", "naics2", "cbsa"],
        "files": {"occupation": {"names": r"occupations_workathome", "kinds": (".csv",), "tokens": ("onetsoccode", "teleworkable")},
                  "industry": {"names": r"^naics_workfromhome$", "kinds": (".csv",), "tokens": ("naics", "teleworkableemp")},
                  "metro": {"names": r"^msa_workfromhome$", "kinds": (".csv",), "tokens": ("area", "teleworkableemp")}}},
    "geography": {
        "title": "Census CBSA delineation (county -> metro)", "theme": "geography", "publisher": "US Census Bureau / OMB",
        "url": "https://www.census.gov/geographies/reference-files/time-series/demo/metro-micro/delineation-files.html",
        "access": "found by POLISY_DA (CBSA_REFERENCE)", "grain": "county", "keys": ["county_fips", "cbsa"], "files": {}},
}


# --------------------------------------------------------------------------- discovery
EXTRA_EXTS = (".html", ".htm", ".7z", ".json", ".gz", ".xml", ".dat")


def _extra_clean(p):
    """Clean name of a file polisy_core does not index: 'usa_00003.dat.gz' -> 'usa_00003'."""
    stem = Path(p.stem)
    if p.suffix.lower() == ".gz" and stem.suffix.lower() in (".csv", ".tsv", ".dat", ".txt"):
        stem = Path(stem.stem)
    return pc.clean_name(stem.name)[0]


def _lab_items():
    """polisy_core's index of the search folders plus the lab's own download folder, 4 levels deep,
    plus the file types polisy_core does not index (.html reports, .7z archives, gzipped tables, IPUMS
    codebooks and fixed-width data)."""
    items = list(pc._index())
    seen = {str(i["path"]) for i in items}
    for root, depth in pc._roots():
        for kind, p in pc._walk(root, depth):
            if kind == "file" and p.suffix.lower() in EXTRA_EXTS and str(p) not in seen:
                seen.add(str(p))
                try:
                    items.append({"path": p, "kind": p.suffix.lower(), "clean": _extra_clean(p),
                                  "size": p.stat().st_size, "mtime": p.stat().st_mtime})
                except OSError:
                    pass
    raw = Path(LAB["RAW"])
    if raw.exists():
        for kind, p in pc._walk(raw, 4, cap=2000):
            if str(p) in seen:
                continue
            clean, ext = pc.clean_name(p.name)
            if kind == "file" and p.suffix.lower() in EXTRA_EXTS:
                clean, ext = _extra_clean(p), p.suffix.lower()
            k = "dir" if kind == "dir" else ext
            if k:
                try:
                    items.append({"path": p, "kind": k, "clean": clean, "size": p.stat().st_size, "mtime": p.stat().st_mtime})
                except OSError:
                    pass
    return items


_ZIPS = {}


def _zip_tables(path):
    """Table files inside a zip: (name as stored, clean name, extension, size). Cached per zip version."""
    try:
        st = Path(path).stat()
        key = (str(path), st.st_size, st.st_mtime)
    except OSError:
        return []
    if key not in _ZIPS:
        out = []
        try:
            with zipfile.ZipFile(path) as zf:
                for i in zf.infolist():
                    n = i.filename
                    if n.endswith("/") or "__MACOSX" in n or Path(n).name.startswith("."):
                        continue
                    clean, ext = pc.clean_name(Path(n).name)
                    if ext in pc.TABLES:
                        out.append((n, clean, ext, i.file_size))
        except (OSError, zipfile.BadZipFile):
            pass
        _ZIPS[key] = out
    return _ZIPS[key]


def _fits(path, member, tokens):
    if not tokens:
        return True
    t = pc._tokens(path, member, rows=6)
    return bool(t) and all(pc._has(t, w) for w in tokens)


def discover(source, role):
    """Files for one role of one source: CONFIG override first, then the search folders.

    Returns a list of (path, member) pairs, best first. Every table inside a zip is a
    candidate of its own, matched by its own name (or by the zip's name), so one download
    holding many files (IRS: one per year and direction) is found without unzipping.
    Several files are returned only for roles marked many=True.
    """
    spec = SOURCES[source]["files"][role]
    key = f"LAB_{source}_{role}".upper()
    forced = pc.CONFIG.get(key)
    if forced:
        paths = [Path(p) for p in (forced if isinstance(forced, (list, tuple)) else [forced])]
        found = [(p, None) for p in paths if p.exists()]
        if found:
            return found
        log(f"{key}: CONFIG path(s) not found, searching instead")
    rx = re.compile(spec["names"], re.I)
    frx = re.compile(spec["folders"], re.I) if spec.get("folders") else None
    tokens = spec.get("tokens", ())
    hits, seen = [], set()

    def add(path, member, clean, size, mtime):
        ident = (clean, size, member and Path(member).parent.name)
        if ident in seen or not _fits(path, member, tokens):
            return
        seen.add(ident)
        hits.append((path, member, mtime))

    def in_folder(path):                  # e.g. every file in POLISY/data/discern, whatever its name
        return bool(frx) and bool(frx.search(pc.clean_name(Path(path).parent.name)[0]))
    for it in _lab_items():
        if it["kind"] == ".zip":
            zip_named = bool(rx.search(it["clean"])) or in_folder(it["path"])
            for name, clean, ext, size in _zip_tables(it["path"]):
                if ext in spec["kinds"] and (zip_named or rx.search(clean) or
                                             (frx is not None and frx.search(pc.clean_name(Path(name).parent.name)[0]))):
                    add(it["path"], name, clean, size, it["mtime"])
        elif it["kind"] in spec["kinds"] and (rx.search(it["clean"]) or in_folder(it["path"])):
            add(it["path"], None, it["clean"], it["size"], it["mtime"])
    hits.sort(key=lambda h: h[2], reverse=True)
    out = [(p, m) for p, m, _ in hits]
    return out if spec.get("many") else out[:1]


def unpack_archives():
    """Extract .7z archives the adapters need (the AIOE repository ships QCEW as county_naics_2019.7z)."""
    raw = dirs()["RAW"] / "unpacked"
    for it in _lab_items():
        if it["kind"] != ".7z" or not re.search(r"county_naics|oes|abilities", it["clean"]):
            continue
        dest = raw / it["clean"]
        if dest.exists() and any(dest.iterdir()):
            continue
        try:
            import py7zr
            with py7zr.SevenZipFile(it["path"]) as z:
                z.extractall(dest)
            log(f"unpacked {it['path'].name} -> {dest}")
        except Exception as e:
            log(f"cannot unpack {it['path'].name} ({e}); pip install py7zr")


def inventory():
    """Which files were found for every source and role (the data catalog on the site)."""
    unpack_archives()
    rows = []
    for s, meta in SOURCES.items():
        for role in meta["files"]:
            found = discover(s, role)
            rows.append({"source": s, "role": role, "files": len(found),
                         "paths": "; ".join(str(p) + (f" :: {m}" if m else "") for p, m in found[:6]) + (" ..." if len(found) > 6 else "")})
    inv = pd.DataFrame(rows)
    RESULTS["catalog"] = {s: {k: v for k, v in meta.items() if k != "files"} | {
        "roles": inv[inv.source == s][["role", "files", "paths"]].to_dict("records")} for s, meta in SOURCES.items()}
    return inv


# --------------------------------------------------------------------------- downloads
def _get(url, dest=None, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if dest:
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(data)
    return data


def _links(page_url, pattern=r'href="([^"]+\.(?:xlsx|csv|zip|dta|xls))"'):
    html = _get(page_url).decode("utf-8", "ignore")
    out = []
    for h in re.findall(pattern, html, flags=re.I):
        out.append(h if h.startswith("http") else urllib.parse.urljoin(page_url, h))
    return sorted(set(out))


def fetch_aioe(raw):
    dest = raw / "aioe"
    if discover("aioe", "abilities") and discover("aioe", "appendix"):
        log("aioe: already present")
        return
    if shutil.which("git"):
        try:
            subprocess.run(["git", "clone", "--depth", "1", "https://github.com/AIOE-Data/AIOE", str(dest)],
                           check=True, capture_output=True, timeout=900, env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"})
            log(f"aioe: cloned into {dest}")
        except Exception as e:
            log(f"aioe: git clone failed ({e}); downloading files one by one")
    if not (dest / "AIOE_DataAppendix.xlsx").exists():
        base = "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/"
        for f in ["AIOE_DataAppendix.xlsx", "Language Modeling AIOE and AIIE.xlsx", "Image Generation AIOE and AIIE.xlsx",
                  "Input/abilities_2020.dta", "Input/mturk_mapping_matrix.dta", "Input/application_list.dta",
                  "Input/occ_title_2020.dta", "Input/oes_4dig_naics.zip", "Input/county_naics_2019.7z",
                  "Generative AI/occ_salary_data_2021.dta", "Generative AI/occ_required_education.dta",
                  "Generative AI/occ_creative_weight.dta", "Generative AI/occ_representation.dta"]:
            try:
                _get(base + urllib.parse.quote(f), dest / f)
            except Exception as e:
                log(f"aioe: {f} failed ({e})")
    for z in dest.rglob("*.7z"):
        if not z.with_suffix(".dta").exists():
            try:
                import py7zr
                with py7zr.SevenZipFile(z) as a:
                    a.extractall(z.parent)
                log(f"aioe: extracted {z.name}")
            except Exception as e:
                log(f"aioe: cannot extract {z.name} ({e}); pip install py7zr")


def fetch_zenodo(raw, record="21873968"):
    if any(discover("dynamic_aioe", r) for r in ("soc2010", "soc2018", "data")):
        log("dynamic_aioe: already present")
        return
    try:
        meta = json.loads(_get(f"https://zenodo.org/api/records/{record}"))
    except Exception as e:
        log(f"dynamic_aioe: Zenodo API unreachable ({e}). Download the files from https://zenodo.org/records/{record} "
            f"into {raw / 'dynamic_aioe'}")
        return
    for f in meta.get("files", []):
        name, url, size = f.get("key"), f.get("links", {}).get("self"), f.get("size", 0)
        if not name or not url:
            continue
        if size and size > 3e9:
            log(f"dynamic_aioe: skipping {name} ({size / 1e9:.1f} GB); download it by hand if needed")
            continue
        try:
            _get(url, raw / "dynamic_aioe" / name, timeout=900)
            log(f"dynamic_aioe: {name} ({size / 1e6:.1f} MB)")
        except Exception as e:
            log(f"dynamic_aioe: {name} failed ({e})")


def fetch_page_files(raw, source, page, keep=r"."):
    if discover(source, "data"):
        log(f"{source}: already present")
        return
    try:
        links = [u for u in _links(page) if re.search(keep, u, re.I)]
    except Exception as e:
        log(f"{source}: cannot read {page} ({e}). Download the data files by hand into {raw / source}")
        return
    log(f"{source}: {len(links)} file links on {page}")
    for u in links:
        try:
            _get(u, raw / source / Path(urllib.parse.urlparse(u).path).name, timeout=600)
        except Exception as e:
            log(f"{source}: {u} failed ({e})")


def fetch_irs(raw, first=2011, last=2023):
    have = {pc.clean_name(Path(m or p).name)[0] for p, m in discover("irs_migration", "state") + discover("irs_migration", "county")}
    got = 0
    for y in range(first, last):
        yy = f"{y % 100:02d}{(y + 1) % 100:02d}"
        for lvl in ("state", "county"):
            for d in ("inflow", "outflow"):
                name = f"{lvl}{d}{yy}.csv"
                if pc.clean_name(name)[0] in have:
                    continue
                try:
                    _get(f"https://www.irs.gov/pub/irs-soi/{name}", raw / "irs_migration" / name, timeout=300)
                    got += 1
                except Exception:
                    pass
    log(f"irs_migration: {got} new files downloaded ({len(have)} already present)")


def download(url, dest, timeout=900, chunk=1 << 22):
    """Stream a (possibly multi-gigabyte) file to disk through a .part file; a zip is checked before it is kept."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers=UA)
    got, last = 0, 0
    with urllib.request.urlopen(req, timeout=timeout) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        while True:
            b = r.read(chunk)
            if not b:
                break
            f.write(b)
            got += len(b)
            if got - last >= 1e9:
                last = got
                log(f"  {dest.name}: {got / 1e9:.1f}" + (f" of {total / 1e9:.1f}" if total else "") + " GB")
    if total and got != total:
        part.unlink(missing_ok=True)
        raise IOError(f"incomplete download ({got:,} of {total:,} bytes)")
    if dest.suffix.lower() == ".zip" and not zipfile.is_zipfile(part):
        part.unlink(missing_ok=True)
        raise IOError("the download is not a zip file")
    part.replace(dest)
    return dest


PV_BASE = "https://s3.amazonaws.com/data.patentsview.org/"
# (source, role) -> (folder on PatentsView's server, table). Names and folders as listed in PatentsView's own
# sources.yml (github.com/PatentsView/PatentsView-Code-Snippets, data-downloads).
PV_FILES = {
    ("patentsview", "patent"): ("download", "g_patent"),
    ("patentsview", "application"): ("download", "g_application"),
    ("patentsview", "cpc"): ("download", "g_cpc_current"),
    ("patentsview", "inventor"): ("download", "g_inventor_disambiguated"),
    ("patentsview", "location"): ("download", "g_location_disambiguated"),
    ("patentsview", "assignee"): ("download", "g_assignee_disambiguated"),
    ("patentsview", "cpc_title"): ("download", "g_cpc_title"),
    ("patentsview", "abstract"): ("download", "g_patent_abstract"),
    ("patentsview", "citation"): ("download", "g_us_patent_citation"),
    ("patentsview_pregrant", "application"): ("pregrant_publications", "pg_published_application"),
    ("patentsview_pregrant", "cpc"): ("pregrant_publications", "pg_cpc_current"),
    ("patentsview_pregrant", "inventor"): ("pregrant_publications", "pg_inventor_disambiguated"),
    ("patentsview_pregrant", "location"): ("pregrant_publications", "pg_location_disambiguated"),
    ("patentsview_pregrant", "assignee"): ("pregrant_publications", "pg_assignee_disambiguated"),
    ("patentsview_pregrant", "crosswalk"): ("pregrant_publications", "pg_granted_pgpubs_crosswalk"),
    ("patentsview_pregrant", "abstract"): ("pregrant_publications", "pg_published_application_abstract"),
}
# What each step needs. "core" is enough for patents, filing years, places and the firm link by name.
PV_SETS = {
    "core": [("patentsview", r) for r in ("patent", "application", "cpc", "inventor", "location", "assignee", "cpc_title")],
    "pregrant": [("patentsview_pregrant", r) for r in ("application", "cpc", "inventor", "location", "assignee", "crosswalk")],
    "text": [("patentsview", "abstract"), ("patentsview_pregrant", "abstract")],
    "citations": [("patentsview", "citation")],
}


def fetch_patentsview(dest=None, tables=("core", "pregrant")):
    """Download PatentsView tables (as published, zipped) into dest, default lab/raw/patentsview.

    `tables`: set names from PV_SETS ("core", "pregrant", "text", "citations") or table names such as
    "g_application". A table already found in any search folder, under its PatentsView name, is skipped, so
    your own copies are never downloaded again."""
    dest = Path(dest) if dest else dirs()["RAW"] / "patentsview"
    want = []
    for t in tables:
        want += PV_SETS.get(t, [k for k, v in PV_FILES.items() if v[1] == t])
    for key in dict.fromkeys(want):
        folder, table = PV_FILES[key]
        have = discover(*key)
        if have:
            log(f"patentsview: {table} already present ({Path(have[0][0]).name})")
            continue
        url = f"{PV_BASE}{folder}/{table}.tsv.zip"
        try:
            t0 = time.time()
            p = download(url, dest / f"{table}.tsv.zip", timeout=3600)
            log(f"patentsview: {table} downloaded ({p.stat().st_size / 1e9:.2f} GB, {time.time() - t0:.0f}s)")
        except Exception as e:
            log(f"patentsview: {table} failed ({type(e).__name__}: {e}); download {url} by hand into {dest}")


def fetch_aipd(raw):
    """The AI Patent Dataset's predictions file: the download links are read from the USPTO page."""
    if discover("aipd", "predictions"):
        log("aipd: already present")
        return
    page = SOURCES["aipd"]["url"]
    try:
        links = [u for u in _links(page, r'href="([^"]+\.(?:zip|csv|dta|tsv|gz))"')
                 if re.search(r"ai_model_prediction|aipd|ai_patent|predictions", u, re.I)]
    except Exception as e:
        log(f"aipd: cannot read {page} ({type(e).__name__}: {e}). Download the predictions file (ai_model_predictions) "
            f"by hand into POLISY/data/aipd")
        return
    if not links:
        log(f"aipd: no predictions file linked on {page}; download it by hand into POLISY/data/aipd")
    for u in links[:3]:
        name = Path(urllib.parse.urlparse(u).path).name
        try:
            download(u, raw / "aipd" / name, timeout=3600)
            log(f"aipd: {name} downloaded")
        except Exception as e:
            log(f"aipd: {u} failed ({type(e).__name__}: {e}); download it by hand into POLISY/data/aipd")


ONET_ZIP = "https://www.onetcenter.org/dl_files/database/db_29_0_text.zip"


def fetch_onet(raw):
    """O*NET's text database (task statements and ratings); POLISY_DA module 05 downloads the same zip."""
    if discover("onet_tasks", "tasks") and discover("onet_tasks", "ratings"):
        log("onet_tasks: already present")
        return
    try:
        download(ONET_ZIP, raw / "onet" / Path(ONET_ZIP).name, timeout=900)
        log("onet_tasks: O*NET 29.0 text database downloaded")
    except Exception as e:
        log(f"onet_tasks: {ONET_ZIP} failed ({type(e).__name__}: {e}); download it by hand from "
            "https://www.onetcenter.org/database.html (Text) into POLISY/data")


GITHUB = "https://raw.githubusercontent.com/"
GITHUB_FILES = {      # source -> (role, url): small open files the stress tests use as controls
    "county_context": [("data", GITHUB + "evangambit/JsonOfCounties/master/counties.json")],
    "telework": [("occupation", GITHUB + "jdingel/DingelNeiman-workathome/master/occ_onet_scores/output/occupations_workathome.csv"),
                 ("industry", GITHUB + "jdingel/DingelNeiman-workathome/master/national_measures/output/NAICS_workfromhome.csv"),
                 ("metro", GITHUB + "jdingel/DingelNeiman-workathome/master/MSA_measures/output/MSA_workfromhome.csv")],
    "elections": [("county_results", GITHUB + f"tonmcg/US_County_Level_Election_Results_08-24/master/{y}_US_County_Level_Presidential_Results.csv")
                  for y in (2016, 2020, 2024)],
}


def fetch_github(raw):
    """The GitHub-hosted controls: county context, telework shares and (when POLISY_DA has no MIT file) county returns."""
    for source, files in GITHUB_FILES.items():
        if source == "elections" and pc.locate("COUNTYPRES")["path"] is not None:
            continue
        for role, url in files:
            name = url.rsplit("/", 1)[1]
            have = {Path(m or p).name.lower() for p, m in discover(source, role)}
            if name.lower() in have or (have and not SOURCES[source]["files"][role].get("many")):
                continue
            try:
                _get(url, raw / source / name, timeout=300)
                log(f"{source}: {name} downloaded")
            except Exception as e:
                log(f"{source}: {name} failed ({e}); download it from {url} into a search folder")


def fetch_all(patentsview=False, pv_tables=("core", "pregrant")):
    """Download what can be downloaded; never re-download a file that is already found. PatentsView and the AI
    Patent Dataset (several gigabytes) only with patentsview=True."""
    raw = dirs()["RAW"]
    fetch_aioe(raw)
    fetch_zenodo(raw)
    fetch_github(raw)
    fetch_page_files(raw, "btos", "https://www.census.gov/hfp/btos/data_downloads", keep=r"\.(xlsx|csv|zip)$")
    fetch_page_files(raw, "cspp", "https://ippsr.msu.edu/public-policy/correlates-state-policy", keep=r"correlates|cspp|codebook")
    fetch_irs(raw)
    fetch_onet(raw)
    if patentsview:
        fetch_patentsview(raw / "patentsview", pv_tables)
        fetch_aipd(raw)


# --------------------------------------------------------------------------- profiles
def profile_file(path, member=None, nrows=20000):
    """Columns, types, missingness, distinct counts and examples of one file (a sample of rows)."""
    path = Path(path)
    ext = Path(member or path.name).suffix.lower()
    try:
        if ext in (".tsv",) or (ext == ".zip" and member and member.lower().endswith(".tsv")):
            df = _read_tsv_sample(path, member, nrows)
        elif ext == ".dta" and not member:
            with pd.read_stata(path, iterator=True) as r:
                df = r.read(nrows)
        elif ext == ".html":
            return {"file": str(path), "kind": "html report", "size_mb": round(path.stat().st_size / 1e6, 1)}
        else:
            df = pc.read_table(path, member)
            df = df.head(nrows)
    except Exception as e:
        return {"file": str(path), "error": f"{type(e).__name__}: {e}"}
    cols = []
    for c in df.columns[:400]:
        s = df[c]
        num = pd.to_numeric(s, errors="coerce")
        cols.append({"name": str(c), "non_null": round(float(s.notna().mean()), 3), "distinct": int(s.nunique(dropna=True)),
                     "numeric": bool(num.notna().sum() >= 0.9 * s.notna().sum() and s.notna().any()),
                     "examples": [str(v)[:40] for v in s.dropna().unique()[:3]]})
    return {"file": str(path) + (f" :: {member}" if member else ""), "rows_sampled": len(df), "columns": len(df.columns),
            "fields": cols, "size_mb": round(path.stat().st_size / 1e6, 1)}


def _read_tsv_sample(path, member, nrows):
    if member:
        with zipfile.ZipFile(path) as zf, zf.open(member) as fh:
            head = b"".join(fh.readline() for _ in range(nrows + 1))
        return pd.read_csv(io.BytesIO(head), sep="\t", dtype=str, on_bad_lines="skip", quoting=3)
    return pd.read_csv(path, sep="\t", dtype=str, nrows=nrows, on_bad_lines="skip", quoting=3)


def profile_all():
    out = {}
    for s, meta in SOURCES.items():
        for role in meta["files"]:
            done = set()
            for p, m in discover(s, role):
                stem = Path(m or p).stem.lower()
                if stem in done:                 # the same table in another format (e.g. .tsv, .dta and .xlsx)
                    continue
                if len(done) >= 4:
                    break
                done.add(stem)
                pr = profile_file(p, m)
                out[f"{s}/{role}/{Path(m or p).name}"] = pr
                if "fields" in pr:
                    log(f"profile {s}/{role}: {Path(p).name}: {pr['columns']} columns, e.g. " +
                        ", ".join(f['name'] for f in pr["fields"][:8]))
    RESULTS["profiles"] = out
    (Path(LAB["RESULTS"]) / "profiles" / "profiles.json").write_text(json.dumps(out, indent=1, default=str))
    return out
