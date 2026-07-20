from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages #reducer
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    
    messages: Annotated[list[BaseMessage], add_messages]
    ltm_context: str
    doc_context: str  