# -*- coding: utf-8 -*-
"""Patents -> firms (gvkey), and the firm-year patent panel.

Which firm owns a patent comes from DISCERN 2.0 first: it follows subsidiaries and ownership changes, patent by
patent, for Compustat firms and patents granted 1980-2021. DISCERN names the owner by permno_adj, mapped to gvkey by
year from a DISCERN file carrying both, else WRDS's CRSP/Compustat Merged link table, else Compustat's LPERMNO.
Outside DISCERN's years (and for published applications) the owner comes from PatentsView's disambiguated assignee,
matched by name to Compustat and to DISCERN's names (subsidiary and owner lists, with the years each firm held a
name, and the assignee names on DISCERN's patents). The two are compared where both exist, so the name match's
error rate is known.

Canonical tables
  discern_patents     patent_id -> gvkey (and permno_adj), from DISCERN's patent-level file
  discern_firm_year   DISCERN's own firm-year panel, as delivered (for comparison with the thesis)
  assignee_gvkey      PatentsView assignee -> gvkey by name: exact after normalizing (polisy_core.norm_name, the same
                      rule as the VRscores employer match), else fuzzy at LAB SETTINGS name_min_score
  patent_firm         patent_id -> gvkey, the link used ("discern" or "name"), and share = 1 / firms owning the patent
  application_firm    published application -> gvkey: its patent's link once granted, else the assignee name
  patent_citations    patent_id: backward citations, forward citations (all; within five years of grant, empty
                      where those five years are not over)
Panels (lab/panels, and results/tables as CSV and Stata files)
  firm_patents_year   gvkey x filing year (see FIRM_COLUMNS)
  panel_firm_year     the same with the VRscores workforce (POLISY_DA's firm_year) and DIPI, where present

Exploration and search (LAB SETTINGS explore_window, W = 5 years)
  explore            patents whose main CPC subclass does not appear on any of the firm's patents filed in the W
                     years before (a class new to the firm)
  search_depth       Katila & Ahuja (2002): how often the firm's citations in year t repeat citations it made in
                     t-W..t-1, per citation (sum over cited patents of n_t x n_prior / sum of n_t)
  search_scope       Katila & Ahuja (2002): the share of year-t citations not made in t-W..t-1
Years before the data's first year + W are left empty (the firm's history is unknown).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..core import log, LAB, canon, diagnostic, pc, panel_path, squash, RESULTS
from ..sources import discover
from .. import staging as sg
from .patents import ID, _norm_id, _view, _copy

PAT_NAMES = ["patent", "patentid", "patentnumber", "patnum", "patno", "patentno", "patnr", "pnum", "patentnum",
             "publnnr", "patid", "grantnumber", "patentnbr"]
YEAR_NAMES = ["year", "fyear", "appyear", "grantyear", "gyear", "applicationyear", "grantyr", "appyr", "datayear", "pubyear"]
NAME_NAMES = ["name", "subname", "subsidiaryname", "conm", "companyname", "firmname", "assigneename", "namestd", "stdname",
              "orgname", "standardname", "coname", "subsidiary"]
FIRM_COLUMNS = {
    "pat_filed": "granted patents filed in the year (fractional when several firms own a patent)",
    "pat_granted": "patents granted in the year",
    "ai_filed": "AI patents by the label in LAB SETTINGS ai_label (AIPD where it covers the patents)",
    "ai_label_covered": "patents the ai_label covers (for AIPD: patents in the dataset)",
    "ai_aipd_filed": "AI patents, AI Patent Dataset", "ai_cpc_filed": "AI patents, broad CPC definition",
    "ai_cpc_narrow_filed": "AI patents, G06N only", "climate_filed": "Y02/Y04S patents", "weapons_filed": "F41/F42 patents",
    "explore_filed": "patents in a CPC subclass new to the firm (none of its patents in the W years before)",
    "new_subclasses": "CPC subclasses on the year's patents that the firm did not use in the W years before",
    "prior_patents": "the firm's patents filed in the W years before (0 = no history, so everything is new)",
    "cites_fwd5_filed": "forward citations within five years of grant, summed over the year's patents",
    "back_cites": "backward citations to US patents made by the year's patents",
    "search_depth": "Katila & Ahuja search depth", "search_scope": "Katila & Ahuja search scope",
    "apps_filed": "published applications filed in the year", "apps_ai_aipd_filed": "... AI by the AIPD",
    "apps_ai_cpc_filed": "... AI by CPC (broad)", "apps_pending": "... not granted (yet)",
    "pat_discern": "patents linked through DISCERN", "pat_name": "patents linked by assignee name",
}


# --------------------------------------------------------------------------- DISCERN
def _columns_of(path, member):
    """Column names of a table without reading it all (Stata: the header only)."""
    if Path(member or path).suffix.lower() == ".dta":
        p, tmp = sg.local(path, member)
        try:
            with pd.read_stata(p, iterator=True) as r:
                return list(r.variable_labels())
        finally:
            if tmp:
                Path(p).unlink(missing_ok=True)
    c = sg.con()
    rd, tmp = sg.readable(path, member)
    try:
        return sg.columns(c, rd)
    finally:
        sg.close(c)
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


PUB_NAMES = ["openalexid", "openalex", "doi", "pmid", "pmcid", "wosid", "magid"]      # scientific publications
APP_NAMES = ["pgpubid", "documentnumber", "publicationnumber", "pubnumber", "pubno", "applicationid", "applicationnumber",
             "appid", "applid", "appnumber", "appno"]                                  # published patent applications
PERMNO_NAMES = ["permnoadj", "permno", "lpermno"]
LINK_NAMES = {"linkdt", "linkenddt", "linktype", "linkprim"}                           # WRDS's CRSP-Compustat link table
PAIR_SOURCES = {0: "DISCERN's own files", 1: "the CRSP-Compustat link table", 2: "Compustat's LPERMNO"}


def _spells(cols):
    """The owner spells a DISCERN name file spreads over columns (permno_adj1, fyear1, nyear1, permno_adj2, ...):
    [(permno_adjK, fyearK, nyearK), ...] in the order of K, a year column None where the file lacks it."""
    by = {}
    for col in cols:
        m = re.fullmatch(r"(permnoadj|fyear|nyear)(\d+)", squash(col))
        if m:
            by.setdefault(int(m.group(2)), {})[m.group(1)] = col
    return [(v["permnoadj"], v.get("fyear"), v.get("nyear")) for _, v in sorted(by.items()) if "permnoadj" in v]


def _classify(cols, fname=""):
    """What a DISCERN table is, from its columns (and, for the firm panel, its file name):
      patents       a patent number and its owner: at grant (discern_pat_grant_1980_2021) or at filing
                    (discern_pat_app_1980_2021, patents applied for in those years)
      publications  scientific articles (discern_pub_1980_2021): not used here
      applications  published patent applications: not used here (an application gets its firm through its granted
                    patent or its assignee's name, and the generative-AI wave comes after DISCERN's last year)
      crosswalk     permno_adj <-> gvkey (DISCERN's permno-gvkey file, or WRDS's CRSP-Compustat link table)
      panel         the firm-year panel
      names         firm and subsidiary names, one owner per row, or owner spells spread over columns
                    (discern_sub_names, discern_uo_names: permno_adj1, fyear1, nyear1, permno_adj2, ...)"""
    sq = {squash(x) for x in cols}
    pat = sg.exact_col(cols, PAT_NAMES)
    gv = sg.exact_col(cols, ["gvkey"]) or next((x for x in cols if "gvkey" in squash(x)), None)
    pn = sg.exact_col(cols, PERMNO_NAMES)
    yr = sg.exact_col(cols, YEAR_NAMES)
    nm = sg.exact_col(cols, NAME_NAMES)
    wide = _spells(cols)
    firm = gv or pn
    f = fname.lower()
    if pat and firm:
        kind = "patents"
    elif sg.exact_col(cols, PUB_NAMES):
        kind = "publications"
    elif firm and sg.exact_col(cols, APP_NAMES):
        kind = "applications"
    elif firm and yr and re.search(r"panel|firm_?year", f):
        kind = "panel"
    elif gv and pn and (sq & LINK_NAMES or (not nm and len(cols) <= 8)):
        kind = "crosswalk"
    elif nm and (wide or (firm and (len(cols) <= 5 or "name" in f))):
        kind = "names"
    elif firm and yr and gv:
        kind = "panel"
    else:
        kind = None
    roles = {"patent": pat, "gvkey": gv, "permno": pn, "year": yr, "name": nm, "spells": wide,
             "start": sg.exact_col(cols, ["linkdt"]), "end": sg.exact_col(cols, ["linkenddt"]),
             "linktype": sg.exact_col(cols, ["linktype"]), "linkprim": sg.exact_col(cols, ["linkprim"]),
             "sample": sg.exact_col(cols, ["sample"])}
    if kind == "patents":
        roles["dated"] = "app" if re.search(r"app", f) and "grant" not in f else "grant"
    return kind, roles


def _gv(expr):
    return f"nullif(lpad(regexp_extract(CAST({expr} AS VARCHAR), '(\\d+)', 1), 6, '0'), '000000')"


def _pn(expr):
    """permno_adj as text, the same whether Stata stored it as 10107 or 10107.0."""
    return f"nullif(regexp_replace(CAST({expr} AS VARCHAR), '\\.0+$', ''), '')"


def _pid(expr):
    """DISCERN patent numbers (often stored as numbers, 4000000.0) -> PatentsView patent_id; letters kept (D, RE, PP)."""
    v = f"upper(regexp_replace(CAST({expr} AS VARCHAR), '\\.0+$', ''))"
    return f"CASE WHEN regexp_matches({v}, '^[0-9]+$') THEN ltrim({v}, '0') ELSE regexp_replace({v}, '[^A-Z0-9]', '', 'g') END"


def _int(expr):
    return f"try_cast(try_cast({expr} AS DOUBLE) AS INTEGER)"


def _date_year(expr):
    """The year of a date stored as 2001-05-31, 2001-05-31 00:00:00 or 20010531 (empty for WRDS's 'E', still active)."""
    v = f"CAST({expr} AS VARCHAR)"
    return f"year(coalesce(try_cast({v} AS TIMESTAMP), try_strptime({v}, '%Y%m%d')))"


def _q(col):
    return sg.pc_quote(col)


def _n(n, word):
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _pairs(view, r, pri):
    """(permno, gvkey, year, pri) from a table carrying both ids: by the table's own year, by every year of a link's
    date range (WRDS's link table, primary links only), or without a year."""
    pn, gv = _pn(f"t.{_q(r['permno'])}"), _gv(f"t.{_q(r['gvkey'])}")
    where = [f"t.{_q(r['linktype'])} IN ('LU', 'LC')"] if r.get("linktype") else []
    where += [f"t.{_q(r['linkprim'])} IN ('P', 'C')"] if r.get("linkprim") else []
    w = (" WHERE " + " AND ".join(where)) if where else ""
    if r.get("start"):
        y0 = _date_year(f"t.{_q(r['start'])}")
        y1 = f"coalesce({_date_year('t.' + _q(r['end']))}, year(current_date))" if r.get("end") else "year(current_date)"
        return f"SELECT {pn} AS permno, {gv} AS gvkey, unnest(range({y0}, {y1} + 1)) AS year, {pri} AS pri FROM {view} t{w}"
    yr = _int(f"t.{_q(r['year'])}") if r["year"] else "NULL::INTEGER"
    return f"SELECT {pn} AS permno, {gv} AS gvkey, {yr} AS year, {pri} AS pri FROM {view} t{w}"


def _compustat_permnos(c):
    """(permno, gvkey, year, pri) from the Compustat file when it carries CRSP's LPERMNO (a CCM extract), else None."""
    loc = pc.locate("COMPUSTAT")
    if loc["path"] is None:
        return None
    rd, tmp = sg.readable(loc["path"], loc["member"])
    try:
        cols = sg.columns(c, rd)
        pn = sg.exact_col(cols, ["lpermno", "permno"])
        gv = sg.exact_col(cols, ["gvkey"])
        fy = sg.exact_col(cols, ["fyear", "year"])
        if not (pn and gv):
            return None
        yr = _int(_q(fy)) if fy else "NULL::INTEGER"
        c.execute(f"CREATE OR REPLACE TABLE comp_pn AS SELECT DISTINCT {_pn(_q(pn))} AS permno, {_gv(_q(gv))} AS gvkey, "
                  f"{yr} AS year, 2 AS pri FROM {rd}")
        return "SELECT * FROM comp_pn"
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


def adapt_discern():
    for old in (canon("discern_patents"), canon("discern_firm_year"), sg.staged_path("discern", "names")):
        Path(old).unlink(missing_ok=True)          # never keep a result from an earlier, different DISCERN download
    files = discover("discern", "tables")
    if not files:
        log("discern: not found. Put the DISCERN 2.0 download (its .csv or .dta files) in POLISY/data/discern; without it "
            "patents are linked to firms by assignee name only")
        return False
    links = [f for f in discover("discern", "links") if f not in files]
    tables = {"patents": [], "panel": [], "crosswalk": [], "names": []}
    for path, member in files + links:
        fname = Path(member or path).name
        try:
            cols = _columns_of(path, member)
        except Exception as e:
            log(f"discern: cannot read {fname} ({type(e).__name__}: {e})")
            continue
        kind, roles = _classify(cols, fname)
        roles["origin"] = "link" if (path, member) in links else "discern"
        if roles["origin"] == "link" and kind != "crosswalk":
            kind = None
        shown = {("owner_spells" if k == "spells" else k): (len(v) if k == "spells" else v) for k, v in roles.items()
                 if v and k != "origin"}
        what = {"publications": "scientific publications, not used here",
                "applications": "published applications, not used here (they get their firm through the granted patent "
                                "or the assignee name)"}
        log(f"discern: {fname}: " + (f"{kind} table ({', '.join(f'{k}={v}' for k, v in shown.items())})" if kind in tables
                                     else what.get(kind, f"not used (columns {cols[:8]})")))
        if kind in tables:
            tables[kind].append((path, member, roles))
    tables["panel"].sort(key=lambda t: not re.search(r"panel", Path(t[1] or t[0]).name.lower()))   # a file named panel first
    c = sg.con()
    try:
        for kind, found in tables.items():             # stage each table (Stata files become Parquet once)
            for i, (path, member, roles) in enumerate(found):
                out = sg.staged_path("discern", f"{kind}_{i}")
                if not sg.fresh(out, path, member):
                    rd, tmp = sg.readable(path, member)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    c.execute(f"COPY (SELECT * FROM {rd}) TO '{pc.sqlp(out)}' (FORMAT parquet, COMPRESSION zstd)")
                    sg.write_stamp(out, path, member, roles=roles)
                    if tmp is not None:
                        Path(tmp).unlink(missing_ok=True)
                _view(c, f"d_{kind}_{i}", out)
        # permno_adj -> gvkey: DISCERN's own files first, then WRDS's link table, then Compustat's LPERMNO; one gvkey per
        # permno_adj and year (pg), and the one it has most years (pg1) for rows without a year or outside the table's years
        pairs = [_pairs(f"d_{k}_{i}", r, 0 if r["origin"] == "discern" else 1)
                 for k in ("crosswalk", "panel", "patents", "names") for i, (_, _, r) in enumerate(tables[k]) if r["permno"] and r["gvkey"]]
        comp = _compustat_permnos(c)
        pairs += [comp] if comp else []
        c.execute("CREATE OR REPLACE TABLE pg AS " + (
            f"""SELECT permno, year, first(gvkey ORDER BY pri, n DESC, gvkey) AS gvkey, min(pri) AS pri
                FROM (SELECT permno, gvkey, year, min(pri) AS pri, count(*) AS n FROM ({' UNION ALL '.join(pairs)})
                      WHERE permno IS NOT NULL AND gvkey IS NOT NULL GROUP BY permno, gvkey, year)
                GROUP BY permno, year""" if pairs else
            "SELECT NULL::VARCHAR AS permno, NULL::INTEGER AS year, NULL::VARCHAR AS gvkey, 0 AS pri WHERE FALSE"))
        c.execute("""CREATE OR REPLACE TABLE pg1 AS SELECT permno, first(gvkey ORDER BY pri, n DESC, gvkey) AS gvkey
                     FROM (SELECT permno, gvkey, min(pri) AS pri, count(*) AS n FROM pg GROUP BY 1, 2) GROUP BY 1""")
        by = dict(c.execute("SELECT pri, count(*) FROM (SELECT permno, min(pri) AS pri FROM pg GROUP BY 1) GROUP BY 1").fetchall())
        log("discern: permno_adj -> gvkey for " + (f"{_n(sum(by.values()), 'firm')}: " + ", ".join(
            f"{n:,} {'from' if k == min(by) else 'more from'} {PAIR_SOURCES[k]}" for k, n in sorted(by.items()))
            if by else "no firm: no file links the two"))

        def firm_of(alias, r):
            """SQL (gvkey, joins) for a DISCERN table row: its own gvkey, else its permno_adj through pg (same year) or pg1."""
            if r["gvkey"]:
                return _gv(f"{alias}.{_q(r['gvkey'])}"), ""
            pn = _pn(f"{alias}.{_q(r['permno'])}")
            yr = _int(f"{alias}.{_q(r['year'])}") if r["year"] else "NULL"
            return ("coalesce(x1.gvkey, x2.gvkey)",
                    f" LEFT JOIN pg x1 ON x1.permno = {pn} AND x1.year = {yr} LEFT JOIN pg1 x2 ON x2.permno = {pn}")
        wrote = False
        parts = []
        for i, (_, _, r) in enumerate(tables["patents"]):
            gv, joins = firm_of("t", r)
            yr = _int(f"t.{_q(r['year'])}") if r["year"] else "NULL::INTEGER"
            pn = _pn(f"t.{_q(r['permno'])}") if r["permno"] else "NULL::VARCHAR"
            parts.append(f"SELECT {_pid('t.' + _q(r['patent']))} AS patent_id, {gv} AS gvkey, {pn} AS permno_adj, "
                         f"{yr} AS discern_year, '{r.get('dated', 'grant')}' AS discern_file FROM d_patents_{i} t{joins}")
        if parts:
            c.execute("CREATE OR REPLACE TABLE dpa AS SELECT DISTINCT * FROM (" + " UNION ALL ".join(parts) + ") WHERE patent_id <> ''")
            tot, got = c.execute("SELECT count(DISTINCT patent_id), count(DISTINCT patent_id) FILTER (WHERE gvkey IS NOT NULL) "
                                 "FROM dpa").fetchone()
            diagnostic("DISCERN patents -> gvkey", "discern patents", "permno_adj -> gvkey", "permno_adj, year", got, tot, "patents")
            if got:
                _copy(c, "SELECT * FROM dpa WHERE gvkey IS NOT NULL", "discern_patents")
                k = c.execute("SELECT count(DISTINCT gvkey), min(discern_year), max(discern_year) FROM dpa WHERE gvkey IS NOT NULL").fetchone()
                log(f"discern: {got:,} of {tot:,} patents ({got / tot:.1%}) owned by {k[0]:,} Compustat firms"
                    + (f", years {k[1]}-{k[2]}" if k[1] else ""))
                wrote = True
            if got < tot:
                c.execute("CREATE OR REPLACE TABLE dmiss AS SELECT * FROM dpa WHERE patent_id NOT IN "
                          "(SELECT patent_id FROM dpa WHERE gvkey IS NOT NULL)")
                nopn = pc.q1(c, "SELECT count(DISTINCT patent_id) FROM dmiss WHERE permno_adj IS NULL")
                miss = pc.q(c, "SELECT permno_adj, count(DISTINCT patent_id) AS patents FROM dmiss WHERE permno_adj IS NOT NULL "
                               "GROUP BY 1 ORDER BY 2 DESC LIMIT 5")
                log(f"discern: {_n(tot - got, 'patent')} without a gvkey"
                    + (f"; {nopn:,} of them have no permno_adj" if nopn else "")
                    + (f"; owners (permno_adj) with the most: {', '.join(f'{a} ({b:,})' for a, b in miss.itertuples(index=False))}"
                       if len(miss) else "")
                    + ("" if by else ". Nothing links permno_adj to gvkey: add WRDS's CRSP/Compustat Merged link table "
                       "(ccmxpf_lnkhist, with gvkey, lpermno, linkdt, linkenddt) to POLISY/data, or use a Compustat extract "
                       "with LPERMNO"))
            for i, (_, _, r) in enumerate(tables["patents"]):
                if r.get("sample"):                     # which of DISCERN's samples the patents come from, for the record
                    s = pc.q(c, f"SELECT CAST({_q(r['sample'])} AS VARCHAR) AS v, count(*) AS n FROM d_patents_{i} "
                                "GROUP BY 1 ORDER BY 2 DESC LIMIT 6")
                    log("discern: patents by DISCERN's sample column: " + ", ".join(f"{a} {b:,}" for a, b in s.itertuples(index=False)))
        if tables["panel"]:
            _, _, r = tables["panel"][0]
            gv, joins = firm_of("t", r)
            drop = ", ".join(_q(x) for x in (r["year"], r["gvkey"]) if x)
            order = f"ORDER BY {_pn(_q(r['permno']))}" if r["permno"] else ""
            _copy(c, f"""SELECT * FROM (SELECT {gv} AS gvkey, {_int('t.' + _q(r['year']))} AS year,
                                               t.* EXCLUDE ({drop}) FROM d_panel_0 t{joins})
                         WHERE gvkey IS NOT NULL AND year IS NOT NULL
                         QUALIFY row_number() OVER (PARTITION BY gvkey, year {order}) = 1""", "discern_firm_year")
        parts = []                                     # names for the assignee name match, with the years each firm held them
        for i, (_, _, r) in enumerate(tables["patents"]):
            if r["name"]:                              # the assignee names on the patents DISCERN gives each firm
                gv, joins = firm_of("t", r)
                yr = _int(f"t.{_q(r['year'])}") if r["year"] else "NULL::INTEGER"
                parts.append(f"SELECT {gv} AS gvkey, CAST(t.{_q(r['name'])} AS VARCHAR) AS name, {yr} AS fy0, {yr} AS fy1 "
                             f"FROM d_patents_{i} t{joins}")
        for i, (_, _, r) in enumerate(tables["names"]):
            name = f"CAST(t.{_q(r['name'])} AS VARCHAR)"
            if r["spells"]:                            # one row per owner spell: the name, that owner, its years
                for pn_col, fy_col, ny_col in r["spells"]:
                    fy = _int(f"t.{_q(fy_col)}") if fy_col else "NULL::INTEGER"
                    ny = _int(f"t.{_q(ny_col)}") if ny_col else "NULL::INTEGER"
                    last = f"CASE WHEN {ny} >= 1800 THEN {ny} WHEN {ny} >= 1 THEN {fy} + {ny} - 1 END"  # a year or a count
                    parts.append(f"SELECT x.gvkey, {name} AS name, {fy} AS fy0, {last} AS fy1 FROM d_names_{i} t "
                                 f"JOIN pg1 x ON x.permno = {_pn('t.' + _q(pn_col))}")
            else:
                gv, joins = firm_of("t", r)
                yr = _int(f"t.{_q(r['year'])}") if r["year"] else "NULL::INTEGER"
                parts.append(f"SELECT {gv} AS gvkey, {name} AS name, {yr} AS fy0, {yr} AS fy1 FROM d_names_{i} t{joins}")
        if parts:
            c.execute("CREATE OR REPLACE TABLE dn AS SELECT gvkey, name, min(fy0) AS fy0, max(fy1) AS fy1 FROM ("
                      + " UNION ALL ".join(parts) + ") WHERE gvkey IS NOT NULL AND name IS NOT NULL AND name <> '' GROUP BY 1, 2")
            n_names, n_firms = c.execute("SELECT count(DISTINCT name), count(DISTINCT gvkey) FROM dn").fetchone()
            if n_names:
                c.execute(f"COPY dn TO '{pc.sqlp(sg.staged_path('discern', 'names'))}' (FORMAT parquet)")
                log(f"discern: {_n(n_names, 'name')} (firms, subsidiaries and the assignees on DISCERN's patents) of "
                    f"{_n(n_firms, 'Compustat firm')} for the assignee name match")
        return wrote
    finally:
        sg.close(c)


# --------------------------------------------------------------------------- assignee names -> gvkey
def _compustat_names():
    loc = pc.locate("COMPUSTAT")
    if loc["path"] is None:
        return None
    c = sg.con()
    rd, tmp = sg.readable(loc["path"], loc["member"])
    try:
        cols = sg.columns(c, rd)
        gv = sg.exact_col(cols, ["gvkey"])
        nm = sg.exact_col(cols, ["conm", "conml", "companyname", "coname", "name"])
        fy = sg.exact_col(cols, ["fyear", "year", "datadate"])
        if not (gv and nm):
            log(f"firm names: Compustat file {Path(loc['path']).name} has no gvkey or company name column")
            return None
        yr = f"try_cast(substr(CAST({sg.pc_quote(fy)} AS VARCHAR), 1, 4) AS INTEGER)" if fy else "NULL::INTEGER"
        d = pc.q(c, f"""SELECT {_gv(sg.pc_quote(gv))} AS gvkey, CAST({sg.pc_quote(nm)} AS VARCHAR) AS name,
                               min({yr}) AS fy0, max({yr}) AS fy1 FROM {rd} GROUP BY 1, 2""")
        return d.dropna(subset=["gvkey", "name"]).assign(source="compustat")
    finally:
        sg.close(c)
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


def _assignees():
    """PatentsView assignees (granted and pre-grant) with how many patents they hold and in which years."""
    g = sg.staged_path("patentsview", "g_assignee_disambiguated")
    p = sg.staged_path("patentsview_pregrant", "pg_assignee_disambiguated")
    if not g.exists() and not p.exists():
        return None
    c = sg.con()
    try:
        parts = []
        if g.exists() and canon("patents").exists():
            parts.append(f"""SELECT a.assignee_id, a.org, try_cast(try_cast(a.atype AS DOUBLE) AS INTEGER) % 10 AS atype, p.app_year AS y
                             FROM read_parquet('{pc.sqlp(g)}') a JOIN read_parquet('{pc.sqlp(canon('patents'))}') p USING (patent_id)""")
        if p.exists() and canon("applications").exists():
            parts.append(f"""SELECT a.assignee_id, a.org, try_cast(try_cast(a.atype AS DOUBLE) AS INTEGER) % 10 AS atype, p.app_year AS y
                             FROM read_parquet('{pc.sqlp(p)}') a JOIN read_parquet('{pc.sqlp(canon('applications'))}') p USING (pgpub_id)""")
        if not parts:
            return None
        return pc.q(c, f"""WITH x AS (SELECT * FROM ({' UNION ALL '.join(parts)}) WHERE org IS NOT NULL AND org <> ''),
                                o AS (SELECT assignee_id, first(org ORDER BY k DESC, org) AS org
                                      FROM (SELECT assignee_id, org, count(*) AS k FROM x GROUP BY 1, 2) GROUP BY 1),
                                t AS (SELECT assignee_id, first(atype ORDER BY k DESC, atype NULLS LAST) AS atype
                                      FROM (SELECT assignee_id, atype, count(*) AS k FROM x GROUP BY 1, 2) GROUP BY 1)
                           SELECT x.assignee_id, any_value(o.org) AS org, any_value(t.atype) AS atype, count(*) AS docs,
                                  min(x.y) AS y0, max(x.y) AS y1
                           FROM x JOIN o USING (assignee_id) JOIN t USING (assignee_id) GROUP BY 1 ORDER BY 1""")
    finally:
        sg.close(c)


_ASSIGNEES = {}


def _dictionary(cutoff=None):
    """Firm names for the name match, with the years each firm held each name: Compustat's (its fiscal years) and
    DISCERN's (owner spells of subsidiary and owner names, and the assignee names on the patents it gives each firm).
    cutoff: only what was known by that year (names first held later left out, later years cut), for the
    out-of-sample check."""
    firms = _compustat_names()
    dn = sg.staged_path("discern", "names")
    if dn.exists():
        extra = pd.read_parquet(dn).assign(source="discern names")
        for col in ("fy0", "fy1"):
            if col not in extra:
                extra[col] = np.nan
        firms = extra if firms is None else pd.concat([firms, extra], ignore_index=True)
    if firms is None or firms.empty:
        return None
    firms = firms.copy()
    if cutoff is not None:
        firms = firms[firms.fy0.isna() | (firms.fy0 <= cutoff)].copy()
        firms["fy1"] = firms.fy1.clip(upper=cutoff)
    firms["name_norm"] = firms.name.map(pc.norm_name)
    return firms[firms.name_norm.str.len() >= 3]


def _match(firms, a):
    """Company assignees -> gvkey by normalized name: exact, then fuzzy for the unmatched (assignees with 5+ documents);
    a name several firms held goes to the one that held it last within the assignee's years (_by_years)."""
    lut = firms.groupby("name_norm").gvkey.agg(lambda s: sorted(set(s)))
    spans = {}                                  # for names several firms held: the years each held it
    shared = firms[firms.name_norm.isin(lut.index[lut.map(len) > 1])]
    for (n, g), y in shared.groupby(["name_norm", "gvkey"]).agg(fy0=("fy0", "min"), fy1=("fy1", "max")).iterrows():
        spans.setdefault(n, {})[g] = (y.fy0, y.fy1)
    rows = []
    for r in a.itertuples(index=False):
        cands = lut.get(r.name_norm)
        if cands:
            best = _by_years(cands, r.y0, r.y1, spans.get(r.name_norm, {}))
            rows.append((r.assignee_id, r.org, r.name_norm, best, "exact", 100.0, len(cands) > 1, r.docs))
    got = {x[0] for x in rows}
    min_score = float(LAB["SETTINGS"].get("name_min_score", 95))
    try:
        from rapidfuzz import fuzz, process
        pool = lut.index.to_numpy()
        blocks = {}
        for i, n in enumerate(pool):
            blocks.setdefault(n.split()[0], []).append(i)
        todo = a[~a.assignee_id.isin(got) & (a.docs >= 5) & (a.name_norm.str.len() >= 4)]
        for r in todo.itertuples(index=False):
            idx = blocks.get(r.name_norm.split()[0], [])
            if not idx:
                continue
            hit = process.extractOne(r.name_norm, pool[idx], scorer=fuzz.token_sort_ratio, score_cutoff=min_score)
            if hit:
                cands = lut[hit[0]]
                rows.append((r.assignee_id, r.org, r.name_norm, _by_years(cands, r.y0, r.y1, spans.get(hit[0], {})), "fuzzy",
                             float(hit[1]), len(cands) > 1, r.docs))
    except ImportError:
        log("firm names: pip install rapidfuzz for fuzzy name matches (exact matches only for now)")
    m = pd.DataFrame(rows, columns=["assignee_id", "assignee_org", "name_norm", "gvkey", "method", "score", "ambiguous", "docs"])
    name = (firms.assign(c=firms.source.eq("compustat")).sort_values(["gvkey", "c", "fy1", "name"], ascending=[True, False, False, True],
                                                                       na_position="last")
            .drop_duplicates("gvkey").set_index("gvkey").name)
    m["firm_name"] = m.gvkey.map(name)
    return m


def match_assignees():
    """assignee_gvkey: company assignees -> gvkey by normalized name (exact), then fuzzy for the unmatched."""
    firms = _dictionary()
    dn = sg.staged_path("discern", "names")
    if firms is None:
        log("firm names: no Compustat file (POLISY_DA's COMPUSTAT input) and no DISCERN names, so assignees cannot be "
            "matched to firms by name")
        return False
    a = _assignees()
    if a is None or a.empty:
        log("firm names: no assignees (g_assignee_disambiguated) to match")
        return False
    a = a[a.atype.isin([2, 3]) | a.atype.isna()].copy()          # companies, US and foreign
    a["name_norm"] = a.org.map(pc.norm_name)
    _ASSIGNEES["a"] = a
    m = _match(firms, a)
    m.to_parquet(canon("assignee_gvkey"), index=False)
    share = m.docs.sum() / max(a.docs.sum(), 1)
    log(f"canonical assignee_gvkey: {len(m):,} company assignees matched to {m.gvkey.nunique():,} firms "
        f"({(m.method == 'exact').sum():,} exact, {(m.method == 'fuzzy').sum():,} fuzzy, {m.ambiguous.sum():,} names shared by "
        f"several gvkeys, resolved by years), holding {share:.1%} of company-assigned patents and applications")
    diagnostic("assignees -> Compustat firms (names)", "assignee_gvkey", "Compustat names" + (" + DISCERN names" if dn.exists() else ""),
               "normalized company name", int(m.docs.sum()), int(a.docs.sum()), "company-assigned documents")
    return True


def _holdout(c, last, years=3):
    """How well the name match does on patents it has not seen: the name list as it stood in last - years (names first
    held later left out, ownership cut at that year), matched to the assignees of the patents DISCERN links in the
    following years, and compared with DISCERN. This is the name match's error rate for the grants after DISCERN."""
    a = _ASSIGNEES.get("a")
    ga = sg.staged_path("patentsview", "g_assignee_disambiguated")
    cutoff = int(last) - years
    firms = _dictionary(cutoff)
    if a is None or firms is None or not ga.exists():
        return
    m = _match(firms, a)
    c.register("mh_df", m[["assignee_id", "gvkey"]])
    c.execute(f"""CREATE OR REPLACE TABLE nh AS SELECT DISTINCT s.patent_id, h.gvkey
                  FROM read_parquet('{pc.sqlp(ga)}') s JOIN mh_df h USING (assignee_id) JOIN p USING (patent_id)
                  WHERE p.year > {cutoff} AND p.year <= {last}""")
    c.unregister("mh_df")
    tot, found, agree = c.execute(f"""
        WITH ev AS (SELECT DISTINCT dl.patent_id FROM dl JOIN p USING (patent_id) WHERE p.year > {cutoff} AND p.year <= {last})
        SELECT count(*), count(*) FILTER (WHERE patent_id IN (SELECT patent_id FROM nh)),
               count(*) FILTER (WHERE patent_id IN (SELECT n.patent_id FROM nh n JOIN dl d USING (patent_id, gvkey)))
        FROM ev""").fetchone()
    if not tot:
        return
    log(f"patent_firm: out of sample (names as known in {cutoff}, DISCERN's grants of {cutoff + 1}-{last}): the name match "
        f"finds {found / tot:.1%} of DISCERN's {tot:,} patents and names DISCERN's firm for {agree / max(found, 1):.1%} of those it finds")
    diagnostic("name match agrees with DISCERN (out of sample)", "patent_firm (name)", "discern_patents", "patent_id", agree, found,
               "patents both link", note=f"names as known in {cutoff}, grants {cutoff + 1}-{last}; the name match finds "
                                         f"{found / tot:.1%} of DISCERN's patents")


def _by_years(cands, y0, y1, span):
    """Among firms that held the same name (a subsidiary sold from one to another, two firms of one name), the one that
    held it last within the assignee's patenting years y0-y1, which owns the recent patents the name match fills in
    after DISCERN's last year; then the one that held it longest. span: {gvkey: (first, last year)}. Firms whose years
    are unknown come after those that overlap, firms that never overlap last."""
    if len(cands) == 1:
        return cands[0]

    def key(g):
        f0, f1 = span.get(g, (np.nan, np.nan))
        if pd.isna(y0) or pd.isna(y1) or pd.isna(f0) or pd.isna(f1):
            return (1, 0, 0)
        overlap = min(y1, f1) - max(y0, f0)
        return (2, min(y1, f1), overlap) if overlap >= 0 else (0, overlap, 0)
    return max(cands, key=key)


# --------------------------------------------------------------------------- patent -> firm
def adapt_patent_firms():
    pats = canon("patents")
    if not pats.exists():
        log("patent_firm: needs the patents table (adapter patentsview)")
        return False
    have_names = match_assignees()
    have_d = canon("discern_patents").exists()
    if not have_d and not have_names:
        log("patent_firm: neither DISCERN nor an assignee-name match is available, so no patent has a firm")
        return False
    c = sg.con()
    try:
        _view(c, "p", pats)
        if have_d:
            _view(c, "d", canon("discern_patents"))
            dfile = "d.discern_file" if "discern_file" in sg.columns(c, "d") else "'grant'"
            c.execute(f"CREATE OR REPLACE TABLE dall AS SELECT DISTINCT d.patent_id, d.gvkey, {dfile} AS f FROM d JOIN p USING (patent_id)")
            owner = LAB["SETTINGS"].get("discern_owner", "filing")
            pref = "app" if owner == "filing" else "grant"
            c.execute(f"""CREATE OR REPLACE TABLE dl AS SELECT patent_id, gvkey FROM (
                              SELECT patent_id, gvkey, dense_rank() OVER (PARTITION BY patent_id ORDER BY (f = '{pref}') DESC) AS r
                              FROM dall) WHERE r = 1""")
            both, same = c.execute("""SELECT (SELECT count(*) FROM (SELECT patent_id FROM dall GROUP BY 1 HAVING count(DISTINCT f) = 2)),
                                             (SELECT count(DISTINCT a.patent_id) FROM dall a JOIN dall b
                                              ON a.patent_id = b.patent_id AND a.gvkey = b.gvkey AND a.f = 'grant' AND b.f = 'app')""").fetchone()
            if both:
                log(f"patent_firm: {both:,} patents are in both DISCERN's grant- and application-dated files; the owner differs "
                    f"for {both - same:,} ({(both - same) / both:.1%}: sold between filing and grant); the owner at {owner} is used "
                    "(LAB SETTINGS discern_owner: 'filing' or 'grant')")
            # DISCERN covers every grant up to the last fiscal year of its grant-dated file (fiscal years end in other
            # months, so its last fiscal year also holds some grants of the next calendar year); later grants only where
            # it has them
            gfile = "WHERE d.discern_file = 'grant'" if dfile != "'grant'" else ""
            last = pc.q1(c, f"SELECT max(d.discern_year) FROM d {gfile}") or \
                pc.q1(c, "SELECT max(p.year) FROM dl JOIN p USING (patent_id)")
        else:
            c.execute("CREATE OR REPLACE TABLE dl AS SELECT NULL::VARCHAR AS patent_id, NULL::VARCHAR AS gvkey WHERE FALSE")
            last = None
        ga = sg.staged_path("patentsview", "g_assignee_disambiguated")
        if have_names and ga.exists():
            _view(c, "ag", canon("assignee_gvkey"))
            c.execute(f"""CREATE OR REPLACE TABLE nl AS SELECT DISTINCT a.patent_id, g.gvkey
                          FROM read_parquet('{pc.sqlp(ga)}') a JOIN ag g USING (assignee_id) JOIN p USING (patent_id)""")
        else:
            c.execute("CREATE OR REPLACE TABLE nl AS SELECT NULL::VARCHAR AS patent_id, NULL::VARCHAR AS gvkey WHERE FALSE")
        fill = LAB["SETTINGS"].get("name_fill", "after_discern")
        if not have_d or last is None:
            use = "TRUE"
        elif fill == "unlinked":
            use = "n.patent_id NOT IN (SELECT patent_id FROM dl)"
        elif fill == "none":
            use = "FALSE"
        else:                                    # after DISCERN's last grant year, for the patents it leaves unlinked
            use = f"p.year > {last} AND n.patent_id NOT IN (SELECT patent_id FROM dl)"
        c.execute(f"""CREATE OR REPLACE TABLE pf AS
            WITH x AS (SELECT patent_id, gvkey, 'discern' AS link FROM dl
                       UNION ALL
                       SELECT n.patent_id, n.gvkey, 'name' AS link FROM nl n JOIN p USING (patent_id) WHERE {use})
            SELECT patent_id, gvkey, link, 1.0 / count(*) OVER (PARTITION BY patent_id) AS share FROM x""")
        _copy(c, "SELECT * FROM pf", "patent_firm")
        n_all, n_co = c.execute("SELECT count(*), count(*) FILTER (WHERE assignee_type IN (2, 3)) FROM p").fetchone()
        k = c.execute("""SELECT count(DISTINCT patent_id), count(DISTINCT patent_id) FILTER (WHERE link = 'discern'),
                                count(DISTINCT patent_id) FILTER (WHERE link = 'name'), count(DISTINCT gvkey) FROM pf""").fetchone()
        log(f"patent_firm: {k[0]:,} patents linked to {k[3]:,} firms ({k[1]:,} through DISCERN, {k[2]:,} by assignee name"
            + (f", the name match filling in {fill.replace('_', ' ')}"
               + (f" (grants after {last} that DISCERN leaves unlinked)" if fill == 'after_discern' and have_d else "")
               if have_d else "") + f"); {k[0] / max(n_co, 1):.1%} of the {n_co:,} company-assigned patents")
        diagnostic("patents -> firms (gvkey)", "patents", "DISCERN" + (" + assignee names" if have_names else ""), "patent_id",
                   k[0], n_co, "company-assigned patents")
        if have_d and have_names and last is not None:   # the name match's error rate, on patents it has not seen
            _holdout(c, last)
        _application_firms(c)
        return True
    finally:
        sg.close(c)


def _application_firms(c):
    apps = canon("applications")
    if not apps.exists():
        return
    _view(c, "a", apps)
    pa = sg.staged_path("patentsview_pregrant", "pg_assignee_disambiguated")
    names = ""
    if pa.exists() and canon("assignee_gvkey").exists():
        names = f"""UNION ALL
                    SELECT a.pgpub_id, g.gvkey, 'name' AS link FROM a JOIN read_parquet('{pc.sqlp(pa)}') s ON s.pgpub_id = a.pgpub_id
                    JOIN read_parquet('{pc.sqlp(canon('assignee_gvkey'))}') g ON g.assignee_id = s.assignee_id
                    WHERE a.granted_patent_id IS NULL"""
    _copy(c, f"""WITH x AS (SELECT a.pgpub_id, f.gvkey, 'patent: ' || f.link AS link FROM a JOIN pf f ON f.patent_id = a.granted_patent_id
                            {names})
                 SELECT DISTINCT pgpub_id, gvkey, link, 1.0 / count(*) OVER (PARTITION BY pgpub_id) AS share FROM (SELECT DISTINCT * FROM x)""",
          "application_firm")


# --------------------------------------------------------------------------- citations
def adapt_citations():
    """Citation counts per patent, from g_us_patent_citation (the largest PatentsView table: staged once)."""
    found = discover("patentsview", "citation")
    if not found:
        log("citations: no g_us_patent_citation. Forward citations and search depth and scope need it (the notebook's "
            "download step, set 'citations'); exploration by new classes does not")
        return False
    if not canon("patents").exists():
        return False
    path, _ = sg.stage("patentsview", "g_us_patent_citation", found[0],
                       {"patent_id": (ID, True), "cited": ([r"citationpatentid", r"citedpatentid", r"citedpatentnumber"], True),
                        "category": [r"citationcategory", r"category"]})
    if path is None:
        return False
    c = sg.con()
    try:
        _view(c, "p", canon("patents"))
        c.execute(f"CREATE OR REPLACE VIEW cit AS SELECT patent_id, {_norm_id('cited')} AS cited FROM read_parquet('{pc.sqlp(path)}') "
                  "WHERE regexp_matches(cited, '^[0-9]')")
        last = pc.q1(c, "SELECT max(year) FROM p")
        _copy(c, f"""WITH b AS (SELECT c.patent_id, count(*) AS back_cites FROM cit c GROUP BY 1),
                          f AS (SELECT c.cited AS patent_id, count(*) AS fwd_cites,
                                       count(*) FILTER (WHERE q.year - d.year BETWEEN 0 AND 5) AS fwd_cites_5y
                                FROM cit c JOIN p q ON q.patent_id = c.patent_id JOIN p d ON d.patent_id = c.cited GROUP BY 1)
                     SELECT p.patent_id, coalesce(b.back_cites, 0) AS back_cites, coalesce(f.fwd_cites, 0) AS fwd_cites,
                            CASE WHEN p.year <= {last} - 5 THEN coalesce(f.fwd_cites_5y, 0) END AS fwd_cites_5y
                     FROM p LEFT JOIN b USING (patent_id) LEFT JOIN f USING (patent_id)""", "patent_citations")
        return True
    finally:
        sg.close(c)


# --------------------------------------------------------------------------- the firm-year panel
def _label():
    lab = LAB["SETTINGS"].get("ai_label", "aipd")
    return {"aipd": "ai_aipd", "cpc_broad": "ai_broad", "cpc_narrow": "ai"}.get(lab, "ai_aipd")


def build_firm_panel():
    pf = canon("patent_firm")
    if not pf.exists():
        log("firm panel: needs patent_firm (DISCERN or the assignee-name match)")
        return None
    W = int(LAB["SETTINGS"].get("explore_window", 5))
    c = sg.con()
    try:
        _view(c, "p", canon("patents"))
        _view(c, "pf", pf)
        label = _label()
        c.execute(f"""CREATE OR REPLACE TABLE f AS
            SELECT pf.gvkey, pf.share, pf.link, p.patent_id, p.year AS grant_year, p.app_year, p.main_subclass,
                   p.ai, p.ai_broad, p.ai_aipd, p.{label} AS ai_label, p.climate, p.weapons
            FROM pf JOIN p USING (patent_id)""")
        y0 = pc.q1(c, "SELECT min(year) FROM p")      # the first grant year: earlier filings are only partly in the data
        def s(cond):  # noqa: E306
            return f"sum(CASE WHEN {cond} THEN share ELSE 0 END)"
        c.execute(f"""CREATE OR REPLACE TABLE fy AS
            SELECT gvkey, app_year AS year, sum(share) AS pat_filed, {s('ai_label')} AS ai_filed,
                   sum(CASE WHEN ai_label IS NOT NULL THEN share ELSE 0 END) AS ai_label_covered,
                   {s('ai_aipd')} AS ai_aipd_filed, {s('ai_broad')} AS ai_cpc_filed, {s('ai')} AS ai_cpc_narrow_filed,
                   {s('climate')} AS climate_filed, {s('weapons')} AS weapons_filed,
                   {s("link = 'discern'")} AS pat_discern, {s("link = 'name'")} AS pat_name
            FROM f WHERE app_year IS NOT NULL GROUP BY 1, 2""")
        c.execute("CREATE OR REPLACE TABLE gy AS SELECT gvkey, grant_year AS year, sum(share) AS pat_granted FROM f GROUP BY 1, 2")
        # exploration: the main subclass of each patent against every subclass the firm used in the W years before
        cpc = sg.staged_path("patentsview", "g_cpc_current")
        if cpc.exists():
            c.execute(f"""CREATE OR REPLACE TABLE fs AS
                SELECT DISTINCT f.gvkey, f.app_year AS y,
                       coalesce(nullif(upper(trim(k.subclass)), ''), substr(upper(replace(k.grp, ' ', '')), 1, 4)) AS s
                FROM f JOIN read_parquet('{pc.sqlp(cpc)}') k USING (patent_id) WHERE f.app_year IS NOT NULL""")
        else:
            c.execute("CREATE OR REPLACE TABLE fs AS SELECT DISTINCT gvkey, app_year AS y, main_subclass AS s FROM f WHERE app_year IS NOT NULL")
        c.execute(f"""CREATE OR REPLACE TABLE ex AS
            WITH m AS (SELECT gvkey, app_year AS y, main_subclass AS s, share FROM f WHERE app_year IS NOT NULL),
                 known AS (SELECT DISTINCT m.gvkey, m.y, m.s FROM m JOIN fs ON fs.gvkey = m.gvkey AND fs.s = m.s
                                                              AND fs.y BETWEEN m.y - {W} AND m.y - 1),
                 newc AS (SELECT a.gvkey, a.y, count(*) AS new_subclasses FROM fs a
                          WHERE NOT EXISTS (SELECT 1 FROM fs b WHERE b.gvkey = a.gvkey AND b.s = a.s AND b.y BETWEEN a.y - {W} AND a.y - 1)
                          GROUP BY 1, 2),
                 hist AS (SELECT a.gvkey, a.year AS y, sum(b.pat_filed) AS prior_patents FROM fy a
                          JOIN fy b ON b.gvkey = a.gvkey AND b.year BETWEEN a.year - {W} AND a.year - 1 GROUP BY 1, 2)
            SELECT m.gvkey, m.y AS year, sum(CASE WHEN k.s IS NULL THEN m.share ELSE 0 END) AS explore_filed,
                   any_value(n.new_subclasses) AS new_subclasses, coalesce(any_value(h.prior_patents), 0) AS prior_patents
            FROM m LEFT JOIN known k USING (gvkey, y, s) LEFT JOIN newc n USING (gvkey, y) LEFT JOIN hist h USING (gvkey, y)
            GROUP BY 1, 2""")
        extra, cols = "", ""
        if canon("patent_citations").exists():
            _view(c, "pc_", canon("patent_citations"))
            c.execute("""CREATE OR REPLACE TABLE fc AS SELECT gvkey, app_year AS year, sum(share * fwd_cites_5y) AS cites_fwd5_filed
                         FROM f JOIN pc_ USING (patent_id) WHERE app_year IS NOT NULL GROUP BY 1, 2""")
            extra += " LEFT JOIN fc USING (gvkey, year)"
            cols += ", fc.cites_fwd5_filed"
            cit = sg.staged_path("patentsview", "g_us_patent_citation")
            if cit.exists():
                c.execute(f"""CREATE OR REPLACE TABLE ka AS
                    WITH g AS (SELECT f.gvkey, f.app_year AS y, {_norm_id('c.cited')} AS cited, count(*) AS n
                               FROM f JOIN read_parquet('{pc.sqlp(cit)}') c USING (patent_id)
                               WHERE f.app_year IS NOT NULL AND regexp_matches(c.cited, '^[0-9]') GROUP BY 1, 2, 3),
                         w AS (SELECT a.gvkey, a.y, a.cited, a.n, coalesce(sum(b.n), 0) AS prior
                               FROM g a LEFT JOIN g b ON b.gvkey = a.gvkey AND b.cited = a.cited AND b.y BETWEEN a.y - {W} AND a.y - 1
                               GROUP BY 1, 2, 3, 4)
                    SELECT gvkey, y AS year, sum(n) AS back_cites, sum(n * prior) / sum(n) AS search_depth,
                           sum(CASE WHEN prior = 0 THEN n ELSE 0 END) / sum(n) AS search_scope
                    FROM w GROUP BY 1, 2""")
                extra += " LEFT JOIN ka USING (gvkey, year)"
                cols += (f", ka.back_cites, CASE WHEN year >= {y0} + {W} THEN ka.search_depth END AS search_depth, "
                         f"CASE WHEN year >= {y0} + {W} THEN ka.search_scope END AS search_scope")
        if canon("application_firm").exists():
            _view(c, "a", canon("applications"))
            _view(c, "af", canon("application_firm"))
            c.execute("""CREATE OR REPLACE TABLE ay AS
                SELECT af.gvkey, a.app_year AS year, sum(af.share) AS apps_filed,
                       sum(CASE WHEN a.ai_aipd THEN af.share ELSE 0 END) AS apps_ai_aipd_filed,
                       sum(CASE WHEN a.ai_broad THEN af.share ELSE 0 END) AS apps_ai_cpc_filed,
                       sum(CASE WHEN a.granted_patent_id IS NULL THEN af.share ELSE 0 END) AS apps_pending
                FROM af JOIN a USING (pgpub_id) WHERE a.app_year IS NOT NULL GROUP BY 1, 2""")
            extra += " FULL JOIN ay USING (gvkey, year)"
            cols += ", ay.apps_filed, ay.apps_ai_aipd_filed, ay.apps_ai_cpc_filed, ay.apps_pending"
        d = pc.q(c, f"""SELECT gvkey, year, fy.* EXCLUDE (gvkey, year), gy.pat_granted,
                              CASE WHEN year >= {y0} + {W} THEN ex.explore_filed END AS explore_filed,
                              CASE WHEN year >= {y0} + {W} THEN ex.new_subclasses END AS new_subclasses,
                              ex.prior_patents {cols}
                       FROM fy FULL JOIN gy USING (gvkey, year) LEFT JOIN ex USING (gvkey, year) {extra}
                       ORDER BY gvkey, year""")
    finally:
        sg.close(c)
    num = [x for x in d.columns if x not in ("gvkey", "year")]
    fill = [x for x in num if x.endswith(("_filed", "_granted", "_covered", "_pending")) or x in ("pat_discern", "pat_name")]
    d[fill] = d[fill].fillna(0)
    d["year"] = d.year.astype(int)
    early = d.year < y0
    if early.any():
        log(f"firm panel: {int(early.sum()):,} firm-years filed before {y0} left out ({d.loc[early, 'pat_filed'].sum():,.0f} patents): "
            f"PatentsView starts with the patents granted in {y0}, so earlier filing years are incomplete")
        d = d[~early].reset_index(drop=True)
    _save_panel(d, "firm_patents_year")
    log(f"firm panel: {d.gvkey.nunique():,} firms, {len(d):,} firm-years, filing years {d.year.min()}-{d.year.max()}; "
        f"AI label '{LAB['SETTINGS'].get('ai_label', 'aipd')}'; exploration window {W} years, so exploration and search "
        f"measures start in {y0 + W}")
    return d


STATA_SHORT = [("Liberalism", "Lib"), ("Alignment", "Align"), ("Employees", "Emp"), ("Employee", "Emp"), ("Donations", "Don"),
               ("Members", "Mem"), ("Execucomp", "Exec"), ("Outsider", "Out"), ("NonDonors", "NonDon"), ("ThisYr", "Yr"),
               ("Industry", "Ind"), ("Stdev", "Sd"), ("Board", "Brd"), ("_filed", "_f")]


def stata_names(cols):
    """{column: Stata name}: at most 32 characters, letters, digits and underscores, unique; long names are shortened
    by the words in STATA_SHORT (dipi_numEmployeeDonationsThisYr_10yr -> dipi_numEmpDonationsThisYr_10yr), then cut."""
    out, seen = {}, set()
    for col in cols:
        n = re.sub(r"\W", "_", str(col))
        n = "_" + n if n[:1].isdigit() else n
        for long_, short in STATA_SHORT:
            if len(n) <= 32:
                break
            n = n.replace(long_, short)
        n, base, k = n[:32], n[:32], 1
        while n.lower() in seen:
            n, k = base[:32 - len(str(k)) - 1] + f"_{k}", k + 1
        seen.add(n.lower())
        out[col] = n
    return out


def _save_panel(d, name):
    from ..core import write
    write(d, name, where="PANELS")
    tables = Path(LAB["RESULTS"]) / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    d.to_csv(tables / f"{name}.csv", index=False)
    try:                                        # for Stata: short names (the full name as the label), no missing-type surprises
        s = d.copy()
        for col in s.columns:
            if s[col].dtype == bool:
                s[col] = s[col].astype("int8")
            elif s[col].dtype == object:
                s[col] = s[col].astype(str).replace({"None": "", "nan": ""})
        names = stata_names(s.columns)
        s = s.rename(columns=names)
        labels = {names[c]: str(c)[:80] for c in names if names[c] != c}
        s.to_stata(tables / f"{name}.dta", write_index=False, version=118, variable_labels=labels or None)
    except Exception as e:
        log(f"{name}: no Stata copy ({type(e).__name__}: {e}); the CSV has everything")


def build_panel_firm_year():
    """firm_patents_year joined to the VRscores workforce (POLISY_DA panels/firm_year) and DIPI, where present."""
    fp = panel_path("firm_patents_year")
    if not fp.exists():
        return None
    d = pd.read_parquet(fp)
    parts = [d]
    fy = Path(pc.CONFIG["PANELS"]) / "firm_year.parquet"
    if fy.exists():
        v = pd.read_parquet(fy)
        v["gvkey"] = pc.norm_gvkey(v.gvkey)
        v = v.rename(columns={x: f"vr_{x}" for x in v.columns if x not in ("gvkey", "year")})
        parts.append(v)
        log(f"firm panel: VRscores workforce for {v.gvkey.nunique():,} firms (POLISY_DA's name match)")
    try:
        dipi = pc.load_dipi()
    except Exception as e:
        dipi = None
        log(f"firm panel: DIPI not read ({type(e).__name__}: {e})")
    if dipi is not None:
        keep = [x for x in dipi.columns if x in ("gvkey", "year") or pd.api.types.is_numeric_dtype(dipi[x])]
        dp = dipi[keep].rename(columns={x: f"dipi_{x}" for x in keep if x not in ("gvkey", "year")})
        parts.append(dp)
    if len(parts) == 1:
        log("firm panel: no VRscores firm_year (POLISY_DA module 06) or DIPI yet; panel_firm_year = firm_patents_year")
    out = parts[0]
    for x in parts[1:]:
        out = out.merge(x, on=["gvkey", "year"], how="outer")
    out = out.sort_values(["gvkey", "year"])
    _save_panel(out, "panel_firm_year")
    both = out[out.pat_filed.fillna(0) > 0]
    checks = [("vr_workers", "VRscores workforce")]
    if dipi is not None and pc.dipi_measure(dipi):
        checks.append((f"dipi_{pc.dipi_measure(dipi)}", "DIPI"))
    for col, label in checks:
        if col in out and out[col].notna().any():
            y = out.loc[out[col].notna(), "year"]
            sub = both[both.year.between(y.min(), y.max())]      # the years the source covers
            diagnostic(f"firm patents -> {label}", "firm_patents_year", label, "gvkey x year",
                       int(sub[col].notna().sum()), len(sub), "firm-years with patents",
                       note=f"filing years {int(y.min())}-{int(y.max())}, the years {label} covers")
    return out


def adapt_firms():
    """DISCERN, the assignee-name match, patent_firm, citations and the firm panels, in order."""
    got_d = adapt_discern()
    linked = adapt_patent_firms()
    adapt_citations()
    if linked:
        build_firm_panel()
        build_panel_firm_year()
    RESULTS.setdefault("notes", {})["firm_panel_columns"] = FIRM_COLUMNS
    return bool(got_d or linked)
