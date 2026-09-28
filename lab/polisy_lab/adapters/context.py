# -*- coding: utf-8 -*-
"""Controls for the stress tests: county context (density, education, income, housing costs, climate,
industry mix) and the share of jobs that can be done at home (Dingel & Neiman 2020).

county_context   one row per county from JsonOfCounties (counties.json)
occ_telework     6-digit SOC -> share of O*NET occupations in it that can be done at home
ind_telework     2-digit NAICS -> share of employment that can be done at home
metro_telework   CBSA -> share of employment that can be done at home
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..core import write, log, pc
from ..sources import discover

# County Business Patterns sector names in counties.json -> 2-digit NAICS used by Dingel & Neiman
SECTORS = {"Agriculture": "11", "Mining": "21", "Utilities": "22", "Construction": "23", "Manufacturing": "31-33",
           "Wholesale trade": "42", "Retail trade": "44-45", "Transportation and warehousing": "48-49", "Information": "51",
           "Finance and insurance": "52", "Real estate and rental and leasing": "53",
           "Professional, scientific, and technical services": "54", "Management of companies and enterprises": "55",
           "Administrative and support and waste management and remediation services": "56", "Educational services": "61",
           "Health care and social assistance": "62", "Arts, entertainment, and recreation": "71",
           "Accommodation and food services": "72", "Other services (except public administration)": "81"}
KNOWLEDGE = ("51", "52", "54", "55")


def _num(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else np.nan
    except (TypeError, ValueError):
        return np.nan


def adapt_county_context():
    found = discover("county_context", "data")
    if not found:
        log("county_context: counties.json not found (module fetch downloads it)")
        return False
    path = found[0][0]
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log(f"county_context: cannot read {Path(path).name} ({e})")
        return False
    rows = []
    for c in data if isinstance(data, list) else data.values():
        fips = str(c.get("fips") or "").strip()
        if not fips.isdigit():
            continue
        pop = (c.get("population") or {})
        edu, col, noaa = c.get("edu") or {}, c.get("cost-of-living") or {}, c.get("noaa") or {}
        el = (c.get("elections") or {}).get("2016") or {}
        row = {"county_fips": fips.zfill(5), "land_km2": _num(c.get("land_area (km^2)")), "pop2019": _num(pop.get("2019")),
               "pop2010": _num(pop.get("2010")), "ba_share": _num(edu.get("bachelors+")), "avg_income": _num(c.get("avg_income")),
               "housing_cost": _num(col.get("housing_costs")), "temp_jan": _num(noaa.get("temp-jan")), "temp_jul": _num(noaa.get("temp-jul")),
               "rep_share_2016": _num(el.get("gop")) / _num(el.get("total")) if _num(el.get("total")) else np.nan}
        emp = {}
        for name, v in (c.get("industry") or {}).items():
            code = next((n for k, n in SECTORS.items() if name.startswith(k)), None)
            e = _num((v or {}).get("employees"))
            if code and e > 0:
                emp[code] = emp.get(code, 0) + e
        tot = sum(emp.values())
        for code in SECTORS.values():
            row["emp_" + code] = emp.get(code, 0) / tot if tot else np.nan
        row["knowledge_emp_share"] = sum(emp.get(k, 0) for k in KNOWLEDGE) / tot if tot else np.nan
        rows.append(row)
    d = pd.DataFrame(rows).drop_duplicates("county_fips")
    d["log_density"] = np.log(d.pop2019 / d.land_km2.clip(lower=1))
    d["log_income"] = np.log(d.avg_income.where(d.avg_income > 0))
    d["log_housing"] = np.log(d.housing_cost.where(d.housing_cost > 0))
    log(f"county_context: {Path(path).name}, {len(d):,} counties")
    write(d, "county_context", note="JsonOfCounties: ACS 2019 education, BEA income, NOAA climate, CBP industry mix")
    return True


def adapt_telework():
    got = False
    occ = discover("telework", "occupation")
    if occ:
        t = pc.read_table(*occ[0])
        t.columns = [pc.squash(c) for c in t.columns]
        t = t.assign(soc=t.onetsoccode.astype(str).str[:7], teleworkable=pd.to_numeric(t.teleworkable, errors="coerce"))
        write(t.groupby("soc", as_index=False).teleworkable.mean(), "occ_telework", note="Dingel & Neiman (2020)")
        got = True
    for role, key, name in (("industry", "naics", "ind_telework"), ("metro", "area", "metro_telework")):
        f = discover("telework", role)
        if not f:
            continue
        t = pc.read_table(*f[0])
        t.columns = [pc.squash(c) for c in t.columns]
        out = pd.DataFrame({("naics2" if role == "industry" else "cbsa"): t[key].astype(str).str.strip(),
                            "teleworkable_emp": pd.to_numeric(t.teleworkableemp, errors="coerce")})
        write(out.dropna(), name, note="Dingel & Neiman (2020)")
        got = True
    if not got:
        log("telework: Dingel & Neiman files not found (module fetch downloads them)")
    return got
