# Data sources

Everything in `data/` is read-only at runtime; the app makes no network calls. `returns.csv` is rebuilt with `python scripts/build_returns.py` (downloaded 17 Oct 2026).

## returns.csv

Monthly total returns as decimals, January 2000 to December 2025 (312 months), in US dollars.

| Column | What it is | Source | Terms |
|---|---|---|---|
| `cash` | One-month US Treasury bill return | Kenneth R. French Data Library, `F-F_Research_Data_Factors` (`RF`; Ibbotson to 2024-05, then ICE BofA US 1-Month Treasury Bill Index) | Publicly posted; the library page states only "Copyright Eugene F. Fama and Kenneth R. French", so we cite it and redistribute only derived monthly returns |
| `us_equity` | US value-weighted market, total return | French library, same file (`Mkt-RF + RF`, from CRSP) | as above |
| `intl_equity` | Developed markets excluding the US | French library, `Developed_ex_US_3_Factors` (`Mkt-RF + RF`) | as above |
| `em_equity` | Emerging markets | French library, `Emerging_5_Factors` (`Mkt-RF + RF`) | as above |
| `us_tech` | US technology industry ("HiTec": computers, software, electronic equipment) | French library, `10_Industry_Portfolios`, value-weighted `HiTec` | as above |
| `short_bonds` | 2-year US Treasury, total return | FRED `DGS2` month-end yield (Federal Reserve H.15), converted with Swinkels (2019) eqs. 1–3, maturity 2 years | H.15 is US government data in the public domain |
| `bonds` | 10-year US Treasury, total return | FRED `DGS10` month-end yield, same method, maturity 10 years | as above |
| `gold` | Gold, monthly average price change | World Bank Commodity Price Data (Pink Sheet), `CMO-Historical-Data-Monthly.xlsx`, sheet "Monthly Prices", column "Gold" | World Bank open data, CC BY 4.0 |

Method references: Swinkels, L. (2019). Treasury Bond Return Data Starting in 1962. *Data*, 4(3), 91. https://doi.org/10.3390/data4030091 (CC BY 4.0). The paper reports its 10-year series matching Global Financial Data's Treasury index with R² 0.996 over 1962–2018.

Known simplifications: bond returns assume a par bond at constant maturity and no trading costs; gold uses monthly average prices, not month-end; fund NAVs subtract the fund's fee (TER) monthly from the asset-class return.

## products.csv, portfolios.yaml

Written by the team. The funds are **fictional**; each tracks one asset class in `returns.csv`. Risk ratings follow how Chinese fund distributors rate products under the CSRC suitability Measures and the AMAC guidelines: money market and short-term bond funds R1, ordinary bond funds R2, equity index funds R3, commodity (gold), emerging-market and single-sector funds R4. See `docs/methodology.md`.

## questionnaire.yaml, glossary.yaml, rules.yaml, personas.yaml

Written by the team. Glossary definitions cite SEC Investor.gov, the CFPB and the CSRC Measures; each source URL is in the file. Personas are fictional.
