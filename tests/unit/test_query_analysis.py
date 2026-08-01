import pytest

from app.services.query_analysis import analyze_query

pytestmark = pytest.mark.unit


class TestScope:
    @pytest.mark.parametrize(
        "message",
        [
            "Show my followers",
            "Which post performed best?",
            "What's my engagement rate?",
            "How many followers did I gain last month?",
            "Compare this month with last month",
            "Give me growth recommendations",
            "What should I post tomorrow?",
            "how am I doing?",
        ],
    )
    def test_analytics_questions_are_in_scope(self, message):
        assert analyze_query(message).in_scope is True

    @pytest.mark.parametrize(
        "message",
        [
            "Tell me a joke",
            "Write me a Python script to sort a list",
            "What's the weather in Chennai today?",
            "Who is the president of France?",
            "2 + 2 * 8",
            "Give me a recipe for pasta",
            "What's the bitcoin price?",
        ],
    )
    def test_other_domains_are_refused(self, message):
        assert analyze_query(message).in_scope is False

    @pytest.mark.parametrize(
        "message",
        ["yes", "yeah do it", "what about last month?", "why?", "tell me more", "and reels?"],
    )
    def test_short_follow_ups_are_never_refused(self, message):
        """These carry no analytics vocabulary of their own but continue a
        previous answer - refusing them would break every conversation at
        the second turn."""
        assert analyze_query(message).in_scope is True

    def test_an_ambiguous_question_reaches_the_agent(self):
        """With no signal either way, the agent's own prompt declines more
        gracefully than a blunt keyword refusal would."""
        assert analyze_query("what do you think?").in_scope is True


class TestIntent:
    @pytest.mark.parametrize(
        "message, expected",
        [
            ("Compare this month with last month", "comparison"),
            ("Which post performed worst?", "worst_content"),
            ("What was my best performing reel?", "best_content"),
            ("What should I post next?", "recommendation"),
            ("When is the best time to post?", "posting_time"),
            ("How many followers did I gain?", "growth"),
            ("Tell me about my audience", "audience"),
            ("What's my engagement rate?", "engagement"),
            ("How much reach did I get?", "reach"),
            ("Give me an overview", "summary"),
        ],
    )
    def test_intent_is_detected(self, message, expected):
        assert analyze_query(message).intent == expected

    def test_comparison_wins_over_the_time_word_it_contains(self):
        """'compare ... last month' must not fall through to a growth or
        summary intent just because it mentions a month."""
        assert analyze_query("compare last month to this month").intent == "comparison"

    def test_worst_is_not_swallowed_by_best(self):
        assert analyze_query("show my lowest performing posts").intent == "worst_content"


class TestTimeRange:
    @pytest.mark.parametrize(
        "message, expected_days",
        [
            ("engagement today", 1),
            ("reach yesterday", 1),
            ("posts this week", 7),
            ("reach last week", 7),
            ("engagement this month", 30),
            ("followers last month", 30),
            ("reach last 30 days", 30),
            ("growth last quarter", 90),
            ("reach last 6 months", 180),
            ("engagement last year", 365),
        ],
    )
    def test_relative_ranges_map_to_days(self, message, expected_days):
        assert analyze_query(message).days == expected_days

    @pytest.mark.parametrize(
        "message, expected_days",
        [("reach last 5 days", 5), ("engagement last 3 weeks", 21), ("posts last 2 months", 60)],
    )
    def test_explicit_counts_are_parsed(self, message, expected_days):
        assert analyze_query(message).days == expected_days

    def test_an_absurd_range_is_capped_at_a_year(self):
        assert analyze_query("reach last 99 months").days == 365

    def test_no_time_reference_leaves_the_window_unset(self):
        """Unset means the agent applies its documented default rather than
        this layer inventing one."""
        assert analyze_query("what is my engagement rate?").days is None


class TestEntities:
    def test_metrics_are_extracted(self):
        analysis = analyze_query("show my likes and comments")
        assert "likes" in analysis.metrics
        assert "comments" in analysis.metrics

    @pytest.mark.parametrize(
        "message, expected",
        [
            ("my best reel", "REELS"),
            ("how are my videos doing", "VIDEO"),
            ("carousel performance", "CAROUSEL_ALBUM"),
            ("which photos did best", "IMAGE"),
        ],
    )
    def test_media_type_is_extracted(self, message, expected):
        assert analyze_query(message).media_type == expected

    def test_sort_order_follows_the_intent(self):
        assert analyze_query("my best post").sort_order == "top"
        assert analyze_query("my worst post").sort_order == "bottom"
        assert analyze_query("my engagement rate").sort_order is None


class TestHint:
    def test_the_hint_carries_what_was_parsed(self):
        hint = analyze_query("what was my best reel last month?").as_hint()

        assert "intent=best_content" in hint
        assert "lookback_days=30" in hint
        assert "media_type=REELS" in hint
        assert "order=top" in hint

    def test_unset_entities_are_omitted_rather_than_guessed(self):
        hint = analyze_query("how is my account doing?").as_hint()

        assert "lookback_days" not in hint
        assert "media_type" not in hint
