from langchain_core.tools import tool
from simpleeval import simple_eval


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression.
    Input must be a valid Python math expression string.
    Example: '2 + 2', '(10 * 5) / 2', '2 ** 8'
    """
    try:
        result = simple_eval(expression)
        return str(result)
    except Exception as e:
        return f"Calculation error: {str(e)}"