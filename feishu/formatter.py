"""
Formats analyst output as a Feishu Interactive Card.

Card layout:
- Header: "Portfolio Analysis Report — YYYY-MM-DD"
- Per-stock sections: ticker + BUY/HOLD/SELL badge + confidence + reasoning
- Overall Portfolio Assessment section
- Footer: trigger source (scheduled / manual) + runtime
"""

import re
from datetime import datetime


# Feishu card color tags for recommendations
_REC_COLORS = {
    "BUY": "green",
    "HOLD": "yellow",
    "SELL": "red",
}

_CONFIDENCE_ICONS = {
    "High": "🟢",
    "Medium": "🟡",
    "Low": "🔴",
}


def build_card(
    analyst_text: str,
    tickers: list[str],
    trigger: str = "scheduled",
    elapsed_seconds: float = 0.0,
) -> dict:
    """
    Build a Feishu interactive card from the raw analyst text output.

    Args:
        analyst_text: Full streamed text from analyst.py
        tickers: List of ticker symbols in the portfolio
        trigger: 'scheduled' | 'manual' | reason string
        elapsed_seconds: How long the analysis took

    Returns:
        Feishu card dict (pass directly to bot.send_card / bot.reply_card)
    """
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    elements = []

    # ── Per-stock sections ───────────────────────────────────────
    stock_blocks = _split_stock_sections(analyst_text, tickers)
    for ticker, block_text in stock_blocks.items():
        rec = _extract_recommendation(block_text)
        color = _REC_COLORS.get(rec, "default")
        confidence = _extract_confidence(block_text)
        conf_icon = _CONFIDENCE_ICONS.get(confidence, "")

        elements.append({
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "grey",
            "columns": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": (
                                    f"**{ticker}**\n"
                                    f"<font color='{color}'>**{rec}**</font>  "
                                    f"{conf_icon} {confidence} confidence"
                                ),
                            },
                        }
                    ],
                }
            ],
        })

        # Reasoning + risk as markdown text block
        reasoning = _extract_section(block_text, "Reasoning")
        risk = _extract_section(block_text, "Key Risk")
        detail_parts = []
        if reasoning:
            detail_parts.append(f"**Reasoning:** {reasoning}")
        if risk:
            detail_parts.append(f"**Key Risk:** {risk}")
        if detail_parts:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(detail_parts),
                },
            })

        elements.append({"tag": "hr"})

    # ── Overall Portfolio Assessment ─────────────────────────────
    overall = _extract_overall_assessment(analyst_text)
    if overall:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**Overall Portfolio Assessment**\n{overall}",
            },
        })
        elements.append({"tag": "hr"})

    # ── Footer ───────────────────────────────────────────────────
    elapsed_str = f"{elapsed_seconds:.0f}s" if elapsed_seconds else ""
    footer_parts = [f"Trigger: {trigger}", f"Generated: {date_str}"]
    if elapsed_str:
        footer_parts.append(f"Runtime: {elapsed_str}")

    elements.append({
        "tag": "note",
        "elements": [
            {"tag": "plain_text", "content": " · ".join(footer_parts)}
        ],
    })

    card = {
        "schema": "2.0",
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"Portfolio Analysis Report — {date_str}",
            },
            "template": "blue",
        },
        "body": {
            "elements": elements,
        },
    }
    return card


def build_error_card(error_message: str, trigger: str = "unknown") -> dict:
    """Build a simple error card when the agent fails."""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return {
        "schema": "2.0",
        "header": {
            "title": {"tag": "plain_text", "content": "Analysis Failed"},
            "template": "red",
        },
        "body": {
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**Error:** {error_message}",
                    },
                },
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": f"Trigger: {trigger} · {date_str}"}
                    ],
                },
            ]
        },
    }


def build_ack_card(tickers: list[str]) -> dict:
    """Immediate acknowledgement card sent while analysis is running."""
    ticker_str = ", ".join(tickers)
    return {
        "schema": "2.0",
        "header": {
            "title": {"tag": "plain_text", "content": "Running Analysis..."},
            "template": "wathet",
        },
        "body": {
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"Analyzing: **{ticker_str}**\nThis usually takes 30–60 seconds.",
                    },
                }
            ]
        },
    }


# ── Internal helpers ─────────────────────────────────────────────

def _split_stock_sections(text: str, tickers: list[str]) -> dict[str, str]:
    """
    Split analyst text into per-ticker chunks.
    Falls back to returning {ticker: full_text} if parsing fails.
    """
    result = {}
    # Try to find sections by ticker heading pattern: "## AAPL" or "**AAPL**" or "AAPL:"
    for i, ticker in enumerate(tickers):
        next_ticker = tickers[i + 1] if i + 1 < len(tickers) else None
        pattern = rf"(?:#{1,3}\s*\*{{0,2}}{re.escape(ticker)}\*{{0,2}}|^\*\*{re.escape(ticker)}\*\*)"
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            start = match.start()
            if next_ticker:
                next_pattern = rf"(?:#{1,3}\s*\*{{0,2}}{re.escape(next_ticker)}\*{{0,2}}|^\*\*{re.escape(next_ticker)}\*\*)"
                next_match = re.search(next_pattern, text[start + 1:], re.IGNORECASE | re.MULTILINE)
                end = start + 1 + next_match.start() if next_match else len(text)
            else:
                end = len(text)
            result[ticker] = text[start:end]
        else:
            result[ticker] = text  # fallback: full text

    return result


def _extract_recommendation(text: str) -> str:
    """Extract BUY / HOLD / SELL from a stock section."""
    m = re.search(r"\b(BUY|HOLD|SELL)\b", text, re.IGNORECASE)
    return m.group(1).upper() if m else "N/A"


def _extract_confidence(text: str) -> str:
    """Extract High / Medium / Low confidence."""
    m = re.search(r"Confidence[:\s*_]*\**(High|Medium|Low)\**", text, re.IGNORECASE)
    return m.group(1).capitalize() if m else "N/A"


def _extract_section(text: str, label: str) -> str:
    """Extract content after a bolded label like **Reasoning:** or **Key Risk:**"""
    pattern = rf"\*{{0,2}}{re.escape(label)}\*{{0,2}}[:\s]+(.+?)(?=\n\s*[-*#\n]|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()[:400]
    return ""


def _extract_overall_assessment(text: str) -> str:
    """Extract the overall portfolio assessment section."""
    m = re.search(
        r"OVERALL PORTFOLIO ASSESSMENT(.+?)(?=\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).strip()[:800]
    return ""
