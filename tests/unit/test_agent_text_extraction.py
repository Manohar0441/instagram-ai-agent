import pytest

from app.integrations.ai_agent import extract_text

pytestmark = pytest.mark.unit


class TestPlainString:
    def test_a_string_passes_through(self):
        assert extract_text("Your reach was 5,000.") == "Your reach was 5,000."

    def test_an_empty_string_stays_empty(self):
        assert extract_text("") == ""


class TestContentBlocks:
    """Gemini 2.5+ returns typed blocks rather than a string. Before this was
    handled, the whole list was str()-ed straight into the chat window."""

    def test_a_single_text_block_is_unwrapped(self):
        content = [{"type": "text", "text": "Your reach was 5,000."}]
        assert extract_text(content) == "Your reach was 5,000."

    def test_reasoning_signatures_are_never_shown(self):
        """The `extras.signature` payload is opaque model internals - it must
        not reach the user, which is exactly what the raw repr leaked."""
        content = [
            {
                "type": "text",
                "text": "Your account has 1,175 followers.",
                "extras": {"signature": "Cr4JARFNMg+ERz5QzZtu7QAsRu6cWcuS3S4SCP"},
            }
        ]

        result = extract_text(content)

        assert result == "Your account has 1,175 followers."
        assert "signature" not in result
        assert "extras" not in result

    def test_thinking_blocks_are_dropped(self):
        content = [
            {"type": "thinking", "thinking": "The user wants follower counts..."},
            {"type": "text", "text": "You have 1,175 followers."},
        ]
        assert extract_text(content) == "You have 1,175 followers."

    def test_multiple_text_blocks_are_joined(self):
        content = [
            {"type": "text", "text": "First paragraph."},
            {"type": "text", "text": "Second paragraph."},
        ]
        assert extract_text(content) == "First paragraph.\n\nSecond paragraph."

    def test_bare_strings_in_a_list_are_kept(self):
        assert extract_text(["Just text."]) == "Just text."


class TestDegradedInput:
    """An unrecognized shape must produce nothing rather than a Python repr -
    showing internals is worse than showing an empty answer."""

    @pytest.mark.parametrize(
        "content",
        [[], None, {"unexpected": "shape"}, [{"type": "thinking", "thinking": "..."}]],
        ids=["empty_list", "none", "bare_dict", "only_thinking"],
    )
    def test_unrenderable_content_yields_empty_string(self, content):
        result = extract_text(content)

        assert result == ""
        assert "{" not in result
        assert "'type'" not in result
