"""Deterministic analysis of a user's chat question.

Runs before the agent is invoked, so an out-of-scope question costs nothing
and cannot reach the model at all. Everything here is pure string matching:
no LLM call, no I/O, and therefore nothing a crafted question can influence
beyond its own classification.
"""
import re
from dataclasses import dataclass, field
from typing import Literal

Intent = Literal[
    "summary",
    "account_performance",
    "content_performance",
    "growth",
    "engagement",
    "reach",
    "audience",
    "best_content",
    "worst_content",
    "comparison",
    "posting_time",
    "recommendation",
    "unknown",
]

SortOrder = Literal["top", "bottom"]

# Vocabulary that marks a question as being about this account's analytics.
# Deliberately broad: a false negative (refusing a real question) is far more
# annoying than a false positive, which the agent's own prompt still handles.
_IN_SCOPE_TERMS = frozenset({
    "account", "analytics", "audience", "average", "bio", "caption",
    "carousel", "comment", "comments", "compare", "comparison", "content",
    "engagement", "follower", "followers", "following", "grow", "growth",
    "hashtag", "impression", "impressions", "insight", "insights", "instagram",
    "like", "likes", "media", "metric", "metrics", "performance", "performed",
    "performing", "post", "posted", "posting", "posts", "profile", "reach",
    "recommend", "recommendation", "reel", "reels", "save", "saved", "saves",
    "share", "shares", "statistics", "stats", "story", "stories", "strategy",
    "trend", "trends", "video", "videos", "view", "views", "visits",
})

# High-confidence signals that a question belongs to another domain. Only
# consulted when no in-scope vocabulary is present at all.
_OUT_OF_SCOPE_PATTERNS = (
    r"\b(write|generate|debug|fix|refactor)\s+(me\s+)?(a\s+|some\s+)?(python|java|c\+\+|sql|code|script|function|program)\b",
    r"\btell me a (joke|story|poem)\b",
    r"\b(weather|forecast|temperature)\s+(in|for|today|tomorrow)\b",
    r"\b(stock|share)\s+(price|market)\b",
    r"\b(bitcoin|crypto|ethereum)\b",
    r"\bwho (is|was) the (president|prime minister|ceo)\b",
    r"\b(recipe|cook|bake)\b",
    r"\btranslate\b",
    r"^\s*[\d\s+\-*/().]+\s*=?\s*\??\s*$",  # a bare arithmetic expression
)

# Short conversational continuations. These carry no vocabulary of their own
# but are valid follow-ups to a previous answer ("yes", "what about last
# month?"), so they must never be refused.
_CONTINUATION_PATTERNS = (
    r"^\s*(yes|yep|yeah|yup|sure|ok|okay|please|go ahead|do it|continue)\b",
    r"^\s*(no|nope|nah)\b",
    r"^\s*(what|how)\s+about\b",
    r"^\s*(and|also|then)\b",
    r"^\s*(why|why\s+not|explain|elaborate|more|tell me more|details?)\b",
    r"^\s*(show|give)\s+me\s+more\b",
)

REFUSAL_MESSAGE = (
    "I'm an Instagram analytics assistant, so I can only help with questions "
    "about your connected account - your reach, engagement, followers, posts, "
    "audience, and content strategy. Try asking something like \"how did my "
    "account perform this week?\" or \"which post got the most engagement?\""
)

# Ordered most-specific first: the first matching pattern wins, so
# "compare this month with last month" classifies as a comparison rather
# than being caught by the broader "month" of a growth question.
_INTENT_PATTERNS: tuple[tuple[Intent, str], ...] = (
    ("comparison", r"\b(compare|comparison|versus|vs\.?|difference between|better than)\b"),
    # Before best/worst: "best time to post" is a scheduling question, and
    # would otherwise be captured by the bare "best" of a ranking question.
    ("posting_time", r"\b(when should|best time|posting time|what time|schedule)\b"),
    ("worst_content", r"\b(worst|lowest|least|underperform\w*|poorest|flop\w*)\b"),
    ("best_content", r"\b(best|top|highest|most (engag\w+|liked|viewed|popular)|winner)\b"),
    ("recommendation", r"\b(recommend\w*|suggest\w*|should i|advice|ideas?|improve|strategy|what to post)\b"),
    ("growth", r"\b(grow\w*|gain\w*|lost|losing|new followers|follower (count|change))\b"),
    ("audience", r"\b(audience|demographic\w*|who (follows|are my)|profile visits?)\b"),
    ("engagement", r"\b(engagement|engaged|likes?|comments?|saves?|shares?)\b"),
    ("reach", r"\b(reach|impressions?|views?|seen)\b"),
    ("content_performance", r"\b(posts?|reels?|stor(y|ies)|videos?|carousels?|content)\b"),
    ("account_performance", r"\b(account|performance|how (am i|are we) doing|metrics|stats)\b"),
    ("summary", r"\b(summar\w*|overview|snapshot|how.s it going|report)\b"),
)

# Relative time expressions mapped to a lookback window in days. Ordered
# longest-phrase-first so "last 3 months" isn't matched by "last month".
_TIME_RANGES: tuple[tuple[str, int], ...] = (
    (r"\blast\s+(?:12\s+months|year)\b", 365),
    (r"\bpast\s+year\b", 365),
    (r"\blast\s+6\s+months\b", 180),
    (r"\blast\s+(?:3\s+months|quarter)\b", 90),
    (r"\bpast\s+90\s+days\b", 90),
    (r"\blast\s+30\s+days\b", 30),
    (r"\bpast\s+month\b", 30),
    (r"\blast\s+month\b", 30),
    (r"\bthis\s+month\b", 30),
    (r"\blast\s+(?:2\s+weeks|fortnight)\b", 14),
    (r"\blast\s+week\b", 7),
    (r"\bthis\s+week\b", 7),
    (r"\bpast\s+7\s+days\b", 7),
    (r"\byesterday\b", 1),
    (r"\btoday\b", 1),
)

_METRIC_TERMS: tuple[tuple[str, str], ...] = (
    ("engagement_rate", r"\bengagement\b"),
    ("reach", r"\breach\b"),
    ("impressions", r"\bimpressions?\b"),
    ("likes", r"\blikes?\b"),
    ("comments", r"\bcomments?\b"),
)

_MEDIA_TYPES: tuple[tuple[str, str], ...] = (
    ("REELS", r"\breels?\b"),
    ("VIDEO", r"\bvideos?\b"),
    ("CAROUSEL_ALBUM", r"\bcarousels?\b"),
    ("IMAGE", r"\b(images?|photos?|pictures?)\b"),
)


@dataclass(frozen=True)
class QueryAnalysis:
    """What a deterministic read of the user's question can establish."""

    in_scope: bool
    intent: Intent = "unknown"
    days: int | None = None
    metrics: tuple[str, ...] = field(default_factory=tuple)
    media_type: str | None = None
    sort_order: SortOrder | None = None

    def as_hint(self) -> str:
        """Render the extracted entities as a note for the agent's prompt.

        This is guidance, not instruction: the agent still chooses its own
        tools. It exists so a question like "last month" reliably produces a
        30-day window instead of the model's default guess.
        """
        parts: list[str] = [f"intent={self.intent}"]
        if self.days is not None:
            parts.append(f"lookback_days={self.days}")
        if self.metrics:
            parts.append(f"metrics={','.join(self.metrics)}")
        if self.media_type:
            parts.append(f"media_type={self.media_type}")
        if self.sort_order:
            parts.append(f"order={self.sort_order}")
        return " ".join(parts)


def analyze_query(message: str) -> QueryAnalysis:
    """Classify a chat message before it reaches the model."""
    text = message.lower().strip()

    if not _is_in_scope(text):
        return QueryAnalysis(in_scope=False)

    intent = _detect_intent(text)
    return QueryAnalysis(
        in_scope=True,
        intent=intent,
        days=_extract_days(text),
        metrics=_extract_metrics(text),
        media_type=_extract_media_type(text),
        sort_order=_extract_sort_order(text, intent),
    )


def _is_in_scope(text: str) -> bool:
    """Decide whether a question is about this account's analytics.

    Biased towards allowing: only a question with no analytics vocabulary at
    all *and* a clear other-domain signal is refused. Anything ambiguous
    reaches the agent, whose own prompt declines politely with context.
    """
    if any(re.search(pattern, text) for pattern in _CONTINUATION_PATTERNS):
        return True

    words = set(re.findall(r"[a-z]+", text))
    if words & _IN_SCOPE_TERMS:
        return True

    if any(re.search(pattern, text) for pattern in _OUT_OF_SCOPE_PATTERNS):
        return False

    # No signal either way - let the agent handle it conversationally.
    return True


def _detect_intent(text: str) -> Intent:
    for intent, pattern in _INTENT_PATTERNS:
        if re.search(pattern, text):
            return intent
    return "unknown"


def _extract_days(text: str) -> int | None:
    for pattern, days in _TIME_RANGES:
        if re.search(pattern, text):
            return days

    # An explicit "last N days/weeks/months" beats the fixed phrases above.
    match = re.search(r"\blast\s+(\d{1,3})\s+(day|week|month)s?\b", text)
    if match:
        count, unit = int(match.group(1)), match.group(2)
        multiplier = {"day": 1, "week": 7, "month": 30}[unit]
        return min(count * multiplier, 365)

    return None


def _extract_metrics(text: str) -> tuple[str, ...]:
    return tuple(metric for metric, pattern in _METRIC_TERMS if re.search(pattern, text))


def _extract_media_type(text: str) -> str | None:
    for media_type, pattern in _MEDIA_TYPES:
        if re.search(pattern, text):
            return media_type
    return None


def _extract_sort_order(text: str, intent: Intent) -> SortOrder | None:
    if intent == "worst_content":
        return "bottom"
    if intent == "best_content":
        return "top"
    return None
