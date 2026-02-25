"""
Scheduled runner for the stock-research-agent.

Runs the full analysis pipeline on a cron schedule and posts the result
to a configured Feishu chat.

Usage:
    python3 scheduler.py

Configuration via environment variables (see .env):
    SCHEDULE_CRON   — cron expression, default "0 9 * * 1-5" (9 AM Mon–Fri)
    SCHEDULE_TZ     — timezone, default "Asia/Shanghai"
    FEISHU_CHAT_ID  — Feishu chat_id to post results to
    PORTFOLIO_PATH  — path to portfolio JSON, default "portfolio.json"
"""

import asyncio
import json
import os
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from feishu import bot, formatter
from agents.researcher import research_stock
from agents.aggregator import aggregate_research
from agents.analyst import analyze_and_recommend


load_dotenv()


async def run_and_post(trigger: str = "scheduled"):
    """Run the full pipeline and post the card to Feishu."""
    chat_id = os.environ["FEISHU_CHAT_ID"]
    portfolio_path = os.environ.get("PORTFOLIO_PATH", "portfolio.json")

    with open(portfolio_path) as f:
        stocks = json.load(f)["stocks"]

    tickers = [s["ticker"] for s in stocks]
    print(f"[scheduler] Starting analysis: {', '.join(tickers)}")

    # Send ack card first
    bot.send_card(chat_id, formatter.build_ack_card(tickers))

    start = time.monotonic()
    try:
        semaphore = asyncio.Semaphore(5)

        async def research_with_limit(stock):
            async with semaphore:
                return await research_stock(stock)

        research_results = await asyncio.gather(*[research_with_limit(s) for s in stocks])
        aggregated = await aggregate_research(stocks, research_results)
        analyst_text = await analyze_and_recommend(stocks, aggregated)

        elapsed = time.monotonic() - start
        print(f"[scheduler] Analysis complete in {elapsed:.0f}s")

        card = formatter.build_card(
            analyst_text, tickers, trigger=trigger, elapsed_seconds=elapsed
        )
        bot.send_card(chat_id, card)

    except Exception as exc:
        print(f"[scheduler] ERROR: {exc}")
        bot.send_card(chat_id, formatter.build_error_card(str(exc), trigger=trigger))


def main():
    cron_expr = os.environ.get("SCHEDULE_CRON", "0 9 * * 1-5")
    tz = os.environ.get("SCHEDULE_TZ", "Asia/Shanghai")

    scheduler = AsyncIOScheduler(timezone=tz)
    trigger = CronTrigger.from_crontab(cron_expr, timezone=tz)
    scheduler.add_job(run_and_post, trigger, kwargs={"trigger": "scheduled"})

    print(f"[scheduler] Starting — cron='{cron_expr}' tz='{tz}'")
    scheduler.start()

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        print("[scheduler] Shutting down.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
