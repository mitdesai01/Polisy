# -*- coding: utf-8 -*-
"""05 Downloads: fetch the open datasets, skip politely when blocked.

What it does: downloads O*NET, AIOE, the Census delineation files (List 1, counties; List 2,
principal cities), ACS metro tables and (optionally) PatentsView into data/raw.
ACS: one acs1_<year>.json per year in polisy_core.ACS_YEARS, from the Census API, and only for
years that no ACS file you already have covers (an ACS CSV in the data folder counts). A reply
that is not a data table (an error page, a request for an API key) is not saved; the log says
what came back. Without a download, save the ACS table as a CSV in the data folder instead.
Why: every later module reads from data/raw, so a blocked download should fail here with
an instruction, not halfway through an analysis.
Expect: files in data/raw and a printed line per source. Anything that fails prints the
manual URL to use instead.
Files you already have are not downloaded again, under whatever name and in whichever
search folder they sit (polisy_core.find), so a manual download is never overwritten.
Downloads keep their original file names.
Run it first: module 04 needs the Census file and module 06 the O*NET and AIOE files.
Diagnostics: run 01 again afterwards; every source you intend to use should say ok.
"""
import json
import urllib.request
from pathlib import Path
import pandas as pd
from polisy_core import CONFIG, paths, log, locate, read_acs, ACS_VARS, ACS_YEARS

# input key: (URLs tried in order, page to download from by hand)
SOURCES = {
    "ONET": (["https://www.onetcenter.org/dl_files/database/db_29_0_text.zip"],
             "https://www.onetcenter.org/database.html"),
    "AIOE": (["https://raw.githubusercontent.com/AIOE-Data/AIOE/main/AIOE_DataAppendix.xlsx",
              "https://raw.githubusercontent.com/AIOE-Data/AIOE/master/AIOE_DataAppendix.xlsx"],
             "https://github.com/AIOE-Data/AIOE"),
    "CBSA_REFERENCE": (["https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/"
                        "2023/delineation-files/list1_2023.xlsx"],
                       "https://www.census.gov/geographies/reference-files/time-series/demo/metro-micro/delineation-files.html"),
    "CBSA_PRINCIPAL_CITIES": (["https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/"
                               "2023/delineation-files/list2_2023.xlsx"],
                              "https://www.census.gov/geographies/reference-files/time-series/demo/metro-micro/delineation-files.html"),
}


def fetch(url, dest: Path, manual_url="", quiet=False):
    if dest.exists() and dest.stat().st_size > 0:
        log(f"{dest.name}: already present")
        return dest
    try:
        req = urllib.request.Request(url, headers={"User-Agent": CONFIG["USER_AGENT"]})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
        dest.write_bytes(data)
        log(f"{dest.name}: downloaded ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest
    except Exception as e:
        if not quiet:
            log(f"{dest.name}: download failed ({e}). Download by hand from {manual_url or url} into {dest.parent}")
        return None


def acs_metro(P, years=ACS_YEARS):
    have = read_acs()
    have = set() if have is None else set(have.year)
    for y in years:
        if y in have:
            log(f"ACS {y}: already have it")
            continue
        dest = P["RAW"] / f"acs1_{y}.json"
        if dest.exists():
            dest.unlink()                  # an earlier reply that was not a data table (read_acs said why)
        url = (f"https://api.census.gov/data/{y}/acs/acs1?get=NAME," + ",".join(ACS_VARS) +
               "&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:*")
        if CONFIG["CENSUS_API_KEY"]:
            url += f"&key={CONFIG['CENSUS_API_KEY']}"
        data = b""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": CONFIG["USER_AGENT"]})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            table = json.loads(data)
            if not (isinstance(table, list) and len(table) > 1 and "B01003_001E" in table[0]):
                raise ValueError("the reply is not an ACS data table")
        except Exception as e:
            head = data[:100].decode("utf-8", "replace").replace("\n", " ")
            log(f"ACS {y}: not downloaded ({type(e).__name__}: {e}{'; reply starts ' + repr(head) if head else ''}). "
                "Set CONFIG['CENSUS_API_KEY'] (free at api.census.gov/data/key_signup.html) and run 05 again, or save "
                "the ACS metro table as a CSV (NAME, CBSA code, year and the variables) in your data folder.")
            continue
        dest.write_bytes(data)
        log(f"ACS {y}: downloaded, {len(table) - 1} metro and micro areas")


def main(patentsview=False):
    P = paths()
    for key, (urls, manual) in SOURCES.items():
        have = locate(key)
        if have["path"] is not None:
            log(f"{key}: already have {have['path']} (found by {have['found_by']})")
            continue
        for i, url in enumerate(urls):
            if fetch(url, P["RAW"] / Path(url).name, manual if i == len(urls) - 1 else "", quiet=i < len(urls) - 1):
                break
    acs_metro(P)
    if patentsview:
        base = "https://s3.amazonaws.com/data.patentsview.org/download/"
        for f in ("g_patent.tsv.zip", "g_inventor_disambiguated.tsv.zip",
                  "g_location_disambiguated.tsv.zip", "g_cpc_current.tsv.zip"):
            fetch(base + f, P["RAW"] / f, "https://patentsview.org/download/data-download-tables")
    yy = [str(y)[2:] for y in CONFIG["OEWS_YEARS"]]
    log("OEWS zips are not downloaded here: BLS blocks scripted requests intermittently. Download "
        + ", ".join(f"oesm{y}nat.zip, oesm{y}ma.zip and oesm{y}in4.zip" for y in yy)
        + " by hand from https://www.bls.gov/oes/tables.htm into /content or data/raw; any name variant works.")
    return True


if __name__ == "__main__":
    main()
