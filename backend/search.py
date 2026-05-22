import httpx
import os

async def search(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": os.getenv("SERPER_API_KEY", ""), "Content-Type": "application/json"},
                json={"q": query, "num": 5, "gl": "bd", "hl": "en"},
            )
            data = r.json()
        results = []
        for item in data.get("organic", [])[:5]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            results.append(f"• {title}: {snippet}")
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search failed: {e}"
