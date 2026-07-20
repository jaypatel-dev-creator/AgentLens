import yfinance as yf
from langchain_core.tools import tool


@tool
def finance(ticker: str) -> str:
    """
    Get current stock price and basic info for a ticker symbol.
    Input must be a valid stock ticker symbol.
    Example: 'AAPL', 'GOOGL', 'TSLA', 'RELIANCE.NS'
    """
    try:
        stock = yf.Ticker(ticker) #convert ticker to stock object so that we can use .info
        info = stock.info

        price = info.get("currentPrice") or info.get("regularMarketPrice", "N/A") #either get current stock price or regular stock price if fallback to NA if both not available 
        name = info.get("longName", ticker) #full name of company default to ticker passed as parameter 
        currency = info.get("currency", "USD") #currency of stock default to USA 
        change = info.get("regularMarketChangePercent", 0) #
        direction = "▲" if change >= 0 else "▼"

        return (
            f"{name} ({ticker})\n"
            f"Price: {price} {currency}\n"
            f"Change: {direction} {abs(change):.2f}%"
        )
    except Exception as e:
        return f"Finance fetch error: {str(e)}"