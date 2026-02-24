import json
import os
from openai import OpenAI

def _get_client():
    return OpenAI(
        base_url=os.environ["AOAI_ENDPOINT"],
        api_key=os.environ["AOAI_API_KEY"],
    )


async def analyze_and_recommend(stocks: list, aggregated_findings: str) -> str:
    """
    Uses AOAI to generate buy/sell/hold recommendations for each stock.
    Streams output to console for real-time feedback.
    """
    portfolio_text = json.dumps(stocks, indent=2)

    prompt = f"""Based on the research below, provide clear investment recommendations.

PORTFOLIO:
{portfolio_text}

AGGREGATED RESEARCH FINDINGS:
{aggregated_findings}

For each stock provide:
- **Recommendation**: BUY / HOLD / SELL
- **Confidence**: High / Medium / Low
- **Reasoning**: 2-3 specific points from the research
- **Key Risk**: The main risk to this call

End with an OVERALL PORTFOLIO ASSESSMENT covering:
- Sector concentration
- Portfolio-level risk
- Top 1-2 actionable priorities
"""

    full_text = ""
    stream = _get_client().chat.completions.create(
        model=os.environ["AOAI_DEPLOYMENT"],
        max_tokens=4096,
        stream=True,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior portfolio analyst. Make direct, specific recommendations "
                    "grounded strictly in the provided research data. Do not speculate beyond what the data supports."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            print(delta, end="", flush=True)
            full_text += delta

    print()  # final newline after streaming
    return full_text
