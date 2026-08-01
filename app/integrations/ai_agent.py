from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def build_agent_graph(llm: BaseChatModel, tools: list[BaseTool]) -> CompiledStateGraph:
    """Compile a tool-calling agent graph.

    The graph alternates between an "agent" node (the LLM, with tools bound)
    and a "tools" node (executes whatever tool calls the LLM requested),
    looping until the LLM responds with plain text and no further tool
    calls. New tools only need to be added to the `tools` list passed in -
    the graph shape itself doesn't change.
    """
    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: MessagesState) -> dict[str, list[AIMessage]]:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()


def run_agent(
    graph: CompiledStateGraph,
    system_prompt: str,
    message: str,
    recursion_limit: int,
) -> tuple[str, list[str]]:
    """Run the agent graph for a single user message.

    Returns the final natural-language response along with the names of
    any tools the agent called along the way.
    """
    result = graph.invoke(
        {"messages": [SystemMessage(content=system_prompt), HumanMessage(content=message)]},
        config={"recursion_limit": recursion_limit},
    )

    messages = result["messages"]
    tools_used = [
        call["name"]
        for msg in messages
        if isinstance(msg, AIMessage)
        for call in (msg.tool_calls or [])
    ]

    return extract_text(messages[-1].content), tools_used


def extract_text(content: Any) -> str:
    """Reduce an LLM message's content to the text a user should see.

    Older models return a plain string, but Gemini 2.5+ returns a list of
    typed content blocks - including reasoning blocks carrying opaque
    `signature` payloads. str()-ing that list leaks a raw Python repr into
    the chat, so only the text blocks are kept and joined.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
        if parts:
            return "\n\n".join(parts).strip()

    # Nothing recognizable: prefer an empty string over exposing internals.
    return ""


def generate_structured_response(
    llm: BaseChatModel,
    system_prompt: str,
    user_prompt: str,
    output_schema: type[T],
) -> T:
    """Ask the LLM to produce a single response matching a Pydantic schema.

    Used for one-shot generation tasks where the required data is already
    known and gathered upfront (unlike the tool-calling agent above, which
    is for open-ended questions where the model must decide what to fetch).
    The model's native structured-output/JSON-schema mode enforces the
    shape, so the result is guaranteed to validate against output_schema.
    """
    structured_llm = llm.with_structured_output(output_schema)
    return structured_llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    )
