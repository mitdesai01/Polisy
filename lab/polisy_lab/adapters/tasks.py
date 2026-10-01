# -*- coding: utf-8 -*-
"""Which jobs AI invention targets: AI patent text matched to O*NET tasks, after Webb (2020).

Method
  1. Verb-object pairs. Every text is parsed (spaCy, en_core_web_sm) and reduced to the pairs of a verb and its
     direct object, both lemmatized: "Method for diagnosing diseases using neural networks" -> (diagnose, disease).
     A verb joined to another by "and" shares its object ("detecting and classifying objects" -> detect object,
     classify object), and so do joined objects. Light verbs that say nothing about the work (be, have, include,
     comprise, use, provide, ... see LIGHT_VERBS) are dropped. O*NET task statements are parsed the same way, with
     "They" in front so the parser reads their first word as a verb ("They diagnose and treat patients").
  2. AI inventions: granted patents, plus published applications not granted (yet), that the AI label marks (LAB
     SETTINGS ai_label; "aipd" uses the AI Patent Dataset where it covers the document and the broad CPC flag after
     its last year). Text: the title, or the title and the start of the abstract (webb_text, webb_abstract_words).
     Dated by filing year and grouped into the periods in webb_periods.
  3. Exposure (Webb's measure): a pair's weight in a period is the share of that period's AI inventions whose text
     contains it; a task's exposure is the sum of its pairs' weights; an occupation's is the average over its tasks,
     weighted by O*NET task importance, and its percentile among occupations.
  4. Incidence (whose work a given AI invention touches): an invention touches a task when they share a pair that is
     specific to few occupations (in at most webb_generic_share of them; "analyze data" is not). An occupation's
     touch is the share of its task importance touched; each invention's touches are scaled to sum to one, so
     summing over inventions gives fractional inventions per occupation and filing year.

Canonical tables
  onet_tasks             task_id: O*NET-SOC code, SOC code, title, task, type, importance (IM, 1-5)
  onet_task_pairs        task_id x verb x obj
  webb_pairs             period x verb x obj: AI inventions with the pair and their share of the period's AI inventions
  occ_ai_invention       soc x period: exposure, percentile, tasks and tasks matched ("all" = every period together)
  patent_occ_incidence   doc_id (patent_id or pgpub_id) x soc: touch (share of the occupation's task importance) and
                         incidence (the invention's weight on the occupation, summing to one)
  occ_ai_incidence_year  soc x filing year: fractional AI inventions targeting the occupation, and how many touch it
Parsed pairs are cached per document in lab/staged/tasks, so an interrupted run resumes where it stopped and a new
label or new documents only parse what is new.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from ..core import log, LAB, canon, pc, find_col
from ..sources import discover
from .. import staging as sg
from .patents import _copy

LIGHT_VERBS = {"be", "have", "do", "include", "comprise", "contain", "consist", "use", "utilize", "employ", "provide", "make",
               "allow", "enable", "permit", "perform", "base", "relate", "involve", "facilitate", "get", "say", "embody"}
LEMMA_FIX = {"datum": "data", "medium": "media"}


def load_nlp():
    """spaCy's English pipeline without named entities: LAB SETTINGS webb_model (en_core_web_md, which reads patent
    sentences somewhat better than the small model at the same speed), downloaded when missing; the small model if
    the medium one cannot be had. The model used is written back to the settings, since the cache is kept per model."""
    import spacy
    want = LAB["SETTINGS"].get("webb_model", "en_core_web_md")
    for model in dict.fromkeys([want, "en_core_web_sm"]):
        for attempt in (0, 1):
            try:
                nlp = spacy.load(model, disable=["ner"])
                LAB["SETTINGS"]["webb_model"] = model
                return nlp
            except OSError:
                if attempt == 0:
                    try:
                        from spacy.cli import download
                        download(model)
                    except (Exception, SystemExit) as e:
                        log(f"tasks: cannot download {model} ({type(e).__name__})")
                        break
    raise OSError("no spaCy English model; pip install spacy, then python -m spacy download en_core_web_md")


def _verb(v):
    """The verb's lemma. The small English model sometimes tags a verb as a noun ('A model generates text and answers
    questions'); a word with a direct object is a verb, so its -s is undone here."""
    if v.pos_ in ("VERB", "AUX"):
        return v.lemma_.lower()
    w = v.text.lower()
    for suf, rep in (("ies", "y"), ("sses", "ss"), ("shes", "sh"), ("ches", "ch"), ("xes", "x"), ("zzes", "zz")):
        if w.endswith(suf) and len(w) > len(suf) + 1:
            return w[: -len(suf)] + rep
    return w[:-1] if w.endswith("s") and not w.endswith("ss") and len(w) > 3 else v.lemma_.lower()


def _has_object(v):
    return any(ch.dep_ in ("dobj", "obj") for ch in v.children)


def doc_pairs(doc):
    """Verb-object pairs of one parsed text (lemmas, lower case)."""
    out = set()
    for t in doc:
        if t.dep_ not in ("dobj", "obj") or t.pos_ not in ("NOUN", "PROPN") or t.head.pos_ not in ("VERB", "NOUN", "PROPN"):
            continue
        objs = [t] + [x for x in t.conjuncts if x.pos_ in ("NOUN", "PROPN")]
        verbs = [t.head] + [v for v in t.head.conjuncts if v.pos_ == "VERB" and not _has_object(v)]
        for v in verbs:
            vl = _verb(v)
            if vl in LIGHT_VERBS or not vl.isalpha() or len(vl) < 2:
                continue
            for o in objs:
                ol = o.lemma_.lower()
                ol = LEMMA_FIX.get(ol, ol)
                if ol.isalpha() and len(ol) >= 2:
                    out.add((vl, ol))
    return out


def parse(texts, nlp, batch_size=256, n_process=1):
    return [doc_pairs(d) for d in nlp.pipe(texts, batch_size=batch_size, n_process=n_process)]


# --------------------------------------------------------------------------- O*NET tasks
def onet_tasks():
    t, r = discover("onet_tasks", "tasks"), discover("onet_tasks", "ratings")
    if not t:
        log("tasks: O*NET's Task Statements not found (POLISY_DA module 05 or the lab's fetch downloads the O*NET text zip)")
        return None
    ts = pc.read_table(*t[0])
    code = find_col(ts, [r"onetsoccode", r"onetsoc", r"code"], "O*NET-SOC code", True, "Task Statements")
    tid = find_col(ts, [r"taskid"], "task id", True, "Task Statements")
    task = find_col(ts, [r"task", r"taskstatement"], "task", True, "Task Statements")
    ttype = find_col(ts, [r"tasktype"], "task type", False, "Task Statements")
    title = find_col(ts, [r"title"], "", False)
    d = pd.DataFrame({"task_id": ts[tid].astype(str).str.replace(r"\.0$", "", regex=True), "onet_soc": ts[code].astype(str),
                      "title": ts[title] if title else None, "task": ts[task].astype(str),
                      "task_type": ts[ttype] if ttype else None})
    d["soc"] = d.onet_soc.str[:7]
    d["importance"] = pd.NA
    if r:
        rt = pc.read_table(*r[0])
        rid = find_col(rt, [r"taskid"], "task id", True, "Task Ratings")
        sc = find_col(rt, [r"scaleid"], "scale", True, "Task Ratings")
        val = find_col(rt, [r"datavalue", r"value"], "value", True, "Task Ratings")
        im = rt[rt[sc].astype(str).str.upper() == "IM"]
        imp = pd.to_numeric(im[val], errors="coerce").groupby(im[rid].astype(str).str.replace(r"\.0$", "", regex=True)).mean()
        d["importance"] = d.task_id.map(imp)
    miss = d.importance.isna()
    d["importance"] = pd.to_numeric(d.importance, errors="coerce")
    d.loc[miss, "importance"] = d.groupby("soc").importance.transform("mean")[miss]
    d["importance"] = d.importance.fillna(1.0)
    d = d.drop_duplicates("task_id")
    d.to_parquet(canon("onet_tasks"), index=False)
    log(f"canonical onet_tasks: {len(d):,} tasks of {d.soc.nunique():,} occupations (SOC codes); importance from Task Ratings "
        f"for {1 - miss.mean():.0%}")
    return d


def task_pairs(tasks, nlp):
    """onet_task_pairs, parsed again only when the task statements (or the spaCy model) change."""
    import hashlib
    import json
    key = hashlib.sha1(("|".join(tasks.task_id + ":" + tasks.task) + LAB["SETTINGS"].get("webb_model", "en_core_web_md")
                        ).encode()).hexdigest()
    out, stamp = canon("onet_task_pairs"), canon("onet_task_pairs").with_suffix(".stamp.json")
    if out.exists() and stamp.exists() and json.loads(stamp.read_text()).get("key") == key:
        return pd.read_parquet(out)
    texts = ["They " + s[:1].lower() + s[1:] for s in tasks.task.fillna("")]
    got = parse(texts, nlp)
    rows = [(tid, soc, v, o) for tid, soc, ps in zip(tasks.task_id, tasks.soc, got) for v, o in ps]
    tp = pd.DataFrame(rows, columns=["task_id", "soc", "verb", "obj"]).drop_duplicates()
    tp.to_parquet(out, index=False)
    stamp.write_text(json.dumps({"key": key}))
    log(f"canonical onet_task_pairs: {len(tp):,} pairs; {tp.task_id.nunique() / max(len(tasks), 1):.0%} of tasks have at least one")
    return tp


# --------------------------------------------------------------------------- AI inventions and their text
def _label_sql():
    return {"aipd": "coalesce(ai_aipd, ai_broad)", "cpc_broad": "ai_broad", "cpc_narrow": "ai"}.get(
        LAB["SETTINGS"].get("ai_label", "aipd"), "coalesce(ai_aipd, ai_broad)")


def _universe(c):
    """Table u: AI inventions (granted patents; published applications not granted) with filing year."""
    lab = _label_sql()
    parts = [f"SELECT patent_id AS doc_id, 'patent' AS kind, app_year FROM read_parquet('{pc.sqlp(canon('patents'))}') "
             f"WHERE {lab} AND app_year IS NOT NULL"]
    if canon("applications").exists():
        parts.append(f"SELECT pgpub_id AS doc_id, 'application' AS kind, app_year FROM read_parquet('{pc.sqlp(canon('applications'))}') "
                     f"WHERE {lab} AND granted_patent_id IS NULL AND app_year IS NOT NULL")
    c.execute("CREATE OR REPLACE TABLE u AS " + " UNION ALL ".join(parts))
    # the superset of any AI flag, so a later change of label finds its texts already extracted
    anyai = "(coalesce(ai_aipd, false) OR ai_broad OR ai)"
    parts = [f"SELECT patent_id AS doc_id FROM read_parquet('{pc.sqlp(canon('patents'))}') WHERE {anyai}"]
    if canon("applications").exists():
        parts.append(f"SELECT pgpub_id FROM read_parquet('{pc.sqlp(canon('applications'))}') WHERE {anyai} AND granted_patent_id IS NULL")
    c.execute("CREATE OR REPLACE TABLE uany AS " + " UNION ALL ".join(parts))


def _abstracts(c):
    """staged/tasks/ai_abstracts.parquet: the abstracts of every AI-flagged invention (read once from the big tables)."""
    out = sg.staged_path("tasks", "ai_abstracts")
    srcs = [("patentsview", "abstract", {"doc_id": ([r"patentid"], True), "abstract": ([r"patentabstract", r"abstract"], True)}),
            ("patentsview_pregrant", "abstract", {"doc_id": ([r"pgpubid", r"documentnumber"], True), "abstract": ([r"abstract"], True)})]
    found = [(s, f[0], spec) for s, role, spec in srcs for f in [discover(s, role)] if f]
    if not found:
        return None
    key = ";".join(f"{Path(p).name}:{Path(p).stat().st_size}" for _, (p, m), _ in found) + f";{pc.q1(c, 'SELECT count(*) FROM uany')}"
    if out.exists() and (sg.stamp_of(out) or {}).get("key") == key:
        return out
    parts = []
    tmps = []
    for s, (path, member), spec in found:
        rd, tmp = sg.readable(path, member)
        tmps.append(tmp)
        cols = sg.columns(c, rd)
        m = sg.match_columns(cols, spec, f"{s}/abstract")
        parts.append(f"SELECT CAST({sg.pc_quote(m['doc_id'])} AS VARCHAR) AS doc_id, {sg.pc_quote(m['abstract'])} AS abstract "
                     f"FROM {rd} WHERE {sg.pc_quote(m['doc_id'])} IN (SELECT doc_id FROM uany)")
    out.parent.mkdir(parents=True, exist_ok=True)
    c.execute(f"COPY ({' UNION ALL '.join(parts)}) TO '{pc.sqlp(out)}' (FORMAT parquet, COMPRESSION zstd)")
    out.with_suffix(".stamp.json").write_text(__import__("json").dumps({"key": key}))
    for tmp in tmps:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)
    log(f"tasks: abstracts of {sg.rows(out):,} AI inventions extracted")
    return out


def _texts(c):
    """Table tx(doc_id, text) for the AI inventions in u."""
    mode = LAB["SETTINGS"].get("webb_text", "title+abstract")
    words = int(LAB["SETTINGS"].get("webb_abstract_words", 60))
    titles = [f"SELECT patent_id AS doc_id, title FROM read_parquet('{pc.sqlp(sg.staged_path('patentsview', 'g_patent'))}')"]
    pgp = sg.staged_path("patentsview_pregrant", "pg_published_application")
    if pgp.exists():
        titles.append(f"SELECT pgpub_id AS doc_id, title FROM read_parquet('{pc.sqlp(pgp)}')")
    c.execute("CREATE OR REPLACE VIEW ti AS " + " UNION ALL ".join(titles))
    ab = _abstracts(c) if "abstract" in mode else None
    if "abstract" in mode and ab is None:
        log("tasks: no abstract tables (g_patent_abstract, pg_published_application_abstract), so titles only")
    abs_sql = (f"coalesce(' ' || array_to_string(list_slice(string_split(regexp_replace(a.abstract, '\\s+', ' ', 'g'), ' '), 1, {words}), ' '), '')"
               if ab is not None else "''")
    c.execute(f"""CREATE OR REPLACE TABLE tx AS
        SELECT u.doc_id, trim(coalesce(t.title, '') || '.' || {abs_sql}) AS text
        FROM u LEFT JOIN (SELECT doc_id, first(title ORDER BY length(title) DESC, title) AS title FROM ti GROUP BY 1) t USING (doc_id)
        {f"LEFT JOIN (SELECT doc_id, first(abstract ORDER BY length(abstract) DESC, abstract) AS abstract FROM read_parquet('{pc.sqlp(ab)}') GROUP BY 1) a USING (doc_id)" if ab is not None else ""}""")
    return f"{mode.replace('+', '_')}{words if ab is not None else ''}"


def _parse_cached(c, nlp, tag, chunk=20000):
    """Parse the texts in tx that the cache does not hold yet; the cache holds one row per pair (docs without a pair
    appear once with an empty verb), so a rerun only parses what is new."""
    model = LAB["SETTINGS"].get("webb_model", "en_core_web_md")
    cache = sg.staged_path("tasks", "x").parent / f"pairs_{tag}_{model}"
    cache.mkdir(parents=True, exist_ok=True)
    have = list(cache.glob("part_*.parquet"))
    if have:
        c.execute(f"CREATE OR REPLACE VIEW cache AS SELECT * FROM read_parquet('{pc.sqlp(cache)}/part_*.parquet')")
        todo = pc.q(c, "SELECT doc_id, text FROM tx WHERE doc_id NOT IN (SELECT DISTINCT doc_id FROM cache) ORDER BY doc_id")
    else:
        todo = pc.q(c, "SELECT doc_id, text FROM tx ORDER BY doc_id")
    n0 = len(todo)
    if n0:
        log(f"tasks: parsing {n0:,} texts ({len(have)} earlier chunks cached; about {n0 / 150 / 60:.0f} minutes at 150 texts a second)")
    k = len(have)
    t0 = time.time()
    procs = int(LAB["SETTINGS"].get("webb_processes", 1))
    for i in range(0, n0, chunk):
        part = todo.iloc[i:i + chunk]
        got = parse(part.text.fillna("").tolist(), nlp, n_process=procs)
        rows = [(d, v, o) for d, ps in zip(part.doc_id, got) for v, o in (ps or {(None, None)})]
        pd.DataFrame(rows, columns=["doc_id", "verb", "obj"]).to_parquet(cache / f"part_{k:05d}.parquet", index=False)
        k += 1
        done = i + len(part)
        rate = done / max(time.time() - t0, 1e-9)
        log(f"tasks: {done:,} of {n0:,} texts parsed ({rate:.0f} a second, {(n0 - done) / max(rate, 1e-9) / 60:.0f} minutes left)")
    c.execute(f"CREATE OR REPLACE VIEW cache AS SELECT * FROM read_parquet('{pc.sqlp(cache)}/part_*.parquet')")
    c.execute("CREATE OR REPLACE TABLE dp AS SELECT DISTINCT doc_id, verb, obj FROM cache WHERE verb IS NOT NULL "
              "AND doc_id IN (SELECT doc_id FROM u)")


def _periods_sql():
    per = LAB["SETTINGS"].get("webb_periods") or [(1976, 2030)]
    return "CASE " + " ".join(f"WHEN app_year BETWEEN {a} AND {b} THEN '{a}-{min(b, 2030)}'" for a, b in per) + " END"


def adapt_patent_tasks():
    if not LAB["SETTINGS"].get("webb_run", False):
        log("tasks: skipped (it parses every AI patent's text, up to an hour or two the first time); set "
            "LAB['SETTINGS']['webb_run'] = True to run it (the notebook's task-matching step does)")
        return False
    if not canon("patents").exists() or not sg.staged_path("patentsview", "g_patent").exists():
        log("tasks: needs the patent layer first (adapters aipd, patentsview, pregrant)")
        return False
    try:
        nlp = load_nlp()
    except Exception as e:
        log(f"tasks: spaCy is not available ({type(e).__name__}: {e}); pip install spacy, then python -m spacy download en_core_web_sm")
        return False
    tasks = onet_tasks()
    if tasks is None:
        return False
    tp = task_pairs(tasks, nlp)
    c = sg.con()
    try:
        _universe(c)
        tag = _texts(c)
        _parse_cached(c, nlp, tag)
        c.register("tasks_df", tasks[["task_id", "soc", "importance"]])
        c.register("tp_df", tp)
        c.execute("CREATE OR REPLACE TABLE tk AS SELECT * FROM tasks_df")
        c.execute("CREATE OR REPLACE TABLE tp AS SELECT DISTINCT task_id, soc, verb, obj FROM tp_df")
        c.execute(f"CREATE OR REPLACE TABLE up AS SELECT doc_id, app_year, {_periods_sql()} AS period FROM u")
        # 3. Webb's exposure, by period and for all periods together
        c.execute("""CREATE OR REPLACE TABLE docs_p AS
            SELECT period, count(DISTINCT doc_id) AS n FROM up WHERE doc_id IN (SELECT doc_id FROM dp) GROUP BY 1
            UNION ALL SELECT 'all', count(DISTINCT doc_id) FROM up WHERE doc_id IN (SELECT doc_id FROM dp)""")
        c.execute("""CREATE OR REPLACE TABLE wp AS
            WITH x AS (SELECT up.period, dp.verb, dp.obj, count(DISTINCT dp.doc_id) AS docs FROM dp JOIN up USING (doc_id) GROUP BY 1, 2, 3
                       UNION ALL SELECT 'all', verb, obj, count(DISTINCT doc_id) FROM dp GROUP BY 2, 3)
            SELECT x.period, x.verb, x.obj, x.docs, x.docs / n.n AS share FROM x JOIN docs_p n USING (period)""")
        _copy(c, "SELECT * FROM wp WHERE docs >= 2 ORDER BY period, share DESC", "webb_pairs")
        _copy(c, """WITH te AS (SELECT w.period, tp.task_id, sum(w.share) AS exposure FROM tp JOIN wp w USING (verb, obj) GROUP BY 1, 2),
                         per AS (SELECT DISTINCT period FROM wp),
                         grid AS (SELECT per.period, tk.* FROM per CROSS JOIN tk)
                    SELECT g.soc, g.period, sum(g.importance * coalesce(te.exposure, 0)) / sum(g.importance) AS exposure,
                           count(*) AS tasks, count(te.task_id) AS tasks_matched
                    FROM grid g LEFT JOIN te USING (period, task_id) GROUP BY 1, 2""", "occ_ai_invention")
        c.execute(f"""CREATE OR REPLACE TABLE oai AS SELECT *, percent_rank() OVER (PARTITION BY period ORDER BY exposure) AS percentile
                      FROM read_parquet('{pc.sqlp(canon('occ_ai_invention'))}')""")
        _copy(c, "SELECT * FROM oai ORDER BY period, soc", "occ_ai_invention")
        # 4. incidence through pairs specific to few occupations
        share = float(LAB["SETTINGS"].get("webb_generic_share", 0.05))
        c.execute(f"""CREATE OR REPLACE TABLE spec AS
            WITH n AS (SELECT count(DISTINCT soc) AS n FROM tk)
            SELECT verb, obj, count(DISTINCT soc) AS n_occ FROM tp GROUP BY 1, 2 HAVING count(DISTINCT soc) <= greatest(1, {share} * (SELECT n FROM n))""")
        c.execute("""CREATE OR REPLACE TABLE touch AS
            WITH hit AS (SELECT DISTINCT dp.doc_id, tp.soc, tp.task_id FROM dp JOIN spec USING (verb, obj) JOIN tp USING (verb, obj)),
                 tot AS (SELECT soc, sum(importance) AS imp FROM tk GROUP BY 1)
            SELECT hit.doc_id, hit.soc, sum(tk.importance) / any_value(tot.imp) AS touch
            FROM hit JOIN tk USING (task_id) JOIN tot ON tot.soc = hit.soc GROUP BY 1, 2""")
        _copy(c, "SELECT doc_id, soc, touch, touch / sum(touch) OVER (PARTITION BY doc_id) AS incidence FROM touch", "patent_occ_incidence")
        _copy(c, f"""SELECT i.soc, up.app_year AS year, sum(i.incidence) AS ai_incidence, count(*) AS ai_inventions_touching
                     FROM read_parquet('{pc.sqlp(canon('patent_occ_incidence'))}') i JOIN up USING (doc_id) GROUP BY 1, 2""",
              "occ_ai_incidence_year")
        n_u, n_dp, n_inc = c.execute("""SELECT (SELECT count(*) FROM u), (SELECT count(DISTINCT doc_id) FROM dp),
                                               (SELECT count(DISTINCT doc_id) FROM touch)""").fetchone()
        log(f"tasks: {n_u:,} AI inventions; {n_dp / max(n_u, 1):.0%} have a verb-object pair, {n_inc / max(n_u, 1):.0%} touch at "
            f"least one occupation through an occupation-specific pair")
        return True
    finally:
        sg.close(c)
