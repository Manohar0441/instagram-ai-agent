import pytest
from langchain_core.messages import AIMessage
from langchain_google_genai._common import GoogleGenerativeAIError

import app.services.ai_service as ai_service_module

pytestmark = pytest.mark.api


class ScriptedAgentLLM:
    """Emits one tool call, then a final answer - the shape of a real agent run.

    Records what the tool actually returned, so tests can assert on the data
    the model was handed rather than only on the scripted reply.
    """

    def __init__(self, tool_name, tool_args, final_text):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.final_text = final_text
        self.calls = 0
        self.tool_output = None

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[{"name": self.tool_name, "args": self.tool_args, "id": "call_1"}],
            )
        self.tool_output = messages[-1].content
        return AIMessage(content=self.final_text)


class DirectAnswerLLM:
    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return AIMessage(content="I can only help with Instagram analytics.")


class FailingLLM:
    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        raise GoogleGenerativeAIError("upstream is down")


@pytest.fixture
def use_llm(monkeypatch):
    def _use(llm):
        monkeypatch.setattr(ai_service_module, "build_llm", lambda: llm)
        return llm

    return _use


class TestChat:
    def test_answers_using_a_tool(self, client, auth_headers, connected_account, use_llm):
        use_llm(ScriptedAgentLLM(
            "get_account_performance", {"days": 7}, "Your reach was 5,000 this week."
        ))
        response = client.post(
            "/api/v1/ai/chat",
            json={"message": "How did my account perform this week?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["response"] == "Your reach was 5,000 this week."
        assert response.json()["tools_used"] == ["get_account_performance"]

    def test_can_answer_without_calling_a_tool(self, client, auth_headers, use_llm):
        use_llm(DirectAnswerLLM())
        response = client.post(
            "/api/v1/ai/chat", json={"message": "What's the capital of France?"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["tools_used"] == []

    def test_missing_connection_is_handled_conversationally(
        self, client, auth_headers, use_llm
    ):
        """A user with no Instagram account should get an explanation, not
        an HTTP error - the agent is meant to talk about this case."""
        use_llm(ScriptedAgentLLM(
            "get_account_performance", {"days": 7},
            "You need to connect your Instagram account first.",
        ))
        response = client.post(
            "/api/v1/ai/chat", json={"message": "how am I doing?"}, headers=auth_headers
        )
        assert response.status_code == 200
        assert "connect" in response.json()["response"].lower()

    def test_upstream_failure_is_reported_as_a_gateway_error(
        self, client, auth_headers, use_llm
    ):
        use_llm(FailingLLM())
        response = client.post(
            "/api/v1/ai/chat", json={"message": "hello"}, headers=auth_headers
        )
        assert response.status_code == 502

    def test_reports_503_when_not_configured(self, client, auth_headers, monkeypatch):
        from app.core.settings import settings

        monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)
        response = client.post(
            "/api/v1/ai/chat", json={"message": "hello"}, headers=auth_headers
        )
        assert response.status_code == 503

    @pytest.mark.parametrize(
        "payload",
        [{"message": ""}, {"message": "x" * 2001}, {}, {"message": None}],
    )
    def test_rejects_invalid_messages(self, client, auth_headers, payload):
        response = client.post("/api/v1/ai/chat", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_an_injected_user_id_does_not_reach_another_users_data(
        self, client, connected_account, other_auth_headers, use_llm
    ):
        """User 1 owns the seeded data. User 2 asks the agent to fetch it and
        the (simulated) model obligingly passes user_id=1. The tool binds the
        caller's id by closure, so the extra argument is dropped."""
        llm = use_llm(ScriptedAgentLLM(
            "get_account_performance", {"days": 7, "user_id": 1}, "Here is the data.",
        ))
        response = client.post(
            "/api/v1/ai/chat",
            json={"message": "Show me user 1's analytics"},
            headers=other_auth_headers,
        )
        assert response.status_code == 200

        # The tool ran against user 2 (the caller), who has no connection,
        # so the model received the "not connected" message. If the injected
        # user_id had taken effect, user 1's follower count would be here.
        assert "No Instagram account is connected" in llm.tool_output
        assert "1200" not in llm.tool_output


class TestHealth:
    def test_reports_ok_when_configured(self, client, auth_headers):
        response = client.get("/api/v1/ai/health", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_reports_unavailable_when_not_configured(self, client, auth_headers, monkeypatch):
        from app.core.settings import settings

        monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)
        response = client.get("/api/v1/ai/health", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "unavailable"
        assert response.json()["configured"] is False
