# -*- coding: utf-8 -*-
"""Patents -> firms (gvkey), and the firm-year patent panel.

Which firm owns a patent comes from DISCERN 2.0 first: it follows subsidiaries and ownership changes, patent by
patent, for Compustat firms and patents granted 1980-2021. Outside DISCERN's years (and for published applications)
the owner comes from PatentsView's disambiguated assignee, matched by name to Compustat (and to DISCERN's subsidiary
names when the download has them). The two are compared where both exist, so the name match's error rate is known.

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
        c.close()
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


def _classify(cols):
    sq = [squash(x) for x in cols]
    pat = sg.exact_col(cols, PAT_NAMES)
    gv = sg.exact_col(cols, ["gvkey"]) or next((x for x, s in zip(cols, sq) if "gvkey" in s), None)
    pn = sg.exact_col(cols, ["permnoadj", "permno"])
    yr = sg.exact_col(cols, YEAR_NAMES)
    nm = sg.exact_col(cols, NAME_NAMES)
    firm = gv or pn
    if pat and firm:
        kind = "patents"                                   # patent number and owner
    elif gv and pn and not pat and not nm and len(cols) <= 8:
        kind = "crosswalk"                                 # permno_adj <-> gvkey
    elif firm and nm and not pat and len(cols) <= 5:
        kind = "names"                                     # firm and subsidiary names
    elif firm and yr and not pat:
        kind = "panel"                                     # the firm-year panel
    else:
        kind = None
    return kind, {"patent": pat, "gvkey": gv, "permno": pn, "year": yr, "name": nm}


def _gv(expr):
    return f"nullif(lpad(regexp_extract(CAST({expr} AS VARCHAR), '(\\d+)', 1), 6, '0'), '000000')"


def _pn(expr):
    """permno_adj as text, the same whether Stata stored it as 10107 or 10107.0."""
    return f"nullif(regexp_replace(CAST({expr} AS VARCHAR), '\\.0+$', ''), '')"


def _pid(expr):
    """DISCERN patent numbers (often stored as numbers, 4000000.0) -> PatentsView patent_id; letters kept (D, RE, PP)."""
    v = f"upper(regexp_replace(CAST({expr} AS VARCHAR), '\\.0+$', ''))"
    return f"CASE WHEN regexp_matches({v}, '^[0-9]+$') THEN ltrim({v}, '0') ELSE regexp_replace({v}, '[^A-Z0-9]', '', 'g') END"


def adapt_discern():
    files = discover("discern", "tables")
    if not files:
        log("discern: not found. Put the DISCERN 2.0 download (its .dta or .csv files) in POLISY/data/discern; without it "
            "patents are linked to firms by assignee name only")
        return False
    tables = {"patents": [], "panel": [], "crosswalk": [], "names": []}
    for path, member in files:
        try:
            cols = _columns_of(path, member)
        except Exception as e:
            log(f"discern: cannot read {Path(member or path).name} ({type(e).__name__}: {e})")
            continue
        kind, roles = _classify(cols)
        log(f"discern: {Path(member or path).name}: " + (f"{kind} table ({', '.join(f'{k}={v}' for k, v in roles.items() if v)})"
                                                         if kind else f"not used (columns {cols[:8]})"))
        if kind:
            tables[kind].append((path, member, roles))
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
        # permno_adj -> gvkey (by year where the table has one), from a crosswalk file or any table carrying both
        pairs = [f"SELECT {_pn(sg.pc_quote(r['permno']))} AS permno, {_gv(sg.pc_quote(r['gvkey']))} AS gvkey, "
                 + (f"try_cast({sg.pc_quote(r['year'])} AS INTEGER)" if r["year"] else "NULL::INTEGER") + f" AS year FROM d_{k}_{i}"
                 for k in ("crosswalk", "panel", "patents", "names") for i, (_, _, r) in enumerate(tables[k]) if r["permno"] and r["gvkey"]]
        c.execute("CREATE OR REPLACE TABLE pg AS " + (
            "SELECT permno, gvkey, year, count(*) AS n FROM (" + " UNION ALL ".join(pairs) + ") WHERE gvkey IS NOT NULL AND permno IS NOT NULL GROUP BY ALL"
            if pairs else "SELECT NULL::VARCHAR AS permno, NULL::VARCHAR AS gvkey, NULL::INTEGER AS year, 0::BIGINT AS n WHERE FALSE"))
        c.execute("CREATE OR REPLACE TABLE pg1 AS SELECT permno, arg_max(gvkey, n) AS gvkey FROM "
                  "(SELECT permno, gvkey, sum(n) AS n FROM pg GROUP BY 1, 2) GROUP BY 1")

        def firm_of(alias, r):
            """SQL (gvkey, joins) for a DISCERN table row: its own gvkey, else its permno_adj through pg (same year) or pg1."""
            if r["gvkey"]:
                return _gv(f"{alias}.{sg.pc_quote(r['gvkey'])}"), ""
            pn = _pn(f"{alias}.{sg.pc_quote(r['permno'])}")
            yr = f"try_cast({alias}.{sg.pc_quote(r['year'])} AS INTEGER)" if r["year"] else "NULL"
            return ("coalesce(x1.gvkey, x2.gvkey)",
                    f" LEFT JOIN pg x1 ON x1.permno = {pn} AND x1.year = {yr} LEFT JOIN pg1 x2 ON x2.permno = {pn}")
        wrote = False
        parts = []
        for i, (_, _, r) in enumerate(tables["patents"]):
            if not r["gvkey"] and not pairs:
                log("discern: the patent file has permno_adj but no gvkey, and no table maps permno_adj to gvkey; add DISCERN's "
                    "permno-gvkey file to the folder")
                continue
            gv, joins = firm_of("t", r)
            yr = f"try_cast(t.{sg.pc_quote(r['year'])} AS INTEGER)" if r["year"] else "NULL::INTEGER"
            pn = _pn(f"t.{sg.pc_quote(r['permno'])}") if r["permno"] else "NULL::VARCHAR"
            parts.append(f"SELECT {_pid('t.' + sg.pc_quote(r['patent']))} AS patent_id, {gv} AS gvkey, {pn} AS permno_adj, "
                         f"{yr} AS discern_year FROM d_patents_{i} t{joins}")
        if parts:
            n = _copy(c, "SELECT DISTINCT * FROM (" + " UNION ALL ".join(parts) + ") WHERE patent_id <> '' AND gvkey IS NOT NULL",
                      "discern_patents")
            k = c.execute(f"SELECT count(DISTINCT patent_id), count(DISTINCT gvkey), min(discern_year), max(discern_year) "
                          f"FROM read_parquet('{pc.sqlp(canon('discern_patents'))}')").fetchone()
            log(f"discern: {k[0]:,} patents owned by {k[1]:,} firms" + (f", years {k[2]}-{k[3]}" if k[2] else ""))
            wrote = n > 0
        if tables["panel"]:
            _, _, r = tables["panel"][0]
            gv, joins = firm_of("t", r)
            drop = ", ".join(sg.pc_quote(x) for x in (r["year"], r["gvkey"]) if x)
            _copy(c, f"""SELECT * FROM (SELECT {gv} AS gvkey, try_cast(t.{sg.pc_quote(r['year'])} AS INTEGER) AS year,
                                               t.* EXCLUDE ({drop}) FROM d_panel_0 t{joins})
                         WHERE gvkey IS NOT NULL AND year IS NOT NULL
                         QUALIFY row_number() OVER (PARTITION BY gvkey, year) = 1""", "discern_firm_year")
        if tables["names"]:
            parts = []
            for i, (_, _, r) in enumerate(tables["names"]):
                gv, joins = firm_of("t", r)
                parts.append(f"SELECT {gv} AS gvkey, CAST(t.{sg.pc_quote(r['name'])} AS VARCHAR) AS name FROM d_names_{i} t{joins}")
            c.execute("CREATE OR REPLACE TABLE dn AS SELECT DISTINCT * FROM (" + " UNION ALL ".join(parts) + ") "
                      "WHERE gvkey IS NOT NULL AND name IS NOT NULL")
            c.execute(f"COPY dn TO '{pc.sqlp(sg.staged_path('discern', 'names'))}' (FORMAT parquet)")
            log(f"discern: {pc.q1(c, 'SELECT count(*) FROM dn'):,} firm and subsidiary names for the assignee name match")
        return wrote
    finally:
        c.close()


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
        c.close()
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
        return pc.q(c, f"""SELECT assignee_id, mode(org) AS org, mode(atype) AS atype, count(*) AS docs, min(y) AS y0, max(y) AS y1
                           FROM ({' UNION ALL '.join(parts)}) WHERE org IS NOT NULL AND org <> '' GROUP BY 1""")
    finally:
        c.close()


def match_assignees():
    """assignee_gvkey: company assignees -> gvkey by normalized name (exact), then fuzzy for the unmatched."""
    firms = _compustat_names()
    dn = sg.staged_path("discern", "names")
    if dn.exists():
        extra = pd.read_parquet(dn).assign(fy0=np.nan, fy1=np.nan, source="discern names")
        firms = extra if firms is None else pd.concat([firms, extra], ignore_index=True)
    if firms is None or firms.empty:
        log("firm names: no Compustat file (POLISY_DA's COMPUSTAT input) and no DISCERN names, so assignees cannot be "
            "matched to firms by name")
        return False
    a = _assignees()
    if a is None or a.empty:
        log("firm names: no assignees (g_assignee_disambiguated) to match")
        return False
    a = a[a.atype.isin([2, 3]) | a.atype.isna()].copy()          # companies, US and foreign
    a["name_norm"] = a.org.map(pc.norm_name)
    firms["name_norm"] = firms.name.map(pc.norm_name)
    firms = firms[firms.name_norm.str.len() >= 3]
    span = firms.groupby("gvkey").agg(fy0=("fy0", "min"), fy1=("fy1", "max"))
    lut = firms.groupby("name_norm").gvkey.agg(lambda s: sorted(set(s)))
    rows = []
    for r in a.itertuples(index=False):
        cands = lut.get(r.name_norm)
        if cands:
            best = _by_years(cands, r.y0, r.y1, span)
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
                rows.append((r.assignee_id, r.org, r.name_norm, _by_years(cands, r.y0, r.y1, span), "fuzzy", float(hit[1]),
                             len(cands) > 1, r.docs))
    except ImportError:
        log("firm names: pip install rapidfuzz for fuzzy name matches (exact matches only for now)")
    m = pd.DataFrame(rows, columns=["assignee_id", "assignee_org", "name_norm", "gvkey", "method", "score", "ambiguous", "docs"])
    name = firms.drop_duplicates("gvkey").set_index("gvkey").name
    m["firm_name"] = m.gvkey.map(name)
    m.to_parquet(canon("assignee_gvkey"), index=False)
    share = m.docs.sum() / max(a.docs.sum(), 1)
    log(f"canonical assignee_gvkey: {len(m):,} company assignees matched to {m.gvkey.nunique():,} firms "
        f"({(m.method == 'exact').sum():,} exact, {(m.method == 'fuzzy').sum():,} fuzzy, {m.ambiguous.sum():,} names shared by "
        f"several gvkeys, resolved by years), holding {share:.1%} of company-assigned patents and applications")
    diagnostic("assignees -> Compustat firms (names)", "assignee_gvkey", "Compustat names" + (" + DISCERN names" if dn.exists() else ""),
               "normalized company name", int(m.docs.sum()), int(a.docs.sum()), "company-assigned documents")
    return True


def _by_years(cands, y0, y1, span):
    """Among firms sharing a name, the one whose Compustat years overlap the assignee's patenting years most."""
    if len(cands) == 1:
        return cands[0]
    best, score = cands[0], -1e9
    for g in cands:
        if g not in span.index or pd.isna(span.at[g, "fy0"]) or pd.isna(y0):
            s = 0
        else:
            s = min(y1, span.at[g, "fy1"]) - max(y0, span.at[g, "fy0"])
        if s > score:
            best, score = g, s
    return best


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
            c.execute("CREATE OR REPLACE TABLE dl AS SELECT DISTINCT d.patent_id, d.gvkey FROM d JOIN p USING (patent_id)")
            last = pc.q1(c, "SELECT max(p.year) FROM dl JOIN p USING (patent_id)")
            first = pc.q1(c, "SELECT min(p.year) FROM dl JOIN p USING (patent_id)")
        else:
            c.execute("CREATE OR REPLACE TABLE dl AS SELECT NULL::VARCHAR AS patent_id, NULL::VARCHAR AS gvkey WHERE FALSE")
            last = first = None
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
        else:
            use = f"p.year > {last}"
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
            + (f", the name match filling in {fill.replace('_', ' ')}" + (f" (grants after {last})" if fill == 'after_discern' and have_d else "")
               if have_d else "") + f"); {k[0] / max(n_co, 1):.1%} of the {n_co:,} company-assigned patents")
        diagnostic("patents -> firms (gvkey)", "patents", "DISCERN" + (" + assignee names" if have_names else ""), "patent_id",
                   k[0], n_co, "company-assigned patents")
        if have_d and have_names and last is not None:   # does the name match agree with DISCERN where both exist?
            a = c.execute("""SELECT count(*), count(s.patent_id)
                             FROM (SELECT DISTINCT patent_id FROM nl WHERE patent_id IN (SELECT patent_id FROM dl)) b
                             LEFT JOIN (SELECT DISTINCT patent_id FROM nl JOIN dl USING (patent_id, gvkey)) s USING (patent_id)""").fetchone()
            rec = c.execute(f"""SELECT count(DISTINCT d.patent_id), count(DISTINCT n.patent_id)
                                FROM dl d JOIN p USING (patent_id) LEFT JOIN nl n USING (patent_id)
                                WHERE p.year BETWEEN {first} AND {last}""").fetchone()
            if a[0]:
                log(f"patent_firm: where DISCERN and the name match both link a patent ({a[0]:,} patents), they agree on the firm for "
                    f"{a[1] / a[0]:.1%}; the name match finds {rec[1] / max(rec[0], 1):.1%} of DISCERN's patents")
                diagnostic("name match agrees with DISCERN", "patent_firm (name)", "discern_patents", "patent_id", a[1], a[0],
                           "patents linked by both", note=f"the name match finds {rec[1] / max(rec[0], 1):.1%} of DISCERN's patents")
        _application_firms(c)
        return True
    finally:
        c.close()


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
        c.close()


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
        y0 = pc.q1(c, "SELECT min(app_year) FROM p")
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
        c.close()
    num = [x for x in d.columns if x not in ("gvkey", "year")]
    fill = [x for x in num if x.endswith(("_filed", "_granted", "_covered", "_pending")) or x in ("pat_discern", "pat_name")]
    d[fill] = d[fill].fillna(0)
    d["year"] = d.year.astype(int)
    _save_panel(d, "firm_patents_year")
    log(f"firm panel: {d.gvkey.nunique():,} firms, {len(d):,} firm-years, filing years {d.year.min()}-{d.year.max()}; "
        f"AI label '{LAB['SETTINGS'].get('ai_label', 'aipd')}'; exploration window {W} years")
    return d


def _save_panel(d, name):
    from ..core import write
    write(d, name, where="PANELS")
    tables = Path(LAB["RESULTS"]) / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    d.to_csv(tables / f"{name}.csv", index=False)
    try:                                        # for Stata: short names, no missing-type surprises
        s = d.copy()
        for col in s.columns:
            if s[col].dtype == bool:
                s[col] = s[col].astype("int8")
            elif s[col].dtype == object:
                s[col] = s[col].astype(str).replace({"None": "", "nan": ""})
        s.to_stata(tables / f"{name}.dta", write_index=False, version=118)
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
    both = out.dropna(subset=["pat_filed"])
    checks = [("vr_workers", "VRscores workforce")]
    if dipi is not None and pc.dipi_measure(dipi):
        checks.append((f"dipi_{pc.dipi_measure(dipi)}", "DIPI"))
    for col, label in checks:
        if col in out:
            diagnostic(f"firm patents -> {label}", "firm_patents_year", label, "gvkey x year",
                       int(both[col].notna().sum()), len(both), "firm-years with patents")
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
