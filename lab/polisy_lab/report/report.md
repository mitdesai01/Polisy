<div class="summary" markdown="1">
#### In brief

- POLISY's first run linked workforce partisanship (VRscores) to ten AI-exposure measures, IRS county migration and the Correlates of State Policy, and graded 28 findings. Checked against the 2024–2026 literature and put through three stress tests, **none of its headline findings is new in the form it was first reported**. Most replicate documented patterns; several are artefacts of how VRscores is built.
- **The "AI exodus" is not about AI.** Households did leave AI-exposed counties, and faster every year, but {{stress-mig.attenuation:.0%}} of the 2020–22 gradient disappears once density, education, income, housing costs, climate, the 2016 vote and telework are held equal. What grew after 2016 is the partisan and telework gradient of migration ({fig:mig-years}).
- **AI exposure's Democratic lean is composition.** Generative-AI exposure leans Democratic only because of who holds the exposed jobs: once education, pay, telework, gender and race are held equal, it leans neither way. Routine-automation risk is different: it leans Republican net of all of these and of occupation group ({fig:occ-models}).
- **Most of what looks like organisational ideology is occupational structure.** The occupations an industry employs account for {{stress-structure.r2_share:.0%}} of the variance in its partisanship and {{stress-structure.r2_balance:.0%}} of the variance in its political balance ({fig:structure}).
- **The frontier is at the level of the firm**, which the first run never reached. Four seams look open and fit your projects: structural versus elective partisanship in organisations; the political distance between those who decide on AI and those whose work it touches; whether leaders or inventors set the direction of invention when their politics differ; and technology as a force that reshapes the political composition of firms (Section 5).
</div>

## 1. What POLISY is, and where it sits

Your workbook maps 211 items. It is strongest on leader ideology and upper echelons, on workforce ideology and fit, on partisanship in finance and on cross-border knowledge flows. Two projects anchor it: P1 asks whether political incongruence between a CEO and the workforce shapes innovation; P2 asks whether CEO ideology shapes cross-border innovation networks, and deliberately makes its claim about the *direction and structure* of innovation rather than its volume, because the evidence on volume is mixed [@kiss2026; @fehder2024].

POLISY's first run worked one level up from that seam. Its units were 825 occupations, 246 industries, 359 metro areas, 51 states and 3,130 counties. It linked VRscores [@kagan2026] to AI exposure from @felten2021 and DAIOE 2010–2024 [@daioe2026], to comparison measures from @eloundou2024, @webb2020 and @frey2017, to IRS county flows from 2012–13 to 2021–22, and to state policy. It never reached the firm: the public VRscores employer file has no identifiers, DIPI [@mannor2025] and Compustat sit in the POLISY_DA pipeline but not in the lab, and patents were deferred.

That has two consequences. First, the first run speaks mainly to the political economy of AI, a literature in economics and political science, rather than to politics inside organisations. Second, your workbook holds almost none of that literature: no AI-exposure economics, no politics of automation, no recent work on AI and partisanship, and not the two 2025–26 papers closest to P1 [@frake2026; @amr2025]. Appendix B lists what to add. {fig:seam} places the first run's findings and the proposed seams on one map.

<!-- figure: seam -->

## 2. What the first run found, and what is new

{tab:audit} sets every finding against the closest published or working-paper evidence, checked in September 2026. The verdicts are blunt on purpose. A pattern the literature already documents is *established*; one that the stress tests explain by who holds the jobs or where they live is *composition*; one produced by how the data were built is an *artefact*.

<!-- table: audit -->

The balance is clear. Only a handful of findings extend a conversation; the rest replicate documented patterns, dissolve into composition, describe, or are artefacts. About a quarter are artefacts of VRscores: each worker's party is fixed at the November 2024 voter file, so every "drift" is cohort replacement, and in states where party is inferred rather than registered the drift is larger again [@kagan2026]. Your own VRscores report found the same.

This is not a failure. A lab that rediscovers known patterns from new data has validated its plumbing. But it means POLISY's contribution has to come from what it can link next, not from what it found first.

## 3. Three stress tests

Each test takes a headline finding, names the first rival explanation a referee would raise, and re-estimates the finding with that explanation held equal. The tests run inside the lab (`analyses/stress.py`) and re-grade the findings they test, so the interactive lab and the tables above already reflect them.

### 3.1 AI exposure and county migration

The claim was that households are leaving AI-exposed counties, faster every year and within the same state: one SD more AI exposure (AIGE) meant −0.16 points of households a year in 2013–16 and −0.86 in 2020–22. The rivals are well known. Remote work emptied dense cores into suburbs and smaller places [@ramani2021]; high earners left large expensive cities [@eig2023]; movers went to Republican places [@mckee2025; @gimpel2025]. AIGE is high exactly where density, telework and Democratic votes are high.

<!-- figure: mig-models -->

With state-by-year fixed effects only, the 2020–22 coefficient is {{stress-mig.coef_base:+.2f}} (t = {{stress-mig.t_base:.1f}}). Adding density, education, income, housing costs, January temperature, the 2016 Republican vote share and the share of the county's jobs that can be done at home [@dingel2020] brings it to {{stress-mig.coef_full:+.2f}} (t = {{stress-mig.t_full:.1f}}). {tab:mig-full} shows what does the work: the 2016 vote and telework.

<!-- table: mig-full -->

The year-by-year estimates in {fig:mig-years} tell the same story over time. The controlled AI coefficient is small and flat from 2013 to 2022. What grows is the partisan gradient: the coefficient on the 2016 vote rises from {{stress-mig.rep16_2013_16:+.2f}} in 2013–16 to {{stress-mig.rep16_2020_22:+.2f}} in 2020–22, net of every other control.

<!-- figure: mig-years -->

**Verdict.** The "AI exodus" should be dropped as a finding. The partisan gradient that survives is interesting, but it is a crowded political-geography question, and the IRS files cannot see movers' party, occupation or employer. They cannot tell political sorting apart from taxes, housing supply or pandemic-era policy.

### 3.2 The partisan face of AI exposure

Across occupations, the correlation between exposure and the Republican share of a workforce ran from −0.18 for generative-AI exposure (DAIOE) to +0.23 for Webb's AI-patent measure. The rival explanation is composition. Generative-AI exposure falls on educated, disproportionately female, teleworkable occupations [@eloundou2024; @gmyrek2023], and each of those traits leans Democratic.

<!-- figure: occ-models -->

The test adds telework, then gender and race shares, then occupation-group fixed effects. Generative-AI exposure leans Democratic on its own ({{stress-occ.genai_raw:+.1f}} points per SD, t = {{stress-occ.genai_raw_t:.1f}}). The lean disappears once gender and race are held equal ({{stress-occ.genai_demog:+.1f}}) and stays near zero with occupation groups ({{stress-occ.genai_full:+.1f}}). Computerisation risk goes the other way and strengthens with controls, to {{stress-occ.comp_full:+.1f}} points per SD (t = {{stress-occ.comp_full_t:.1f}}). {tab:occ-pairs} puts the two waves in one model.

<!-- table: occ-pairs -->

Three things follow.

1. **This extends a known result rather than overturning one.** @bloom2026 find that the partisan gap in AI *use* disappears once education, occupation and industry are held equal, and @muro2026 map exposure onto Democratic counties. The stress test moves the argument from use to exposure, and from surveys and county votes to voter-file partisanship.
2. **The two waves are not symmetric.** Automation risk keeps a Republican lean among otherwise similar occupations. That fits the politics of automation: routine workers facing status decline move right [@kurer2020; @anelli2021; @frey2018; @gallego2022]. Generative AI's partisan face, by contrast, is carried entirely by who holds the jobs. A generative-AI backlash therefore need not follow the partisan script of the automation backlash. It is more likely to run through professional, gender and status groups, and through organisations, than through a partisan realignment.
3. **Exposure measures are not politically neutral.** Felten, Raj & Seamans's AIOE turns from a slight Democratic lean to a clear Republican one once composition is held equal. The choice of measure decides whether AI's exposed workforce looks blue or red. A related selection problem affects usage-based measures [@yin2026]. Any study that uses exposure to explain political outcomes [@grant2026; @antoniades2025] should report more than one measure.

**Caveats.** Occupation partisanship is national, so occupations concentrated in Republican regions look Republican for that reason alone. Demographic shares cover about 300 occupations.

### 3.3 How much of workforce partisanship is structural

The first run predicted each industry's partisanship from the occupations it employs, using national occupation partisanship and the industry's staffing pattern. The stress test extends this to political balance: how evenly a workforce is split, the construct @castiglia2025 links to lower innovation.

<!-- figure: structure -->

Occupations account for {{stress-structure.r2_share:.0%}} of the variance in industry partisanship and {{stress-structure.r2_balance:.0%}} of the variance in balance, across {{stress-structure.n}} industries. The result is consistent with @frake2026, who find that the partisan gap between Democrats' and Republicans' coworkers falls from 11.7 to 2.9 points once geography, industry and occupation are held equal.

The consequence for management research is direct. Organisation-level political constructs are measured as raw aggregates of donations or registrations: organisational ideology [@gupta2017], workforce balance [@castiglia2025], and P1's leader–workforce incongruence. They therefore mix two things. One is the occupational structure the work requires. The other is whatever the organisation attracts, selects and keeps. Only the second is plausibly organisational. This cannot be tested at the industry level, but it can be tested at the firm level. That is Seam 1.

### 3.4 What survives, and why it matters

<div class="callout good" markdown="1">
Three results survive the stress tests and are unusual enough to build on. None is a paper on its own; each is the foundation for one.

1. **The asymmetry between technological waves.** Routine automation leans Republican among otherwise similar occupations; generative AI's partisan lean is carried entirely by who holds the jobs. This predicts that conflict over generative AI will run through professional, gender and status groups inside organisations rather than through a partisan realignment. Seams 2 and 4 test that prediction.
2. **Exposure measures are not politically neutral.** The sign of AI's partisan incidence depends on the measure and on what is held equal. Any study of AI and politics should report more than one measure; POLISY already does.
3. **Organisational ideology is mostly occupational structure.** The field's core constructs mix what the work requires with what the organisation selects. Seam 1 separates them, and P1 needs the separation anyway.
</div>

## 4. What is not new, and why

<div class="callout warn" markdown="1">
**Established, or explained by composition.** Five patterns are already documented or are explained by composition:

- Movers go to Republican states and counties, increasingly after 2019 [@mckee2025; @gimpel2025].
- Large, AI-exposed counties lose high-income households [@eig2023; @ramani2021].
- AI exposure concentrates in Democratic places and among Democratic workers, through education [@muro2026; @bloom2026]. Brookings finds that 62 of the 100 most AI-exposed counties voted Democratic in 2024.
- Across occupations, education pulls Democratic and pay pulls Republican: the "Brahmin left" and "merchant right" [@gethin2022].
- Partisans sort into different employers [@frake2026; @fos2022; @colonnelli2025]. Your VRscores report has the same 8.4% to 8.7% over-exposure.

**Artefacts.** The Democratic drift of employers, industries, metros and states reflects cohort replacement, because party is fixed at 2024, and inferred rather than registered party. Treat any VRscores trend as composition, never as political change.

**Intriguing but fragile.** Large AI and big-tech workforces barely joined the Democratic drift: −1.1 points against −4.1 for other large employers. The comparison covers 34 firms, and voter files miss non-citizen workers, a large share of technology workforces. It is not a finding until it holds on firm-matched data restricted to registration states.
</div>

## 5. The research frontier: four seams

A seam qualifies if it meets four tests:

- it runs from politics through organisations to innovation or technology;
- the literature had not answered it as of September 2026;
- POLISY and the data you hold make it feasible;
- a credible design towards causality exists.

All four seams below are at the level of the firm. Each continues something POLISY found.

### 5.1 Seam 1: Structural and elective partisanship in organisations

Question
:   How much of an organisation's political composition follows from the work it does and where it does it? That includes its lean, its balance, and the distance between leaders and workforce. And does only the remainder shape what the organisation does, such as innovating, taking stands and keeping people? The remainder is what the organisation attracts, selects and retains.

Builds on
:   Organisational political ideology [@gupta2017]; workforce balance and innovation [@castiglia2025]; workplace segregation net of occupation [@frake2026]; ideological skew through attraction, selection and attrition [@amr2025]; ideological misfit and exit [@bermiss2018]; co-partisan hiring [@colonnelli2025]; executive sorting [@fos2022].

What is missing
:   A counterfactual. Organisation-level measures are raw aggregates, and none asks what an organisation's occupations and locations would imply. Frake et al. show that structure removes three quarters of coworker similarity. Management research still treats the raw aggregate as the organisation's ideology, and no study tests which component drives outcomes.

What POLISY adds
:   The machinery for the counterfactual: occupation partisanship, staffing patterns and exposure on one crosswalk. It also adds first evidence that structure explains most of industry partisanship and half of balance ({fig:structure}).

Rival explanations
:   Location: a firm in a Republican county hires Republican workers, which is structural too, but by place. Also founding conditions and founder ideology; unionisation and public ownership; the party-data regime; and who keeps an online profile.

Data and design
:   Firm × occupation × metro headcounts (Revelio positions, the data behind VRscores) give expected partisanship E[p] = Σ s<sub>o,m</sub> p<sub>o,m</sub>. Elective partisanship is p − E[p]. Apply the same split to balance and to CEO–workforce distance. Then re-estimate balance → innovation and P1's incongruence → innovation with both components. If the theory holds, only the elective component predicts innovation and turnover.

Mechanisms
:   Attraction, selection, attrition and co-partisan hiring networks create elective partisanship. Value congruence [@edwards2009] and affective polarisation [@iyengar2019] explain why only that part shapes cooperation, voice and exit. Structural partisanship is a by-product of technology and location.

Towards causality
:   Shocks that change elective composition with structure held fixed: acquisitions, exogenous CEO departures, headquarters relocations [@barber2024]. Shift-share predictions of structural change from national occupation growth. Election periods raise the salience of partisanship without changing composition [@reinwald2026], giving a within-firm test of mechanism.

First paper
:   *Structural and elective partisanship: decomposing the political composition of organisations.* A measurement paper with a reanalysis of balance and incongruence. It becomes P1's measurement backbone. Outlets: Organization Science, Strategic Management Journal, Organizational Research Methods.

### 5.2 Seam 2: Who decides and who is exposed

Question
:   When the leaders who decide how to adopt AI differ politically from the workers whose tasks AI touches, what changes? Is adoption faster or slower, and more often labour-replacing than labour-augmenting? Is it followed by more voice or exit?

Builds on
:   CEO partisanship and AI hiring [@chu2026]; partisanship and AI use at work [@bloom2026]; exposure and support for AI regulation [@grant2026]; CEO ideology and inventiveness [@kiss2026]; employees' reactions to their CEO's politics [@wowak2022].

What is missing
:   The two sides have only been studied apart. @chu2026 look at the CEO: Republican-leaning CEOs devote a smaller share of hiring to AI. @bloom2026 look at individual workers. No study measures the political distance between those who decide and those who are exposed. Section 3.2 shows that exposure is carried by identifiable occupational groups, which makes that distance measurable inside a firm.

What POLISY adds
:   Occupation partisanship and ten exposure measures on one crosswalk. It also adds the finding that exposure's partisan face depends on the measure and on composition, which tells a design which measures to report and what to hold equal.

Rival explanations
:   CEO ideology standing in for risk preference [@christensen2015]; technological opportunity by industry; tech-hub location; workforce partisanship standing in for education and occupation (Seam 1). Also reverse causality: AI-intensive firms hiring Democratic engineers.

Data and design
:   DIPI for leaders, and the VRscores employer panel matched to Compustat. Firm occupation mix × exposure for the exposed. AI adoption from job postings, AI patents, and AI mentions in 10-Ks and earnings calls. Voice and exit from NLRB petitions, WARN notices and Revelio turnover. The design is a triple difference around the release of ChatGPT on 30 November 2022: the workforce's pre-period exposure × leader–exposed distance × post.

Mechanisms
:   Motivated reasoning that discounts costs borne by out-partisans [@iyengar2019]; trust and legitimacy [@edwards2009; @wowak2022]; hiring AI talent through co-partisan networks [@colonnelli2025]; moral framing of automation versus augmentation.

Towards causality
:   Exogenous CEO turnover varies leader politics with the workforce held fixed. The partisan composition of the local CEO labour market can serve as an instrument [@chu2026]. State and city AI employment laws (New York City Local Law 144, 2023; Colorado's AI Act, 2024) shift the cost of adoption. The 2016–2022 period provides a check on pre-trends.

First paper
:   *Who decides, who is exposed: political distance and the adoption of AI.* The AI-era extension of P1. Outlets: Strategic Management Journal, Organization Science, Management Science.

### 5.3 Seam 3: Who directs the direction of invention?

Question
:   When a firm's leaders and its inventors differ politically, whose views set the direction of the firm's invention? And does the direction of AI invention follow politics even though AI carries no party label, through whose work it automates?

Builds on
:   Inventors' party and the direction of invention [@dossi2026; @fehder2024]; political sentiment and patenting [@engelberg2025]; partisan lines in inventor collaboration [@chen2025]; CEO ideology and inventiveness [@kiss2026]; ideological misfit and exit [@bermiss2018]; co-partisan hiring [@colonnelli2025]; the direction of technical change [@acemoglu2020; @autor2024]. P2's positioning already argues for direction over volume.

What is already known
:   @dossi2026 settle the question at the level of the inventor. They link about 95,600 inventors in four closed-primary states to voter files. Democrats are 31% more likely than Republicans to patent green technologies and 35% more likely to patent women's-health technologies; they are 39% less likely to patent weapons. The gaps are not explained by ability or skills, they widened through 2015 and have stayed wide since, and they carry into citations. Asking whether partisan inventors pursue partisan-coded AI (climate AI, health AI, defence AI) would repeat their design on a new technology class.

What is missing
:   Two things their design leaves open. The first is organisations. Adding organisation fixed effects removes 38–42% of the green and weapons gaps, and they treat that share as a robustness check rather than a question. Nobody asks whether leaders' politics steer the firm's portfolio, or how a contest between leaders and inventors over direction is resolved: by reassignment, exit or voice. The second is technologies without a party label. They restrict attention to issues with a clear party position and a clear mapping to patents, and note that other politically relevant technologies are harder to identify. AI is the leading case. It has no stable party position, but it carries partisan weight through incidence, meaning whose work it replaces, which is exactly what POLISY measures (Section 3.2).

What POLISY adds
:   Occupation partisanship and exposure on one crosswalk, which turns any patent mapped to occupations into a measure of whose work it targets. Also VRscores employer composition, DIPI for leaders, and PatentsView adapters written but not yet run. Their data recipe can be replicated: closed-primary voter files for Florida, New Jersey, New York and Pennsylvania, matched to PatentsView on name and city (53% of patents).

Rival explanations
:   Organisational specialisation: when firms specialise, organisation effects absorb technology, as @dossi2026 note. Also customers and procurement, especially defence contracts; location; and reverse selection, where weapons firms attract Republican leaders.

Data and design
:   Firm portfolios from DISCERN, inventor party from the four-state voter files, and leader ideology from DIPI. The core design uses CEO successions with the inventor team held fixed. Does the firm's share of green, weapons and contested-AI patents move toward the new leader's politics? Do misaligned inventors leave or switch domains? For AI, map each patent to the occupations whose tasks it performs [@webb2020; @autor2024] and weight by their partisanship. Do inventors and firms automate out-partisans' work more readily?

Mechanisms
:   Managerial discretion over the R&D portfolio set against bottom-up idea generation; misfit exit; and, for incidence, out-group discounting [@iyengar2019].

Towards causality
:   Stacked difference-in-differences around exogenous CEO departures. Inventors who move between firms whose leaders differ politically. For AI subdomains whose politicisation can be dated, event studies of alignment as the coding emerges: facial recognition after the 2020 moratoria, military AI after the 2026 disputes over defence contracts.

First paper
:   *Who directs the direction? Leader and inventor politics in the firm's technological portfolio.* This is the upper-echelons contribution that @dossi2026 leave open, and a natural home for P1's incongruence argument. Outlets: Strategic Management Journal, Academy of Management Journal, Research Policy. The AI-incidence question is a second, riskier paper.

### 5.4 Seam 4: Technology and the political composition of firms

Question
:   Does adopting automation or AI change who works in a firm, and so its political composition? Does that change feed back into the firm's politics: its public stands, its PAC giving, its lobbying on AI and its internal incongruence?

Builds on
:   Trade shocks and polarisation [@autor2020]; robots and the radical right [@anelli2021; @frey2018]; the declining middle [@kurer2020]; theories of ideological skew [@amr2025]; the political transformation of corporate America [@steel2025]; executive sorting [@fos2022].

What is missing
:   In political science, technology is a shock to voters and regions. In organisation research, it plays no part at all as a driver of political composition. The theory of how organisations become red, blue or purple [@amr2025] runs through founding conditions and attraction, selection and attrition, with no role for the technology of production.

What POLISY adds
:   A flaw of VRscores for measuring political change becomes an asset here. Party is fixed at 2024, so a change in an employer's score is a change in who works there, which is exactly the channel of interest. The analysis should be restricted to registration states, where drift is not an artefact.

Rival explanations
:   Growth and relocation; cohort replacement unrelated to technology; mergers and restructuring; the party-data regime.

Data and design
:   The VRscores employer-year panel, 2012–2024. Occupation flows from Revelio. Adoption timing from first AI postings and first AI patents. FEC PAC data, LobbyView and CEO statements for the firm's politics. The design compares a shift-share prediction of composition change (initial occupation shares × exposure × post) with the actual change.

Mechanisms
:   Occupational substitution: clerical and administrative work, which is disproportionately female and Democratic-leaning, against engineering hires. Also the relocation of work, and attrition of workers who object.

Towards causality
:   An exposure-based shift-share after 2022, with 2016–2022 as a placebo window. Earlier automation waves (robots, software) should shift composition the other way, which gives a sign test.

First paper
:   *Automation and the political composition of the firm.* The most novel of the four, and the longest data build. Outlets: Administrative Science Quarterly, Academy of Management Journal, Organization Science.

Table: The four seams compared (as of September 2026)

| Seam | How new | Closest work | Feasible with data in hand | Main risk |
|---|---|---|---|---|
| 1. Structural vs elective partisanship | Extends segregation research into management constructs | @frake2026; @castiglia2025 | High, once firm occupation mix is added | Read as a methods note unless the reanalysis changes a published result |
| 2. Who decides, who is exposed | Open | @chu2026; @bloom2026 | Medium: needs AI-adoption data | Others extend CEO-level work to the workforce first |
| 3. Who directs the direction | Answered for inventors by @dossi2026; open for leaders and for AI coded by incidence | @dossi2026; @fehder2024; @engelberg2025 | Medium: replicate the four-state voter-file match; DIPI for leaders | Read as Dossi & Morando plus CEOs unless leader turnover identifies the contest |
| 4. Technology → political composition | Open; new theory | @amr2025; @autor2020 | Medium: VRscores plus occupation flows | Short window since 2022 |

**What not to pursue.** Migration and AI is not a POLISY paper: the field is crowded, the exposure measure is a proxy, and the IRS files cannot see who moves. Use migration only as a source of variation. For example, remote-work inflows of Democratic-leaning professionals into Sun Belt metros shift the partisanship of local labour pools, a possible shock to firm composition in Seam 1. Inflows also bring education, so the design must hold it equal.

## 6. Evidence still needed

The first run was limited by what it could link, not by method. The data below move POLISY to the firm level, roughly in order of payoff.

Table: Data that would move POLISY to the level of the firm

| Data | Unlocks | Access | Priority |
|---|---|---|---|
| VRscores employer file matched to Compustat (GVKEY) | Seams 1, 2, 4; P1 | In hand; validated name matching, LobbyView names, or the authors' crosswalk (routes in your VRscores report) | 1 |
| Firm × occupation × location headcounts (Revelio positions) | Seam 1 baseline; Seam 2 exposure; Seam 4 flows | WRDS (check the Groningen licence) or a Revelio academic licence | 1 |
| DIPI: CEO, top-team and board ideology | Seams 2, 3; P1 | In hand | 1 |
| Firm AI adoption: AI job-posting shares; USPTO AI Patent Dataset; AI mentions in 10-Ks (EDGAR full text) and earnings calls | Seams 2, 4 | Postings via WRDS or Lightcast; EDGAR and USPTO free; transcripts via WRDS | 1 |
| PatentsView, with patents mapped to the occupations whose tasks they perform [@webb2020; @autor2024] and firms linked through DISCERN | Seam 3 | Free; compute and validation | 2 |
| Inventor partisanship: closed-primary voter files (Florida, New Jersey, New York, Pennsylvania) matched on name and city, as in @dossi2026; donations (DIME) for other states | Seam 3; P1; P2 | State voter files are public or low-cost; DIME is free | 2 |
| Occupation × metro partisanship | Holds geography equal in Seam 1 and in Section 3.2 | Ask the VRscores authors; or L2 with Revelio | 2 |
| Worker-level party, occupation and AI use (Cooperative Election Study; Gallup Workforce Panel) | Mechanisms for Seam 2 | CES free; Gallup restricted | 3 |
| Voice and exit: NLRB petitions, WARN notices, Glassdoor reviews | Outcomes for Seams 2 and 4 | Free, except Glassdoor | 3 |
| State and city AI employment laws (NCSL database) | Shocks and moderators for Seam 2 | Free | 3 |
| Census BTOS AI use by sector and state | Exposure against actual use | Free | 3 |
| Official county controls (Census Gazetteer, ACS, USDA codes) | Replace the compiled county file used in Section 3.1 | Free | 3 |

## 7. From findings to papers

A sequence that builds each step on the last:

1. **Now: a short research note on the partisan face of AI exposure** (Section 3.2), for Research & Politics, Socius or PNAS Nexus. It needs no new data, and its contribution is the asymmetry between waves and the measure-dependence. Check its overlap with @bloom2026 before writing.
2. **Next six to nine months: Seam 1.** It is the foundation for P1 and for Seams 2 and 4, and it needs one data addition, firm occupation mix.
3. **Then Seam 2 or Seam 4.** Both use the same firm panel; Seam 2 extends P1 into AI, and Seam 4 has the stronger claim to a new theory.
4. **In parallel with P2: Seam 3.** Start by replicating the four-state inventor–voter match of @dossi2026, which P1 and P2 need anyway. Then ask the question they leave open: whether leaders or inventors set the firm's direction. It shares P2's patent infrastructure and its claim about direction.

## 8. Data and methods

**Sources.** VRscores occupation, industry, metro and employer summaries from the VRscores report [@kagan2026]; AIOE, AIIE and AIGE [@felten2021]; DAIOE v1.0.0 and its SOC 2018 comparison panel [@daioe2026], which carries @eloundou2024, @webb2020 and @frey2017; IRS SOI county migration files, 2012–13 to 2021–22; the Correlates of State Policy; telework shares from @dingel2020; county context from a public compilation of ACS 2019, BEA, NOAA and County Business Patterns data [@gambit]; and county presidential returns for 2016–2024 compiled by @mcgovern. No synthetic data were used anywhere.

**Estimation.** All models are weighted least squares, with every continuous regressor z-scored, so coefficients read as effects per standard deviation. Migration models use state-by-year fixed effects with errors clustered by county. Occupation models use HC1 errors and, where stated, occupation-group fixed effects. Link rates for every join are in the interactive lab's data tab.

**Limits.** County controls come from a compiled source; official files should replace them before publication. Telework is measured through each county's sector mix, not its occupations. Occupation partisanship is national. VRscores covers workers with online profiles who are registered to vote.

**Reproducing.** The Colab notebook in the repository runs every step. Figures and tables here are regenerated from `results.json` at every build; the text is not.

## Appendix A. All findings

<!-- table: findings -->

## Appendix B. Literature to add to Gyaanpatrika

These items are not in the workbook and bear directly on the seams above. Each reference was checked online in September 2026; items marked in the reference list still need a detail verified.

Table: Additions to the Literature tab, by stream

| Reference | Stream | Project | Why it matters |
|---|---|---|---|
| @frake2026 | Workplace politics & ideological fit | P1 | Workplace political segregation net of occupation; the benchmark for Seam 1 |
| @amr2025 | Workplace politics & ideological fit | P1 | Theory of how organisations become ideologically skewed; Seam 4 adds technology to it |
| @colonnelli2025 | Workplace politics & ideological fit | P1 | Owners hire co-partisans; causal evidence on sorting |
| @chu2026 | Leader & firm political ideology | P1 | CEO partisanship and AI hiring; closest competitor for Seam 2 |
| @bloom2026 | Leader & firm political ideology | P1 | Partisan gap in AI use is composition; Section 3.2 extends it to exposure |
| @muro2026 | Polarisation & party systems | General | AI exposure mapped on county votes |
| @grant2026 | Polarisation & party systems | General | Occupational AI exposure raises support for AI regulation |
| @haslberger2025 | Polarisation & party systems | General | Experimental exposure to generative AI and policy preferences |
| @antoniades2025 | Polarisation & party systems | General | Electoral effects of local AI adoption |
| @magistro2026 | Political psychology & neuroscience of ideology | Micro leg | Common attitudes toward AI and globalisation |
| @chueri2026 | Polarisation & party systems | General | How parties frame AI and work in 33 parliaments |
| @dossi2026 | Innovation measurement & science of science | P2 | Inventors' party shapes what they invent and cite; the benchmark Seam 3 must go beyond |
| @chen2025 | Innovation search, recombination & networks | P2 | Collaboration between Democratic and Republican inventors fell after 2016 |
| @engelberg2025 | Innovation measurement & science of science | P2 | Political sentiment and patenting; partisans cluster by technology |
| @felten2021 | Innovation measurement & science of science | General | AIOE, AIIE and AIGE; in SMJ, so the exposure measure management readers know |
| @webb2020 | Innovation measurement & science of science | P2 | Patent-based exposure; AI targets high-skill tasks |
| @eloundou2024 | Innovation measurement & science of science | General | Language-model exposure |
| @autor2024 | Innovation search, recombination & networks | P2 | Links patents to the occupations they affect; the incidence measure for Seam 3 |
| @acemoglu2020 | Comparative political economy of innovation | P2 | The direction of AI as a choice |
| @kurer2020 | Polarisation & party systems | General | Routine workers, status decline and the populist right |
| @anelli2021 | Polarisation & party systems | General | Individual robot exposure and radical-right support |
| @gallego2022 | Polarisation & party systems | General | Review: automation, AI and political behaviour |
| @autor2020 | Comparative political economy of innovation | General | Trade shocks and polarisation; the template for Seam 4 |
| @gethin2022 | Polarisation & party systems | General | Education left, income right |
| @dingel2020 | Methods & identification | General | Telework shares, a standard control for AI exposure |
