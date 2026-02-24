import yfinance as yf


def get_stock_context(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        hist = stock.history(period="1mo")

        current_price = float(hist["Close"].iloc[-1]) if not hist.empty else None
        month_ago_price = float(hist["Close"].iloc[0]) if not hist.empty else None
        price_change_pct = (
            round((current_price - month_ago_price) / month_ago_price * 100, 2)
            if current_price and month_ago_price
            else None
        )

        return {
            "current_price": round(current_price, 2) if current_price else None,
            "price_change_1mo_pct": price_change_pct,
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "pe_ratio": info.get("trailingPE"),
            "market_cap_b": round(info["marketCap"] / 1e9, 1) if info.get("marketCap") else None,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
    except Exception as e:
        return {"error": str(e)}
