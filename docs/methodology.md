# Methodology

What FirstStep computes, how, and what each choice is based on. Every rule named here lives in `server/data/rules.yaml` under the same ID and has an allow test and a deny test. Sources are listed at the end.

## 1. Design principle

**The LLM talks; a deterministic rules engine decides.** The language model chooses which tool to call and writes the words. Every number, product and order comes from tested Python in `app/engine` and `app/policy`. Execution needs a token that only the user's Confirm click can create, and the model never sees it.

## 2. Readiness: should this person invest at all? (`READY-01`, `READY-02`)

Before any portfolio, Sprout checks two things:

- **Emergency fund ≥ 3 months of living costs** (`READY-01`). Vanguard UK puts building 3–6 months of expenses in an accessible account before investing, and HSBC UK recommends at least 3 months [V1, H1]. We use the low end, 3, so the gate stops people with no cushion without blocking people who have a reasonable one.
- **No debt above 8% a year** (`READY-02`). Paying off expensive debt is a surer return than investing. Vanguard's guidance is to pay off the highest-rate debts first, while lower-rate loans such as student loans and mortgages can coexist with investing [V1, V2]. Personal-finance guidance places the cut-off between about 6% and 8% [B1, R1]. We use 8% so credit cards (often above 20%) are blocked and typical student loans are not.

If either check fails, the session goes to `SAVINGS_PLAN` and no investment tool exists. The plan follows the common order: keep a small cash buffer, pay the highest-rate debt first ("avalanche"), then build the 3-month fund [B1, V1].

## 3. Risk profile: C1 to C5

Regulators distinguish a client's **willingness** to take risk (risk tolerance) from their **ability** to bear losses (capacity for loss). The UK regulator's FG11/05 review found that 9 of the 11 risk-profiling tools it examined had weaknesses that could lead to flawed results, and its former technical specialist later named weak coverage of capacity for loss as a lasting problem [F1]. ESMA's MiFID II suitability guidelines require the assessment to cover the client's ability to bear losses and risk tolerance, and require questionnaires to be fit for purpose [E1]. The CFA Institute's comment on those guidelines asked for risk to be assessed on both willingness and ability [C1].

FirstStep therefore asks two sets of questions (`data/questionnaire.yaml`):

- **Tolerance:** five situational questions, such as "Your $1,000 drops to $800 in a month. What do you do?" and a choice between outcome ranges for $10,000. Situational items are the design of the Grable & Lytton risk-tolerance scale, the most widely used validated scale (Cronbach's α 0.77 across 160,279 respondents) [G1]. Tolerance is the **average** of the five answers, rounded half up: several items reduce the noise of any one answer.
- **Capacity:** age band, income stability, number of dependants, and a direct capacity-for-loss question ("If the money you invest fell by a third, would it change your plans?"). Capacity is the **lowest** of these scores: one hard constraint, such as needing the money within a year, is enough to limit how much loss a person can absorb.
- **Final class = min(tolerance, capacity, horizon cap).** `HOR-01` caps a goal under 3 years at C2 and under 1 year at C1, because shorter horizons suit less volatile holdings [S1].

## 4. Suitability: C1–C5 against R1–R5 (`SUIT-01`)

China's CSRC *Measures for the Suitability Management of Securities and Futures Investors* (2016, amended 2022) require distributors to rate each product's risk, classify each investor, and not recommend products above an ordinary investor's risk tolerance [CS1]. Fund distributors publish the matching they use under these Measures and the AMAC guidelines: C1 investors buy R1 products, C2 up to R2, C3 up to R3, C4 up to R4, and C5 any product [A1]. `SUIT-01` applies exactly this matrix, **per product**, at three points: listing, proposing and ordering.

**Product ratings** (`data/products.csv`) follow the same distributors' rating tables [A1, A2]: money market and short-term bond funds R1, ordinary bond funds R2, equity funds R3, and commodity (gold) funds R4, which are treated as more complex than equity funds. We also rate emerging-market and single-sector (technology) funds R4 because of their larger swings. There are no R5 products (leverage, structured products), which are out of scope.

A consequence: because suitability is checked per product, C1 and C2 portfolios can hold only R1–R2 funds and contain **no equity**. That is how the Chinese regime works, and it is why Mei (C2) is offered a bond-based plan instead of "everything in tech".

## 5. Model portfolios and diversification (`CONC-01`)

Each class has one model portfolio (`data/portfolios.yaml`). Equity shares rise with the class (0%, 0%, 50%, 70%, 90%), like target-risk fund ranges such as Vanguard LifeStrategy, which steps from 20% to 100% equity [V3]. Funds are low-cost index funds, as Vanguard's principles recommend (broadly diversified funds, low cost) [V3]. One high-fee actively managed fund is on the shelf only so the comparison tool can show what fees cost in dollars.

`CONC-01` keeps any single product at 40% or less and any single equity asset class at 60% or less, except for C5. A test checks every model portfolio against `SUIT-01` and `CONC-01` for its own class.

## 6. Market data (`data/returns.csv`)

Monthly total returns, January 2000 to December 2025, for 8 asset classes. The period includes the 2000–02 dot-com crash, 2008 and the March 2020 crash. The app never calls a live data feed.

- **Equities and cash** come from the Kenneth R. French Data Library: the US market, developed markets excluding the US, emerging markets and the US technology industry (`HiTec`), each as `Mkt-RF + RF`, and the one-month T-bill (`RF`) as cash [K1].
- **Bonds** are built from FRED's 2- and 10-year Treasury constant-maturity yields with the par-bond formulas of Swinkels (2019) [W1]:
  - duration D = (1/Y)·[1 − (1 + Y/2)^(−2M)]
  - convexity C = (2/Y²)·[1 − (1 + Y/2)^(−2M)] − 2M / [Y·(1 + Y/2)^(2M+1)]
  - monthly return R = (1 + Y_{t−1})^(1/12) − 1 − D·ΔY + ½·C·ΔY²

  Swinkels reports this series matching Global Financial Data's 10-year Treasury index with R² 0.996 over 1962–2018.
- **Gold** is the World Bank's monthly average gold price [WB1].

Checks on the built file: US equity returns 8.3% a year over 2000–2025, and March 2020 is −13.3% for US equity and +4.3% for 10-year Treasuries (yields fell from 1.13% to 0.67%). Fund NAVs subtract each fund's fee monthly from its asset-class return.

## 7. Language policy (`LANG-*`)

Before a reply is shown, it is checked for guarantees, claims of no risk, promises of growth and price predictions. A hit regenerates the reply once, then falls back to a safe message. The categories follow FINRA Rule 2210, which bars promissory and exaggerated claims, performance predictions and statements implying guaranteed results [FN1]. Outcomes are always shown as ranges, never one number, and never called a "backtest".

## Sources

- [A1] Debon Fund Management, 销售适当性匹配意见 (suitability matching opinion), Jan 2026. https://www.dbfund.com.cn/upload/word/1767922826575-德邦基金管理有限公司销售适当性匹配意见-202601.docx
- [A2] China Merchants Fund, product risk rating disclosure (2024). https://www.cmfchina.com/upload/20240611/202406111718089072198.pdf
- [B1] Betterment, How to manage debt and invest at the same time. https://www.betterment.com/resources/tag/debt
- [C1] CFA Institute, comment letter on ESMA's draft suitability guidelines (13 Oct 2017). https://rpc.cfainstitute.org/sites/default/files/-/media/documents/comment-letter/2015-2019/20171013.pdf
- [CS1] CSRC, Measures for the Suitability Management of Securities and Futures Investors (amended 2022), English text. https://www.lexiscn.com/law/law-english-1-4389916-T.html?eng=0
- [E1] ESMA, Guidelines on certain aspects of the MiFID II suitability requirements, ESMA35-43-3172 (23 Sep 2022). https://prod.finanssivalvonta.fi/globalassets/en/publications/supervision-releases/2023/esma35-43-3172_guidelines_on_certain_aspects_of_the_mifid_ii_suitability_requirements.pdf
- [F1] FSA, Finalised guidance FG11/05, Assessing suitability: establishing the risk a customer is willing and able to take (Mar 2011); consultation GC11/01. https://fca.org.uk/publication/guidance-consultation/gc11_01.pdf
- [FN1] FINRA Rule 2210 summary in SEC filing SR-FINRA-2026-004. https://www.finra.org/sites/default/files/2026-02/SR-FINRA-2026-004-Federal-Register-Notice.pdf
- [G1] Kuzniak, Rabbani, Heo, Ruiz-Menjivar and Grable (2015), The Grable and Lytton risk-tolerance scale: a 15-year retrospective, Financial Services Review. https://openjournals.libs.uga.edu/fsr/article/view/3240
- [H1] HSBC UK, Invest or repay your debts. https://hsbc.co.uk/investments/invest-or-repay-your-debts
- [K1] Kenneth R. French Data Library. https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- [R1] ConsumerAffairs, Invest or pay off debt? https://www.consumeraffairs.com/finance/invest-or-pay-off-debt.html
- [S1] SEC Investor.gov, Asset allocation and diversification. https://www.investor.gov/introduction-investing/getting-started/asset-allocation
- [V1] Vanguard UK, Five steps to take before you start investing. https://www.vanguardinvestor.co.uk/articles/latest-thoughts/how-it-works/five-steps-to-take-before-you-start-investing
- [V2] Vanguard Canada, Guide to financial wellness (2023). https://vanguard.ca/content/dam/intl/americas/canada/en/documents/FLFW_042023.pdf
- [V3] Vanguard UK, LifeStrategy model portfolios (20–80% equity) and Principles for Investing Success. https://www.vanguard.co.uk/professional/product/fund/mps/STUSA09BRE/lifestrategy-60-equity-mps-classic
- [W1] Swinkels, L. (2019). Treasury Bond Return Data Starting in 1962. *Data* 4(3), 91. https://doi.org/10.3390/data4030091
- [WB1] World Bank, Commodity Markets (Pink Sheet) monthly data. https://www.worldbank.org/en/research/commodity-markets
