import httpx
import os

def _headers():
    key = os.getenv("SUPABASE_ANON_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

def _url(path=""):
    return f"{os.getenv('SUPABASE_URL', '')}/rest/v1{path}"

async def save_message(sender: str, content: str, msg_type: str = "text"):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(_url("/messages"), headers=_headers(),
                         json={"sender": sender, "content": content, "msg_type": msg_type})
    except Exception:
        pass  # don't crash if DB is unavailable

async def get_history(limit: int = 60):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(_url("/messages"), headers=_headers(),
                            params={"select": "*", "order": "created_at.asc",
                                    "limit": str(limit)})
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []

async def get_context(limit: int = 20):
    """OpenAI-format messages for AI context window"""
    history = await get_history(limit)
    out = []
    for m in history:
        if m.get("msg_type") == "image":
            continue
        role = "user" if m["sender"] == "You" else "assistant"
        prefix = "" if m["sender"] == "You" else f"[{m['sender']}]: "
        out.append({"role": role, "content": f"{prefix}{m['content']}"})
    return out
