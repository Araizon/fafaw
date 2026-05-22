/* ─────────────────────────────────────────────────────────────────────────────
   Fafaw — Frontend App
   Change WS_URL to your Render backend URL after deploy.
───────────────────────────────────────────────────────────────────────────── */

const WS_URL = "wss://fafaw-production.up.railway.app/ws";
// ─── State ────────────────────────────────────────────────────────────────────
let ws = null;
let agents = {};        // { name: { emoji, color, offline } }
let typingSet = new Set();
let reconnectTimer = null;
let lastSender = null;
let lastTime = 0;

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const messagesEl   = document.getElementById("messages");
const inputEl      = document.getElementById("msg-input");
const sendBtn      = document.getElementById("send-btn");
const agentListEl  = document.getElementById("agent-list");
const connStatus   = document.getElementById("conn-status");
const typingBar    = document.getElementById("typing-bar");
const headerOnline = document.getElementById("header-online");

// Lightbox
const lightbox = document.createElement("div");
lightbox.id = "lightbox";
lightbox.innerHTML = '<img id="lb-img" src="" alt="Generated image"/>';
document.body.appendChild(lightbox);
const lbImg = document.getElementById("lb-img");
lightbox.addEventListener("click", () => lightbox.classList.remove("open"));

// ─── WebSocket ────────────────────────────────────────────────────────────────
function connect() {
  clearTimeout(reconnectTimer);
  try { ws = new WebSocket(WS_URL); }
  catch { scheduleReconnect(); return; }

  ws.onopen = () => {
    connStatus.textContent = "⚡ Connected";
    connStatus.className = "connected";
  };

  ws.onclose = () => {
    connStatus.textContent = "⚡ Reconnecting...";
    connStatus.className = "disconnected";
    scheduleReconnect();
  };

  ws.onerror = () => ws.close();

  ws.onmessage = (e) => {
    try { handleMsg(JSON.parse(e.data)); }
    catch (err) { console.error("Parse error", err); }
  };

  // Keep alive
  setInterval(() => ws?.readyState === 1 && ws.send(JSON.stringify({ type: "ping" })), 25000);
}

function scheduleReconnect() {
  reconnectTimer = setTimeout(connect, 3000);
}

// ─── Message handling ─────────────────────────────────────────────────────────
function handleMsg(data) {
  switch (data.type) {

    case "init":
      data.agents.forEach(a => {
        agents[a.name] = { emoji: a.emoji, color: a.color, offline: false };
      });
      renderAgentList();
      updateHeaderOnline();
      break;

    case "history":
      if (data.messages?.length) {
        document.getElementById("welcome-msg")?.remove();
        data.messages.forEach(m => appendMessage(m.sender, m.content, m.msg_type, m.created_at, true));
        scrollToBottom(false);
      }
      break;

    case "message":
      document.getElementById("welcome-msg")?.remove();
      removeTypingIndicator(data.agent);
      appendMessage(data.agent, data.content, data.msg_type);
      scrollToBottom();
      break;

    case "typing":
      if (data.status) addTypingIndicator(data.agent);
      else removeTypingIndicator(data.agent);
      updateTypingBar();
      break;

    case "agent_status":
      Object.entries(data.agents).forEach(([name, offline]) => {
        if (agents[name]) agents[name].offline = offline;
      });
      renderAgentList();
      updateHeaderOnline();
      break;

    case "system":
      appendSystem(data.content);
      scrollToBottom();
      break;

    case "searching":
      appendSearching(data.agent, data.query);
      break;

    case "error":
      appendSystem(`⚠️ ${data.agent} encountered an error.`);
      break;
  }
}

// ─── Render helpers ───────────────────────────────────────────────────────────

function agentColor(name) {
  return agents[name]?.color ?? "#888";
}

function agentEmoji(name) {
  return agents[name]?.emoji ?? "🤖";
}

function formatTime(iso) {
  const d = iso ? new Date(iso) : new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function shouldGroup(sender) {
  const now = Date.now();
  const grouped = sender === lastSender && (now - lastTime) < 60000;
  lastSender = sender;
  lastTime = now;
  return grouped;
}

function appendMessage(sender, content, msgType = "text", timestamp = null, fromHistory = false) {
  const isUser = sender === "You";
  const grouped = shouldGroup(sender);

  const row = document.createElement("div");
  row.className = `msg-row ${isUser ? "from-user" : "from-ai"}`;

  // Meta (avatar + name + time) — skip if grouped
  if (!grouped || fromHistory) {
    const meta = document.createElement("div");
    meta.className = "msg-meta";

    if (!isUser) {
      const av = document.createElement("div");
      av.className = "msg-avatar";
      av.style.background = agentColor(sender) + "22";
      av.style.color = agentColor(sender);
      av.textContent = agentEmoji(sender);
      meta.appendChild(av);

      const nm = document.createElement("span");
      nm.className = "msg-sender";
      nm.style.color = agentColor(sender);
      nm.textContent = sender;
      meta.appendChild(nm);
    }

    const tm = document.createElement("span");
    tm.className = "msg-time";
    tm.textContent = formatTime(timestamp);
    meta.appendChild(tm);

    row.appendChild(meta);
  }

  // Bubble or image
  if (msgType === "image") {
    const wrap = document.createElement("div");
    wrap.className = "msg-image";
    wrap.innerHTML = `<div class="img-loading">🎨 Generating image...</div>`;

    const img = new Image();
    img.onload = () => {
      wrap.innerHTML = "";
      wrap.appendChild(img);
      scrollToBottom();
    };
    img.onerror = () => {
      wrap.innerHTML = `<div class="img-loading" style="color:var(--rex)">⚠️ Image failed to load.</div>`;
    };
    img.src = content;
    img.alt = "AI generated image";
    img.addEventListener("click", () => {
      lbImg.src = content;
      lightbox.classList.add("open");
    });

    row.appendChild(wrap);
  } else {
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    if (!isUser) {
      bubble.style.background = agentColor(sender) + "18";
      bubble.style.borderColor = agentColor(sender) + "30";
    }

    bubble.innerHTML = formatContent(content);
    row.appendChild(bubble);
  }

  messagesEl.appendChild(row);
}

function formatContent(text) {
  // Convert code blocks
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code>${escHtml(code.trim())}</code></pre>`;
  });
  // Inline code
  text = text.replace(/`([^`]+)`/g, (_, c) => `<code>${escHtml(c)}</code>`);
  // Bold
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // Line breaks (preserve)
  text = text.replace(/\n/g, "<br>");
  return text;
}

function escHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function appendSystem(text) {
  const el = document.createElement("div");
  el.className = "msg-system";
  el.textContent = text;
  messagesEl.appendChild(el);
  lastSender = null;
}

let searchEl = null;
function appendSearching(agent, query) {
  document.getElementById("searching-indicator")?.remove();
  searchEl = document.createElement("div");
  searchEl.id = "searching-indicator";
  searchEl.className = "msg-searching";
  searchEl.innerHTML = `<span class="spin">🔍</span> ${agent} is searching for "<em>${escHtml(query)}</em>"`;
  messagesEl.appendChild(searchEl);
  scrollToBottom();
}

// ─── Typing indicators ────────────────────────────────────────────────────────
function addTypingIndicator(agent) {
  typingSet.add(agent);
  document.getElementById(`typing-${agent}`)?.remove();

  const el = document.createElement("div");
  el.className = "typing-indicator";
  el.id = `typing-${agent}`;

  const av = document.createElement("div");
  av.className = "msg-avatar";
  av.style.background = agentColor(agent) + "22";
  av.style.color = agentColor(agent);
  av.textContent = agentEmoji(agent);

  const dots = document.createElement("div");
  dots.className = "typing-dots";
  dots.innerHTML = "<span></span><span></span><span></span>";

  el.appendChild(av);
  el.appendChild(dots);
  messagesEl.appendChild(el);
  scrollToBottom();
}

function removeTypingIndicator(agent) {
  typingSet.delete(agent);
  document.getElementById(`typing-${agent}`)?.remove();
  document.getElementById("searching-indicator")?.remove();
}

function updateTypingBar() {
  if (typingSet.size === 0) {
    typingBar.style.display = "none";
    typingBar.textContent = "";
    return;
  }
  const names = [...typingSet].join(", ");
  typingBar.textContent = `${names} ${typingSet.size === 1 ? "is" : "are"} typing...`;
  typingBar.style.display = "block";
}

// ─── Agent list sidebar ───────────────────────────────────────────────────────
const AGENT_TAGS = {
  Rex:  "Fast & funny ⚡",
  Alex: "Wise & balanced 🧠",
  Gem:  "Creative & artsy 💎",
  Dev:  "Code expert 💻",
  Mist: "Deep thinker 🌫️",
};

function renderAgentList() {
  agentListEl.innerHTML = "";
  Object.entries(agents).forEach(([name, info]) => {
    const card = document.createElement("div");
    card.className = `agent-card${info.offline ? " offline" : ""}`;
    card.innerHTML = `
      <div class="agent-avatar" style="background:${info.color}22; color:${info.color}">
        ${info.emoji}
        <div class="agent-status-dot"></div>
      </div>
      <div class="agent-info">
        <div class="agent-name" style="color:${info.color}">${name}</div>
        <div class="agent-tag">${AGENT_TAGS[name] ?? ""}</div>
      </div>
      ${info.offline ? `<button class="reset-btn" onclick="resetAgent('${name}')">retry</button>` : ""}
    `;
    agentListEl.appendChild(card);
  });
}

function updateHeaderOnline() {
  const online = Object.values(agents).filter(a => !a.offline).length;
  headerOnline.textContent = `${online} online`;
}

window.resetAgent = function(name) {
  fetch(`${WS_URL.replace("ws://","http://").replace("wss://","https://").replace("/ws","")}/reset-agent/${name}`, {
    method: "POST"
  }).catch(() => {});
};

// ─── Send message ─────────────────────────────────────────────────────────────
function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || !ws || ws.readyState !== 1) return;

  document.getElementById("welcome-msg")?.remove();
  appendMessage("You", text, "text");
  scrollToBottom();

  ws.send(JSON.stringify({ type: "message", content: text }));
  inputEl.value = "";
  inputEl.style.height = "auto";
  updateCharCount();
  lastSender = "You";
}

sendBtn.addEventListener("click", sendMessage);

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-resize textarea
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
  updateCharCount();
});

function updateCharCount() {
  const len = inputEl.value.length;
  const el = document.getElementById("char-count");
  el.textContent = len > 1800 ? `${len}/2000` : "";
}

// ─── Scroll ───────────────────────────────────────────────────────────────────
function scrollToBottom(smooth = true) {
  requestAnimationFrame(() => {
    messagesEl.scrollTo({
      top: messagesEl.scrollHeight,
      behavior: smooth ? "smooth" : "instant",
    });
  });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
connect();
