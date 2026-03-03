"""
Personal finance tools for the finance_agent.

Covers budgeting, investment analysis, deal-finding, and expense tracking.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

# REAL API keys
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID", "")  # For bank account data


def calculate_budget(
    monthly_income: float,
    expenses: dict,
    savings_goal_pct: float = 20.0,
) -> dict:
    """
    Analyze a monthly budget, flag problem areas, and suggest improvements.

    Args:
        monthly_income: Gross monthly income in USD.
        expenses: Dict of category → monthly amount (e.g. {'rent': 1500, 'food': 600}).
        savings_goal_pct: Target savings as a percentage of income (default 20%).

    Returns:
        A dict with 'status', 'summary', 'budget_breakdown', 'flags', and 'recommendations'.
    """
    if monthly_income <= 0:
        return {"status": "error", "message": "Monthly income must be positive."}

    total_expenses = sum(expenses.values())
    savings = monthly_income - total_expenses
    savings_pct = (savings / monthly_income) * 100

    # 50/30/20 rule categorization
    needs_categories = {"rent", "mortgage", "utilities", "groceries", "insurance", "minimum_debt", "transportation"}
    wants_categories = {"dining", "entertainment", "subscriptions", "clothing", "travel", "gym"}

    needs_total = sum(v for k, v in expenses.items() if any(n in k.lower() for n in needs_categories))
    wants_total = sum(v for k, v in expenses.items() if any(w in k.lower() for w in wants_categories))
    other_total = total_expenses - needs_total - wants_total

    flags = []
    recommendations = []

    # Needs > 50%
    needs_pct = needs_total / monthly_income * 100
    if needs_pct > 55:
        flags.append(f"Needs are {needs_pct:.1f}% of income (target ≤50%). Housing may be too expensive.")
        recommendations.append("Consider refinancing, downsizing, or finding a roommate to reduce housing costs.")

    # Wants > 30%
    wants_pct = wants_total / monthly_income * 100
    if wants_pct > 30:
        flags.append(f"Wants are {wants_pct:.1f}% of income (target ≤30%).")
        recommendations.append("Audit subscriptions and dining expenses — these are the easiest cuts.")

    # Savings below goal
    if savings_pct < savings_goal_pct:
        flags.append(f"Savings rate is {savings_pct:.1f}% (target {savings_goal_pct:.0f}%).")
        recommendations.append(f"Automate transfers of ${(monthly_income * savings_goal_pct / 100):.0f}/mo to savings on payday.")

    # Specific large categories
    for cat, amt in expenses.items():
        pct = amt / monthly_income * 100
        if "subscription" in cat.lower() and amt > 100:
            flags.append(f"Subscriptions total ${amt:.0f}/mo. Audit for unused services.")
        if "food" in cat.lower() or "dining" in cat.lower():
            if pct > 15:
                flags.append(f"Food/dining is {pct:.1f}% of income (${amt:.0f}/mo). Consider meal prep.")

    breakdown = {cat: {"amount": amt, "pct_of_income": round(amt / monthly_income * 100, 1)}
                 for cat, amt in sorted(expenses.items(), key=lambda x: -x[1])}

    return {
        "status": "success",
        "monthly_income": monthly_income,
        "total_expenses": total_expenses,
        "savings": savings,
        "savings_rate_pct": round(savings_pct, 1),
        "savings_goal_pct": savings_goal_pct,
        "breakdown": breakdown,
        "50_30_20_analysis": {
            "needs": {"amount": needs_total, "pct": round(needs_pct, 1), "target_pct": 50},
            "wants": {"amount": wants_total, "pct": round(wants_pct, 1), "target_pct": 30},
            "savings_actual": {"amount": savings, "pct": round(savings_pct, 1), "target_pct": 20},
        },
        "flags": flags,
        "recommendations": recommendations,
        "disclaimer": "This is educational budgeting guidance, not professional financial advice.",
    }


def get_stock_quote(symbol: str) -> dict:
    """
    Get the current stock quote and basic fundamentals for a ticker symbol.

    Args:
        symbol: Stock ticker symbol (e.g. 'AAPL', 'VOO', 'MSFT').

    Returns:
        A dict with 'status', 'symbol', 'price', 'change', 'change_pct',
        'volume', 'market_cap', and '52_week_range'.
    """
    symbol = symbol.upper().strip()

    if ALPHA_VANTAGE_KEY:
        # REAL API: Alpha Vantage
        # import httpx
        # url = "https://www.alphavantage.co/query"
        # params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": ALPHA_VANTAGE_KEY}
        # r = httpx.get(url, params=params)
        # data = r.json().get("Global Quote", {})
        # return {
        #     "status": "success",
        #     "symbol": symbol,
        #     "price": float(data.get("05. price", 0)),
        #     "change": float(data.get("09. change", 0)),
        #     "change_pct": data.get("10. change percent", "0%"),
        #     "volume": int(data.get("06. volume", 0)),
        # }
        pass

    # Mock response
    mock_prices = {
        "AAPL": 215.50, "MSFT": 420.30, "GOOGL": 175.80, "AMZN": 195.20,
        "VOO": 515.40, "VTI": 265.30, "SPY": 575.20, "QQQ": 488.60,
        "NVDA": 875.40, "META": 565.20,
    }
    price = mock_prices.get(symbol, 100.00)

    return {
        "status": "success",
        "symbol": symbol,
        "price": price,
        "change": round(price * 0.012, 2),
        "change_pct": "1.2%",
        "volume": 15_420_000,
        "52_week_range": f"${price * 0.75:.2f} – ${price * 1.35:.2f}",
        "source": "mock — configure ALPHA_VANTAGE_KEY for live quotes",
        "fetched_at": datetime.utcnow().isoformat(),
        "disclaimer": "Not financial advice. Verify on brokerage platform before acting.",
    }


def analyze_investment_portfolio(holdings: list[dict]) -> dict:
    """
    Analyze an investment portfolio for diversification, allocation, and risk.

    Args:
        holdings: List of holding dicts, each with 'symbol', 'shares', 'avg_cost'.
                  Example: [{'symbol': 'VOO', 'shares': 10, 'avg_cost': 420.00}]

    Returns:
        A dict with 'status', 'total_value', 'allocation', 'diversification_score',
        'risk_level', and 'recommendations'.
    """
    if not holdings:
        return {"status": "error", "message": "No holdings provided."}

    # Asset class classification
    etf_index = {"VOO", "VTI", "SPY", "QQQ", "VXUS", "BND", "AGG", "VNQ"}
    tech_stocks = {"AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"}
    bond_etfs = {"BND", "AGG", "TLT", "IEF", "VGIT"}

    mock_prices = {
        "AAPL": 215.50, "MSFT": 420.30, "GOOGL": 175.80, "AMZN": 195.20,
        "VOO": 515.40, "VTI": 265.30, "SPY": 575.20, "QQQ": 488.60,
        "NVDA": 875.40, "META": 565.20, "BND": 74.50, "VNQ": 92.30,
    }

    enriched = []
    total_value = 0.0
    total_cost = 0.0

    for h in holdings:
        sym = h.get("symbol", "").upper()
        shares = float(h.get("shares", 0))
        avg_cost = float(h.get("avg_cost", 0))
        price = mock_prices.get(sym, avg_cost * 1.1)
        value = shares * price
        cost_basis = shares * avg_cost
        gain_loss = value - cost_basis
        total_value += value
        total_cost += cost_basis
        enriched.append({
            "symbol": sym,
            "shares": shares,
            "avg_cost": avg_cost,
            "current_price": price,
            "value": round(value, 2),
            "gain_loss": round(gain_loss, 2),
            "gain_loss_pct": round((gain_loss / cost_basis * 100) if cost_basis > 0 else 0, 1),
            "asset_class": (
                "index_etf" if sym in etf_index else
                "bond" if sym in bond_etfs else
                "tech_stock" if sym in tech_stocks else
                "stock"
            ),
        })

    # Allocation by asset class
    allocation = {}
    for h in enriched:
        ac = h["asset_class"]
        allocation[ac] = allocation.get(ac, 0) + h["value"]

    allocation_pct = {k: round(v / total_value * 100, 1) for k, v in allocation.items()}

    # Diversification scoring (simple heuristic)
    score = 0
    rec = []
    if allocation_pct.get("index_etf", 0) >= 50:
        score += 40
    else:
        rec.append("Increase index ETF allocation (VOO, VTI) to ≥50% for core stability.")
    if allocation_pct.get("tech_stock", 0) > 40:
        rec.append("Tech concentration is high (>40%). Consider diversifying into other sectors.")
    else:
        score += 30
    if allocation_pct.get("bond", 0) >= 10:
        score += 20
    else:
        rec.append("Consider adding bond ETFs (BND, AGG) for ballast — target 10–20% depending on risk tolerance.")
    if len(enriched) >= 5:
        score += 10

    risk_level = "aggressive" if allocation_pct.get("tech_stock", 0) > 50 else \
                 "moderate" if allocation_pct.get("index_etf", 0) > 50 else "balanced"

    return {
        "status": "success",
        "total_value": round(total_value, 2),
        "total_cost_basis": round(total_cost, 2),
        "total_gain_loss": round(total_value - total_cost, 2),
        "total_return_pct": round((total_value - total_cost) / total_cost * 100, 1) if total_cost > 0 else 0,
        "holdings": enriched,
        "allocation_by_asset_class": allocation_pct,
        "diversification_score": score,
        "risk_level": risk_level,
        "recommendations": rec,
        "disclaimer": "Not financial advice. Consult a fiduciary advisor for personalized guidance.",
    }
