import asyncio
from tools.finnhub_client import get_company_news, get_analyst_recommendations
from tools.yfinance_client import get_stock_context


async def research_stock(stock: dict) -> dict:
    """Fetch news, analyst ratings, and price context for a single stock."""
    ticker = stock["ticker"]
    print(f"  Researching {ticker}...")

    # Run all three blocking I/O calls concurrently in thread pool
    news, recommendations, context = await asyncio.gather(
        asyncio.to_thread(get_company_news, ticker),
        asyncio.to_thread(get_analyst_recommendations, ticker),
        asyncio.to_thread(get_stock_context, ticker),
    )

    current_price = context.get("current_price")
    avg_cost = stock.get("avg_cost")
    unrealized_pnl_pct = (
        round((current_price - avg_cost) / avg_cost * 100, 2)
        if current_price and avg_cost
        else None
    )

    return {
        "ticker": ticker,
        "shares": stock.get("shares"),
        "avg_cost": avg_cost,
        "unrealized_pnl_pct": unrealized_pnl_pct,
        "price_context": context,
        "recent_news": news,
        "analyst_recommendations": recommendations,
    }
