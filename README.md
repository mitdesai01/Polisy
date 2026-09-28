# POLISY

**Politics, Organizations, Leadership, Strategy & Innovation.** A research lab built as code. It links workforce partisanship (VRscores) to open data on AI exposure, AI adoption, migration, state policy and innovation. It keeps every pattern it finds as a graded finding, with the research question it raises and the data that would settle it, and it writes an interactive website of the results.

Research theme 1: **Political Ideology × AI × Innovation**.

## What is in this repository

| Path | What it is |
|---|---|
| `lab/` | The POLISY lab: the `polisy_lab` package (dataset registry and file discovery, adapters, linked panels, analyses, website generator) |
| `lab/notebooks/POLISY_AI_Innovation_Lab.ipynb` | Runs the lab from start to finish in Google Colab; `polisy_lab_colab.py` is the same code as a script |
| `lab/docs/TECHNICAL_REPORT.md` | How to run it, what each stage does, the datasets and how they link, the methods, what the first run found, how to extend it |
| `POLISY_DA/` | The POLISY data pipeline: `polisy_core.py` (finds and reads every input by name and content) and modules 01-10 |
| `POLISY_Lab.ipynb` | Runs POLISY_DA modules 01-10 in Colab |
| `docs/` | The website built by the first run, ready for GitHub Pages |
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

`docs/` holds the site from the first run: a findings board with an evidence map, a chart explorer, maps of counties, metros and states, the data catalog with the match rate of every join, and the technical report. `docs/polisy_lab_offline.html` opens without internet.

To publish it with GitHub Pages, go to Settings → Pages → Deploy from a branch, and choose `main` and `/docs`. Pages on a private repository needs a paid GitHub plan; on a free plan, make the repository public first. To publish a new run, replace `docs/` with the new `lab/site/` folder.

## What the first run found

The run on 25 September 2026 used the VRscores report, AIOE, DAIOE v1.0.0, IRS county migration 2012-13 to 2021-22 and the Correlates of State Policy. Highlights:

- **Households are leaving AI-exposed counties, faster every year (robust).** The household-weighted correlation between a county's AI exposure and its net domestic migration went from -0.19 (2012-13) to -0.51 (2020-21). Within the same state, one standard deviation more exposure meant -0.86 points of households a year in 2020-22 (t = -13.6).
- **AI exposure measures disagree about who is exposed (robust).** Across 825 occupations, the correlation with the Republican share of workers runs from -0.18 (DAIOE generative AI) to +0.23 (Webb's AI patent score). With education and wage held equal, computerisation risk leans Republican and generative-AI exposure Democratic.
- **Interstate movers go to more Republican states, and more so over time (robust).** The gap grows from +0.8 points (2012-13) to +2.5 (2020-21), with the political map held at the 2016 election.
- **AI-exposed counties lose richer households than they gain (robust).**

All 28 findings, with their grades, research questions and the data that would settle them, are in the website and in `lab/docs/TECHNICAL_REPORT.md`.

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
