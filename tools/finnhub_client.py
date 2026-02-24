import os
from datetime import datetime, timedelta
import finnhub


def _client():
    return finnhub.Client(api_key=os.environ["FINNHUB_API_KEY"])


def get_company_news(ticker: str, days: int = 7) -> list[dict]:
    end = datetime.now()
    start = end - timedelta(days=days)
    try:
        news = _client().company_news(
            ticker,
            _from=start.strftime("%Y-%m-%d"),
            to=end.strftime("%Y-%m-%d"),
        )
        return [
            {
                "headline": item.get("headline", ""),
                "summary": item.get("summary", "")[:400],
                "source": item.get("source", ""),
                "datetime": datetime.fromtimestamp(item["datetime"]).strftime("%Y-%m-%d")
                if item.get("datetime")
                else "",
            }
            for item in (news or [])[:6]
        ]
    except Exception as e:
        return [{"error": str(e)}]


def get_analyst_recommendations(ticker: str) -> dict:
    try:
        recs = _client().recommendation_trends(ticker)
        if not recs:
            return {}
        latest = recs[0]
        return {
            "period": latest.get("period", ""),
            "strong_buy": latest.get("strongBuy", 0),
            "buy": latest.get("buy", 0),
            "hold": latest.get("hold", 0),
            "sell": latest.get("sell", 0),
            "strong_sell": latest.get("strongSell", 0),
        }
    except Exception as e:
        return {"error": str(e)}
