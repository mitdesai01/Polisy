# POLISY_DA: the POLISY data pipeline

- This folder: `polisy_core.py` and modules `01`–`10`. Zip its files as `POLISY_DA.zip` for Colab.
- `../POLISY_Lab.ipynb`: runs the pipeline in Colab. It loads the code only from `POLISY_DA.zip` and runs module 05 (downloads) before 01–10.
- `../tests/smoke_test.py`: builds small fake downloads with realistic names ("(1)" copies, renamed or unzipped zips, a WRDS random name, a `.tab` county file) and runs every module on them. Run it with `python tests/smoke_test.py`.

## How input files are found

Every input is declared once, in `FILES` in `polisy_core.py`: what it is, the name it downloads as, the looser names that are accepted, and what has to be inside it. `locate(key)` and `find(key)` look for it in this order:

1. `CONFIG[key]`, if that path exists and its contents fit;
2. the download name, in `data/raw` or any `CONFIG["SEARCH_DIRS"]` folder (default: `/content`, `/content/drive/MyDrive`, `~/Downloads`, each one subfolder deep);
3. a similar name: "(1)" copies, "Copy of …", spaces or dashes instead of underscores, other capitals, another extension;
4. the contents alone: zip members (`employer_panel_year_*`, …) or header columns (`gvkey` + `fyear` + `conm`, …).

Module 01 (or `show_files()`) prints which file each input resolved to and how it was found. Inputs it cannot find are listed with their download name and source. When two different files fit equally well, it reports `AMBIGUOUS`, except for inputs that may come as several files (the ACS metro tables, one or many years per file), which `find_all(key)` returns in full and which are all read.

Metros: VRscores and each ACS year use the metros of their own delineation, so `metro_matcher` puts them on the codes of Census List 1 (by code where it still exists, then by city and state, then through List 2's principal cities), and `load_acs_metro` adds up older areas that are one CBSA today. Module 04's `keys/cw_msa_cbsa.csv` and module 06's `output/tables/06_acs_cbsa_map.csv` say which rule matched each metro.

The checklist of file names to double-check at each step: https://claude.ai/code/artifact/1aa6867a-4183-4491-a34a-c7f41a86be48

The POLISY lab (`../lab/`) builds on this pipeline; see the repository README.
