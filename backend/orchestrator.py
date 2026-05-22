import random
from agents import AGENTS, agent_status, get_response, RateLimitError
from search import search as web_search

INTENTS = {
    "image":    ["image", "picture", "photo", "draw", "ছবি", "আঁক", "generate", "বানাও ছবি"],
    "code":     ["code", "কোড", "function", "bug", "error", "script", "website", "web app",
                 "html", "css", "javascript", "python", "program", "ওয়েবসাইট"],
    "analysis": ["why", "how does", "explain", "analyze", "কেন", "কীভাবে", "বুঝাও", "ব্যাখ্যা"],
    "creative": ["write", "story", "poem", "লিখ", "গল্প", "কবিতা", "song", "গান"],
    "search":   ["latest", "recent", "news", "today", "এখন", "সর্বশেষ", "কে জিতেছে",
                 "current", "price", "কত দাম", "weather"],
}

RESPONDER_ORDER = {
    "image":    ["Rex", "Alex", "Gem"],
    "code":     ["Rex", "Dev", "Alex"],
    "analysis": ["Rex", "Alex", "Mist"],
    "creative": ["Rex", "Gem", "Mist"],
    "search":   ["Rex", "Alex", "Dev"],
    "casual":   None,  # random
}

NEEDS_SEARCH = {"search"}


def detect_intent(msg: str) -> str:
    ml = msg.lower()
    for intent, keywords in INTENTS.items():
        if any(k in ml for k in keywords):
            return intent
    return "casual"


def online() -> list[str]:
    return [n for n, off in agent_status.items() if not off]


def pick_responders(msg: str) -> list[str]:
    on = online()
    if not on:
        return []
    intent = detect_intent(msg)
    preferred = RESPONDER_ORDER.get(intent)
    if preferred:
        result = [a for a in preferred if a in on]
        # If less than 2 could respond, fill with random online
        extras = [a for a in on if a not in result]
        if len(result) < 2:
            result += random.sample(extras, min(1, len(extras)))
        return result
    # Casual: Rex + 2 random others
    rex   = ["Rex"] if "Rex" in on else []
    rest  = [a for a in on if a != "Rex"]
    picks = random.sample(rest, min(2, len(rest)))
    return rex + picks


async def process(user_msg: str, broadcast_fn, context_messages: list):
    """
    Main entry point called by WebSocket handler.
    broadcast_fn(data_dict) sends JSON to the client.
    """
    responders = pick_responders(user_msg)
    if not responders:
        await broadcast_fn({"type": "system", "content": "⚠️ সব AI offline আছে এখন। একটু পরে আবার চেষ্টা করো।"})
        return

    intent = detect_intent(user_msg)

    # Do web search if needed (before agents respond)
    search_results = ""
    if intent in NEEDS_SEARCH:
        await broadcast_fn({"type": "searching", "agent": "Alex", "query": user_msg})
        search_results = await web_search(user_msg)

    prior_this_turn: list[dict] = []

    for agent_name in responders:
        if agent_status.get(agent_name):
            # Already offline — skip
            await broadcast_fn({"type": "agent_status", "agents": {agent_name: True}})
            continue

        # Show typing indicator
        await broadcast_fn({"type": "typing", "agent": agent_name, "status": True})

        try:
            text, image_url = await get_response(
                agent_name, context_messages, prior_this_turn, search_results
            )
        except RateLimitError:
            await broadcast_fn({"type": "typing",       "agent": agent_name, "status": False})
            await broadcast_fn({"type": "agent_status", "agents": {agent_name: True}})
            # Try to hand off to next available agent not already in list
            backup = [a for a in online() if a not in responders and not agent_status.get(a)]
            if backup:
                responders.append(backup[0])
            continue
        except Exception as e:
            await broadcast_fn({"type": "typing", "agent": agent_name, "status": False})
            await broadcast_fn({"type": "error", "agent": agent_name, "content": str(e)})
            continue

        # Stop typing, send message
        await broadcast_fn({"type": "typing", "agent": agent_name, "status": False})
        await broadcast_fn({"type": "message", "agent": agent_name,
                            "content": text, "msg_type": "text"})

        if image_url:
            await broadcast_fn({"type": "message", "agent": agent_name,
                                "content": image_url, "msg_type": "image"})

        prior_this_turn.append({"agent": agent_name, "content": text})
