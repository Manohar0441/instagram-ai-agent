import json
from typing import Any

_GROUNDING_RULES = """
Grounding rules (critical):
- Base every claim only on the JSON data provided below. Never invent a
  number, date, or trend that isn't present in it.
- If the data is too sparse to support a real conclusion (e.g. very few
  posts, or a metric that's null/missing), say so plainly instead of
  guessing - e.g. "there isn't enough posting history yet to identify a
  best time to post" rather than inventing a specific hour.
- Be concise and specific: reference actual figures from the data (e.g.
  "reach was 5,200, up 12%") rather than vague generalities.
- Write for the account owner, in a direct, practical tone.
"""

INSIGHTS_SYSTEM_PROMPT = (
    "You are an analytics assistant that writes short, data-grounded "
    "performance insights for an Instagram Business/Creator account."
    + _GROUNDING_RULES
)

RECOMMENDATIONS_SYSTEM_PROMPT = (
    "You are a social media strategist that turns an Instagram account's "
    "own historical performance data into practical, personalized "
    "recommendations. Recommendations must follow from patterns actually "
    "present in the data provided, not generic social-media advice."
    + _GROUNDING_RULES
)

REPORT_SYSTEM_PROMPT = (
    "You are an analytics assistant that writes concise performance reports "
    "for an Instagram Business/Creator account, covering what happened, "
    "what's working, what isn't, and what to do next."
    + _GROUNDING_RULES
)


def _format_context(context: dict[str, Any]) -> str:
    return json.dumps(context, indent=2, default=str)


def build_insights_user_prompt(context: dict[str, Any]) -> str:
    """Build the user prompt asking for the five insight narratives."""
    return (
        "Write five short insight paragraphs (2-4 sentences each) for this "
        "Instagram account, one each for: account_performance, "
        "content_performance, growth_trend, engagement_trend, and "
        "audience_behavior. For audience_behavior, base your observations "
        "only on engagement/profile-visit patterns and posting-time data "
        "present below (there is no demographic data available) - describe "
        "when the audience appears most responsive, not who they are.\n\n"
        f"Data:\n{_format_context(context)}"
    )


def build_recommendations_user_prompt(context: dict[str, Any]) -> str:
    """Build the user prompt asking for the recommendation narratives."""
    return (
        "Using this account's own historical performance data, produce: "
        "best_posting_times (a short paragraph, referencing the "
        "hour/weekday breakdown provided), recommended_content_formats (a "
        "short paragraph comparing the media types below), content_ideas "
        "(3-5 concrete post ideas inspired by what has performed well - "
        "reference the actual topics/captions of top content), "
        "posting_frequency (a short paragraph), and engagement_reach_tips "
        "(3-5 concrete, specific tips).\n\n"
        f"Data:\n{_format_context(context)}"
    )


def build_report_user_prompt(context: dict[str, Any]) -> str:
    """Build the user prompt asking for the report narratives."""
    period = context.get("period", "recent")
    return (
        f"Write a concise {period} performance report for this Instagram "
        "account: summary (2-4 sentences), key_strengths (2-4 bullet "
        "points), areas_for_improvement (2-4 bullet points), and "
        "actionable_next_steps (2-4 concrete, specific bullet points). The "
        "top- and bottom-performing content lists are provided for context "
        "- reference them by type/caption where relevant, but do not "
        "restate their raw numbers verbatim.\n\n"
        f"Data:\n{_format_context(context)}"
    )
