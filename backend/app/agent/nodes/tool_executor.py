import time
import json

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from opentelemetry import trace

from app.agent.state import AgentState
from app.core.logging import get_logger
import app.telemetry as tel

logger = get_logger(__name__)
_tracer = trace.get_tracer("agentlens.tool_executor")


async def tool_executor_node(state: AgentState, tools_by_name: dict[str, BaseTool]) -> dict:
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls
    results = []

    # Read session_id once for this node execution — same for all tool calls in this turn
    session_id = tel.current_session_id.get()

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_input = tool_call["args"]
        tool_id = tool_call["id"]

        tool: BaseTool = tools_by_name.get(tool_name)

        with _tracer.start_as_current_span(f"agentlens.tool.{tool_name}") as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("tool.input", json.dumps(tool_input, default=str)[:500])
            span.set_attribute("tool.found", tool is not None)

            if not tool:
                output = f"Tool '{tool_name}' not found."
                span.set_attribute("tool.success", False)
                span.set_attribute("tool.error", "tool_not_found")
                logger.warning("Tool '%s' not found — possible hallucination", tool_name)

                # ── Per-session tool recording (not found) ───────────────────
                tel.record_session_tool_call(session_id, tool_name, False, 0.0)
            else:
                t0 = time.perf_counter()
                try:
                    output = await tool.ainvoke(tool_input)
                    output = str(output)
                    latency_ms = (time.perf_counter() - t0) * 1000

                    span.set_attribute("tool.success", True)
                    span.set_attribute("tool.output_preview", output[:500])
                    span.set_attribute("tool.latency_ms", round(latency_ms, 2))

                    if tel.tool_call_counter:
                        tel.tool_call_counter.add(
                            1,
                            {"tool.name": tool_name, "tool.success": "true"},
                        )

                    # ── Per-session tool recording (success) ─────────────────
                    tel.record_session_tool_call(session_id, tool_name, True, latency_ms)

                    logger.info(
                        "Tool %s OK — latency: %.1fms | output: %s",
                        tool_name,
                        latency_ms,
                        output[:100],
                    )

                except Exception as e:
                    latency_ms = (time.perf_counter() - t0) * 1000
                    output = f"Tool execution error: {str(e)}"

                    span.set_attribute("tool.success", False)
                    span.set_attribute("tool.error", str(e))
                    span.set_attribute("tool.latency_ms", round(latency_ms, 2))
                    span.record_exception(e)

                    if tel.tool_call_counter:
                        tel.tool_call_counter.add(
                            1,
                            {"tool.name": tool_name, "tool.success": "false"},
                        )

                    # ── Per-session tool recording (failure) ─────────────────
                    tel.record_session_tool_call(session_id, tool_name, False, latency_ms)

                    logger.error("Tool %s failed — %s", tool_name, str(e))

        results.append(
            ToolMessage(
                content=output,
                tool_call_id=tool_id,
            )
        )

    return {"messages": results}