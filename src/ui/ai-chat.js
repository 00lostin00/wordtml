/**
 * AI 助手侧边栏 —— 全局挂载，所有页面可用。
 * 与 /api/ai-chat 后端通信，key 留在服务器端。
 */

const STORAGE_KEY = "ai_chat_history";
const MAX_HISTORY = 40; // 最多保留多少条消息

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch { return []; }
}
function saveHistory(msgs) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs.slice(-MAX_HISTORY)));
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
          .replace(/\n/g, "<br>");
}

function buildSidebar() {
  const wrap = document.createElement("div");
  wrap.id = "ai-sidebar";
  wrap.className = "ai-sidebar";
  wrap.innerHTML = `
    <div class="ai-header">
      <span class="ai-title">✦ AI 助手</span>
      <div class="ai-header-actions">
        <button class="ai-btn-icon" id="ai-clear" title="清空对话">🗑</button>
        <button class="ai-btn-icon" id="ai-close" title="关闭">✕</button>
      </div>
    </div>
    <div class="ai-messages" id="ai-messages"></div>
    <div class="ai-input-area">
      <textarea id="ai-input" class="ai-input" rows="3"
        placeholder="问我任何关于英语或题目的问题…"></textarea>
      <button id="ai-send" class="ai-send-btn">发送</button>
    </div>
  `;

  const toggle = document.createElement("button");
  toggle.id = "ai-toggle";
  toggle.className = "ai-toggle";
  toggle.innerHTML = "✦";
  toggle.title = "AI 助手";

  document.body.appendChild(wrap);
  document.body.appendChild(toggle);
  return { wrap, toggle };
}

function appendMessage(container, role, text, id = null) {
  const div = document.createElement("div");
  div.className = `ai-msg ai-msg-${role}`;
  if (id) div.dataset.id = id;
  div.innerHTML = `<div class="ai-bubble">${escapeHtml(text)}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

function setMsgText(div, text) {
  div.querySelector(".ai-bubble").innerHTML = escapeHtml(text);
}

async function sendMessage(userText, messagesEl, history) {
  if (!userText.trim()) return;

  history.push({ role: "user", content: userText });
  appendMessage(messagesEl, "user", userText);
  saveHistory(history);

  const thinkingDiv = appendMessage(messagesEl, "assistant", "…");

  try {
    const res = await fetch("/api/ai-chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: history.slice(-20), // 最近 20 条作为上下文
      }),
    });

    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "未知错误");

    const reply = data.reply;
    setMsgText(thinkingDiv, reply);
    history.push({ role: "assistant", content: reply });
    saveHistory(history);
  } catch (err) {
    setMsgText(thinkingDiv, `⚠ 请求失败：${err.message}`);
    thinkingDiv.querySelector(".ai-bubble").style.color = "var(--err)";
    history.pop(); // 撤销本次 user 消息
    saveHistory(history);
  }

  messagesEl.scrollTop = messagesEl.scrollHeight;
}

export function initAiChat() {
  isChatAvailable().then((available) => {
    if (available) mountAiChat();
  });
}

async function isChatAvailable() {
  try {
    const res = await fetch("/api/ai-chat/status", { cache: "no-store" });
    if (!res.ok) return false;
    const data = await res.json();
    return data.ok === true && data.enabled === true;
  } catch {
    return false;
  }
}

function mountAiChat() {
  const { wrap, toggle } = buildSidebar();
  const messagesEl = document.getElementById("ai-messages");
  const inputEl    = document.getElementById("ai-input");
  const sendBtn    = document.getElementById("ai-send");
  const closeBtn   = document.getElementById("ai-close");
  const clearBtn   = document.getElementById("ai-clear");

  const history = loadHistory();

  // 渲染历史消息
  for (const msg of history) {
    appendMessage(messagesEl, msg.role, msg.content);
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;

  // 开关侧边栏
  let open = false;
  function toggleSidebar() {
    open = !open;
    wrap.classList.toggle("ai-sidebar--open", open);
    toggle.classList.toggle("ai-toggle--active", open);
    if (open) inputEl.focus();
  }
  toggle.addEventListener("click", toggleSidebar);
  closeBtn.addEventListener("click", toggleSidebar);

  // 发送
  async function doSend() {
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = "";
    sendBtn.disabled = true;
    inputEl.disabled = true;
    await sendMessage(text, messagesEl, history);
    sendBtn.disabled = false;
    inputEl.disabled = false;
    inputEl.focus();
  }
  sendBtn.addEventListener("click", doSend);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); doSend(); }
  });

  // 清空
  clearBtn.addEventListener("click", () => {
    history.length = 0;
    saveHistory(history);
    messagesEl.innerHTML = "";
  });
}
