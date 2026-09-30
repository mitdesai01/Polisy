# -*- coding: utf-8 -*-
"""Adapters: one function per source, each writes canonical tables and returns True when it did.

To add a source: write adapt_<name>() in a module here, register it below, and add its
SOURCES entry in sources.py. Order matters where an adapter reads another's output:
geography reads AIGE county names written by aioe; the patent layer runs aipd -> patentsview ->
pregrant -> inventions -> firms (DISCERN, the name match, citations, the firm panel) -> patent_tasks.
"""
from .ai import adapt_aioe, adapt_dynamic_aioe, adapt_btos
from .politics import adapt_vrscores, adapt_elections, adapt_cspp
from .patents import adapt_aipd, adapt_patentsview, adapt_pregrant, adapt_inventions
from .firms import adapt_firms
from .ipums import adapt_ipums
from .tasks import adapt_patent_tasks
from .geo import adapt_geo, adapt_irs_migration
from .context import adapt_county_context, adapt_telework

ADAPTERS = {
    "aioe": adapt_aioe,
    "dynamic_aioe": adapt_dynamic_aioe,
    "btos": adapt_btos,
    "vrscores": adapt_vrscores,
    "elections": adapt_elections,
    "cspp": adapt_cspp,
    "geography": adapt_geo,
    "irs_migration": adapt_irs_migration,
    "aipd": adapt_aipd,
    "patentsview": adapt_patentsview,
    "pregrant": adapt_pregrant,
    "inventions": adapt_inventions,
    "firms": adapt_firms,
    "ipums": adapt_ipums,
    "patent_tasks": adapt_patent_tasks,
    "county_context": adapt_county_context,
    "telework": adapt_telework,
}
# The patent layer's adapters, in order (the notebook's patent step runs just these).
PATENT_LAYER = ["aipd", "patentsview", "pregrant", "inventions", "firms"]
