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

## 7. Range of outcomes (`project_outcomes`)

Sprout never shows one predicted number. It replays history in many orders and shows a bad, a typical and a good case:

- **Method: moving block bootstrap** [KU1]. The portfolio's own monthly returns from 2000 to 2025 (after fees) are cut into every overlapping 12-month block. 5,000 paths are stitched from randomly chosen blocks. Keeping a year's months in order preserves short-run patterns such as runs of bad months, which resampling single months would break. In Lahiri's comparison, moving-block and circular-block bootstraps were more accurate than the stationary bootstrap of Politis and Romano [LA1, PR1]. We picked 12-month blocks so each block keeps one year's months in order. That length is our design choice, not a tuned optimum.
- **Output:** the 10th, 50th and 90th percentile value at each year end, the money paid in, the chance of ending year 1 below the money paid in, and the chance of reaching the goal. Robo-advisors show the same shape: U.S. Bank's automated investor runs 6,000 scenarios and shows the 15th, 50th and 85th percentiles, and Ally runs 10,000 [UB1, AL1].
- **Honest limits:** returns are before inflation and taxes; 26 years of history is one sample of the world; the fixed seed makes results reproducible, not more certain. The UI titles the chart "Range of outcomes" with the caption "not a prediction".

Check on real data (lump sum $6,000, $300 a month, 10 years, $42,000 paid in): C3's typical case is about $59,500 (bad case $47,300, good case $72,100), and C5's bad case is about $42,300, close to the money paid in, while its good case is about $100,600. The range widens as risk rises, as it should.

## 8. Savings plan when Sprout says "not yet" (`build_savings_plan`)

The whole monthly surplus (income minus costs) goes to one step at a time: (1) a $1,000 starter buffer if savings are lower, so a surprise bill does not go back on the card [ML1]; (2) expensive debts, highest rate first (the "avalanche"), which costs the least interest and matches Vanguard's "pay off the debts with the highest interest rates first" [V1, LT1]; (3) the 3-month emergency fund. Interest accrues monthly at APR/12 while a debt is paid. For Amina ($250 a month, $600 saved, $1,750 on a 22.9% card) the plan is 2 + 8 + 10 = 20 months, and the card costs about $147 in interest.

## 9. Monitoring: drift and cooling-off (`DRIFT-01`, `COOL-01`)

- **Drift.** Each month of fast-forward, fund prices move by their asset class's return minus a twelfth of the yearly fee. If any asset class drifts more than 5 percentage points from target, Sprout proposes a rebalance, which goes through the same confirmation as any order. Vanguard's rebalancing research concludes that annual or semiannual monitoring with rebalancing at 5% thresholds is likely to balance risk control and cost for most investors [V4].
- **Cooling-off.** Selling more than 20% of the portfolio while it is more than 15% below its peak starts a 24-hour simulated cooling-off period, then Sprout asks again.

## 10. Language policy (`LANG-*`)

Before a reply is shown, it is checked for guarantees, claims of no risk, promises of growth and price predictions. A hit regenerates the reply once, then falls back to a safe message. The categories follow FINRA Rule 2210, which bars promissory and exaggerated claims, performance predictions and statements implying guaranteed results [FN1]. Outcomes are always shown as ranges, never one number, and never called a "backtest".

## 11. Security design: the guardian (`app/policy`, `app/audit`)

The design follows the OWASP Top 10 for LLM Applications (2025) [OW1, OW2]:

| OWASP guidance | FirstStep |
|---|---|
| LLM06 Excessive Agency: "require a human to approve high-impact actions before they are taken" | Tier 2 tools (`place_order`, `create_auto_invest`) are never offered to the LLM. Only the Confirm button's request mints a one-time token (`CONF-01`). |
| LLM06: "implement authorization in downstream systems rather than relying on an LLM" | `app/policy` checks every tool call (`STAGE-01`, `SUIT-01`, `CONC-01`, `LIM-01`, `COOL-01`) whatever the model asked for. |
| LLM06: limit extensions and their functionality to the minimum | Each stage exposes only its own tools (`STAGE-01`); tools take strict schemas (`extra="forbid"`). |
| LLM01 Prompt Injection: "use deterministic code to validate" outputs; input and output filtering | Input guard for injection patterns and PII; output filter for `LANG-*` and missing disclosures. |
| LLM06: log and monitor the activity of extensions | Every tool call, policy decision, confirmation and fill goes to the hash-chained audit log. |

**Confirmation tokens (`CONF-01`).** A token is an HMAC-SHA256 over the proposal id, the SHA-256 of the proposal's exact contents, a random nonce and an expiry (10 minutes). Signatures are compared with `hmac.compare_digest`, which the Python documentation recommends over `==` for HMAC checks [PY1]. The nonce is stored when used, so a replayed token fails, as nonce checks do in OpenID [OI1]. A token for one plan cannot execute a changed plan, because the content hash would differ.

**Audit chain.** Each event stores the SHA-256 of the previous event, following the chained-record idea of Schneier and Kelsey's secure audit logs [SK1]. A plain hash chain cannot stop someone who rewrites the whole file and recomputes every hash, so the latest hash is also anchored outside the file (the sandbox database and each order receipt), and the verifier checks against it. Schneier and Kelsey note a limit that applies to us too: the log is only as trustworthy as the machine at the moment it writes.

## Sources

- [OI1] OpenID security list, on nonce checks in OpenID 2.0 (2010). https://lists.openid.net/pipermail/openid-security/2010-July/001160.html
- [OW1] OWASP GenAI, LLM06:2025 Excessive Agency. https://genai.owasp.org/llmrisk/llm062025-excessive-agency/
- [OW2] OWASP GenAI, LLM01:2025 Prompt Injection. https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- [PY1] Python documentation, hmac.compare_digest. https://docs.python.org/3/library/hmac.html
- [SK1] Schneier, B. and Kelsey, J. (1999). Secure audit logs to support computer forensics. *ACM TISSEC* 2(2). https://www.schneier.com/academic/archives/1999/05/secure_audit_logs_to.html

- [AL1] Ally Invest, Monte Carlo methodology. https://www.ally.com/docs/invest/monte-carlo-methodology
- [KU1] Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *Annals of Statistics* 17(3).
- [LA1] Lahiri, S. N. (1999). Theoretical comparisons of block bootstrap methods. *Annals of Statistics* 27(1). https://projecteuclid.org/journals/annals-of-statistics/volume-27/issue-1/Theoretical-comparisons-of-block-bootstrap-methods/10.1214/aos/1018031117.pdf
- [LT1] LendingTree, Debt avalanche vs. snowball study. https://www.lendingtree.com/debt-consolidation/debt-avalanche-snowball-study/
- [ML1] MoneyLion, Pay off debt or invest? (starter fund of $1,000–2,000). https://www.moneylion.com/learn/debt/get-out-of-debt/pay-off-debt-or-invest
- [PR1] Politis, D. N. and Romano, J. P. (1994). The stationary bootstrap. *JASA* 89(428).
- [UB1] U.S. Bank Automated Investor, Methodology and assumptions. https://www.usbank.com/investing/online-investing/automated-investing/methodology-and-assumptions.html
- [V4] Vanguard (2010), Best practices for portfolio rebalancing. https://indexacapital.com/bundles/unaiadvisor/docs/papers/2010-Vanguard-Best-practices-for-portfolio-rebalancing.pdf
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
