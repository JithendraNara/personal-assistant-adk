"""
Web and research tools for the research_agent.

NOTE: Functions marked with "# REAL API" comments show where to integrate
live API calls. Mock data is returned when keys are not configured.
"""

import json
import os
from datetime import datetime
from typing import Optional

# REAL API: from serpapi import GoogleSearch
# REAL API: import httpx

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")


def web_search(query: str, num_results: int = 5) -> dict:
    """
    Search the web for information on a given query.

    Args:
        query: The search query string.
        num_results: Number of results to return (1-10).

    Returns:
        A dict with 'status', 'query', 'results' (list of title/url/snippet dicts).
    """
    num_results = max(1, min(10, num_results))

    if SERPAPI_KEY:
        # REAL API: Uncomment and install serpapi package
        # from serpapi import GoogleSearch
        # search = GoogleSearch({"q": query, "num": num_results, "api_key": SERPAPI_KEY})
        # raw = search.get_dict()
        # results = [
        #     {"title": r.get("title"), "url": r.get("link"), "snippet": r.get("snippet")}
        #     for r in raw.get("organic_results", [])
        # ]
        # return {"status": "success", "query": query, "results": results}
        pass

    # Mock response — replace with real API call above
    mock_results = [
        {
            "title": f"Result {i + 1} for: {query}",
            "url": f"https://example.com/result-{i + 1}",
            "snippet": (
                f"This is a placeholder snippet for result {i + 1} about '{query}'. "
                "Configure SERPAPI_KEY in .env to get real search results."
            ),
        }
        for i in range(num_results)
    ]

    return {
        "status": "success",
        "query": query,
        "source": "mock — configure SERPAPI_KEY for live results",
        "results": mock_results,
        "timestamp": datetime.utcnow().isoformat(),
    }


def fetch_webpage_summary(url: str, focus: Optional[str] = None) -> dict:
    """
    Fetch a webpage and return a summary of its content.

    Args:
        url: The URL to fetch and summarize.
        focus: Optional topic to focus the summary on (e.g. 'pricing', 'features').

    Returns:
        A dict with 'status', 'url', 'title', 'summary', 'word_count'.
    """
    if not url.startswith(("http://", "https://")):
        return {"status": "error", "message": "Invalid URL — must start with http:// or https://"}

    # REAL API: Use httpx or requests to fetch + pass to LLM for summarization
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(url, follow_redirects=True, timeout=10)
    #     text = response.text[:50000]  # Truncate for LLM context
    # Then summarize `text` with an LLM call

    focus_note = f" with a focus on: {focus}" if focus else ""
    return {
        "status": "success",
        "url": url,
        "title": f"Page at {url}",
        "summary": (
            f"[Mock summary{focus_note}] Configure real HTTP fetching in web_tools.py "
            "to get actual page content. The fetch_webpage_summary function supports "
            "optional focus topics to extract specific information from pages."
        ),
        "word_count": 0,
        "note": "Mock response — implement real fetching with httpx",
    }


def get_news_headlines(
    topic: str,
    sources: Optional[str] = None,
    max_articles: int = 5,
) -> dict:
    """
    Retrieve recent news headlines for a given topic.

    Args:
        topic: Topic or keywords to search news for (e.g. 'Python 3.13', 'Dallas Cowboys').
        sources: Optional comma-separated news source domains (e.g. 'bbc.co.uk,reuters.com').
        max_articles: Number of articles to return (1-10).

    Returns:
        A dict with 'status', 'topic', 'articles' (list of title/url/published_at/source dicts).
    """
    max_articles = max(1, min(10, max_articles))

    if NEWS_API_KEY:
        # REAL API: newsapi.org
        # import httpx
        # params = {"q": topic, "pageSize": max_articles, "apiKey": NEWS_API_KEY}
        # if sources:
        #     params["domains"] = sources
        # r = httpx.get("https://newsapi.org/v2/everything", params=params)
        # data = r.json()
        # articles = [
        #     {
        #         "title": a["title"],
        #         "url": a["url"],
        #         "source": a["source"]["name"],
        #         "published_at": a["publishedAt"],
        #         "description": a.get("description", ""),
        #     }
        #     for a in data.get("articles", [])
        # ]
        # return {"status": "success", "topic": topic, "articles": articles}
        pass

    # Mock response
    mock_articles = [
        {
            "title": f"[Mock] Latest news about {topic} — article {i + 1}",
            "url": f"https://news.example.com/{topic.replace(' ', '-')}-{i + 1}",
            "source": "MockNews",
            "published_at": datetime.utcnow().isoformat(),
            "description": (
                f"Placeholder news article {i + 1} about {topic}. "
                "Set NEWS_API_KEY in .env for real headlines."
            ),
        }
        for i in range(max_articles)
    ]

    return {
        "status": "success",
        "topic": topic,
        "source": "mock — configure NEWS_API_KEY for live headlines",
        "articles": mock_articles,
        "fetched_at": datetime.utcnow().isoformat(),
    }


def summarize_text(text: str, max_length: int = 300, style: str = "bullet") -> dict:
    """
    Summarize a block of text into a concise format.

    Args:
        text: The text content to summarize.
        max_length: Target character length for the summary.
        style: Output style — 'bullet' for bullet points, 'paragraph' for prose,
               'tldr' for a single-sentence summary.

    Returns:
        A dict with 'status', 'original_length', 'summary', 'style'.
    """
    if not text or not text.strip():
        return {"status": "error", "message": "No text provided to summarize."}

    valid_styles = {"bullet", "paragraph", "tldr"}
    if style not in valid_styles:
        style = "bullet"

    # The LLM agent calling this tool will handle the actual summarization logic.
    # This function prepares the input and can optionally call an external API.
    # For now, we return the text structure so the agent can summarize directly.

    word_count = len(text.split())
    char_count = len(text)

    # If text is already short, just return it
    if char_count <= max_length:
        return {
            "status": "success",
            "original_length": char_count,
            "word_count": word_count,
            "summary": text,
            "style": style,
            "note": "Text was already within target length.",
        }

    # Return truncated preview + metadata so the LLM can summarize
    preview = text[:2000] + ("..." if len(text) > 2000 else "")
    return {
        "status": "ready_for_summarization",
        "original_length": char_count,
        "word_count": word_count,
        "text_preview": preview,
        "target_length": max_length,
        "requested_style": style,
        "instruction": (
            f"Please summarize the provided text in {style} format, "
            f"targeting around {max_length} characters."
        ),
    }
