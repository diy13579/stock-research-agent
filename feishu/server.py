"""
FastAPI webhook server for Feishu bot events.

Handles:
- URL verification challenge (Feishu setup handshake)
- im.message.receive_v1 events (user messages to the bot)
- Request signature verification

Supported commands (mention the bot in a chat):
  @bot run             — full portfolio analysis
  @bot run AAPL MSFT   — analysis for specific tickers
  @bot help            — show available commands
"""

import hashlib
import hmac
import json
import os
import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from feishu import bot, formatter
from agents.researcher import research_stock
from agents.aggregator import aggregate_research
from agents.analyst import analyze_and_recommend


# ── Startup / shutdown ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from dotenv import load_dotenv
    load_dotenv()
    yield


app = FastAPI(lifespan=lifespan)


# ── Signature verification ───────────────────────────────────────

def _verify_signature(request_body: bytes, timestamp: str, nonce: str, signature: str) -> bool:
    """
    Feishu signature: SHA256(timestamp + nonce + FEISHU_ENCRYPT_KEY + body)
    Only required when Encrypt Key is configured in the Feishu app console.
    If FEISHU_ENCRYPT_KEY is not set, skip verification (development mode).
    """
    encrypt_key = os.environ.get("FEISHU_ENCRYPT_KEY", "")
    if not encrypt_key:
        return True  # skip in dev mode

    content = (timestamp + nonce + encrypt_key + request_body.decode()).encode()
    expected = hmac.new(encrypt_key.encode(), content, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Main webhook endpoint ────────────────────────────────────────

@app.post("/webhook/feishu")
async def feishu_webhook(request: Request):
    body_bytes = await request.body()
    body = json.loads(body_bytes)

    # ── 1. URL verification challenge (one-time setup) ───────────
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge")})

    # ── 2. Signature check ───────────────────────────────────────
    headers = request.headers
    if not _verify_signature(
        body_bytes,
        headers.get("X-Lark-Request-Timestamp", ""),
        headers.get("X-Lark-Request-Nonce", ""),
        headers.get("X-Lark-Signature", ""),
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # ── 3. Route event ───────────────────────────────────────────
    event_type = body.get("header", {}).get("event_type") or body.get("event", {}).get("type")

    if event_type == "im.message.receive_v1":
        event = body.get("event", {})
        asyncio.create_task(_handle_message(event))

    # Always return 200 immediately so Feishu doesn't retry
    return JSONResponse({"code": 0})


# ── Message handler ──────────────────────────────────────────────

async def _handle_message(event: dict):
    """Parse the incoming message and dispatch to the right handler."""
    msg = event.get("message", {})
    message_id = msg.get("message_id", "")
    chat_id = msg.get("chat_id", "")
    msg_type = msg.get("message_type", "")

    if msg_type != "text":
        return  # ignore non-text messages

    try:
        content = json.loads(msg.get("content", "{}"))
        raw_text = content.get("text", "").strip()
    except (json.JSONDecodeError, AttributeError):
        return

    # Strip @bot mention (Feishu includes <at> tags in text)
    # Content looks like: "@_user_1 run AAPL" or plain "run AAPL"
    import re
    clean = re.sub(r"@\S+\s*", "", raw_text).strip().lower()

    if clean.startswith("run"):
        parts = clean.split()
        # Parts after "run" are optional ticker overrides
        extra_tickers = [p.upper() for p in parts[1:] if p.isalpha()]
        await _run_analysis(chat_id, message_id, ticker_override=extra_tickers or None)

    elif clean in ("help", "?"):
        await _send_help(message_id)

    else:
        await bot.reply_text(
            message_id,
            "Unknown command. Try:\n• @bot run\n• @bot run AAPL MSFT\n• @bot help",
        )


async def _run_analysis(chat_id: str, message_id: str, ticker_override: list[str] | None = None):
    """Run the full analysis pipeline and send result card."""
    # Send immediate acknowledgement
    portfolio = _load_portfolio(ticker_override)
    tickers = [s["ticker"] for s in portfolio]
    await asyncio.to_thread(bot.reply_card, message_id, formatter.build_ack_card(tickers))

    start = time.monotonic()
    try:
        analyst_text = await _run_pipeline(portfolio)
        elapsed = time.monotonic() - start
        card = formatter.build_card(analyst_text, tickers, trigger="manual", elapsed_seconds=elapsed)
        await asyncio.to_thread(bot.send_card, chat_id, card)
    except Exception as exc:
        card = formatter.build_error_card(str(exc), trigger="manual")
        await asyncio.to_thread(bot.send_card, chat_id, card)


async def _run_pipeline(stocks: list[dict]) -> str:
    """Execute researcher → aggregator → analyst pipeline."""
    semaphore = asyncio.Semaphore(5)

    async def research_with_limit(stock):
        async with semaphore:
            return await research_stock(stock)

    research_results = await asyncio.gather(*[research_with_limit(s) for s in stocks])
    aggregated = await aggregate_research(stocks, research_results)
    return await analyze_and_recommend(stocks, aggregated)


def _load_portfolio(ticker_override: list[str] | None) -> list[dict]:
    """Load portfolio from JSON, optionally filtering to specific tickers."""
    portfolio_path = os.environ.get("PORTFOLIO_PATH", "portfolio.json")
    with open(portfolio_path) as f:
        all_stocks = json.load(f)["stocks"]

    if ticker_override:
        # Filter to requested tickers; add any not in portfolio as bare entries
        portfolio_map = {s["ticker"]: s for s in all_stocks}
        return [
            portfolio_map.get(t, {"ticker": t, "shares": 0, "avg_cost": 0})
            for t in ticker_override
        ]

    return all_stocks


async def _send_help(message_id: str):
    help_text = (
        "**Stock Research Bot**\n\n"
        "**Commands:**\n"
        "• `@bot run` — analyze your full portfolio\n"
        "• `@bot run AAPL MSFT` — analyze specific tickers\n"
        "• `@bot help` — show this message\n\n"
        "Analysis includes: price context, recent news, analyst ratings, "
        "and BUY/HOLD/SELL recommendations."
    )
    await asyncio.to_thread(bot.reply_text, message_id, help_text)
