"""Build data/returns.csv: monthly returns per asset class, 2000-2025.

Run once and commit the output; the app never touches the network.

    python scripts/build_returns.py

Sources (terms in data/SOURCES.md, method in docs/research/methodology.md):
- Kenneth R. French Data Library: US market, developed ex-US,
  emerging markets, the US "HiTec" industry portfolio, and the
  one-month T-bill rate (cash).
- FRED (Federal Reserve H.15): 2- and 10-year Treasury constant-
  maturity yields, turned into bond total returns with the par-bond
  duration and convexity formulas of Swinkels (2019), "Treasury Bond
  Return Data Starting in 1962", Data 4(3), 91.
- World Bank Commodity Price Data (Pink Sheet): monthly gold price.
"""

import argparse
import csv
import io
import itertools
import logging
import urllib.request
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import openpyxl

SERVER_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = SERVER_DIR / ".cache" / "returns"
FIRST, LAST = "2000-01", "2025-12"

FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
WORLD_BANK = (
    "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
    "related/CMO-Historical-Data-Monthly.xlsx"
)
COLUMNS = [
    "cash",
    "short_bonds",
    "bonds",
    "us_equity",
    "intl_equity",
    "em_equity",
    "us_tech",
    "gold",
]

log = logging.getLogger("build_returns")
Series = dict[str, float]  # "YYYY-MM" -> decimal monthly return


def fetch(url: str, name: str) -> bytes:
    """Return the file at url, downloading it once into the cache."""
    path = CACHE_DIR / name
    if not path.exists():
        log.info("downloading %s", url)
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "firststep-build/1.0"})  # noqa: S310
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (fixed https URLs)
            path.write_bytes(resp.read())
    return path.read_bytes()


def french_table(zip_name: str, columns: Iterable[str]) -> dict[str, Series]:
    """Return monthly columns of a French library CSV zip as decimals.

    The files hold several tables; the first one is monthly, with
    YYYYMM in the first column and returns in percent.
    """
    raw = fetch(FRENCH + zip_name, zip_name)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        text = zf.read(zf.namelist()[0]).decode("latin-1")
    wanted = list(columns)
    out: dict[str, Series] = {c: {} for c in wanted}
    header: list[str] | None = None
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row]
        if not any(cells):
            if header and any(out.values()):
                break  # end of the first (monthly) table
            continue
        if header is None:
            if all(c in cells for c in wanted):
                header = cells
            continue
        key = cells[0]
        if not (len(key) == 6 and key.isdigit()):
            if any(out.values()):
                break
            continue
        month = f"{key[:4]}-{key[4:]}"
        for c in wanted:
            out[c][month] = float(cells[header.index(c)]) / 100
    if not all(out.values()):
        raise ValueError(f"no monthly data for {wanted} in {zip_name}")
    return out


def fred_month_end(series_id: str) -> Series:
    """Return the last valid daily value of each month, in decimals."""
    raw = fetch(FRED + series_id, f"{series_id}.csv").decode()
    out: Series = {}
    for row in csv.DictReader(io.StringIO(raw)):
        value = row.get(series_id, "").strip()
        if value and value != ".":
            out[row["observation_date"][:7]] = float(value) / 100  # later days overwrite
    return out


def par_bond_returns(yields: Series, maturity_years: float) -> Series:
    """Return monthly total returns of a par bond from month-end yields.

    Swinkels (2019), equations (1)-(3): R = income - D*dY + 0.5*C*dY^2,
    with modified duration D and convexity C of a par bond, and the
    income term (1 + Y_{t-1})^(1/12) - 1.
    """
    months = sorted(yields)
    out: Series = {}
    m = maturity_years
    for prev, cur in itertools.pairwise(months):
        y0, y1 = yields[prev], yields[cur]
        y = max(y1, 1e-6)  # keeps the formulas finite near zero yields
        disc = (1 + 0.5 * y) ** (2 * m)
        duration = (1 / y) * (1 - 1 / disc)
        convexity = (2 / y**2) * (1 - 1 / disc) - (2 * m) / (y * (1 + 0.5 * y) ** (2 * m + 1))
        dy = y1 - y0
        out[cur] = (1 + y0) ** (1 / 12) - 1 - duration * dy + 0.5 * convexity * dy**2
    return out


def world_bank_gold() -> Series:
    """Return monthly gold returns from World Bank monthly prices."""
    raw = fetch(WORLD_BANK, "CMO-Historical-Data-Monthly.xlsx")
    book = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    sheet = book["Monthly Prices"]
    gold_col: int | None = None
    prices: dict[str, float] = {}
    for row in sheet.iter_rows(values_only=True):
        if gold_col is None:
            labels = [str(c).strip().lower() if c is not None else "" for c in row]
            if "gold" in labels:
                gold_col = labels.index("gold")
            continue
        key, value = row[0], row[gold_col]
        if isinstance(key, str) and "M" in key and isinstance(value, int | float):
            year, mon = key.split("M")
            prices[f"{year}-{int(mon):02d}"] = float(value)
    months = sorted(prices)
    return {cur: prices[cur] / prices[prev] - 1 for prev, cur in itertools.pairwise(months)}


def month_range(first: str, last: str) -> list[str]:
    """Return every "YYYY-MM" from first to last inclusive."""
    y, m = int(first[:4]), int(first[5:])
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build() -> dict[str, Series]:
    """Return every asset-class series keyed by column name."""
    us = french_table("F-F_Research_Data_Factors_CSV.zip", ["Mkt-RF", "RF"])
    dev = french_table("Developed_ex_US_3_Factors_CSV.zip", ["Mkt-RF", "RF"])
    em = french_table("Emerging_5_Factors_CSV.zip", ["Mkt-RF", "RF"])
    ind = french_table("10_Industry_Portfolios_CSV.zip", ["HiTec"])

    def total(t: dict[str, Series]) -> Series:
        return {k: v + t["RF"][k] for k, v in t["Mkt-RF"].items()}

    return {
        "cash": us["RF"],
        "short_bonds": par_bond_returns(fred_month_end("DGS2"), 2),
        "bonds": par_bond_returns(fred_month_end("DGS10"), 10),
        "us_equity": total(us),
        "intl_equity": total(dev),
        "em_equity": total(em),
        "us_tech": ind["HiTec"],
        "gold": world_bank_gold(),
    }


def main() -> None:
    """Write data/returns.csv and print a summary per column."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=SERVER_DIR / "data" / "returns.csv")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    series = build()
    months = month_range(FIRST, LAST)
    missing = {c: [m for m in months if m not in series[c]] for c in COLUMNS}
    if any(missing.values()):
        raise SystemExit(f"missing months: { {c: v[:3] for c, v in missing.items() if v} }")

    with args.out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", *COLUMNS])
        for m in months:
            w.writerow([m, *(f"{series[c][m]:.6f}" for c in COLUMNS)])

    for c in COLUMNS:
        values = [series[c][m] for m in months]
        growth = 1.0
        for v in values:
            growth *= 1 + v
        annual = growth ** (12 / len(values)) - 1
        print(f"{c:12s} annualised {annual:7.2%}  worst month {min(values):7.2%}")
    print(f"wrote {len(months)} months to {args.out} ({datetime.now(UTC).date().isoformat()})")


if __name__ == "__main__":
    main()
