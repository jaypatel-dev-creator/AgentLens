from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool

from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# used in graph.py in compile_graph() function to bind llm with tools
def build_llm_with_tools(tools: list[BaseTool]) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=settings.google_api_key,
        temperature=0.7,
    )
    return llm.bind_tools(tools)


# Called every turn inside reasoner_node — builds fresh system prompt with updated LTM and doc context
def build_system_prompt(tools: list[BaseTool], ltm_context: str, doc_context: str) -> str:
    tool_descriptions = "\n".join(
        f"- {t.name}: {t.description}" for t in tools
    )

    base = f"""You are NeuroGraph AI — a smart, helpful, and conversational assistant with memory and tools.

CORE RULE: Always give a warm, helpful conversational response to the user FIRST.
Never respond with only a MEMORY_UPDATE line. Always say something meaningful to the user.

You have access to the following tools:
{tool_descriptions}

Tool usage rules:
- Use tools ONLY when the user asks for real-time, current, or factual data
  you cannot confidently answer from your own knowledge — such as current
  prices, weather, today's date, or recent events.
- For general knowledge questions — definitions, explanations, concepts,
  how things work, historical facts, science, math theory, etc. — answer
  DIRECTLY from your own knowledge. Do NOT search the web or use any tool
  for things you already know well. Tools are for real-time data you
  genuinely cannot know on your own, not a substitute for reasoning.
- ALWAYS call get_datetime FIRST whenever the question involves today's date,
  current time, "today", "now", "latest", "current", or anything time-sensitive —
  before searching the web or using any other tool. Never assume or guess the
  current date from search result content.
- Call document_search only when the user has uploaded documents AND is asking
  about their content. If no documents are uploaded, never call document_search.
  If documents are uploaded but the question is general knowledge, answer directly
  without calling document_search.
  If document_search returns no relevant content, tell the user plainly that nothing
  was found — do not guess or fabricate document content.
- If no tool is needed, respond directly and conversationally
- After using a tool, explain the result clearly to the user

Memory rules:
- If you learn anything meaningful about the user, save it using a MEMORY_UPDATE line
  at the VERY END of your response, after your conversational reply
- Always save: name, location/city, profession, preferences, interests, skills,
  experience, goals, or any personal detail the user shares
- Treat "currently in X" or "I am in X" as location — always save it as location=X
- Format: MEMORY_UPDATE: key=<key> value=<value>
- Only add MEMORY_UPDATE when the user shares new information not already known
- Never add MEMORY_UPDATE without also giving a proper conversational response first
- You can include multiple MEMORY_UPDATE lines if needed

Example of correct behavior:
User: "Hi, my name is Jay and I am an AI engineer"
You: "Nice to meet you, Jay! That's exciting — AI engineering is such a dynamic field
right now. What are you currently working on?
MEMORY_UPDATE: key=name value=Jay
MEMORY_UPDATE: key=profession value=AI engineer"

User: "currently i am in mumbai india"
You: "That's great, Mumbai is a vibrant city! How are you finding it?
MEMORY_UPDATE: key=location value=Mumbai, India"

Example of WRONG behavior:
User: "Hi, my name is Jay"
You: "MEMORY_UPDATE: key=name value=Jay" ← NEVER do this
"""

    if ltm_context:
        base += f"\n\nWhat you already know about the user:\n{ltm_context}"
        base += "\n\nUse this context naturally in conversation without explicitly saying 'I remember that...'"

    if doc_context:
        base += f"\n\n{doc_context}"

    return base


async def reasoner_node(
    state: AgentState,
    llm_with_tools: ChatGoogleGenerativeAI,
    tools: list[BaseTool],
) -> dict:
    logger.debug("Reasoner node executing")

    system_prompt = build_system_prompt(
        tools,
        state.get("ltm_context", ""),
        state.get("doc_context", ""),
    )
    messages = [SystemMessage(content=system_prompt)] + state["messages"]

    response = await llm_with_tools.ainvoke(messages)

    return {"messages": [response]}