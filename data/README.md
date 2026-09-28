# Data

The data files are not stored in this repository, because of their size and their own licences. Put your downloads in one folder (in Colab, `MyDrive/POLISY/data`) exactly as they came. Zips do not need unpacking and names do not need changing: every input is found by its name and by what its header contains, including tables inside zips. The notebook downloads the open datasets you do not have yet.

## POLISY lab (Political Ideology × AI × Innovation)

| Dataset | Get it from | Files the lab looks for | Downloaded by the notebook? | Used for |
|---|---|---|---|---|
| VRscores | https://politicsatwork.org/download-data (panels), or the VRscores HTML report | the report (`vrscores_report.html`), or POLISY_DA's panels | no | workforce partisanship by occupation, industry, metro, state, employer |
| AIOE, AIIE, AIGE | https://github.com/AIOE-Data/AIOE | the repository files (`AIOE_DataAppendix.xlsx`, `abilities_2020.dta`, ...) | yes (git clone) | AI exposure of occupations, industries, counties |
| DAIOE v1.0.0 | https://zenodo.org/records/21873968 | `daioe-v1.0.0-scores.zip` (`refresh-2024/daioe_soc2010.*`, `soc2018/daioe_panel_soc2018.dta`) | yes | exposure by year 2010-2024; the comparison of exposure measures |
| IRS SOI migration | https://www.irs.gov/statistics/soi-tax-stats-migration-data | `countyinflowYYYY.csv`, `countyoutflowYYYY.csv`, `stateinflowYYYY.csv`, `stateoutflowYYYY.csv` (any zip or folder) | yes | county and state migration of households and income |
| Correlates of State Policy | https://ippsr.msu.edu/public-policy/correlates-state-policy | the CSPP data file (`cspp_data_*.csv` or `correlates*.csv`); codebook optional | tries the project page | state political and policy environment |
| Census BTOS | https://www.census.gov/hfp/btos/data_downloads | the national, sector and state workbooks | yes | actual AI use by firms (waiting for data in the first run) |
| County context (stress tests) | https://github.com/evangambit/JsonOfCounties (compiled from the Census ACS 2019, BEA, NOAA, County Business Patterns) | `counties.json` | yes | density, education, income, housing costs, climate, industry mix |
| Telework shares (stress tests) | https://github.com/jdingel/DingelNeiman-workathome (Dingel and Neiman 2020) | `occupations_workathome.csv`, `NAICS_workfromhome.csv`, `MSA_workfromhome.csv` | yes | jobs that can be done at home, by occupation, industry and metro |
| County presidential returns 2016-2024, compiled | https://github.com/tonmcg/US_County_Level_Election_Results_08-24 | `2016_US_County_Level_Presidential_Results.csv` (and 2020, 2024) | yes, when POLISY_DA has no MIT file | the 2016 vote in the stress tests; county vote shares |
| PatentsView | https://patentsview.org/download/data-download-tables | `g_patent`, `g_cpc_current`, `g_inventor_disambiguated`, `g_location_disambiguated` (.tsv or .tsv.zip) | only with `patentsview=True` | AI patents, inventors and their moves (deferred) |

The first run used `vrscores_report.html`, the AIOE repository, `daioe-v1.0.0-scores.zip`, `IRS_SOI_County_Migration.zip` (county files 2012-13 to 2021-22) and `cspp_data_2026-09-24_academic_and_policy_addition.zip`.

## POLISY_DA pipeline

Declared in `FILES` in `POLISY_DA/polisy_core.py`; module 01 prints which file each input resolved to.

| Input | Get it from | Downloads as | Downloaded by module 05? |
|---|---|---|---|
| VRscores employer, metro, industry and occupation panels | Harvard Dataverse, VRscores data set (Download all) | `dataverse_files.zip` (one per panel) | no |
| Compustat annual fundamentals | WRDS, Compustat Fundamentals Annual | `Compustat_Final.csv` (WRDS may name it with a random code) | no |
| DIPI organizational leadership file | DIPI open data, Mannor and Busenbark (2025), tiny.cc/politicalideology | `Organizational_Leadership_File.csv` | no |
| County presidential returns | Harvard Dataverse, MIT Election Lab, doi:10.7910/DVN/VOQCHQ | `countypres_2000-2024.csv` | no |
| Census CBSA delineation file, List 1 | census.gov, Metropolitan and Micropolitan Delineation Files | `list1_2023.xlsx` | yes |
| BLS OEWS national, metro and 4-digit industry estimates | bls.gov/oes/tables.htm | `oesm{yy}nat.zip`, `oesm{yy}ma.zip`, `oesm{yy}in4.zip` | no |
| O*NET database, text files | onetcenter.org/database.html | `db_29_0_text.zip` | yes |
| AIOE scores | github.com/AIOE-Data/AIOE | `AIOE_DataAppendix.xlsx` | yes |

The lab reads two of these through POLISY_DA when they are present: the county presidential returns (the partisan direction of county-to-county moves) and the CBSA delineation file (links metros to CBSAs for metro-level AI exposure).

## If the wrong file is picked

- Lab inputs: set `pc.CONFIG["LAB_<SOURCE>_<ROLE>"]` to the path, for example `pc.CONFIG["LAB_CSPP_DATA"]`. The inventory table names every source and role.
- POLISY_DA inputs: set `pc.CONFIG["<KEY>"]`, for example `pc.CONFIG["DIPI"]` or `pc.CONFIG["CBSA_REFERENCE"]`.
