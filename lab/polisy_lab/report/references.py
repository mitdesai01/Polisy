# -*- coding: utf-8 -*-
"""The report's references. Each entry: cite (as it appears in the text), year, the full reference, a link,
and `check` when a detail was not verified against the publication itself (shown in the reference list)."""

REFS = {
    # ---------------------------------------------------------------- workplace politics and organisations
    "frake2026": dict(cite="Frake, Hurst & Kagan", year="2026", link="https://www.nature.com/articles/s41562-026-02501-9",
                      ref="Frake, J., Hurst, R., & Kagan, M. (2026). Political segregation in the US workplace. <i>Nature Human Behaviour</i>."),
    "kagan2026": dict(cite="Kagan, Frake & Hurst", year="2026", link="https://ideas.repec.org/a/inm/ororsc/v37y2026i2p444-465.html",
                      ref="Kagan, M., Frake, J., & Hurst, R. (2026). VRscores: A new measure and data set of workforce politics using voter "
                          "registrations. <i>Organization Science</i>, 37(2), 444&ndash;465."),
    "colonnelli2025": dict(cite="Colonnelli, Pinho Neto & Teso", year="2025", link="https://www.aeaweb.org/articles?id=10.1257/aer.20240151",
                           ref="Colonnelli, E., Pinho Neto, V., & Teso, E. (2025). Politics at work. <i>American Economic Review</i>, 115(10), 3367&ndash;3414."),
    "fos2022": dict(cite="Fos, Kempf & Tsoutsoura", year="2022", link="https://www.nber.org/papers/w30183",
                    ref="Fos, V., Kempf, E., & Tsoutsoura, M. (2022). The political polarization of corporate America (NBER Working Paper 30183; revised 2026)."),
    "castiglia2025": dict(cite="Castiglia", year="2025", link="https://journals.sagepub.com/doi/10.1177/01492063251389882",
                          ref="Castiglia, L. (2025). Striking a political balance? Political polarization and firm innovation. <i>Journal of Management</i>."),
    "gupta2017": dict(cite="Gupta, Briscoe & Hambrick", year="2017", link="https://doi.org/10.1002/smj.2550",
                      ref="Gupta, A., Briscoe, F., & Hambrick, D. C. (2017). Red, blue, and purple firms: Organizational political ideology and "
                          "corporate social responsibility. <i>Strategic Management Journal</i>, 38(5), 1018&ndash;1040."),
    "amr2025": dict(cite="<i>Red, blue, and purple employee populations</i>", year="2025", link="https://doi.org/10.5465/amr.2025.0229", check="authors not verified",
                    ref="The origins and evolution of red, blue, and purple employee populations: A theory of how organizations become ideologically "
                        "skewed (2025). <i>Academy of Management Review</i>."),
    "busenbark2025": dict(cite="Busenbark et al.", year="2025", link="https://www.sciencedirect.com/science/article/abs/pii/S0749597825000305",
                          ref="Busenbark, J. R., et al. (2025). Politics, ideology, and partisanship in the workplace: A perspective on the literature "
                              "and a call for submissions. <i>Organizational Behavior and Human Decision Processes</i>."),
    "mannor2025": dict(cite="Mannor & Busenbark", year="2025", link="https://ideas.repec.org/a/eee/jobhdp/v188y2025ics0749597825000317.html",
                       ref="Mannor, M. J., & Busenbark, J. R. (2025). A donation-based indicator of political ideology (DIPI): An open dataset for "
                           "studying the political ideologies of employees, top management teams, CEOs, boards, and industries. "
                           "<i>Organizational Behavior and Human Decision Processes</i>, 188."),
    "bermiss2018": dict(cite="Bermiss & McDonald", year="2018", link="https://journals.aom.org/doi/10.5465/amj.2016.0817",
                        ref="Bermiss, Y. S., & McDonald, R. (2018). Ideological misfit? Political affiliation and employee departure in the "
                            "private-equity industry. <i>Academy of Management Journal</i>, 61(6), 2182&ndash;2209."),
    "wowak2022": dict(cite="Wowak, Busenbark & Hambrick", year="2022",
                      ref="Wowak, A. J., Busenbark, J. R., & Hambrick, D. C. (2022). How do employees react when their CEO speaks out? Intra- and "
                          "extra-firm implications of CEO sociopolitical activism. <i>Administrative Science Quarterly</i>, 67(2), 553&ndash;593."),
    "swigart2020": dict(cite="Swigart et al.", year="2020", link="https://journals.sagepub.com/doi/10.1177/0149206320909419",
                        ref="Swigart, K. L., Anantharaman, A., Williamson, J. A., & Grandey, A. A. (2020). Working while liberal/conservative: A review "
                            "of political ideology in organizations. <i>Journal of Management</i>, 46(6), 1063&ndash;1091."),
    "edwards2009": dict(cite="Edwards & Cable", year="2009", link="https://doi.org/10.1037/a0014891",
                        ref="Edwards, J. R., & Cable, D. M. (2009). The value of value congruence. <i>Journal of Applied Psychology</i>, 94(3), 654&ndash;677."),
    "reinwald2026": dict(cite="Reinwald et al.", year="2026",
                         ref="Reinwald, M., Kanitz, R., Bamberger, P., Backmann, J., & Hoegl, M. (2026). The elephant and donkey in the room: "
                             "Time-varying effects of political dissimilarity on social interactions at work during US elections. <i>Organization Science</i>."),
    "barber2024": dict(cite="Barber & Blake", year="2024", link="https://sms.onlinelibrary.wiley.com/doi/full/10.1002/smj.3572",
                       ref="Barber, B., IV, & Blake, D. J. (2024). My kind of people: Political polarization, ideology, and firm location. "
                           "<i>Strategic Management Journal</i>, 45, 849&ndash;874."),
    "steel2025": dict(cite="Steel", year="2025", ref="Steel, R. S. (2025). The political transformation of corporate America, 2001&ndash;2022. "
                                                     "<i>American Political Science Review</i>."),
    "christensen2015": dict(cite="Christensen et al.", year="2015",
                            ref="Christensen, D. M., Dhaliwal, D. S., Boivie, S., & Graffin, S. D. (2015). Top management conservatism and corporate "
                                "risk strategies: Evidence from managers' personal political orientation and corporate tax avoidance. "
                                "<i>Strategic Management Journal</i>, 36(12), 1918&ndash;1938."),
    "iyengar2019": dict(cite="Iyengar et al.", year="2019", link="https://doi.org/10.1146/annurev-polisci-051117-073034",
                        ref="Iyengar, S., Lelkes, Y., Levendusky, M., Malhotra, N., & Westwood, S. J. (2019). The origins and consequences of "
                            "affective polarization in the United States. <i>Annual Review of Political Science</i>, 22, 129&ndash;146."),
    # ---------------------------------------------------------------- leaders, politics and innovation
    "chu2026": dict(cite="Chu, Li & Zhu", year="2026", link="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6427178",
                    ref="Chu, Y., Li, A., & Zhu, R. (2026). Politically coded: CEO partisanship and firm AI adoption (SSRN Working Paper 6427178)."),
    "kiss2026": dict(cite="Kiss et al.", year="2026",
                     ref="Kiss, A. N., Yu, Q., Neville, F., & Ward, A. (2026). Breaking through? The divergent consequences of CEO political ideology "
                         "on firm inventiveness. <i>Journal of Management</i>, 52(3), 1010&ndash;1037."),
    "fehder2024": dict(cite="Fehder et al.", year="2024", link="https://doi.org/10.1016/j.respol.2024.105034",
                       ref="Fehder, D. C., Teodoridis, F., Raffiee, J., & Lu, J. (2024). The partisanship of American inventors. "
                           "<i>Research Policy</i>, 53(7), 105034."),
    "engelberg2025": dict(cite="Engelberg et al.", year="forthcoming", link="https://www.nber.org/papers/w31619",
                          ref="Engelberg, J., Lu, R., Mullins, W., & Townsend, R. (forthcoming). Political sentiment and innovation: Evidence from "
                              "patenters. <i>Review of Financial Studies</i> (NBER Working Paper 31619)."),
    "kempf2026": dict(cite="Kempf, Luo & Tsoutsoura", year="2026",
                      ref="Kempf, E., Luo, M., & Tsoutsoura, M. (2026). CEO ideology and global trade (Harvard Business School Working Paper 25-050)."),
    # ---------------------------------------------------------------- AI exposure and its politics
    "bloom2026": dict(cite="Bloom & Makridis", year="2026", link="https://www.nber.org/papers/w34813",
                      ref="Bloom, N., & Makridis, C. (2026). The politics of AI (NBER Working Paper 34813)."),
    "muro2026": dict(cite="Muro et al.", year="2026", link="https://www.brookings.edu/articles/ai-political-geography-worker-exposure/",
                     check="author list not verified",
                     ref="Muro, M., et al. (2026). The political geography of AI exposure. Brookings Institution."),
    "grant2026": dict(cite="Grant, Green & Evans", year="2026", link="https://www.tandfonline.com/doi/full/10.1080/13501763.2026.2710714",
                      ref="Grant, Z., Green, J., & Evans, G. (2026). New tech, new threat? Occupational exposure to artificial intelligence "
                          "increases support for AI regulation. <i>Journal of European Public Policy</i>."),
    "haslberger2025": dict(cite="Haslberger, Gingrich & Bhatia", year="2025", link="https://www.tandfonline.com/doi/full/10.1080/13501763.2025.2554903",
                           ref="Haslberger, M., Gingrich, J., & Bhatia, J. (2025). Rage against the machine? Generative AI exposure, subjective risk, "
                               "and policy preferences. <i>Journal of European Public Policy</i>."),
    "antoniades2025": dict(cite="Antoniades et al.", year="2025", link="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5975634",
                           ref="Antoniades, A., Balcazar, C. F., Chatzikonstantinou, M., & Kern, A. (2025). The electoral consequences of AI "
                               "adoption: Evidence from US elections (SSRN Working Paper 5975634)."),
    "magistro2026": dict(cite="Magistro et al.", year="2026", link="https://onlinelibrary.wiley.com/doi/10.1111/ajps.12959",
                         ref="Magistro, B., et al. (2026). Attitudes toward artificial intelligence (AI) and globalization: Common microfoundations "
                             "and political implications. <i>American Journal of Political Science</i>."),
    "chueri2026": dict(cite="Chueri & T&ouml;rnberg", year="2026", link="https://arxiv.org/abs/2609.02296",
                       ref="Chueri, J., & T&ouml;rnberg, P. (2026). Meeting the coming wave: The emerging politics of AI and work across 33 parliaments "
                           "(arXiv:2609.02296)."),
    "yin2026": dict(cite="Yin & Ogut", year="2026", link="https://arxiv.org/abs/2605.21743",
                    ref="Yin, M., & Ogut, B. (2026). Who uses AI? Platforms, workforce, and AI exposure (arXiv:2605.21743)."),
    "gallego2022": dict(cite="Gallego & Kurer", year="2022", link="https://doi.org/10.1146/annurev-polisci-051120-104535",
                        ref="Gallego, A., & Kurer, T. (2022). Automation, digitalization, and artificial intelligence in the workplace: Implications "
                            "for political behavior. <i>Annual Review of Political Science</i>, 25, 463&ndash;484."),
    "kurer2020": dict(cite="Kurer", year="2020", link="https://doi.org/10.1177/0010414020912283",
                      ref="Kurer, T. (2020). The declining middle: Occupational change, social status, and the populist right. "
                          "<i>Comparative Political Studies</i>, 53(10&ndash;11), 1798&ndash;1835."),
    "anelli2021": dict(cite="Anelli, Colantone & Stanig", year="2021", link="https://doi.org/10.1073/pnas.2111611118",
                       ref="Anelli, M., Colantone, I., & Stanig, P. (2021). Individual vulnerability to industrial robot adoption increases support "
                           "for the radical right. <i>Proceedings of the National Academy of Sciences</i>, 118(47), e2111611118."),
    "frey2018": dict(cite="Frey, Berger & Chen", year="2018", link="https://doi.org/10.1093/oxrep/gry007",
                     ref="Frey, C. B., Berger, T., & Chen, C. (2018). Political machinery: Did robots swing the 2016 US presidential election? "
                         "<i>Oxford Review of Economic Policy</i>, 34(3), 418&ndash;442."),
    "autor2020": dict(cite="Autor et al.", year="2020", link="https://doi.org/10.1257/aer.20170011",
                      ref="Autor, D., Dorn, D., Hanson, G., & Majlesi, K. (2020). Importing political polarization? The electoral consequences of "
                          "rising trade exposure. <i>American Economic Review</i>, 110(10), 3139&ndash;3183."),
    "gethin2022": dict(cite="Gethin, Mart&iacute;nez-Toledano & Piketty", year="2022", link="https://doi.org/10.1093/qje/qjab036",
                       ref="Gethin, A., Mart&iacute;nez-Toledano, C., & Piketty, T. (2022). Brahmin left versus merchant right: Changing political "
                           "cleavages in 21 Western democracies, 1948&ndash;2020. <i>Quarterly Journal of Economics</i>, 137(1), 1&ndash;48."),
    "gmyrek2023": dict(cite="Gmyrek, Berg & Bescond", year="2023",
                       ref="Gmyrek, P., Berg, J., & Bescond, D. (2023). Generative AI and jobs: A global analysis of potential effects on job "
                           "quantity and quality (ILO Working Paper 96). International Labour Organization."),
    # ---------------------------------------------------------------- exposure measures and the direction of technology
    "felten2021": dict(cite="Felten, Raj & Seamans", year="2021", link="https://doi.org/10.1002/smj.3286",
                       ref="Felten, E., Raj, M., & Seamans, R. (2021). Occupational, industry, and geographic exposure to artificial intelligence: "
                           "A novel dataset and its potential uses. <i>Strategic Management Journal</i>, 42(12), 2195&ndash;2217."),
    "webb2020": dict(cite="Webb", year="2020", link="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3482150",
                     ref="Webb, M. (2020). The impact of artificial intelligence on the labor market (SSRN Working Paper 3482150)."),
    "eloundou2024": dict(cite="Eloundou et al.", year="2024", link="https://doi.org/10.1126/science.adj0998",
                         ref="Eloundou, T., Manning, S., Mishkin, P., & Rock, D. (2024). GPTs are GPTs: Labor market impact potential of LLMs. "
                             "<i>Science</i>, 384(6702), 1306&ndash;1308."),
    "frey2017": dict(cite="Frey & Osborne", year="2017", link="https://doi.org/10.1016/j.techfore.2016.08.019",
                     ref="Frey, C. B., & Osborne, M. A. (2017). The future of employment: How susceptible are jobs to computerisation? "
                         "<i>Technological Forecasting and Social Change</i>, 114, 254&ndash;280."),
    "daioe2026": dict(cite="Engberg et al.", year="2026", link="https://zenodo.org/records/21873968", check="initials not checked",
                      ref="Engberg, G&ouml;rg, Hellsten, Javed, Lodefalk, L&auml;ngkvist, Monteiro, Kyvik Nord&aring;s, Pulito, Schroeder, &amp; Tang "
                          "(2026). AI unboxed: Capability arrival and the clerical decline. Data: DAIOE v1.0.0, Zenodo record 21873968."),
    "acemoglu2020": dict(cite="Acemoglu & Restrepo", year="2020", link="https://doi.org/10.1093/cjres/rsz022",
                         ref="Acemoglu, D., & Restrepo, P. (2020). The wrong kind of AI? Artificial intelligence and the future of labour demand. "
                             "<i>Cambridge Journal of Regions, Economy and Society</i>, 13(1), 25&ndash;35."),
    "autor2024": dict(cite="Autor et al.", year="2024", link="https://doi.org/10.1093/qje/qjae008",
                      ref="Autor, D., Chin, C., Salomons, A., & Seegmiller, B. (2024). New frontiers: The origins and content of new work, "
                          "1940&ndash;2018. <i>Quarterly Journal of Economics</i>, 139(3), 1399&ndash;1465."),
    "winner1980": dict(cite="Winner", year="1980",
                       ref="Winner, L. (1980). Do artifacts have politics? <i>Daedalus</i>, 109(1), 121&ndash;136."),
    "dingel2020": dict(cite="Dingel & Neiman", year="2020", link="https://doi.org/10.1016/j.jpubeco.2020.104235",
                       ref="Dingel, J. I., & Neiman, B. (2020). How many jobs can be done at home? <i>Journal of Public Economics</i>, 189, 104235."),
    # ---------------------------------------------------------------- migration
    "ramani2021": dict(cite="Ramani & Bloom", year="2021", link="https://www.nber.org/papers/w28876",
                       ref="Ramani, A., & Bloom, N. (2021). The donut effect of COVID-19 on cities (NBER Working Paper 28876)."),
    "eig2023": dict(cite="Economic Innovation Group", year="2023", link="https://eig.org/high-earners-migration/",
                    ref="Economic Innovation Group (2023). Tax data reveals large flight of high earners from major cities during the pandemic."),
    "mckee2025": dict(cite="McKee, Smith & Zhang", year="2025", link="https://academic.oup.com/psq/advance-article/doi/10.1093/psquar/qqaf107/8341509",
                      ref="McKee, S., Smith, D. A., & Zhang, O. (2025). &ldquo;Welcome to the Free State of Florida&rdquo;: In-migration and rising "
                          "Republicanism in the Sunshine State. <i>Political Science Quarterly</i>."),
    "gimpel2025": dict(cite="Gimpel, Newton & Reeves", year="2025", link="https://doi.org/10.1177/10780874251380677",
                       ref="Gimpel, J. G., Newton, J., & Reeves, A. (2025). Short-haul moves and the political geography of partisanship: "
                           "Intrametropolitan migration as a force for change in U.S. politics. <i>Urban Affairs Review</i>."),
    # ---------------------------------------------------------------- data used here
    "gambit": dict(cite="JsonOfCounties", year="2023", link="https://github.com/evangambit/JsonOfCounties", check="compilation; year of last update not checked",
                   ref="Gambit, E. JsonOfCounties: county-level data compiled from the Census ACS, BEA, NOAA, County Business Patterns and the MIT "
                       "Living Wage Calculator [Data set]. GitHub."),
    "mcgovern": dict(cite="McGovern", year="2024", link="https://github.com/tonmcg/US_County_Level_Election_Results_08-24",
                     ref="McGovern, T. US county-level presidential election results, 2008&ndash;2024 [Data set]. GitHub."),
}


def cite(key, narrative=False):
    r = REFS[key]
    y = r["year"]
    return f"{r['cite']} ({y})" if narrative else f"{r['cite']}, {y}"
