# -*- coding: utf-8 -*-
"""IPUMS USA (American Community Survey microdata) -> occupation, industry and place profiles.

One extract fills several gaps at once (the working guide, Part 6): age, gender, race and education for every
occupation (not only the 301 the AIOE files describe), the public-sector share, where each occupation's jobs are, and
which occupations each industry employs. request_extract() orders it through the IPUMS API with your (free) key.
Or make it on usa.ipums.org with the same sample and variables (IPUMS_VARS), CSV format, and save the data file
and its .xml codebook in POLISY/data/ipums.

Sample: the ACS 5-year file 2019-2023 (IPUMS sample us2023c), about 16 million people, so small occupations have
enough respondents. Profiles use employed people aged 16 and over (EMPSTAT = 1), weighted by PERWT. A 5-year file's
weights represent the average population over the five years.

Canonical tables
  acs_occupation   occsoc (IPUMS's SOC-based code; X marks digits the ACS does not distinguish): workers, n (people in
                   the sample), mean age, shares under 30 and 55+, female, White non-Hispanic, Black, Hispanic, Asian,
                   bachelor's degree or more, graduate degree, public sector, self-employed, non-profit, worked from home,
                   mean log wage of full-time workers, share working in the states where VRscores infers party (primary
                   voting or L2's model), and how concentrated the jobs are across states and metros (Herfindahl index)
  acs_industry     indnaics (IPUMS's NAICS-based code): the same
  acs_occ_state    occsoc x state_fips: workers           acs_occ_metro   occsoc x cbsa (2013 delineation): workers
  acs_ind_occ      indnaics x occsoc: workers (each industry's occupation mix, the input to Seam 1's structural part)
link.py joins them to VRscores occupations (SOC 2018 code -> the most specific OCCSOC that fits) and industries
(NAICS-4 -> the INDNAICS codes within it).
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from ..core import log, canon, pc, dirs, STATE_ABBR
from ..sources import discover
from .. import staging as sg
from .patents import _copy

SAMPLES = ("us2023c",)
IPUMS_VARS = ["STATEFIP", "MET2013", "PERWT", "AGE", "SEX", "RACE", "HISPAN", "EDUC", "EMPSTAT", "CLASSWKR", "OCCSOC",
              "INDNAICS", "INCWAGE", "UHRSWORK", "TRANWORK", "MULTYEAR"]
INFERRED = sorted(STATE_ABBR[s] for s in pc.PRIMARY_STATES | pc.MODELED_STATES if s in STATE_ABBR)


def request_extract(api_key=None, samples=SAMPLES, variables=IPUMS_VARS, dest=None, wait=True,
                    description="POLISY: ACS occupation, industry and place profiles"):
    """Order the extract through the IPUMS API (pip install ipumspy), wait for it and download it to dest (default
    lab/raw/ipums). The key: api_key, or the IPUMS_API_KEY environment variable (in Colab, a secret). Extracts take
    from a few minutes to an hour; the numbered extract also appears on usa.ipums.org under My Data."""
    key = api_key or os.environ.get("IPUMS_API_KEY")
    if not key:
        raise ValueError("no IPUMS API key: get one at https://account.ipums.org/api_keys and pass it as api_key or set "
                         "the IPUMS_API_KEY environment variable")
    from ipumspy import IpumsApiClient, MicrodataExtract
    client = IpumsApiClient(key)
    ext = MicrodataExtract(collection="usa", samples=list(samples), variables=list(variables), description=description,
                           data_format="csv")
    client.submit_extract(ext)
    log(f"ipums: extract {ext.extract_id} submitted ({', '.join(samples)}; {len(variables)} variables)")
    if not wait:
        return ext
    client.wait_for_extract(ext, timeout=4 * 3600)
    dest = Path(dest) if dest else dirs()["RAW"] / "ipums"
    dest.mkdir(parents=True, exist_ok=True)
    client.download_extract(ext, download_dir=dest)
    log(f"ipums: extract {ext.extract_id} downloaded to {dest}")
    return dest


def _ddi_layout(xml_path):
    """{variable: (start column, width, implied decimals)} from an IPUMS codebook (.xml, DDI)."""
    out = {}
    for el in ET.parse(xml_path).getroot().iter():
        if not el.tag.endswith("}var") and el.tag != "var":
            continue
        name = el.attrib.get("ID") or el.attrib.get("name")
        loc = next((x for x in el if x.tag.endswith("location")), None)
        if name is None or loc is None:
            continue
        start = int(loc.attrib.get("StartPos", 0))
        width = int(loc.attrib.get("width") or int(loc.attrib.get("EndPos", start)) - start + 1)
        out[name.upper()] = (start, width, int(el.attrib.get("dcml", 0) or 0))
    return out


def _source(c):
    """A view `acs_raw` with the extract's variables as text; returns (column names, the data file) or (None, None).
    CSV extracts are read as they are; a fixed-width extract is cut into variables with its .xml codebook."""
    data = discover("ipums", "data")
    if not data:
        return None, None
    path, member = data[0]
    p, _ = sg.local(path, member)
    name = p.name.lower()
    comp = ", compression='gzip'" if name.endswith(".gz") else ""
    if name.endswith((".csv", ".csv.gz")):
        c.execute(f"CREATE OR REPLACE VIEW acs_raw AS SELECT * FROM read_csv('{pc.sqlp(p)}', header=true, all_varchar=true{comp})")
    elif name.endswith(".parquet"):
        c.execute(f"CREATE OR REPLACE VIEW acs_raw AS SELECT * FROM read_parquet('{pc.sqlp(p)}')")
    elif name.endswith((".dat", ".dat.gz")):
        stem = re.sub(r"\.dat(\.gz)?$", "", p.name, flags=re.I)
        ddi = [x for x, _ in discover("ipums", "ddi")]
        match = [x for x in ddi if Path(x).stem.lower() == stem.lower()] or ddi
        if not match:
            log(f"ipums: {p.name} is fixed-width but its .xml codebook is missing; save both files from the IPUMS extract page")
            return None, None
        lay = _ddi_layout(match[0])
        c.execute(f"CREATE OR REPLACE VIEW acs_lines AS SELECT line FROM read_csv('{pc.sqlp(p)}', header=false, delim='{chr(1)}', "
                  f"quote='', escape='', columns={{'line': 'VARCHAR'}}{comp})")
        parts = []
        for v, (start, width, dec) in lay.items():
            raw = f"trim(substr(line, {start}, {width}))"
            parts.append(f"CAST(try_cast({raw} AS DOUBLE) / {10 ** dec} AS VARCHAR) AS {v}" if dec else f"{raw} AS {v}")
        c.execute("CREATE OR REPLACE VIEW acs_raw AS SELECT " + ", ".join(parts) + " FROM acs_lines")
    else:
        log(f"ipums: {p.name} is neither a CSV nor a fixed-width IPUMS data file")
        return None, None
    return [r[0].upper() for r in c.execute("DESCRIBE SELECT * FROM acs_raw").fetchall()], p


def adapt_ipums():
    c = sg.con()
    try:
        cols, path = _source(c)
        if cols is None:
            log("ipums: no extract found. Request one with polisy_lab.adapters.ipums.request_extract(api_key) (the notebook's "
                "IPUMS step), or save an IPUMS USA extract (CSV, with its .xml codebook) in POLISY/data/ipums")
            return False
        # IPUMS names are upper case; a CSV may have them in any case
        real = {r[0].upper(): r[0] for r in c.execute("DESCRIBE SELECT * FROM acs_raw").fetchall()}
        need = ["PERWT", "AGE", "EMPSTAT", "OCCSOC", "INDNAICS"]
        miss = [v for v in need if v not in real]
        if miss:
            log(f"ipums: the extract lacks {miss}; request it again with IPUMS_VARS ({', '.join(IPUMS_VARS)})")
            return False

        def num(v, default="NULL"):
            return f'try_cast("{real[v]}" AS DOUBLE)' if v in real else default
        edu_ba = f"{num('EDUCD')} >= 101" if "EDUCD" in real else f"{num('EDUC')} >= 10"
        edu_gr = f"{num('EDUCD')} >= 114" if "EDUCD" in real else f"{num('EDUC')} >= 11"
        public = f"{num('CLASSWKRD')} BETWEEN 24 AND 28" if "CLASSWKRD" in real else "NULL"
        nonprofit = f"{num('CLASSWKRD')} = 23" if "CLASSWKRD" in real else "NULL"
        c.execute(f"""CREATE OR REPLACE TABLE p AS SELECT
                upper(trim(CAST("{real['OCCSOC']}" AS VARCHAR))) AS occsoc, upper(trim(CAST("{real['INDNAICS']}" AS VARCHAR))) AS indnaics,
                lpad(CAST(try_cast({num('STATEFIP')} AS INTEGER) AS VARCHAR), 2, '0') AS state_fips,
                nullif(CAST(try_cast({num('MET2013')} AS INTEGER) AS VARCHAR), '0') AS cbsa,
                {num('PERWT')} AS w, {num('AGE')} AS age, {num('SEX')} AS sex, {num('RACE')} AS race, {num('HISPAN', '0')} AS hispan,
                ({edu_ba}) AS ba, ({edu_gr}) AS grad, ({public}) AS public, ({nonprofit}) AS nonprofit,
                {num('CLASSWKR')} = 1 AS selfemp, {num('TRANWORK')} AS tranwork, {num('INCWAGE')} AS incwage, {num('UHRSWORK')} AS hours
            FROM acs_raw WHERE {num('EMPSTAT')} = 1 AND {num('AGE')} >= 16 AND {num('PERWT')} > 0""")
        n, w = c.execute("SELECT count(*), sum(w) FROM p").fetchone()
        years = ""
        if "MULTYEAR" in real or "YEAR" in real:
            yv = "MULTYEAR" if "MULTYEAR" in real else "YEAR"
            y = c.execute(f"SELECT min(try_cast(\"{real[yv]}\" AS INTEGER)), max(try_cast(\"{real[yv]}\" AS INTEGER)) FROM acs_raw").fetchone()
            years = f", survey years {y[0]}-{y[1]}"
        log(f"ipums: {n:,} employed people aged 16+ in {path.name} (weighted {w / 1e6:,.1f} million workers{years})")
        inferred = ", ".join(f"'{s}'" for s in INFERRED)

        def share(cond):
            return f"sum(w * ({cond})::INT) / sum(w)"
        prof = f"""sum(w) AS workers, count(*) AS n, sum(w * age) / sum(w) AS age, {share('age < 30')} AS age_under30,
                   {share('age >= 55')} AS age_55plus, {share('sex = 2')} AS female, {share('race = 1 AND hispan = 0')} AS white_nh,
                   {share('race = 2 AND hispan = 0')} AS black_nh, {share('hispan BETWEEN 1 AND 4')} AS hispanic,
                   {share('race IN (4, 5, 6) AND hispan = 0')} AS asian_nh, {share('ba')} AS ba_plus, {share('grad')} AS graduate,
                   {share('public')} AS public_sector, {share('selfemp')} AS self_employed, {share('nonprofit')} AS nonprofit,
                   sum(w * (tranwork = 80)::INT) / nullif(sum(w * (tranwork > 0)::INT), 0) AS work_from_home,
                   sum(w * ln(CASE WHEN incwage > 0 THEN incwage END))      -- DuckDB takes the log before the FILTER
                     FILTER (WHERE hours >= 35 AND incwage > 0 AND incwage < 999998)
                     / sum(w) FILTER (WHERE hours >= 35 AND incwage > 0 AND incwage < 999998) AS log_wage_ft,
                   {share(f'state_fips IN ({inferred})')} AS inferred_party_states"""
        for key, name in (("occsoc", "acs_occupation"), ("indnaics", "acs_industry")):
            c.execute(f"CREATE OR REPLACE TABLE g AS SELECT {key}, {prof} FROM p WHERE {key} NOT IN ('', '0', '000000') GROUP BY 1")
            for geo, col in (("state_fips", "hhi_states"), ("cbsa", "hhi_metros")):
                c.execute(f"""CREATE OR REPLACE TABLE h AS SELECT {key}, sum(s * s) AS {col} FROM
                              (SELECT {key}, sum(w) / sum(sum(w)) OVER (PARTITION BY {key}) AS s FROM p WHERE {geo} IS NOT NULL GROUP BY {key}, {geo})
                              GROUP BY 1""")
                c.execute(f"CREATE OR REPLACE TABLE g AS SELECT * FROM g LEFT JOIN h USING ({key})")
            _copy(c, f"SELECT * FROM g ORDER BY {key}", name)
        _copy(c, "SELECT occsoc, state_fips, sum(w) AS workers, count(*) AS n FROM p GROUP BY 1, 2", "acs_occ_state")
        _copy(c, "SELECT occsoc, cbsa, sum(w) AS workers, count(*) AS n FROM p WHERE cbsa IS NOT NULL GROUP BY 1, 2", "acs_occ_metro")
        _copy(c, "SELECT indnaics, occsoc, sum(w) AS workers, count(*) AS n FROM p GROUP BY 1, 2", "acs_ind_occ")
        return True
    finally:
        sg.close(c)


# --------------------------------------------------------------------------- links used by link.py
def occsoc_for(soc, codes):
    """The most specific OCCSOC code that fits a SOC code ('15-1252' -> '151252', else '15125X', '1512XX' ...)."""
    s = re.sub(r"\D", "", str(soc))
    if len(s) != 6:
        return None
    best, spec = None, -1
    for code in codes:
        k = str(code).strip().upper()
        if len(k) != 6 or not k[:2].isdigit():
            continue
        if all(ch == d or not ch.isdigit() for ch, d in zip(k, s)):
            n = sum(ch.isdigit() for ch in k)
            if n > spec:
                best, spec = code, n
    return best


def occupation_profiles(socs):
    """{SOC code: acs_occupation row as a dict (columns prefixed acs_)} for the codes given, and the OCCSOC used."""
    t = canon("acs_occupation")
    if not t.exists():
        return None
    d = pd.read_parquet(t)
    codes = d.occsoc.tolist()
    link = pd.DataFrame({"soc": pd.Series(socs).dropna().unique()})
    link["occsoc"] = link.soc.map(lambda s: occsoc_for(s, codes))
    prof = d.rename(columns={x: f"acs_{x}" for x in d.columns if x != "occsoc"})
    return link.merge(prof, on="occsoc", how="left")


def industry_profiles(naics4):
    """NAICS-4 -> acs_industry profiles: the INDNAICS codes within the NAICS-4 industry, weighted by workers; where the
    ACS only has a coarser code (for example 3MS, miscellaneous manufacturing), that code stands in (acs_coarse = True)."""
    t = canon("acs_industry")
    if not t.exists():
        return None
    d = pd.read_parquet(t)
    d["digits"] = d.indnaics.str.extract(r"^(\d+)")[0].fillna("")
    stats = [x for x in d.columns if x not in ("indnaics", "digits", "workers", "n")]
    rows = []
    for k in pd.Series(naics4).dropna().unique():
        k = str(k)
        fine = d[(d.digits.str.len() >= 4) & (d.digits.str[:4] == k)]
        coarse = False
        if fine.empty:
            cand = d[(d.digits.str.len() >= 2) & (d.digits.str.len() < 4) & d.digits.map(lambda x: k.startswith(x) if x else False)]
            fine = cand[cand.digits.str.len() == cand.digits.str.len().max()] if len(cand) else cand
            coarse = True
        if fine.empty:
            continue
        wts = fine.workers
        row = {"naics4": k, "acs_workers": float(wts.sum()), "acs_n": int(fine.n.sum()), "acs_coarse": coarse,
               "acs_indnaics": ";".join(fine.indnaics)}
        for s in stats:
            v = fine[s]
            ok = v.notna()
            row[f"acs_{s}"] = float((v[ok] * wts[ok]).sum() / wts[ok].sum()) if ok.any() and wts[ok].sum() else None
        rows.append(row)
    return pd.DataFrame(rows)
