"""
Web search tool with support for Tavily (default), Jina AI, and Brave Search
"""

from langchain_core.tools import tool
from typing import Dict, Any, Optional
import os


def _search_brave(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search using Brave Search API.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        Dictionary with search results in unified format
    """
    import requests

    api_key = os.getenv("WEB_SEARCH_API_KEY") or os.getenv("BRAVE_API_KEY")
    if not api_key:
        return {
            "error": "WEB_SEARCH_API_KEY or BRAVE_API_KEY not configured. Please set in .env file",
            "help": "Get API key at: https://api.search.brave.com/"
        }

    max_results = min(max_results, 20)

    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key.strip(),
        }
        params = {"q": query, "count": max_results}

        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        web = data.get("web", {})
        raw_results = web.get("results", [])[:max_results]

        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("description", ""),
                "description": r.get("description", ""),
            })

        return {
            "success": True,
            "provider": "brave",
            "query": query,
            "answer": web.get("query", {}).get("original", query),
            "results_count": len(results),
            "results": results,
            "message": f"✅ Found {len(results)} results for: {query}",
        }
    except requests.exceptions.RequestException as e:
        return {
            "error": f"Brave search failed: {str(e)}",
            "query": query,
        }
    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}",
            "query": query,
        }


def _search_tavily(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search using Tavily API (recommended - structured results with answers)

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        Dictionary with search results in Tavily format
    """
    try:
        from tavily import TavilyClient
    except ImportError:
        return {
            "error": "Tavily library not installed. Install with: pip install tavily-python",
            "fallback": "Consider using Jina provider instead"
        }

    # Get API key from multiple possible environment variables
    api_key = os.getenv("WEB_SEARCH_API_KEY") or os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {
            "error": "WEB_SEARCH_API_KEY or TAVILY_API_KEY not configured. Please set in .env file",
            "help": "Get API key at: https://tavily.com"
        }

    try:
        tavily_client = TavilyClient(api_key=api_key)
        response = tavily_client.search(query, max_results=max_results, include_answer=True)

        # Tavily returns structured data with answer, images, results
        return {
            "success": True,
            "provider": "tavily",
            "query": response.get("query", query),
            "answer": response.get("answer", ""),
            "results_count": len(response.get("results", [])),
            "results": response.get("results", []),
            "images": response.get("images", []),
            "response_time": response.get("response_time", ""),
            "message": f"✅ Found {len(response.get('results', []))} results for: {query}"
        }
    except Exception as e:
        return {
            "error": f"Tavily search failed: {str(e)}",
            "query": query
        }


def _search_jina(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search using Jina AI API (alternative - markdown-based results)

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        Dictionary with search results in Jina format
    """
    import requests

    # Get API key from multiple possible environment variables
    api_key = os.getenv("WEB_SEARCH_API_KEY") or os.getenv("JINA_API_KEY")
    if not api_key:
        return {
            "error": "WEB_SEARCH_API_KEY or JINA_API_KEY not configured. Please set in .env file",
            "help": "Get API key at: https://jina.ai"
        }

    # Limit max results
    max_results = min(max_results, 10)

    try:
        # Use Jina AI Search API
        url = "https://s.jina.ai/"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Retain-Images": "none"  # Don't return images for speed
        }

        # Make search request
        search_url = f"{url}{query}"
        response = requests.get(search_url, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse response (Jina returns markdown)
        content = response.text

        # Extract structured information (simplified parsing)
        results = []
        lines = content.split('\n')
        current_result = {}

        for line in lines[:max_results * 10]:  # Parse more lines to get max_results
            if line.startswith('##'):  # Title
                if current_result:
                    results.append(current_result)
                    if len(results) >= max_results:
                        break
                current_result = {"title": line.replace('##', '').strip()}
            elif line.startswith('URL:'):
                current_result["url"] = line.replace('URL:', '').strip()
            elif line and 'title' in current_result and 'snippet' not in current_result:
                current_result["snippet"] = line.strip()

        if current_result and len(results) < max_results:
            results.append(current_result)

        return {
            "success": True,
            "provider": "jina",
            "query": query,
            "results_count": len(results),
            "results": results,
            "message": f"✅ Found {len(results)} results for: {query}"
        }

    except requests.exceptions.RequestException as e:
        return {
            "error": f"Jina search failed: {str(e)}",
            "query": query
        }
    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}",
            "query": query
        }


@tool
def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the internet for information using Tavily AI search.

    Returns structured results with AI-generated answers.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Dictionary with search results:
        {
            "success": True,
            "provider": "tavily",
            "query": "...",
            "answer": "AI-generated answer",
            "results": [
                {
                    "title": "...",
                    "url": "...",
                    "content": "...",
                    "score": 0.95,
                    "favicon": "..."
                }
            ],
            "images": [...],
            "response_time": "1.23"
        }
    """
    if len(query) < 3:
        return {
            "error": "Query too short. Minimum 3 characters required.",
            "current_length": len(query)
        }

    # Determine provider from env var (not exposed to agent)
    provider = os.getenv("WEB_SEARCH_PROVIDER", "tavily").lower()

    # Route to appropriate provider
    if provider == "tavily":
        return _search_tavily(query, max_results)
    elif provider == "jina":
        return _search_jina(query, max_results)
    elif provider == "brave":
        return _search_brave(query, max_results)
    else:
        return {
            "error": f"Unknown search provider: {provider}",
            "valid_providers": ["tavily", "jina", "brave"],
            "help": "Set WEB_SEARCH_PROVIDER in .env to 'tavily', 'jina', or 'brave'"
        }


def _extract_tavily(urls: str, query: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract web page content using Tavily Extract API

    Args:
        urls: Single URL or comma-separated list of URLs to extract content from
        query: Optional query for reranking extracted content chunks

    Returns:
        Dictionary with extracted content
    """
    try:
        from tavily import TavilyClient
    except ImportError:
        return {
            "error": "Tavily library not installed. Install with: pip install tavily-python",
            "fallback": "Consider using alternative extraction method"
        }

    # read_webpage uses Tavily Extract only — prefer TAVILY_API_KEY so Brave/Jina search key is not sent to Tavily
    api_key = os.getenv("TAVILY_API_KEY") or os.getenv("WEB_SEARCH_API_KEY")
    if not api_key:
        return {
            "error": "TAVILY_API_KEY (or WEB_SEARCH_API_KEY) not configured. Please set in .env file",
            "help": "Get API key at: https://tavily.com"
        }

    try:
        tavily_client = TavilyClient(api_key=api_key)

        # Build extract parameters
        extract_params = {"urls": urls}
        if query:
            extract_params["query"] = query

        response = tavily_client.extract(**extract_params)

        return {
            "success": True,
            "provider": "tavily_extract",
            "urls": urls,
            "results": response.get("results", []),
            "failed_results": response.get("failed_results", []),
            "results_count": len(response.get("results", [])),
            "response_time": response.get("response_time", ""),
            "usage": response.get("usage", {}),
            "message": f"✅ Extracted content from {len(response.get('results', []))} URL(s)"
        }
    except Exception as e:
        err_msg = str(e)
        out = {"error": f"Tavily extract failed: {err_msg}", "urls": urls}
        if "unauthorized" in err_msg.lower() or "invalid api key" in err_msg.lower() or "missing" in err_msg.lower():
            out["hint"] = "Set TAVILY_API_KEY (or WEB_SEARCH_API_KEY) in .env with a valid key from https://tavily.com"
        return out


@tool
def read_webpage(urls: str, query: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract and read web page content from specified URLs using Tavily Extract.

    This tool extracts the main content from web pages, returning cleaned text
    in markdown format. Useful for reading articles, documentation, or any web content.

    Args:
        urls: Single URL or comma-separated list of URLs to extract content from
                 Example: "https://en.wikipedia.org/wiki/Artificial_intelligence"
                          "https://example.com/page1,https://example.com/page2"
        query: Optional query for reranking extracted content chunks based on relevance.
               When provided, chunks are reordered to be more relevant to the query.

    Returns:
        Dictionary with extracted web page content:
        {
            "success": True,
            "provider": "tavily_extract",
            "results": [
                {
                    "url": "...",
                    "raw_content": "Extracted markdown content...",
                    "images": [],
                    "favicon": "..."
                }
            ],
            "results_count": 1,
            "response_time": "0.02"
        }
    """
    if not urls or len(urls.strip()) < 8:
        return {
            "error": "Invalid URL. Please provide a valid URL (minimum 8 characters).",
            "provided": urls
        }

    return _extract_tavily(urls, query)
