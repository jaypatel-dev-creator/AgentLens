from langchain_tavily import TavilySearch
from app.core.config import get_settings



def get_search_tool() -> TavilySearch:
    settings = get_settings()
    return TavilySearch(
        max_results=5,
        tavily_api_key=settings.tavily_api_key,
        search_depth="advanced",
        topic="general",
        days=7,
        description=(
            "Search the web for current information, news, recent events, "
            "or anything that requires up-to-date knowledge."
        ),
    )