# POLISY

**Politics, Organizations, Leadership, Strategy & Innovation.** A research lab built as code. It links workforce partisanship (VRscores) to open data on AI exposure, AI adoption, migration, state policy and innovation. It keeps every pattern it finds as a graded finding, with the research question it raises and the data that would settle it, stress-tests the headline findings, and writes a research report and an interactive lab.

Research theme 1: **Political Ideology × AI × Innovation**.

## What is in this repository

| Path | What it is |
|---|---|
| `lab/` | The POLISY lab: the `polisy_lab` package (dataset registry and file discovery, adapters, linked panels, analyses, website generator) |
| `lab/notebooks/POLISY_AI_Innovation_Lab.ipynb` | Runs the lab from start to finish in Google Colab; `polisy_lab_colab.py` is the same code as a script |
| `lab/docs/TECHNICAL_REPORT.md` | How to run it, what each stage does, the datasets and how they link, the methods, what the first run found, how to extend it |
| `POLISY_DA/` | The POLISY data pipeline: `polisy_core.py` (finds and reads every input by name and content) and modules 01-10 |
| `POLISY_Lab.ipynb` | Runs POLISY_DA modules 01-10 in Colab |
| `docs/` | The research report (`index.html`) and the interactive lab (`lab.html`) from the latest run, ready for GitHub Pages |
| `data/README.md` | Every dataset: what it is, where to get it, what the lab does with it |
| `tests/`, `lab/tests/` | Tests for the file finder and for the lab |

## Quick start in Google Colab

1. In Google Drive, create `MyDrive/POLISY/data` and put your downloads there as they came. Zips are fine and names do not matter. `data/README.md` lists the datasets.
2. Put the code in `MyDrive/POLISY`: on GitHub use Code → Download ZIP and upload the zip as it is.
3. Open `lab/notebooks/POLISY_AI_Innovation_Lab.ipynb` in Colab (File → Upload notebook) and run the cells in order. It installs what Colab lacks, downloads the open datasets you do not have yet, and writes everything, including the website, to `MyDrive/POLISY/lab`.

On your own machine:

```bash
pip install -r requirements.txt
```

```python
import os, sys
os.environ["POLISY_LAB_ROOT"] = "/path/to/POLISY/lab"      # where the lab writes
sys.path[:0] = ["POLISY_DA", "lab"]
import polisy_core as pc
from polisy_lab import run_all
pc.CONFIG["SEARCH_DIRS"] = ["/path/to/your/downloads"]
run_all()     # fetch, inventory, profile, adapt, link, analyze, site
```

## The website

`docs/` holds the site built from the latest run:

- `docs/index.html`, **the research report**: a critical assessment of the findings against the 2024-2026 literature, three stress tests, and four research seams at the level of the firm, with numbered figures and tables and a reference list. It is generated from `lab/polisy_lab/report/report.md` (the argument, yours to edit) and `results.json` (every figure, table and key number).
- `docs/lab.html`, **the interactive lab**, the report's appendix: every finding with its grade, a chart explorer, maps of counties, metros and states, the data catalog with the match rate of every join, and the technical report. `docs/polisy_lab_offline.html` is the same lab without internet.

To publish it with GitHub Pages, go to Settings → Pages → Deploy from a branch, and choose `main` and `/docs`. Pages on a private repository needs a paid GitHub plan; on a free plan, make the repository public first. To publish a new run, replace `docs/` with the new `lab/site/` folder.

## What the first run found, and what is new

The first run (25 September 2026) linked the VRscores report, AIOE, DAIOE v1.0.0, IRS county migration 2012-13 to 2021-22 and the Correlates of State Policy. The research report checks every finding against the literature and stress-tests the headline ones (28 September 2026):

- **The "AI exodus" is mostly the partisan and telework geography of migration.** Households did leave AI-exposed counties, but 88% of the 2020-22 gradient disappears once density, education, income, housing costs, climate, the 2016 vote and telework are held equal.
- **AI exposure's Democratic lean is composition; automation risk's Republican lean is not.** Generative-AI exposure leans Democratic only through the education, gender and race of the people in exposed jobs; computerisation risk leans Republican with every control.
- **Most of what looks like organisational ideology is occupational structure.** Occupations explain 72% of industries' partisanship and 54% of their political balance.
- **The rest is mostly established or an artefact.** Movers going to Republican places, high earners leaving large counties, education pulling occupations Democratic, and rising partisan sorting across employers are documented; VRscores "drift" is cohort replacement.

The report argues that the frontier is at the level of the firm, where the first run never went, and sets out four research seams: structural and elective partisanship in organisations; who decides and who is exposed in AI adoption; politics and the direction of AI invention; and technology reshaping the political composition of firms.

## Data

The data files are not in this repository, because of their size and their own licences. `data/README.md` lists each dataset, where to get it and which ones the notebook downloads by itself.

## Tests

```bash
python tests/smoke_test.py                                       # POLISY_DA: finds and reads inputs under messy names
POLISY_TEST_DATA=/path/to/downloads python -m pytest lab/tests -q  # lab: real files only; tests skip what is missing
```

## Sources

- VRscores: Kagan, Frake and Hurst (2026), *Organization Science* 37(2): 444-465; data at https://politicsatwork.org/download-data
- AIOE: Felten, Raj and Seamans (2021), *Strategic Management Journal*; https://github.com/AIOE-Data/AIOE
- DAIOE v1.0.0: Engberg et al. (2026), https://zenodo.org/records/21873968
- IRS SOI migration data: https://www.irs.gov/statistics/soi-tax-stats-migration-data
- Correlates of State Policy (IPPSR, Michigan State University): https://ippsr.msu.edu/public-policy/correlates-state-policy
- DIPI: Mannor and Busenbark (2025), https://www.sciencedirect.com/science/article/abs/pii/S0749597825000317
- Census Business Trends and Outlook Survey: https://www.census.gov/hfp/btos/data_downloads
- PatentsView: https://patentsview.org/download/data-download-tables
