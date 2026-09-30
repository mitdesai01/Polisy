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
| PatentsView, granted patents | https://patentsview.org/download/data-download-tables | `g_patent`, `g_application`, `g_cpc_current`, `g_inventor_disambiguated`, `g_location_disambiguated`, `g_assignee_disambiguated`, `g_cpc_title`; for task matching `g_patent_abstract`; for search depth and scope `g_us_patent_citation` (.tsv or .tsv.zip, in `data/patentsview`) | yes, in step 4b (your own copies are skipped) | patents by filing year, AI, climate and weapons classes, inventors and places, owners |
| PatentsView, published applications | https://patentsview.org/download/pg-download-tables | `pg_published_application`, `pg_cpc_current`, `pg_inventor_disambiguated`, `pg_location_disambiguated`, `pg_assignee_disambiguated`, `pg_granted_pgpubs_crosswalk`; for task matching `pg_published_application_abstract` | yes, in step 4b | invention since about 2021 that is not granted yet (the generative-AI wave) |
| USPTO AI Patent Dataset (AIPD) | https://www.uspto.gov/ip-policy/economic-research/research-datasets/artificial-intelligence-patent-dataset | the predictions file, `ai_model_predictions` (.csv, .tsv, .dta or zipped), in `data/aipd` | tries the USPTO page in step 4b; otherwise by hand | the AI label of patents and published applications (replaces the CPC rules) |
| DISCERN 2.0 | your copy (Arora, Belenzon and Sheer; used in the thesis) | every file of the download in `data/discern` (any names; each is recognized by its columns: the patent-level file, the permno-gvkey file, the firm panel, the name list) | no | which Compustat firm owns each patent, 1980-2021 |
| IPUMS USA, ACS 2019-2023 (5-year) | https://usa.ipums.org (free registration) | the extract's data file (`usa_000NN.csv.gz`, or `.dat.gz` with its `.xml` codebook), in `data/ipums` | yes, in step 4c, with your IPUMS API key | age, gender, race, education, sector, wages, work from home and location of every occupation and industry |
| O*NET task statements and ratings | https://www.onetcenter.org/database.html | `Task Statements.txt`, `Task Ratings.txt` (inside `db_29_0_text.zip`, which POLISY_DA also uses) | yes | the tasks AI patents are matched to (step 6c) |

`lab/docs/DATA_INFRASTRUCTURE.md` explains how these sources are linked and what is built from them.

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
| Census CBSA delineation file, List 2 (principal cities) | census.gov, Metropolitan and Micropolitan Delineation Files | `list2_2023.xlsx` | yes |
| ACS 1-year metro tables (population, median household income, employment, bachelor's share, median age) | Census API (module 05), or any table you saved: one row per metro and year with `NAME`, the CBSA code, `year` and `B01003_001E`, `B19013_001E`, `B23025_004E`, `B15003_022E`, `B15003_001E`, `B01002_001E` | `acs1_<year>.json` from module 05, or for example `ACS_MSA_2012_2024.csv`; several files are all read | yes, for the years no file covers (the Census API may ask for a key: `pc.CONFIG["CENSUS_API_KEY"]`) |
| BLS OEWS national, metro and 4-digit industry estimates | bls.gov/oes/tables.htm | `oesm{yy}nat.zip`, `oesm{yy}ma.zip`, `oesm{yy}in4.zip` | no |
| O*NET database, text files | onetcenter.org/database.html | `db_29_0_text.zip` | yes |
| AIOE scores | github.com/AIOE-Data/AIOE | `AIOE_DataAppendix.xlsx` | yes |

The lab reads two of these through POLISY_DA when they are present: the county presidential returns (the partisan direction of county-to-county moves) and the CBSA delineation file (links metros to CBSAs for metro-level AI exposure).

Metros change between delineations. VRscores names its metros as in an older delineation, and each ACS year uses the metros of its time (2012 the 2009 metros: Los Angeles is 31100 there and 31080 today). Modules 04 and 06 put both on today's CBSA codes, by code where it still exists and otherwise by city and state, using List 2's principal cities for metros whose city is no longer in any title (Anderson, IN is part of Indianapolis today). ACS areas that are one CBSA today are added up; the few small ones absorbed into a bigger metro whose city is no longer a principal city (Madera, CA; Ocean City, NJ) are listed in the log and left out. `output/tables/06_acs_cbsa_map.csv` shows where every ACS area-year went.

## If the wrong file is picked

- Lab inputs: set `pc.CONFIG["LAB_<SOURCE>_<ROLE>"]` to the path, for example `pc.CONFIG["LAB_CSPP_DATA"]`. The inventory table names every source and role.
- POLISY_DA inputs: set `pc.CONFIG["<KEY>"]`, for example `pc.CONFIG["DIPI"]` or `pc.CONFIG["CBSA_REFERENCE"]`.
