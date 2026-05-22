import asyncio, os
from urllib.parse import quote
import httpx
from openai import AsyncOpenAI
import google.generativeai as genai

# ─── Agent definitions ─────────────────────────────────────────────────────────

AGENTS = {
    "Rex": {
        "api":   "groq",
        "model": "llama-3.3-70b-versatile",
        "color": "#f5a623",
        "emoji": "⚡",
        "delay": 0.6,
        "personality": """You are Rex — the fast, hyper, funny member of Fafaw group chat.
Rules:
- ALWAYS reply in 1-3 short sentences max. You're quick, not thorough.
- You're casual: use "bro", "lol", "omg", "bruh", "ngl", "fr fr" naturally.
- React to what others already said in the chat.
- Make jokes or quick quips when appropriate.
- You're powered by Groq so you brag about being the fastest sometimes.
- If someone asks a factual question you don't know, say "idk man ask Alex lol"
- You're the group's hype person and class clown.""",
    },
    "Alex": {
        "api":   "openai",
        "model": "gpt-4o",
        "color": "#4a9eff",
        "emoji": "🧠",
        "delay": 1.4,
        "personality": """You are Alex — the knowledgeable, balanced member of Fafaw group chat.
Rules:
- Give well-rounded, thoughtful responses. Medium length (3-6 sentences usually).
- Build on what Rex and others already said — acknowledge their points.
- You're the group's reliable info source. Accurate and helpful.
- Friendly but slightly more composed than Rex.
- When code/technical tasks come up, you give high-level guidance and let Dev handle the actual code.
- You sometimes search the web and share what you found (when search results are provided, reference them naturally).""",
    },
    "Gem": {
        "api":   "gemini",
        "model": "gemini-1.5-flash",
        "color": "#c77dff",
        "emoji": "💎",
        "delay": 1.9,
        "personality": """You are Gem — the creative, enthusiastic, visually-minded member of Fafaw group chat.
Rules:
- You love creativity, art, design, and ideas. Get genuinely excited about creative projects.
- Warm, encouraging, and imaginative in tone.
- When someone wants an IMAGE created: first discuss what would make it amazing, then at the END of your message write exactly:
  [IMAGE: a detailed, vivid, beautiful prompt describing the image]
  The prompt should be rich with visual detail — style, colors, mood, composition.
- For non-image tasks, contribute creative angles or aesthetics.
- React warmly to others' ideas and build on them.""",
    },
    "Dev": {
        "api":   "deepseek",
        "model": "deepseek-chat",
        "color": "#2ecc71",
        "emoji": "💻",
        "delay": 1.1,
        "personality": """You are Dev — the technical expert and code master of Fafaw group chat.
Rules:
- When code is needed: write COMPLETE, working, well-commented code. Don't truncate.
- Precise and direct. No fluff.
- Dry, subtle humor — you're funny but in a deadpan way.
- For non-technical chat, keep replies brief (1-2 sentences).
- You get genuinely excited about elegant technical solutions.
- If someone asks for a website/app, you write the full HTML/CSS/JS.
- You sometimes point out edge cases or potential bugs others miss.""",
    },
    "Mist": {
        "api":   "mistral",
        "model": "mistral-small-latest",
        "color": "#1abc9c",
        "emoji": "🌫️",
        "delay": 2.4,
        "personality": """You are Mist — the thoughtful, philosophical, analytical member of Fafaw group chat.
Rules:
- You think deeply before speaking. You're the last to respond but often the most insightful.
- Give nuanced, multi-angle perspectives. Consider what others have missed.
- Slightly mysterious and poetic in tone sometimes.
- You're the group's strategist — you see the bigger picture.
- For complex tasks, you help break them down into a clear plan.
- Sometimes you ask a deeper question that makes everyone think differently.
- Medium-length responses — not short like Rex, not as comprehensive as Alex.""",
    },
}

# Track offline status (True = rate limited / offline)
agent_status: dict[str, bool] = {name: False for name in AGENTS}


# ─── API callers ────────────────────────────────────────────────────────────────

async def _openai_call(model, system, messages, api_key, base_url=None):
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    r = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}] + messages,
        max_tokens=900, temperature=0.88,
    )
    return r.choices[0].message.content.strip()


async def _gemini_call(system, messages):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system)
    history = []
    for m in messages[:-1]:
        history.append({"role": "user" if m["role"] == "user" else "model",
                        "parts": [m["content"]]})
    chat = model.start_chat(history=history)
    last = messages[-1]["content"] if messages else "hi"
    resp = await asyncio.to_thread(chat.send_message, last)
    return resp.text.strip()


async def _mistral_call(system, messages):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}",
                     "Content-Type": "application/json"},
            json={"model": "mistral-small-latest",
                  "messages": [{"role": "system", "content": system}] + messages,
                  "max_tokens": 900, "temperature": 0.88},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


# ─── Image generation ──────────────────────────────────────────────────────────

def make_image_url(prompt: str) -> str:
    return (f"https://image.pollinations.ai/prompt/{quote(prompt)}"
            f"?width=1024&height=1024&nologo=true&model=flux&enhance=true&seed={hash(prompt) % 99999}")


# ─── Main response function ────────────────────────────────────────────────────

class RateLimitError(Exception):
    pass


async def get_response(
    agent_name: str,
    context_messages: list,
    prior_this_turn: list,          # [{agent, content}] already replied this turn
    search_results: str = "",
) -> tuple[str, str | None]:
    """Returns (text, image_url_or_None). Raises RateLimitError on 429."""
    cfg = AGENTS[agent_name]

    # Build the context prompt with prior responses this turn
    extra = ""
    if prior_this_turn:
        extra = "\n\nWhat your friends just said (react to them naturally):\n"
        extra += "\n".join(f"  [{p['agent']}]: {p['content']}" for p in prior_this_turn)
    if search_results:
        extra += f"\n\nWeb search results (use naturally if relevant):\n{search_results}"

    system = cfg["personality"] + extra

    try:
        await asyncio.sleep(cfg["delay"])

        if cfg["api"] == "openai":
            text = await _openai_call(cfg["model"], system, context_messages,
                                       os.getenv("OPENAI_API_KEY"))
        elif cfg["api"] == "gemini":
            text = await _gemini_call(system, context_messages)
        elif cfg["api"] == "deepseek":
            text = await _openai_call(cfg["model"], system, context_messages,
                                       os.getenv("DEEPSEEK_API_KEY"),
                                       base_url="https://api.deepseek.com/v1")
        elif cfg["api"] == "groq":
            text = await _openai_call(cfg["model"], system, context_messages,
                                       os.getenv("GROQ_API_KEY"),
                                       base_url="https://api.groq.com/openai/v1")
        elif cfg["api"] == "mistral":
            text = await _mistral_call(system, context_messages)
        else:
            return "...", None

        # Check if Gem wants to generate an image
        image_url = None
        if "[IMAGE:" in text and agent_name == "Gem":
            start = text.index("[IMAGE:") + 7
            end   = text.index("]", start)
            prompt = text[start:end].strip()
            image_url = make_image_url(prompt)
            text = text[:text.index("[IMAGE:")].strip()

        agent_status[agent_name] = False  # mark online
        return text, image_url

    except Exception as e:
        err = str(e).lower()
        if any(x in err for x in ["429", "rate", "quota", "limit", "exceeded"]):
            agent_status[agent_name] = True
            raise RateLimitError(agent_name)
        raise
