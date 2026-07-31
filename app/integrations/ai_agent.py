from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition


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

    final_content = messages[-1].content
    response_text = final_content if isinstance(final_content, str) else str(final_content)
    return response_text, tools_used
