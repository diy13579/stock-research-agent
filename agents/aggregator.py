import json
import os
from openai import OpenAI

def _get_client():
    return OpenAI(
        base_url=os.environ["AOAI_ENDPOINT"],
        api_key=os.environ["AOAI_API_KEY"],
    )


async def aggregate_research(stocks: list, research_results: list) -> str:
    """
    Uses AOAI to aggregate all per-stock research into macro themes,
    cross-stock correlations, and a unified findings summary.
    """
    research_text = json.dumps(research_results, indent=2)

    response = _get_client().chat.completions.create(
        model=os.environ["AOAI_DEPLOYMENT"],
        max_tokens=4096,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a financial research aggregator. Analyze raw per-stock research data and produce a "
                    "structured summary covering:\n"
                    "1. Macro themes and market trends affecting the portfolio\n"
                    "2. Cross-stock correlations and sector concentration risks\n"
                    "3. Most impactful recent news items\n"
                    "4. Overall analyst sentiment across all holdings\n"
                    "Be concise, specific, and grounded in the data provided."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Here is the research data for each stock in the portfolio:\n\n"
                    f"{research_text}\n\n"
                    "Produce a structured aggregated findings report."
                ),
            },
        ],
    )

    return response.choices[0].message.content
