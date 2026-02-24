import asyncio
import json
import sys
from dotenv import load_dotenv

from agents.researcher import research_stock
from agents.aggregator import aggregate_research
from agents.analyst import analyze_and_recommend

load_dotenv()


async def main():
    portfolio_path = sys.argv[1] if len(sys.argv) > 1 else "portfolio.json"

    with open(portfolio_path) as f:
        portfolio = json.load(f)

    stocks = portfolio["stocks"]
    tickers = [s["ticker"] for s in stocks]

    print(f"\nPortfolio: {', '.join(tickers)}")
    print("=" * 60)

    # ── Step 1: Fan-out ──────────────────────────────────────────
    print("\n[1/3] Researching stocks in parallel...")
    semaphore = asyncio.Semaphore(5)  # respect Finnhub free-tier rate limits

    async def research_with_limit(stock):
        async with semaphore:
            return await research_stock(stock)

    research_results = await asyncio.gather(
        *[research_with_limit(stock) for stock in stocks]
    )

    # ── Step 2: Aggregate ────────────────────────────────────────
    print("\n[2/3] Aggregating findings...")
    aggregated = await aggregate_research(stocks, research_results)

    # ── Step 3: Analyst recommendations (streaming) ──────────────
    print("\n[3/3] Generating recommendations...\n")
    print("=" * 60)
    print("  PORTFOLIO ANALYSIS REPORT")
    print("=" * 60 + "\n")

    await analyze_and_recommend(stocks, aggregated)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
