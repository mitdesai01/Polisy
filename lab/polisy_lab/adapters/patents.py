# -*- coding: utf-8 -*-
"""The patent layer: PatentsView (granted patents and published applications) and the USPTO AI Patent Dataset.

Staged once (lab/staged/patentsview, lab/staged/patentsview_pregrant, lab/staged/aipd): each source table with the
columns used here, so later runs never re-read the multi-gigabyte files.

Canonical tables
  aipd                  doc_id, is_patent: the AI Patent Dataset's AI label at LAB SETTINGS aipd_threshold (its
                        default is 50), a stricter label when the file has one, and the eight AI components
  patents               patent_id (utility patents, not withdrawn): grant year (`year`), filing year (`app_year`, from
                        g_application), CPC flags, AIPD labels, main CPC subclass, inventors, first assignee
  patent_places         patent x inventor in the US: county, state, coordinates, share = 1 / inventors on the patent
  patents_county_year   county x grant year (fractional counts), and patents_state_year by state
  ai_cpc_edges          CPC subclasses combined on AI patents, by grant period
  inventor_moves        inventors whose consecutive patents list different states
  applications          pgpub_id (one per application, its first publication): filing and publication year, the same
                        flags, AIPD, first assignee, and the patent it became (pg_granted_pgpubs_crosswalk)
  application_places    published application x inventor in the US
  inventions_year       filing year: granted patents and published applications, with AI (CPC, AIPD), climate, weapons
  inventions_state_year, inventions_county_year   the same by inventor state and county (fractional counts)

Flags from CPC codes (current classification)
  ai (narrow)   G06N, machine learning, except quantum computing (G06N10)
  ai_broad      adds image and video recognition (G06V), image analysis (G06T7), natural language (G06F40), speech
                (G10L15, G10L13), learning and adaptive control (G05B13) and robot learning (B25J9/161, B25J9/163)
  climate       Y02 (climate change mitigation and adaptation technologies) or Y04S (smart grids)
  weapons       F41 (weapons) or F42 (ammunition, blasting)
The AI Patent Dataset (the USPTO's machine-learning classification of each document into eight AI components) is the
better AI label; the CPC flags stay for documents it does not cover and for comparison. Filing year is the inventions' date: grants lag filing by two to
three years, so the last years of granted patents are incomplete, and published applications (18 months after
filing) show recent invention sooner.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..core import log, LAB, canon, diagnostic, pc, STATE_ABBR
from ..sources import discover, SOURCES
from .. import staging as sg

AI_RULES = {  # subfield: SQL condition on main group `g` ("G06N3") and full code `c` ("G06N3/084")
    "sub_ml": "substr(g, 1, 4) = 'G06N' AND g NOT LIKE 'G06N10%'",
    "sub_vision": "substr(g, 1, 4) = 'G06V' OR g = 'G06T7'",
    "sub_language": "g IN ('G06F40', 'G10L15', 'G10L13')",
    "sub_control": "g = 'G05B13'",
    "sub_robotics": "c LIKE 'B25J9/161%' OR c LIKE 'B25J9/163%'",
}
FLAGS = {"climate": "s LIKE 'Y02%' OR s = 'Y04S'", "weapons": "s LIKE 'F41%' OR s LIKE 'F42%'"}
AIPD_PARTS = ("ml", "evo", "nlp", "speech", "vision", "kr", "planning", "hardware")

ID = [r"patentid", r"patentnumber", r"patnum"]
PGID = [r"pgpubid", r"documentnumber", r"publicationnumber", r"pgpubnumber"]
INT = "try_cast({c} AS INTEGER)"
DBL = "try_cast({c} AS DOUBLE)"
CPC = ({"seq": [r"cpcsequence", r"sequence"], "subclass": [r"cpcsubclass", r"subclassid"],
        "grp": ([r"cpcgroup", r"cpcsubgroup", r"groupid"], True), "cpc_type": [r"cpctype"]}, {"seq": INT})
INVENTOR = ({"seq": [r"inventorsequence", r"sequence"], "inventor_id": ([r"inventorid"], True),
             "location_id": ([r"locationid"], True), "gender": [r"gendercode", r"gender"]}, {"seq": INT})
LOCATION = ({"location_id": ([r"locationid", r"id"], True), "state_fips": [r"statefips"], "county_fips": [r"countyfips"],
             "state": [r"disambigstate", r"state"], "country": [r"disambigcountry", r"country"], "city": [r"disambigcity", r"city"],
             "lat": [r"latitude", r"lat"], "lon": [r"longitude", r"lon", r"lng"]}, {"lat": DBL, "lon": DBL})
ASSIGNEE = ({"seq": [r"assigneesequence", r"sequence"], "assignee_id": ([r"assigneeid"], True),
             "org": [r"disambigassigneeorganization", r"organization"],
             "name_first": [r"disambigassigneeindividualnamefirst", r"namefirst"],
             "name_last": [r"disambigassigneeindividualnamelast", r"namelast"],
             "atype": [r"assigneetype", r"type"], "location_id": [r"locationid"]}, {"seq": INT})


def _with(key, spec):
    cols, sel = spec
    return ({key[0]: (key[1], True), **cols}, sel)


# role -> (staged table name, column spec, SQL per column)
PV = {
    "patent": ("g_patent", {"patent_id": (ID, True), "patent_type": [r"patenttype"],
                            "grant_date": ([r"patentdate", r"grantdate", r"date"], True),
                            "title": [r"patenttitle", r"title"], "num_claims": [r"numclaims", r"claims"],
                            "withdrawn": [r"withdrawn"]}, {"num_claims": INT}),
    "application": ("g_application", {"patent_id": (ID, True), "application_id": [r"applicationid", r"applicationnumber"],
                                      "filing_date": ([r"filingdate", r"applicationdate", r"datefiled"], True),
                                      "series_code": [r"seriescode"]}, {}),
    "cpc": ("g_cpc_current", *_with(("patent_id", ID), CPC)),
    "inventor": ("g_inventor_disambiguated", *_with(("patent_id", ID), INVENTOR)),
    "location": ("g_location_disambiguated", *LOCATION),
    "assignee": ("g_assignee_disambiguated", *_with(("patent_id", ID), ASSIGNEE)),
}
PG = {
    "application": ("pg_published_application", {"pgpub_id": (PGID, True), "application_id": [r"applicationid", r"applicationnumber"],
                                                 "filing_date": ([r"filingdate", r"applicationdate", r"datefiled"], True),
                                                 "published_date": [r"publisheddate", r"publicationdate", r"pubdate", r"datepublished"],
                                                 "title": [r"applicationtitle", r"inventiontitle", r"title"],
                                                 "kind": [r"wipokind", r"kind"]}, {}),
    "cpc": ("pg_cpc_current", *_with(("pgpub_id", PGID), CPC)),
    "inventor": ("pg_inventor_disambiguated", *_with(("pgpub_id", PGID), INVENTOR)),
    "location": ("pg_location_disambiguated", *LOCATION),
    "assignee": ("pg_assignee_disambiguated", *_with(("pgpub_id", PGID), ASSIGNEE)),
    "crosswalk": ("pg_granted_pgpubs_crosswalk", {"pgpub_id": (PGID, True), "patent_id": (ID, True),
                                                  "application_id": [r"applicationid"]}, {}),
}


def stage_tables(source, specs, roles):
    """Stage the roles found; returns {role: staged path} (roles not found or unreadable are left out)."""
    out = {}
    for role in roles:
        found = discover(source, role)
        if not found:
            continue
        table, spec, select = specs[role]
        path, _ = sg.stage(source, table, found[0], spec, select)
        if path is not None:
            out[role] = path
    return out


def _view(c, name, path):
    c.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{pc.sqlp(path)}')")


def _norm_id(expr):
    """Document numbers compared across sources: the digits, without leading zeros ('US10000000B2' -> '10000000')."""
    return f"ltrim(regexp_extract({expr}, '(\\d+)', 1), '0')"


def _year(expr):
    return f"try_cast(substr({expr}, 1, 4) AS INTEGER)"


def _date(expr):
    return f"try_cast({expr} AS DATE)"


def _copy(c, sql, name):
    c.execute(f"COPY ({sql}) TO '{pc.sqlp(canon(name))}' (FORMAT parquet, COMPRESSION zstd)")
    n = pc.q1(c, f"SELECT count(*) FROM read_parquet('{pc.sqlp(canon(name))}')")
    log(f"canonical {name}: {n:,} rows")
    return n


# --------------------------------------------------------------------------- AI Patent Dataset
def _stage_aipd(c, path, member):
    """One AI Patent Dataset file -> staged Parquet (doc_id, flag_patent, predictNN_*, ai_score_*), or None when the
    file holds no predictions (documentation, training data)."""
    name = re.sub(r"[^a-z0-9]+", "_", Path(member or path).name.lower())
    out = sg.staged_path("aipd", f"predictions_{name}")
    if sg.fresh(out, path, member):
        return out
    rd, tmp = sg.readable(path, member)
    try:
        cols = sg.columns(c, rd)
        low = {col.lower(): col for col in cols}
        doc = sg.exact_col(cols, ["docid", "documentid", "docnumber", "patentid", "patentnumber", "pubno"])
        keep = [col for lc, col in low.items() if re.fullmatch(r"predict\d+_[a-z_]+|ai_score_[a-z_]+", lc)]
        if doc is None or not keep:
            log(f"aipd: {Path(member or path).name} has no document ids or no AI predictions, so it is not used "
                f"(columns {cols[:10]})")
            return None
        flag = sg.exact_col(cols, ["flagpatent", "ispatent", "patentflag"])
        sel = [f"{sg.pc_quote(doc)} AS doc_id"] + ([f"{sg.pc_quote(flag)} AS flag_patent"] if flag else []) + \
              [f"{sg.pc_quote(col)} AS {col.lower()}" for col in keep]
        out.parent.mkdir(parents=True, exist_ok=True)
        c.execute(f"COPY (SELECT {', '.join(sel)} FROM {rd}) TO '{pc.sqlp(out)}' (FORMAT parquet, COMPRESSION zstd)")
        sg.write_stamp(out, path, member, columns={"doc_id": doc, "flag_patent": flag, "labels": keep})
        log(f"aipd: staged {sg.rows(out):,} documents from {Path(member or path).name} "
            f"({len(keep)} label columns, e.g. {', '.join(keep[:4])})")
        return out
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


def adapt_aipd():
    """The AI Patent Dataset -> staged columns -> canonical aipd. Every predictions file found is read (a release may
    come as one file, or as one for patents and one for published applications); where two files hold the same
    document, the newer file wins."""
    found = discover("aipd", "predictions")
    if not found:
        log(f"aipd: not found. Save the AI Patent Dataset's predictions file (ai_model_predictions, from {SOURCES['aipd']['url']}) "
            "in POLISY/data/aipd; until then AI patents are identified by CPC codes only")
        return False
    c = sg.con()
    try:
        staged = [x for x in (_stage_aipd(c, p, m) for p, m in found) if x is not None]     # newest file first
        if not staged:
            return False
        c.execute("CREATE OR REPLACE VIEW aipd_raw AS " + " UNION ALL BY NAME ".join(
            f"SELECT *, {i} AS src_rank FROM read_parquet('{pc.sqlp(x)}')" for i, x in enumerate(staged)))
        cols = [r[0] for r in c.execute("DESCRIBE SELECT * FROM aipd_raw").fetchall()]
        want = int(LAB["SETTINGS"].get("aipd_threshold", 50))
        levels = sorted({int(m.group(1)) for col in cols for m in [re.fullmatch(r"predict(\d+)_any_ai", col)] if m})
        if levels:
            thr = min(levels, key=lambda t: (abs(t - want), -t))
            ai = f"try_cast(predict{thr}_any_ai AS DOUBLE) >= 1"
            strict = max(levels)
            ai_strict = f"try_cast(predict{strict}_any_ai AS DOUBLE) >= 1" if strict > thr else "NULL"
            part = {p: f"try_cast(predict{thr}_{p} AS DOUBLE) >= 1" for p in AIPD_PARTS if f"predict{thr}_{p}" in cols}
            how = f"predict{thr}_any_ai" + (f" (and predict{strict}_any_ai as the strict label)" if strict > thr else "")
        else:
            scores = [f"try_cast(ai_score_{p} AS DOUBLE)" for p in AIPD_PARTS if f"ai_score_{p}" in cols]
            if not scores:
                log(f"aipd: neither predictNN_any_ai nor ai_score_* columns; columns are {cols[:20]}")
                return False
            ai = f"greatest({', '.join(scores)}) >= {want / 100}"
            ai_strict = "NULL"
            part = {p: f"try_cast(ai_score_{p} AS DOUBLE) >= {want / 100}" for p in AIPD_PARTS if f"ai_score_{p}" in cols}
            how = f"the highest ai_score_* at {want / 100:.2f}"
        is_pat = ("coalesce(try_cast(try_cast(flag_patent AS DOUBLE) AS INTEGER) = 1, length(regexp_extract(doc_id, '(\\d+)', 1)) <= 8)"
                  if "flag_patent" in cols else "length(regexp_extract(doc_id, '(\\d+)', 1)) <= 8")
        inner = (f"SELECT {_norm_id('doc_id')} AS doc_id, {is_pat} AS is_patent, {ai} AS ai, {ai_strict} AS ai_strict"
                 + "".join(f", {cond} AS aipd_{p}" for p, cond in part.items())
                 + ", src_rank FROM aipd_raw WHERE regexp_extract(doc_id, '(\\d+)', 1) <> ''")
        _copy(c, f"SELECT * EXCLUDE (src_rank) FROM ({inner}) "
                 "QUALIFY row_number() OVER (PARTITION BY doc_id, is_patent ORDER BY src_rank, ai DESC NULLS LAST, "
                 "ai_strict DESC NULLS LAST) = 1", "aipd")
        n, npat, nai = c.execute(f"SELECT count(*), sum(is_patent::INT), sum(ai::INT) FROM read_parquet('{pc.sqlp(canon('aipd'))}')").fetchone()
        log(f"aipd: AI label = {how}; {npat:,} patents and {n - npat:,} published applications, {nai / max(n, 1):.1%} AI"
            + (f" (from {len(staged)} files)" if len(staged) > 1 else ""))
        return True
    finally:
        sg.close(c)


def _aipd_view(c, patents=True):
    """View `ad` over canonical aipd for patents (or published applications), or None when there is none."""
    p = canon("aipd")
    if not p.exists():
        return False
    cols = [r[0] for r in c.execute(f"DESCRIBE SELECT * FROM read_parquet('{pc.sqlp(p)}')").fetchall()]
    parts = [x for x in cols if x.startswith("aipd_")]
    c.execute("CREATE OR REPLACE VIEW ad AS SELECT doc_id, ai AS ai_aipd, ai_strict AS ai_aipd_strict"
              + "".join(f", {x}" for x in parts)
              + f" FROM read_parquet('{pc.sqlp(p)}') WHERE {'is_patent' if patents else 'NOT is_patent'}")
    return parts


# --------------------------------------------------------------------------- shared SQL
def _cpc_table(c, key):
    """Per document: AI subfields, climate, weapons, number of classes and subclasses, main subclass."""
    subs = ",\n".join(f"bool_or({cond}) AS {name}" for name, cond in AI_RULES.items())
    flags = ",\n".join(f"bool_or({cond}) AS {name}" for name, cond in FLAGS.items())
    code = "upper(replace(grp, ' ', ''))"
    c.execute(f"""CREATE OR REPLACE TABLE cpcx AS
        WITH x AS (SELECT {key} AS id, seq, {code} AS c, split_part({code}, '/', 1) AS g,
                          coalesce(nullif(upper(trim(subclass)), ''), substr({code}, 1, 4)) AS s FROM cpc)
        SELECT id, {subs}, {flags}, count(*) AS n_cpc, count(DISTINCT s) AS n_subclasses,
               first(s ORDER BY coalesce(seq, 999999), s) AS main_subclass
        FROM x GROUP BY 1""")


def _loc_table(c, views):
    """US locations with 2-digit state and 5-digit county FIPS; `views` are location tables (granted, pre-grant).
    The state comes from state_fips, else from the two-letter state code."""
    c.execute("CREATE OR REPLACE TABLE st_abbr AS SELECT * FROM (VALUES "
              + ", ".join(f"('{a}', '{f}')" for a, f in STATE_ABBR.items()) + ") t(abbr, fips)")
    fips = "nullif(lpad(regexp_extract(coalesce(v.state_fips, ''), '(\\d+)', 1), 2, '0'), '00')"
    parts = []
    for v in views:
        parts.append(f"""SELECT v.location_id, coalesce({fips}, s.fips) AS state_fips, v.county_fips AS raw_county, v.lat, v.lon,
                                upper(coalesce(v.country, 'US')) IN ('US', 'USA', 'UNITED STATES') AS us
                         FROM {v} v LEFT JOIN st_abbr s ON s.abbr = upper(trim(v.state))""")
    raw = "regexp_extract(coalesce(raw_county, ''), '(\\d+)', 1)"
    c.execute(f"""CREATE OR REPLACE TABLE loc AS
        SELECT location_id, state_fips,
               CASE WHEN {raw} = '' THEN NULL WHEN length({raw}) <= 3 AND state_fips IS NOT NULL THEN state_fips || lpad({raw}, 3, '0')
                    ELSE lpad({raw}, 5, '0') END AS county_fips, lat, lon, us
        FROM ({' UNION ALL '.join(parts)})
        QUALIFY row_number() OVER (PARTITION BY location_id ORDER BY state_fips NULLS LAST, county_fips NULLS LAST,
                                   lat NULLS LAST, lon NULLS LAST, us DESC) = 1""")


def _inventor_table(c, key):
    c.execute(f"""CREATE OR REPLACE TABLE invs AS
        SELECT i.{key} AS id, count(*) AS n_inventors, count(*) FILTER (WHERE l.us) AS n_us_inventors,
               first(l.state_fips ORDER BY coalesce(i.seq, 999999), l.state_fips NULLS LAST) AS first_inventor_state
        FROM inv i LEFT JOIN loc l USING (location_id) GROUP BY 1""")


def _assignee_table(c, key):
    c.execute(f"""CREATE OR REPLACE TABLE asg AS
        SELECT {key} AS id, first(assignee_id ORDER BY coalesce(seq, 999999), assignee_id, org) AS assignee_id,
               first(org ORDER BY coalesce(seq, 999999), assignee_id, org) AS assignee_org,
               first(try_cast(try_cast(atype AS DOUBLE) AS INTEGER) % 10 ORDER BY coalesce(seq, 999999), assignee_id, org)
                   AS assignee_type,
               count(*) AS n_assignees
        FROM asg_raw GROUP BY 1""")


FLAG_COLS = ["ai", "ai_broad"] + list(AI_RULES) + list(FLAGS)


def _flag_select(aipd_parts):
    ai = ("coalesce(x.sub_ml, false) AS ai, coalesce(" + " OR ".join(f"x.{s}" for s in AI_RULES) + ", false) AS ai_broad, "
          + ", ".join(f"coalesce(x.{s}, false) AS {s}" for s in list(AI_RULES) + list(FLAGS)))
    rest = ", x.n_cpc, x.n_subclasses, x.main_subclass"
    if aipd_parts is False:
        return ai + rest + ", NULL::BOOLEAN AS ai_aipd, NULL::BOOLEAN AS ai_aipd_strict"
    return ai + rest + ", d.ai_aipd, d.ai_aipd_strict" + "".join(f", d.{p}" for p in aipd_parts)


# --------------------------------------------------------------------------- granted patents
def adapt_patentsview():
    need = ("patent", "cpc", "inventor", "location")
    have = {r: bool(discover("patentsview", r)) for r in PV}
    if not all(have[r] for r in need):
        log(f"patentsview: missing {[r for r in need if not have[r]]}. Put g_patent, g_cpc_current, g_inventor_disambiguated "
            "and g_location_disambiguated (.tsv or .tsv.zip) in POLISY/data/patentsview, or run the notebook's download step. "
            "g_application (filing dates) and g_assignee_disambiguated (owners) are strongly recommended")
        return False
    st = stage_tables("patentsview", PV, PV)
    if not all(r in st for r in need):
        log(f"patentsview: could not stage {[r for r in need if r not in st]} (see the lines above)")
        return False
    for r in ("application", "assignee"):
        if r not in st:
            log(f"patentsview: no {PV[r][0]}; " + ("filing years (app_year) stay empty, so counts by filing year cannot be made"
                                                  if r == "application" else "patents have no owner, so the firm link can use DISCERN only"))
    c = sg.con()
    try:
        for r, p in st.items():
            _view(c, {"patent": "gp", "application": "ga", "cpc": "cpc", "inventor": "inv", "location": "gloc",
                      "assignee": "asg_raw"}[r], p)
        # utility patents that were not withdrawn (a missing column keeps every patent)
        where = ["coalesce(lower(patent_type), 'utility') = 'utility'",
                 "coalesce(lower(withdrawn), '0') IN ('0', 'false', 'f', '', '0.0')"]
        c.execute(f"""CREATE OR REPLACE TABLE pat AS
            SELECT patent_id, {_norm_id('patent_id')} AS pid, {_year('grant_date')} AS year, {_date('grant_date')} AS grant_date,
                   num_claims FROM gp WHERE {' AND '.join(where)}""")
        if "application" in st:
            c.execute(f"""CREATE OR REPLACE TABLE app AS SELECT patent_id, min({_date('filing_date')}) AS filing_date,
                          min({_year('filing_date')}) AS app_year FROM ga GROUP BY 1""")
        else:
            c.execute("CREATE OR REPLACE TABLE app AS SELECT NULL::VARCHAR AS patent_id, NULL::DATE AS filing_date, NULL::INTEGER AS app_year WHERE FALSE")
        _cpc_table(c, "patent_id")
        _loc_table(c, ["gloc"])
        _inventor_table(c, "patent_id")
        if "assignee" in st:
            _assignee_table(c, "patent_id")
        else:
            c.execute("CREATE OR REPLACE TABLE asg AS SELECT NULL::VARCHAR AS id, NULL::VARCHAR AS assignee_id, NULL::VARCHAR AS assignee_org, "
                      "NULL::INTEGER AS assignee_type, NULL::BIGINT AS n_assignees WHERE FALSE")
        parts = _aipd_view(c, patents=True)
        c.execute(f"""CREATE OR REPLACE TABLE pats AS
            SELECT p.patent_id, p.year, p.grant_date, a.app_year, a.filing_date, p.num_claims, {_flag_select(parts)},
                   i.n_inventors, i.n_us_inventors, i.first_inventor_state,
                   s.assignee_id, s.assignee_org, s.assignee_type, s.n_assignees
            FROM pat p LEFT JOIN app a USING (patent_id) LEFT JOIN cpcx x ON x.id = p.patent_id
                 LEFT JOIN invs i ON i.id = p.patent_id LEFT JOIN asg s ON s.id = p.patent_id
                 {'LEFT JOIN ad d ON d.doc_id = p.pid' if parts is not False else ''}
            WHERE p.year IS NOT NULL""")
        n, nai, nb, nf, naipd, ncov = c.execute("""SELECT count(*), sum(ai::INT), sum(ai_broad::INT), count(app_year),
                                                   sum(ai_aipd::INT), count(ai_aipd) FROM pats""").fetchone()
        log(f"patentsview: {n:,} utility patents; AI narrow {nai:,} ({nai / max(n, 1):.2%}), broad {nb:,} ({nb / max(n, 1):.2%}); "
            f"filing year known for {nf / max(n, 1):.1%}")
        diagnostic("patents -> filing dates", "patents", "g_application", "patent_id", nf, n, "patents")
        if parts is not False:
            log(f"patentsview: AI Patent Dataset covers {ncov / max(n, 1):.1%} of patents, {(naipd or 0) / max(ncov, 1):.2%} of them AI")
            diagnostic("patents -> AI Patent Dataset", "patents", "aipd", "patent number", ncov, n, "patents")
            both = c.execute("""SELECT sum((ai_aipd AND ai_broad)::INT), sum(ai_aipd::INT), sum(ai_broad::INT)
                                FROM pats WHERE ai_aipd IS NOT NULL""").fetchone()
            if both[1] and both[2]:
                log(f"patentsview: of the AIPD's AI patents, {both[0] / both[1]:.0%} carry a broad AI CPC code; of the broad CPC "
                    f"AI patents, {both[0] / both[2]:.0%} are AI for the AIPD")
        _copy(c, "SELECT * FROM pats", "patents")
        _places(c)
        _edges_and_moves(c)
        return True
    finally:
        sg.close(c)


def _places(c):
    c.execute("""CREATE OR REPLACE TABLE places AS
        WITH k AS (SELECT patent_id, count(*) AS n FROM inv GROUP BY 1)
        SELECT i.patent_id, i.inventor_id, p.year, p.app_year, l.state_fips, l.county_fips, l.lat, l.lon,
               1.0 / k.n AS share, p.ai, p.ai_broad, p.ai_aipd, p.climate
        FROM inv i JOIN pats p USING (patent_id) JOIN k USING (patent_id) JOIN loc l USING (location_id)
        WHERE l.us AND l.state_fips IS NOT NULL
        QUALIFY row_number() OVER (PARTITION BY i.patent_id, i.inventor_id
                                   ORDER BY i.seq, l.state_fips, l.county_fips NULLS LAST, l.lat NULLS LAST, l.lon NULLS LAST) = 1""")
    m = c.execute("SELECT count(*), count(DISTINCT patent_id), sum(CASE WHEN county_fips IS NULL THEN 1 ELSE 0 END) FROM places").fetchone()
    log(f"patentsview: {m[0]:,} US inventor-patent rows on {m[1]:,} patents; {m[2]:,} without a county")
    _copy(c, "SELECT * FROM places", "patent_places")
    for lvl, key in (("county", "county_fips"), ("state", "state_fips")):
        _copy(c, f"""SELECT {key}, year, sum(share) AS patents, sum(CASE WHEN ai THEN share ELSE 0 END) AS ai_patents,
                            sum(CASE WHEN ai_broad THEN share ELSE 0 END) AS ai_broad_patents,
                            sum(CASE WHEN ai_aipd THEN share ELSE 0 END) AS ai_aipd_patents,
                            sum(CASE WHEN climate THEN share ELSE 0 END) AS climate_patents,
                            count(DISTINCT inventor_id) AS inventors,
                            count(DISTINCT CASE WHEN ai_broad THEN inventor_id END) AS ai_inventors
                     FROM places WHERE {key} IS NOT NULL GROUP BY 1, 2""", f"patents_{lvl}_year")


def _edges_and_moves(c):
    _copy(c, """WITH a AS (SELECT DISTINCT k.patent_id, p.year,
                                  coalesce(nullif(upper(trim(k.subclass)), ''), substr(upper(replace(k.grp, ' ', '')), 1, 4)) AS s
                           FROM cpc k JOIN pats p USING (patent_id) WHERE p.ai_broad),
                     e AS (SELECT x.s AS a, y.s AS b, CASE WHEN x.year < 2010 THEN 'before 2010' WHEN x.year < 2015 THEN '2010-2014'
                                  WHEN x.year < 2020 THEN '2015-2019' ELSE '2020 on' END AS period
                           FROM a x JOIN a y ON x.patent_id = y.patent_id AND x.s < y.s)
                SELECT a, b, period, count(*) AS weight FROM e GROUP BY 1, 2, 3 HAVING count(*) >= 5""", "ai_cpc_edges")
    _copy(c, """WITH s AS (SELECT inventor_id, patent_id, year, min(state_fips) AS state_fips, bool_or(ai_broad) AS ai
                           FROM places GROUP BY 1, 2, 3),
                     o AS (SELECT *, lag(state_fips) OVER (PARTITION BY inventor_id ORDER BY year, patent_id) AS prev FROM s)
                SELECT prev AS origin, state_fips AS dest, year, ai, count(*) AS moves FROM o
                WHERE prev IS NOT NULL AND prev <> state_fips GROUP BY 1, 2, 3, 4""", "inventor_moves")


# --------------------------------------------------------------------------- published applications
def adapt_pregrant():
    need = ("application", "cpc")
    have = {r: bool(discover("patentsview_pregrant", r)) for r in PG}
    if not all(have[r] for r in need):
        log("patentsview_pregrant: missing " + ", ".join(PG[r][0] for r in need if not have[r]) + ". The pre-grant tables "
            "(pg_published_application, pg_cpc_current, pg_inventor_disambiguated, pg_location_disambiguated, "
            "pg_assignee_disambiguated, pg_granted_pgpubs_crosswalk) show invention since 2021 that is not granted yet; "
            "the notebook's download step fetches them")
        return False
    st = stage_tables("patentsview_pregrant", PG, PG)
    if not all(r in st for r in need):
        return False
    c = sg.con()
    try:
        names = {"application": "pa", "cpc": "cpc", "inventor": "inv", "location": "ploc", "assignee": "asg_raw", "crosswalk": "xw"}
        for r, p in st.items():
            _view(c, names[r], p)
        cols = [r[0] for r in c.execute("DESCRIBE SELECT * FROM pa").fetchall()]
        # one row per application: its first publication (republications, kind A2/A9, repeat the same invention)
        has_app = pc.q1(c, "SELECT count(application_id) FROM pa") if "application_id" in cols else 0
        if not has_app and "crosswalk" in st:
            c.execute("CREATE OR REPLACE VIEW pa2 AS SELECT a.* EXCLUDE (application_id), x.application_id FROM pa a "
                      "LEFT JOIN (SELECT pgpub_id, min(application_id) AS application_id FROM xw GROUP BY 1) x USING (pgpub_id)")
        else:
            c.execute("CREATE OR REPLACE VIEW pa2 AS SELECT * FROM pa")
        c.execute(f"""CREATE OR REPLACE TABLE pub AS
            SELECT pgpub_id, {_norm_id('pgpub_id')} AS pid, application_id, {_date('filing_date')} AS filing_date,
                   {_year('filing_date')} AS app_year, {_year('published_date')} AS pub_year
            FROM pa2 WHERE {_year('filing_date')} IS NOT NULL
            QUALIFY row_number() OVER (PARTITION BY coalesce(application_id, pgpub_id)
                                       ORDER BY published_date NULLS LAST, pgpub_id) = 1""")
        n_all, n_one = pc.q1(c, "SELECT count(*) FROM pa"), pc.q1(c, "SELECT count(*) FROM pub")
        if n_all > n_one:
            log(f"patentsview_pregrant: {n_all - n_one:,} republications of the same application dropped (first publication kept)")
        _cpc_table(c, "pgpub_id")
        locs = ["ploc"] if "location" in st else []
        g_loc = sg.staged_path("patentsview", "g_location_disambiguated")
        if g_loc.exists():
            _view(c, "gloc", g_loc)
            locs.append("gloc")
        if "inventor" in st and locs:
            _loc_table(c, locs)
            _inventor_table(c, "pgpub_id")
        else:
            c.execute("CREATE OR REPLACE TABLE invs AS SELECT NULL::VARCHAR AS id, NULL::BIGINT AS n_inventors, "
                      "NULL::BIGINT AS n_us_inventors, NULL::VARCHAR AS first_inventor_state WHERE FALSE")
        if "assignee" in st:
            _assignee_table(c, "pgpub_id")
        else:
            c.execute("CREATE OR REPLACE TABLE asg AS SELECT NULL::VARCHAR AS id, NULL::VARCHAR AS assignee_id, NULL::VARCHAR AS assignee_org, "
                      "NULL::INTEGER AS assignee_type, NULL::BIGINT AS n_assignees WHERE FALSE")
        xw = "(SELECT pgpub_id, min(patent_id) AS granted_patent_id FROM xw GROUP BY 1)" if "crosswalk" in st else \
             "(SELECT NULL::VARCHAR AS pgpub_id, NULL::VARCHAR AS granted_patent_id WHERE FALSE)"
        parts = _aipd_view(c, patents=False)
        c.execute(f"""CREATE OR REPLACE TABLE pubs AS
            SELECT p.pgpub_id, p.application_id, p.app_year, p.filing_date, p.pub_year, g.granted_patent_id, {_flag_select(parts)},
                   i.n_inventors, i.n_us_inventors, i.first_inventor_state, s.assignee_id, s.assignee_org, s.assignee_type, s.n_assignees
            FROM pub p LEFT JOIN cpcx x ON x.id = p.pgpub_id LEFT JOIN invs i ON i.id = p.pgpub_id
                 LEFT JOIN asg s ON s.id = p.pgpub_id LEFT JOIN {xw} g ON g.pgpub_id = p.pgpub_id
                 {'LEFT JOIN ad d ON d.doc_id = p.pid' if parts is not False else ''}""")
        n, nb, ng, nai, ncov, y1 = c.execute("""SELECT count(*), sum(ai_broad::INT), count(granted_patent_id), sum(ai_aipd::INT),
                                                   count(ai_aipd), max(app_year) FROM pubs""").fetchone()
        log(f"patentsview_pregrant: {n:,} published applications filed up to {y1}; {ng / max(n, 1):.0%} became patents; "
            f"AI by CPC (broad) {nb / max(n, 1):.2%}" + (f"; AIPD covers {ncov / max(n, 1):.0%}, {(nai or 0) / max(ncov, 1):.2%} of them AI"
                                                          if parts is not False else ""))
        if parts is not False:
            diagnostic("published applications -> AI Patent Dataset", "applications", "aipd", "publication number", ncov, n, "applications")
        _copy(c, "SELECT * FROM pubs", "applications")
        if "inventor" in st and locs:
            c.execute("""CREATE OR REPLACE TABLE aplaces AS
                WITH k AS (SELECT pgpub_id, count(*) AS n FROM inv GROUP BY 1)
                SELECT i.pgpub_id, i.inventor_id, p.app_year, p.pub_year, l.state_fips, l.county_fips, 1.0 / k.n AS share,
                       p.ai, p.ai_broad, p.ai_aipd, p.climate, p.granted_patent_id IS NOT NULL AS granted
                FROM inv i JOIN pubs p USING (pgpub_id) JOIN k USING (pgpub_id) JOIN loc l USING (location_id)
                WHERE l.us AND l.state_fips IS NOT NULL
                QUALIFY row_number() OVER (PARTITION BY i.pgpub_id, i.inventor_id ORDER BY i.seq, l.state_fips, l.county_fips NULLS LAST) = 1""")
            _copy(c, "SELECT * FROM aplaces", "application_places")
        return True
    finally:
        sg.close(c)


# --------------------------------------------------------------------------- inventions by filing year
def adapt_inventions():
    """Granted patents and published applications by filing year, nationally and by inventor state and county."""
    pats, apps = canon("patents"), canon("applications")
    if not pats.exists():
        log("inventions: needs the patents table (adapter patentsview)")
        return False
    c = sg.con()
    try:
        _view(c, "p", pats)
        have_apps = apps.exists()
        if have_apps:
            _view(c, "a", apps)
        cnt = lambda pre, t: (f"count(*) AS {pre}, sum(ai::INT) AS {pre}_ai_cpc_narrow, sum(ai_broad::INT) AS {pre}_ai_cpc, "  # noqa: E731
                              f"sum(ai_aipd::INT) AS {pre}_ai_aipd, count(ai_aipd) AS {pre}_aipd_covered, "
                              f"sum(climate::INT) AS {pre}_climate, sum(weapons::INT) AS {pre}_weapons")
        c.execute(f"CREATE OR REPLACE TABLE ny AS SELECT app_year AS year, {cnt('patents', 'p')} FROM p WHERE app_year IS NOT NULL GROUP BY 1")
        if have_apps:
            c.execute(f"""CREATE OR REPLACE TABLE ay AS SELECT app_year AS year, {cnt('applications', 'a')},
                          count(granted_patent_id) AS applications_granted FROM a GROUP BY 1""")
            sql = "SELECT * FROM ny FULL JOIN ay USING (year) ORDER BY year"
        else:
            sql = "SELECT * FROM ny ORDER BY year"
        _copy(c, sql, "inventions_year")
        for lvl, key in (("state", "state_fips"), ("county", "county_fips")):
            frac = lambda pre, t: (f"sum(share) AS {pre}, sum(CASE WHEN ai_broad THEN share ELSE 0 END) AS {pre}_ai_cpc, "  # noqa: E731
                                   f"sum(CASE WHEN ai_aipd THEN share ELSE 0 END) AS {pre}_ai_aipd, "
                                   f"sum(CASE WHEN climate THEN share ELSE 0 END) AS {pre}_climate")
            parts = [f"SELECT {key}, app_year AS year, {frac('patents', 'pp')} FROM read_parquet('{pc.sqlp(canon('patent_places'))}') "
                     f"WHERE {key} IS NOT NULL AND app_year IS NOT NULL GROUP BY 1, 2"]
            if canon("application_places").exists():
                parts.append(f"SELECT {key}, app_year AS year, {frac('applications', 'ap')} FROM read_parquet('{pc.sqlp(canon('application_places'))}') "
                             f"WHERE {key} IS NOT NULL AND app_year IS NOT NULL GROUP BY 1, 2")
                sql = f"SELECT * FROM ({parts[0]}) FULL JOIN ({parts[1]}) USING ({key}, year)"
            else:
                sql = parts[0]
            _copy(c, sql, f"inventions_{lvl}_year")
        return True
    finally:
        sg.close(c)
