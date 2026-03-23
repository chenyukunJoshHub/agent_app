"""
Tools package for Multi-Tool AI Agent.

Provides a collection of tools that the agent can use to interact with external systems.
Also provides ToolRegistry for centralized tool management.

Available tools:
- fetch_url: HTTP GET requests
- web_search: Web search via Tavily API
- read_file: Secure file reading with path validation
- send_email: Email sending with HIL support (mock)
- token_counter: Token counting for LLM models
- csv_analyze: CSV file analysis with basic statistics
"""
from app.tools.csv_analyze import csv_analyze
from app.tools.fetch import fetch_url
from app.tools.file import read_file
from app.tools.registry import ToolRegistry
from app.tools.search import web_search
from app.tools.send_email import send_email
from app.tools.token import token_counter

__all__ = [
    "fetch_url",
    "web_search",
    "read_file",
    "send_email",
    "token_counter",
    "csv_analyze",
    "ToolRegistry",
]
