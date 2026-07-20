from datetime import datetime, timezone
from langchain_core.tools import tool


@tool
def get_datetime(query: str = "") -> str:
    """
    Get the current date and time in UTC.
    Use this whenever the user asks about the current date, time, or day.
    Input can be empty string or any related query.
    """
    now = datetime.now(timezone.utc)#returns current time in utc format and in datetime object .
    return (
        f"Current UTC date and time:\n"
        f"Date: {now.strftime('%A, %B %d, %Y')}\n" #formatting 
        f"Time: {now.strftime('%H:%M:%S')} UTC"
    )