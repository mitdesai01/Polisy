# -*- coding: utf-8 -*-
"""staging: big source tables -> Parquet, once.

The large inputs (PatentsView's tab-separated tables, the USPTO AI Patent Dataset, DISCERN's Stata files, an IPUMS
extract) are read with DuckDB, which streams them, so a file larger than memory is fine. Only the columns the lab
uses are kept. Each one is found by pattern (find_col), and the match is logged. The staged copy is written to
lab/staged/<source>/<table>.parquet with a stamp recording the source file's name, size and date. Later runs reuse
it until the source changes, so a multi-gigabyte file is read once, not at every run.

A zipped table is unzipped to local scratch disk first (Colab's /content, much faster than Drive) and the unzipped
copy is deleted afterwards unless keep=True.
"""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path

import pandas as pd

from .core import LAB, log, pc, find_col, squash

STAGE_VERSION = 1
# unzipped copies and staged tables must never be found as inputs themselves (Colab's /content is a search folder)
pc._SKIP_DIRS.update({"polisy_scratch", "scratch", "staged", "duckdb_tmp"})


def scratch():
    """Local disk for unzipped copies and DuckDB's spill files: POLISY_SCRATCH, else Colab's /content."""
    d = os.environ.get("POLISY_SCRATCH") or ("/content/polisy_scratch" if Path("/content").is_dir()
                                              else str(Path(LAB["TMP"]) / "scratch"))
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


def con(threads=None):
    """A DuckDB connection that spills to local scratch disk (never to Drive)."""
    import duckdb
    c = duckdb.connect()
    tmp = scratch() / "duckdb_tmp"
    tmp.mkdir(exist_ok=True)
    c.execute(f"SET temp_directory = '{pc.sqlp(tmp)}'")
    c.execute("SET preserve_insertion_order = false")
    if threads:
        c.execute(f"SET threads TO {int(threads)}")
    return c


def staged_path(source, table):
    return Path(LAB["STAGED"]) / source / f"{table}.parquet"


def _stamp(path, member):
    st = Path(path).stat()
    return {"file": Path(path).name, "path": str(path), "member": member, "size": st.st_size,
            "mtime": int(st.st_mtime), "version": STAGE_VERSION}


def stamp_of(out):
    s = Path(out).with_suffix(".stamp.json")
    try:
        return json.loads(s.read_text()) if s.exists() else None
    except ValueError:
        return None


def fresh(out, path, member=None):
    """True when `out` was staged from this very file (same name, member, size and date)."""
    old = stamp_of(out)
    if old is None or not Path(out).exists():
        return False
    new = _stamp(path, member)
    return all(old.get(k) == new[k] for k in ("file", "member", "size", "mtime", "version"))


def write_stamp(out, path, member, **extra):
    Path(out).with_suffix(".stamp.json").write_text(json.dumps({**_stamp(path, member), **extra}, indent=1))


def local(path, member=None):
    """(a path DuckDB can read, whether it is a temporary unzipped copy). Zip members are unzipped to scratch;
    a copy of the right size from an earlier run is reused."""
    path = Path(path)
    if member is None and path.suffix.lower() != ".zip":
        return path, False
    with zipfile.ZipFile(path) as zf:
        name = member or next(n for n in zf.namelist()
                              if n.lower().endswith((".tsv", ".csv", ".txt", ".tab", ".dta", ".parquet", ".dat", ".xml"))
                              and "__MACOSX" not in n)
        info = zf.getinfo(name)
        out = scratch() / Path(name).name
        if not (out.exists() and out.stat().st_size == info.file_size):
            log(f"unzipping {Path(name).name} ({info.file_size / 1e9:.2f} GB) to {out.parent}")
            with zf.open(name) as fin, open(out, "wb") as fout:
                shutil.copyfileobj(fin, fout, 1 << 24)
    return out, True


def _ext(p):
    p = Path(p)
    ext = p.suffix.lower()
    return Path(p.stem).suffix.lower() if ext == ".gz" else ext


def reader(p):
    """DuckDB's read expression for a text table (every column as text) or a Parquet file."""
    p = Path(p)
    ext = _ext(p)
    if ext == ".parquet":
        return f"read_parquet('{pc.sqlp(p)}')"
    if ext in (".tsv", ".tab"):
        delim = "\\t"
    elif p.suffix.lower() == ".gz":
        delim = ","
    else:
        d = pc.sniff_delim(p)
        delim = "\\t" if d == "\t" else d
    return (f"read_csv('{pc.sqlp(p)}', delim='{delim}', header=true, quote='\"', escape='\"', all_varchar=true, "
            f"ignore_errors=true, max_line_size=50000000)")


def dta_to_parquet(p, chunk=500_000):
    """A Stata file -> Parquet in scratch, chunk by chunk (DuckDB cannot read .dta). Reused while up to date."""
    p = Path(p)
    out = scratch() / f"{p.stem}.from_dta.parquet"
    if out.exists() and out.stat().st_mtime >= p.stat().st_mtime:
        return out
    import pyarrow as pa
    import pyarrow.parquet as papq
    writer = None
    with pd.read_stata(p, iterator=True, chunksize=chunk, convert_categoricals=False) as it:
        for part in it:
            part = part.astype({c: "string" for c in part.columns if part[c].dtype == object})
            t = pa.Table.from_pandas(part, preserve_index=False)
            if writer is None:
                writer = papq.ParquetWriter(out, t.schema, compression="zstd")
            writer.write_table(t.cast(writer.schema))
    if writer is not None:
        writer.close()
    return out


def readable(path, member=None):
    """(DuckDB read expression, temporary file or None) for any staged-able input: zip members are unzipped, Stata
    files converted."""
    p, tmp = local(path, member)
    if _ext(p) == ".dta":
        q = dta_to_parquet(p)
        return reader(q), (p if tmp else None)
    return reader(p), (p if tmp else None)


def columns(c, rd):
    return list(pc.q(c, f"DESCRIBE SELECT * FROM {rd} LIMIT 0")["column_name"])


def match_columns(cols, spec, source):
    """spec {out: patterns or (patterns, required)} -> {out: source column or None}, logged."""
    out = {}
    for name, pats in spec.items():
        req = False
        if isinstance(pats, tuple):
            pats, req = pats
        out[name] = find_col(cols, pats, name, req, source)
    return out


def exact_col(cols, names):
    """The first column whose squashed name is exactly one of `names` (no partial matches: 'patents', a count,
    must never be taken for 'patent', an identifier)."""
    sq = {squash(c): c for c in cols}
    for n in names:
        if n in sq:
            return sq[n]
    return None


def stage(source, table, found, spec, select=None, where="", keep=False):
    """Stage one table: found = (path, member) from sources.discover. spec maps output names to column patterns
    (see match_columns); select optionally maps output names to SQL templates using {c} for the matched column,
    e.g. {"filing_date": "try_cast({c} AS DATE)"}. Missing optional columns become NULL. Returns
    (staged path, {out: source column}) or (None, {}) when a required column is missing."""
    path, member = found
    out = staged_path(source, table)
    if fresh(out, path, member):
        st = stamp_of(out) or {}
        log(f"{source}/{table}: staged copy is up to date ({out.name})")
        return out, st.get("columns", {})
    c = con()
    rd, tmp = readable(path, member)
    try:
        cols = columns(c, rd)
        try:
            m = match_columns(cols, spec, f"{source}/{table}")
        except KeyError as e:
            log(f"{source}/{table}: {e}")
            return None, {}
        parts = []
        for name, col in m.items():                 # a column the file lacks is kept, empty, with the same type
            tpl = (select or {}).get(name, "{c}")
            parts.append(f"{tpl.format(c=pc_quote(col) if col else 'NULL::VARCHAR')} AS {name}")
        out.parent.mkdir(parents=True, exist_ok=True)
        sql = f"SELECT {', '.join(parts)} FROM {rd}" + (f" WHERE {where.format(**{k: pc_quote(v) for k, v in m.items() if v})}" if where else "")
        c.execute(f"COPY ({sql}) TO '{pc.sqlp(out)}' (FORMAT parquet, COMPRESSION zstd)")
        n = pc.q1(c, f"SELECT count(*) FROM read_parquet('{pc.sqlp(out)}')")
        write_stamp(out, path, member, columns=m, rows=n)
        log(f"{source}/{table}: staged {n:,} rows from {Path(member or path).name}")
        return out, m
    finally:
        c.close()
        if tmp is not None and not keep:
            Path(tmp).unlink(missing_ok=True)


def pc_quote(col):
    return '"' + str(col).replace('"', '""') + '"'


def rows(p):
    import pyarrow.parquet as papq
    return papq.ParquetFile(p).metadata.num_rows if Path(p).exists() else 0
