# -*- coding: utf-8 -*-
"""report: the POLISY research report, an academic HTML page built from report.md and results.json.

    from polisy_lab.report import build_report
    build_report(results, "site/index.html")

report.md holds the argument (edit it freely). Inside it:
    <!-- figure: NAME -->    a numbered figure from figures.FIGURES
    <!-- table: NAME -->     a numbered table from tables.TABLES
    Table: Caption           a caption for the Markdown table that follows
    {fig:NAME} {tab:NAME}    "Figure n" / "Table n", linked
    [@key; @key]  @key       citations (parenthetical / narrative) from references.REFS
    {{finding-id.stat:fmt}}  a number from a finding's stats, e.g. {{stress-mig.attenuation:.0%}}
Figures and tables are rebuilt from the data on every build; the prose is not.
"""
from __future__ import annotations

import html
import re
import time
from pathlib import Path

from ..core import log, __version__
from .figures import FIGURES
from .tables import TABLES
from .references import REFS

HERE = Path(__file__).resolve().parent
FONTS = ("https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400"
         "&family=Source+Sans+3:wght@400;600;700&display=swap")
TITLE = "POLISY: What Is New, What Is Not, and Where the Frontier Is"
SUBTITLE = "A critical assessment of the first POLISY run on politics, AI and innovation"


def _stat(res, fid, key):
    for f in res.get("findings", []):
        if f["id"] == fid:
            return (f.get("stats") or {}).get(key)
    return None


def _fill_stats(text, res):
    def rep(m):
        fid, key, fmt = m.group(1), m.group(2), m.group(3) or ""
        v = _stat(res, fid, key)
        if v is None:
            return "n/a"
        try:
            out = format(float(v), fmt) if fmt else str(v)
        except (TypeError, ValueError):
            out = str(v)
        return out.replace("-", "−") if isinstance(v, (int, float)) and float(v) < 0 else out
    return re.sub(r"\{\{\s*([\w-]+)\.([\w-]+)(?::([^}]+))?\s*\}\}", rep, text)


def _citations(s):
    def one(key, narrative):
        r = REFS.get(key)
        if not r:
            return None
        return (f'<a class="cite" href="#ref-{key}">{r["cite"]} ({r["year"]})</a>' if narrative
                else f'<a class="cite" href="#ref-{key}">{r["cite"]}, {r["year"]}</a>')

    def paren(m):
        keys = [k.strip().lstrip("@") for k in m.group(1).split(";")]
        parts = [one(k, False) for k in keys]
        if not all(parts):
            return m.group(0)
        return "(" + "; ".join(parts) + ")"
    s = re.sub(r"\[((?:@[\w-]+\s*;?\s*)+)\]", paren, s)
    return re.sub(r"(?<![\w@/])@([a-z][\w-]*\d{4}[a-z]?|[a-z]+)(?![\w-])", lambda m: one(m.group(1), True) or m.group(0), s)


def _cited(s):
    return list(dict.fromkeys(re.findall(r'href="#ref-([\w-]+)"', s)))


def build_report(res, out, links=None, fragment=False):
    """Write the report to `out` (an .html path). links: {'lab': 'lab.html', 'data': 'data/', 'code': url}.
    fragment: leave out <!DOCTYPE>, <html>, <head> and <body> (for hosts that add them)."""
    links = {"lab": "lab.html", "data": "data/results.json", "code": "https://github.com/mitdesai01/Polisy", **(links or {})}
    src = (HERE / "report.md").read_text(encoding="utf-8")
    src = _fill_stats(src, res)
    # figures and tables: number them in order of appearance
    order = {"figure": [], "table": []}
    for kind, name in re.findall(r"<!--\s*(figure|table):\s*([\w-]+)\s*-->", src):
        order[kind].append(name)
    # markdown table captions are numbered with the data tables, in order of appearance
    seq, tnum = [], {}
    for m in re.finditer(r"<!--\s*table:\s*([\w-]+)\s*-->|^Table:\s*(.+)$", src, flags=re.M):
        seq.append(m.group(1) or ("md:" + m.group(2).strip()))
    for i, key in enumerate(seq, 1):
        tnum[key] = i
    fnum = {n: i for i, n in enumerate(order["figure"], 1)}
    blocks = {}
    for name, i in fnum.items():
        f = FIGURES.get(name)
        r = f(res) if f else None
        if r is None:
            blocks[f"figure:{name}"] = f'<p class="missing">Figure {i} ({name}) needs data that this run does not have.</p>'
            continue
        svg, cap, notes = r
        blocks[f"figure:{name}"] = (f'<figure class="fig" id="fig-{name}"><div class="plot">{svg}</div>'
                                    f'<figcaption><b>Figure {i}.</b> {cap}<span class="notes">{notes}</span></figcaption></figure>')
    for name in order["table"]:
        i = tnum[name]
        t = TABLES.get(name)
        r = t(res) if t else None
        if r is None:
            blocks[f"table:{name}"] = f'<p class="missing">Table {i} ({name}) needs data that this run does not have.</p>'
            continue
        tab, cap, notes = r
        blocks[f"table:{name}"] = (f'<figure class="tab" id="tab-{name}"><figcaption><b>Table {i}.</b> {cap}</figcaption>'
                                   f'<div class="tbl">{tab}</div><p class="tnotes">{notes}</p></figure>')
    src = re.sub(r"<!--\s*(figure|table):\s*([\w-]+)\s*-->", lambda m: f"\n\n@@BLOCK:{m.group(1)}:{m.group(2)}@@\n\n", src)
    src = re.sub(r"^Table:\s*(.+)$", lambda m: f"\n@@MDCAP:{m.group(1).strip()}@@\n", src, flags=re.M)
    src = re.sub(r"\{fig:([\w-]+)\}", lambda m: f'<a class="xref" href="#fig-{m.group(1)}">Figure {fnum.get(m.group(1), "?")}</a>', src)
    src = re.sub(r"\{tab:([\w-]+)\}", lambda m: f'<a class="xref" href="#tab-{m.group(1)}">Table {tnum.get(m.group(1), "?")}</a>', src)
    body = _markdown(src)
    body = re.sub(r"<p>@@BLOCK:(figure|table):([\w-]+)@@</p>", lambda m: blocks.get(f"{m.group(1)}:{m.group(2)}", ""), body)

    md_numbers = iter([tnum[k] for k in seq if k.startswith("md:")])

    def mdcap(m):                           # Markdown tables are numbered in the order they appear
        return (f'<figure class="tab"><figcaption><b>Table {next(md_numbers, "?")}.</b> {m.group(1)}</figcaption>'
                f'<div class="tbl">{m.group(2)}</div></figure>')
    body = re.sub(r"<p>@@MDCAP:(.+?)@@</p>\s*(<table>.*?</table>)", mdcap, body, flags=re.S)
    body = _citations(body)
    body = body.replace("<table>", '<table class="md">')
    refs = _references(_cited(body))
    toc = _toc(body)
    built = time.strftime("%d %B %Y").lstrip("0")
    run = (res.get("run") or {}).get("finished", "")
    page = (HERE / "template.html").read_text(encoding="utf-8")
    for k, v in {"{{TITLE}}": TITLE, "{{SUBTITLE}}": SUBTITLE, "{{FONTS}}": FONTS, "{{CSS}}": (HERE / "report.css").read_text(encoding="utf-8"),
                 "{{TOC}}": toc, "{{BODY}}": body, "{{REFS}}": refs, "{{BUILT}}": built, "{{RUN}}": html.escape(run),
                 "{{VERSION}}": html.escape(__version__.split(" ")[0]), "{{LAB}}": links["lab"], "{{DATA}}": links["data"], "{{CODE}}": links["code"]}.items():
        page = page.replace(k, v)
    if fragment:                            # for hosts that supply <html>, <head> and <body> themselves
        page = re.sub(r"<!--DOC-->.*?<!--/DOC-->", "", page, flags=re.S)
    else:
        page = page.replace("<!--DOC-->", "").replace("<!--/DOC-->", "")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(page, encoding="utf-8")
    log(f"report: {len(fnum)} figures, {len(tnum)} tables, {len(_cited(body))} references -> {out} ({len(page) / 1e3:,.0f} KB)")
    return Path(out)


def _markdown(src):
    try:
        import markdown
        return markdown.markdown(src, extensions=["tables", "attr_list", "md_in_html", "def_list", "sane_lists", "smarty", "toc"],
                                 extension_configs={"toc": {"permalink": False}, "smarty": {"smart_angled_quotes": False}},
                                 output_format="html")
    except ImportError:
        from ..site import _mini_markdown
        return _mini_markdown(src)


def _toc(body):
    items = []
    for level, hid, text in re.findall(r'<h([23]) id="([^"]+)">(.*?)</h\1>', body):
        text = re.sub(r"<[^>]+>", "", text)
        items.append(f'<a class="l{level}" href="#{hid}">{text}</a>')
    return "\n".join(items)


def _references(keys):
    rows = []
    for k in sorted(keys, key=lambda k: re.sub(r"<[^>]+>|&[a-z]+;", "", REFS[k]["ref"]).lower()):
        r = REFS[k]
        link = f' <a href="{r["link"]}">{html.escape(r["link"].replace("https://", ""))}</a>' if r.get("link") else ""
        check = f' <span class="check">[{r["check"]}]</span>' if r.get("check") else ""
        rows.append(f'<li id="ref-{k}">{r["ref"]}{link}{check}</li>')
    return "<ol class=\"refs\">" + "\n".join(rows) + "</ol>"
