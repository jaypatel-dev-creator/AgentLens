from functools import partial

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.reasoner import reasoner_node, build_llm_with_tools
from app.agent.nodes.tool_executor import tool_executor_node
from app.agent.tools.calculator import calculator
from app.agent.tools.search import get_search_tool
from app.agent.tools.weather import weather
from app.agent.tools.finance import finance
from app.agent.tools.datetime_tool import get_datetime
from app.agent.tools.document_search import make_document_search_tool
from app.core.logging import get_logger
from app.core.exceptions import AgentException

logger = get_logger(__name__)

_initialized: bool = False  # guards against get_graph_with_checkpointer being called before startup


def get_tools(user_id: str) -> list[BaseTool]:
    """
    Build the tool list for a specific request.
    Called per-request because document_search is a closure that captures user_id.
    All other tools are stateless singletons.
    """
    return [
        calculator,
        get_search_tool(),
        weather,
        finance,
        get_datetime,
        make_document_search_tool(user_id),  # factory — user_id baked into closure
    ]


def get_tools_by_name(tools: list[BaseTool]) -> dict[str, BaseTool]:
    return {tool.name: tool for tool in tools}


def should_use_tool(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tool_executor"
    return "end"


def compile_graph() -> None:
    """
    Startup validation — confirms tools, LLM binding, and graph topology
    are all constructable before the first request arrives.
    Sets _initialized so get_graph_with_checkpointer knows startup completed.

    Does NOT store a compiled graph — graph is built fresh per-request in
    get_graph_with_checkpointer() because nodes are user-scoped (document_search
    closure captures user_id and cannot be shared across requests).
    """
    global _initialized

    # Validate the full construction path with a real (non-placeholder) tool set.
    # Any import errors, bad config, or API key issues surface here at startup,
    # not mid-request.
    tools = get_tools("__startup__")
    tools_by_name = get_tools_by_name(tools)
    llm_with_tools = build_llm_with_tools(tools)

    # Validate graph topology — catches any LangGraph API changes or node errors
    builder = StateGraph(AgentState)
    builder.add_node("reasoner", partial(reasoner_node, llm_with_tools=llm_with_tools, tools=tools))
    builder.add_node("tool_executor", partial(tool_executor_node, tools_by_name=tools_by_name))
    builder.set_entry_point("reasoner")
    builder.add_conditional_edges("reasoner", should_use_tool, {"tool_executor": "tool_executor", "end": END})
    builder.add_edge("tool_executor", "reasoner")
    # builder.compile() intentionally NOT called — no checkpointer available at startup

    _initialized = True
    logger.info("LangGraph ReAct graph builder ready.")


def get_graph_with_checkpointer(checkpointer, user_id: str):
    """
    Build and compile a fresh graph per-request with:
    - Tool set scoped to this user (document_search closure captures user_id)
    - The request's checkpointer for STM persistence

    Fresh graph per-request is intentional — nodes are user-scoped and
    cannot be shared. StateGraph construction is cheap; the LLM API call is the bottleneck.
    """
    if not _initialized:
        raise AgentException("Graph not initialized. Call compile_graph() on startup.")

    tools = get_tools(user_id)
    tools_by_name = get_tools_by_name(tools)
    llm_with_tools = build_llm_with_tools(tools)

    graph = StateGraph(AgentState)
    graph.add_node("reasoner", partial(reasoner_node, llm_with_tools=llm_with_tools, tools=tools))
    graph.add_node("tool_executor", partial(tool_executor_node, tools_by_name=tools_by_name))
    graph.set_entry_point("reasoner")
    graph.add_conditional_edges("reasoner", should_use_tool, {"tool_executor": "tool_executor", "end": END})
    graph.add_edge("tool_executor", "reasoner")

    return graph.compile(checkpointer=checkpointer)