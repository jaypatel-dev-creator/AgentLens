import httpx
from langchain_core.tools import tool


@tool
async def weather(city: str) -> str:
    """
    Get current weather for a city.
    Input must be a city name string.
    Example: 'Mumbai', 'London', 'New York'
    """
    try:
        url = f"https://wttr.in/{city}?format=3"#format =3 returns weather in single line string formt 
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.text.strip()
    except Exception as e:
        return f"Weather fetch error: {str(e)}"