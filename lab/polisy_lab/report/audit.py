# -*- coding: utf-8 -*-
"""The novelty audit: for every finding, how it stands against the literature (checked in September 2026).

verdict   Established   the pattern is documented; POLISY replicates it
          Composition   explained by who or where, once the obvious controls are in (see the stress tests)
          Artefact      most likely produced by how the data were built
          Descriptive   a fact worth knowing; no claim to novelty
          Extension     adds a new angle, measure or test to a known conversation
          Test          a stress test run for this report
          Not run       waiting for data
"""

VERDICTS = {
    "Test": "A stress test run for this report",
    "Extension": "Adds a new angle, measure or test to a known conversation",
    "Established": "The pattern is documented; POLISY replicates it",
    "Composition": "Explained by who or where, once the obvious controls are in",
    "Artefact": "Most likely produced by how the data were built",
    "Descriptive": "A fact worth knowing; no claim to novelty",
    "Not run": "Waiting for data",
}

AUDIT = {
    "stress-mig": ("Test", ["ramani2021", "eig2023"], "Shows that mig-ai-exodus is the partisan and telework geography of migration."),
    "stress-occ": ("Extension", ["bloom2026", "muro2026"], "Moves the composition argument from AI use (surveys) to AI exposure (voter files), and "
                                                          "shows that it holds for generative AI but not for routine automation."),
    "stress-structure": ("Extension", ["frake2026", "castiglia2025", "gupta2017"], "Consistent with segregation net of occupation; new is the "
                                                                                  "consequence for organisation-level ideology and balance measures."),
    "mig-ai-exodus": ("Composition", ["ramani2021", "eig2023"], "AIGE stands for dense, Democratic, telework-intensive counties (stress-mig)."),
    "occ-waves": ("Extension", ["webb2020", "yin2026"], "That exposure measures disagree is known; that their partisan sign depends on the measure "
                                                        "and on composition is a caution for studies of AI and politics."),
    "mig-partisan-state": ("Established", ["mckee2025", "gimpel2025"], "Movers to Republican states, rising after 2019, is well documented."),
    "mig-partisan": ("Established", ["mckee2025", "gimpel2025"], "The county-level version of the same pattern."),
    "occ-ai-education": ("Established", ["muro2026", "bloom2026", "eloundou2024"], "Exposure concentrated among educated, Democratic-leaning workers."),
    "state-environment": ("Composition", ["eig2023"], "Policy liberalism, costs and AI exposure cannot be separated across 51 states."),
    "mig-income": ("Established", ["eig2023"], "High earners leaving large cities is documented in the same IRS data."),
    "occ-education-vs-pay": ("Established", ["gethin2022"], "Education left, income right: the Brahmin left and merchant right, by occupation."),
    "sorting": ("Established", ["frake2026", "fos2022", "colonnelli2025"], "Also in the VRscores report (8.4% to 8.7%)."),
    "ind-ai-partisanship": ("Composition", ["bloom2026"], "Runs through education (r = 0.86 with exposure)."),
    "emp-bigtech": ("Descriptive", [], "Intriguing given the tech industry's rightward turn in 2024, but 34 firms, and voter files miss non-citizen workers."),
    "metro-regime": ("Artefact", ["kagan2026"], "Party is inferred rather than registered in these states; flagged in the VRscores report."),
    "ind-composition": ("Extension", ["frake2026"], "See stress-structure."),
    "occ-two-ais": ("Composition", [], "Disappears with education and demographics."),
    "metro-space": ("Artefact", ["kagan2026"], "The clusters follow states' party-data regimes."),
    "state-aige": ("Artefact", ["kagan2026"], "VRscores covers AI-exposed labour markets more densely."),
    "occ-daioe": ("Descriptive", ["daioe2026"], "A cumulative index rises for everyone; relative standing moves little."),
    "mig-exposure-gap": ("Composition", ["ramani2021"], "Moves from dense cores to suburbs and smaller places."),
    "state-regime": ("Artefact", ["kagan2026"], "As metro-regime, at the state level."),
    "ind-drift": ("Artefact", ["kagan2026"], "Party is fixed at 2024, so drift is cohort replacement."),
    "emp-drift": ("Artefact", ["kagan2026"], "As ind-drift, for employers."),
    "policy-twfe": ("Descriptive", [], "One of 23 pairs passes a 10% false-discovery threshold; underpowered."),
    "mig-network": ("Descriptive", [], "The corridors are well known."),
    "landscape": ("Descriptive", [], "Red and blue state archetypes."),
    "state-coverage": ("Artefact", [], "Multi-state metros credited to one state."),
    "occ-anomalies": ("Descriptive", [], "Residual outliers; several look like ethnic occupational niches (e.g. manicurists)."),
    "emp-artifacts": ("Artefact", [], "Restructured firms."),
    "adoption": ("Not run", [], "Needs the Census BTOS files."),
    "patents": ("Not run", [], "Needs PatentsView (deferred)."),
}
