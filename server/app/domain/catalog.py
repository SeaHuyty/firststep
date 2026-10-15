"""Static reference data: product catalog, bucket and answer labels.

Fees and minimums are approximate and illustrative, not live market data.
"""

from .schemas import Product
from .stocks import in_universe

BUCKET_META: dict[str, dict[str, str]] = {
    "emergency": {"label": "Emergency Fund", "why": "A safety cushion for unexpected expenses (3–6 months)."},
    "stocks": {"label": "Global Stocks (ETF)", "why": "Long-term growth through diversified global equities."},
    "bonds": {"label": "Bonds / Fixed Income", "why": "Adds stability and reduces overall volatility."},
    "cash": {"label": "Cash / High-yield Savings", "why": "Liquidity for near-term needs and opportunities."},
    "alt": {"label": "Alternatives (e.g. REITs)", "why": "Optional extra diversification beyond stocks and bonds."},
}

# Which plan buckets each product tab covers.
GROUP_BUCKETS: dict[str, list[str]] = {
    "Global Stocks (ETF)": ["stocks", "alt"],
    "Individual Stocks": ["stocks"],
    "Bonds": ["bonds"],
    "Savings": ["emergency", "cash"],
}

LABELS: dict[str, dict[str, str]] = {
    "goal": {"wealth": "Build wealth", "house": "Buy a house", "business": "Start a business", "income": "Regular income"},
    "horizon": {"1": "Under 2 years", "3": "2–5 years", "7": "5–10 years", "12": "10+ years"},
    "emergency": {"none": "No emergency savings", "insufficient": "Some, but possibly insufficient", "enough": "6+ months covered"},
    "debt": {"none": "No significant debt", "some": "Some manageable debt", "significant": "Significant debt"},
    "risk": {"1": "Conservative", "2": "Moderate", "3": "Aggressive"},
}

PRODUCTS: dict[str, list[Product]] = {
    "Global Stocks (ETF)": [
        Product(name="Vanguard S&P 500 ETF", ticker="VOO", risk=3, fee="0.03%", min="~$100", region="US", blurb="Tracks 500 large U.S. companies. Long-term growth potential with diversified exposure.", domain="vanguard.com"),
        Product(name="iShares Core MSCI World ETF", ticker="IWDA", risk=3, fee="0.20%", min="~$100", region="Developed markets", blurb="Diversified exposure across developed markets.", symbol="IWDA.L", domain="ishares.com"),
        Product(name="Invesco NASDAQ 100 ETF", ticker="QQQM", risk=4, fee="0.15%", min="~$100", region="US", blurb="Leading technology companies. Higher potential return, higher volatility.", domain="invesco.com"),
        Product(name="Vanguard Total Stock Market ETF", ticker="VTI", risk=3, fee="0.03%", min="~$100", region="US", blurb="Thousands of U.S. companies of every size, the broadest U.S. exposure.", domain="vanguard.com"),
        Product(name="Vanguard Total World Stock ETF", ticker="VT", risk=3, fee="0.06%", min="~$100", region="Worldwide", blurb="One fund holding stocks from developed and emerging markets worldwide.", domain="vanguard.com"),
        Product(name="Vanguard Real Estate ETF", ticker="VNQ", risk=4, fee="0.13%", min="~$100", region="US", blurb="U.S. real estate investment trusts (REITs). Adds a non-stock, non-bond diversifier.", domain="vanguard.com"),
    ],
    "Individual Stocks": [],  # chosen by the screener over the S&P 500 (see domain/stocks.py)
    "Bonds": [
        Product(name="Vanguard Total Bond Market ETF", ticker="BND", risk=2, fee="0.03%", min="~$100", region="US", blurb="Broad U.S. investment-grade bonds for stability.", domain="vanguard.com"),
        Product(name="iShares Core U.S. Aggregate Bond ETF", ticker="AGG", risk=2, fee="0.03%", min="~$100", region="US", blurb="Diversified bond exposure with steady income.", domain="ishares.com"),
    ],
    "Savings": [
        Product(name="High-yield Savings Account", ticker="HYSA", risk=1, fee="None", min="$0", region="US", blurb="Instant access, insured deposits. Good home for an emergency fund.", live=False),
        Product(name="Money Market Fund", ticker="MMF", risk=1, fee="~0.10%", min="~$500", region="US", blurb="Short-term, low-risk securities with competitive yield.", live=False),
        Product(name="iShares 0-3 Month Treasury Bond ETF", ticker="SGOV", risk=1, fee="0.09%", min="~$100", region="US", blurb="Very short-term U.S. Treasury bills. Cash-like, tradable like a stock.", domain="ishares.com"),
    ],
}


def group_of(ticker: str) -> str | None:
    found = next((g for g, items in PRODUCTS.items() if any(p.ticker == ticker for p in items)), None)
    return found or ("Individual Stocks" if in_universe(ticker) else None)
