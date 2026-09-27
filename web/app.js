"use strict";

const state = {
  token: sessionStorage.getItem("aidahelp_token") || "",
  conversationId: null,
  busy: false,
};

const ui = {
  messages: document.querySelector("#messages"),
  welcome: document.querySelector("#welcome"),
  form: document.querySelector("#chat-form"),
  input: document.querySelector("#message-input"),
  send: document.querySelector("#send-button"),
  status: document.querySelector("#agent-status"),
  conversations: document.querySelector("#conversation-list"),
  sidebar: document.querySelector("#sidebar"),
  routePill: document.querySelector("#route-pill"),
  intent: document.querySelector("#intent-label"),
  route: document.querySelector("#route-label"),
  warning: document.querySelector("#connection-warning"),
  settings: document.querySelector("#settings-dialog"),
  externalId: document.querySelector("#external-user-id"),
  manualToken: document.querySelector("#manual-token"),
  toast: document.querySelector("#toast"),
};

function authHeaders(json = false) {
  const headers = {};
  if (json) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  return headers;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, { credentials: "omit", ...options });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`服务返回了无法解析的响应（HTTP ${response.status}）`);
  }
  if (!response.ok || !payload.success) {
    if (response.status === 401) clearToken();
    throw new Error(payload.error?.message || `请求失败（HTTP ${response.status}）`);
  }
  return payload.data;
}

function saveToken(token) {
  state.token = token.trim();
  sessionStorage.setItem("aidahelp_token", state.token);
  ui.manualToken.value = state.token;
}

function clearToken() {
  state.token = "";
  sessionStorage.removeItem("aidahelp_token");
}

function showToast(message) {
  ui.toast.textContent = message;
  ui.toast.hidden = false;
  window.setTimeout(() => { ui.toast.hidden = true; }, 2400);
}

function setConnected(connected, text = "") {
  ui.status.textContent = text || (connected ? "在线 · 已建立安全连接" : "未连接");
  ui.warning.hidden = connected;
  if (!connected) {
    ui.warning.textContent = "尚未登录。请打开右上角设置，使用演示登录或填写 Token。";
  }
}

async function demoLogin() {
  const data = await requestJson("/api/v1/auth/demo-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ external_user_id: ui.externalId.value.trim() || "demo-user" }),
  });
  saveToken(data.access_token);
  setConnected(true, `在线 · ${data.nickname || "演示用户"}`);
  if (ui.settings.open) ui.settings.close();
  await loadConversations();
  showToast("演示登录成功");
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function removeWelcome() {
  if (ui.welcome?.isConnected) ui.welcome.remove();
}

function typingIndicator() {
  const wrap = node("span", "typing");
  wrap.append(node("i"), node("i"), node("i"));
  return wrap;
}

function appendMessage(role, text = "", options = {}) {
  removeWelcome();
  const row = node("article", `message-row ${role}`);
  if (role === "assistant") row.append(node("div", "message-avatar", "AI"));
  const card = node("div", "message-card");
  const bubble = node("div", `bubble${options.error ? " error" : ""}`);
  const content = node("span", "message-content", text);
  if (options.typing) {
    bubble.append(typingIndicator());
  } else {
    bubble.append(content);
  }
  card.append(bubble);
  if (options.meta) card.append(node("div", "message-meta", options.meta));
  row.append(card);
  ui.messages.append(row);
  ui.messages.scrollTop = ui.messages.scrollHeight;
  return { row, card, bubble, content };
}

function renderCitations(card, items) {
  if (!Array.isArray(items) || !items.length) return;
  const list = node("div", "citation-list");
  items.forEach((item, index) => {
    const label = item.section_path || item.document_id || `证据 ${index + 1}`;
    const score = typeof item.score === "number" ? ` · ${item.score.toFixed(3)}` : "";
    list.append(node("span", "citation", `[${item.index || index + 1}] ${label}${score}`));
  });
  card.append(list);
}

function renderConfirmation(card, action) {
  const box = node("section", "confirm-card");
  box.append(node("strong", "", action.title || "确认执行操作"));
  const description = action.warning || "这是一项业务写操作，只有确认后才会执行。";
  box.append(node("p", "", description));
  const actions = node("div", "confirm-actions");
  const confirm = node("button", "confirm", "确认执行");
  const cancel = node("button", "cancel", "取消");
  confirm.type = cancel.type = "button";
  confirm.addEventListener("click", () => resumeAction(true, box));
  cancel.addEventListener("click", () => resumeAction(false, box));
  actions.append(confirm, cancel);
  box.append(actions);
  card.append(box);
}

function setRoute(intent, route) {
  if (!intent && !route) return;
  ui.intent.textContent = intent || "unknown";
  ui.route.textContent = route || "unknown";
  ui.routePill.hidden = false;
}

function setBusy(busy) {
  state.busy = busy;
  ui.send.disabled = busy;
  ui.input.disabled = busy;
  if (!busy) ui.input.focus();
}

async function sendMessage(rawText) {
  const message = rawText.trim();
  if (!message || state.busy) return;
  if (!state.token) {
    ui.settings.showModal();
    return;
  }
  setBusy(true);
  appendMessage("user", message, { meta: "刚刚" });
  ui.input.value = "";
  resizeComposer();
  const assistant = appendMessage("assistant", "", { typing: true, meta: "Aida 正在处理" });
  let answer = "";
  let initialized = false;
  try {
    const response = await fetch("/api/v1/chat/stream", {
      method: "POST",
      credentials: "omit",
      headers: authHeaders(true),
      body: JSON.stringify({ message, conversation_id: state.conversationId }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      if (response.status === 401) clearToken();
      throw new Error(payload?.error?.message || `连接失败（HTTP ${response.status}）`);
    }
    const traceId = response.headers.get("X-Trace-ID");
    if (traceId) document.querySelector("#trace-hint").textContent = `Trace ${traceId.slice(0, 8)}`;
    await consumeSse(response, (event) => {
      if (event.event === "status" && !initialized) {
        assistant.bubble.replaceChildren(node("span", "", event.message));
      } else if (event.event === "meta") {
        state.conversationId = event.conversation_id;
        setRoute(event.intent, event.route);
      } else if (event.event === "delta") {
        if (!initialized) {
          assistant.bubble.replaceChildren(assistant.content);
          initialized = true;
        }
        answer += event.text || "";
        assistant.content.textContent = answer;
        ui.messages.scrollTop = ui.messages.scrollHeight;
      } else if (event.event === "citations") {
        renderCitations(assistant.card, event.items);
      } else if (event.event === "interrupt") {
        renderConfirmation(assistant.card, event.action || {});
      } else if (event.event === "error") {
        throw new Error(event.message || "客服暂时不可用");
      }
    });
    assistant.card.querySelector(".message-meta").textContent = "Aida · 已完成";
    await loadConversations();
  } catch (error) {
    assistant.bubble.classList.add("error");
    assistant.bubble.textContent = error.message || "客服暂时不可用";
    assistant.card.querySelector(".message-meta").textContent = "请求失败";
    setConnected(Boolean(state.token));
  } finally {
    setBusy(false);
  }
}

async function consumeSse(response, onEvent) {
  if (!response.body) throw new Error("浏览器不支持流式响应");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const packets = buffer.split("\n\n");
    buffer = packets.pop() || "";
    for (const packet of packets) {
      const data = packet.split("\n").filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim()).join("\n");
      if (!data || data === "[DONE]") continue;
      onEvent(JSON.parse(data));
    }
    if (done) break;
  }
}

async function resumeAction(confirmed, box) {
  if (!state.conversationId || state.busy) return;
  box.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  setBusy(true);
  const pending = appendMessage("assistant", "", { typing: true, meta: "正在处理确认结果" });
  try {
    const data = await requestJson(`/api/v1/chat/${state.conversationId}/resume`, {
      method: "POST",
      headers: authHeaders(true),
      body: JSON.stringify({ confirmed }),
    });
    pending.bubble.textContent = data.answer;
    pending.card.querySelector(".message-meta").textContent = "Aida · 已完成";
    box.replaceChildren(node("strong", "", confirmed ? "已确认执行" : "已取消"));
    await loadConversations();
  } catch (error) {
    pending.bubble.classList.add("error");
    pending.bubble.textContent = error.message;
    box.querySelectorAll("button").forEach((button) => { button.disabled = false; });
  } finally {
    setBusy(false);
  }
}

async function loadConversations() {
  if (!state.token) return;
  try {
    const conversations = await requestJson("/api/v1/conversations?limit=50", {
      headers: authHeaders(),
    });
    ui.conversations.replaceChildren();
    if (!conversations.length) {
      ui.conversations.append(node("div", "empty-list", "还没有会话，问我一个问题吧。"));
      return;
    }
    conversations.forEach((item) => {
      const button = node("button", "conversation-item");
      button.type = "button";
      if (item.id === state.conversationId) button.classList.add("active");
      button.append(node("strong", "", item.title || "新客服会话"));
      button.append(node("span", "", formatDate(item.last_message_at || item.created_at)));
      button.addEventListener("click", () => openConversation(item.id));
      ui.conversations.append(button);
    });
    setConnected(true);
  } catch (error) {
    setConnected(false, error.message);
  }
}

async function openConversation(conversationId) {
  if (state.busy) return;
  state.conversationId = conversationId;
  ui.routePill.hidden = true;
  try {
    const messages = await requestJson(`/api/v1/conversations/${conversationId}/messages?limit=200`, {
      headers: authHeaders(),
    });
    ui.messages.replaceChildren();
    messages.forEach((message, index) => {
      const role = message.role === "user" ? "user" : "assistant";
      const rendered = appendMessage(role, message.content, { meta: formatDate(message.created_at) });
      if (message.metadata?.citations) renderCitations(rendered.card, message.metadata.citations);
      if (message.metadata?.pending_action && index === messages.length - 1) {
        renderConfirmation(rendered.card, message.metadata.pending_action);
      }
    });
    ui.sidebar.classList.remove("open");
    await loadConversations();
  } catch (error) {
    showToast(error.message);
  }
}

function newConversation() {
  state.conversationId = null;
  ui.routePill.hidden = true;
  ui.messages.replaceChildren();
  const welcome = node("section", "welcome");
  welcome.append(node("div", "welcome-icon", "A"));
  welcome.append(node("p", "eyebrow", "NEW CONVERSATION"));
  welcome.append(node("h1", "", "新的会话已经准备好。"));
  welcome.append(node("p", "welcome-copy", "告诉我你遇到的问题，我会自动选择知识检索、业务工具或固定流程。"));
  ui.messages.append(welcome);
  ui.sidebar.classList.remove("open");
  loadConversations();
  ui.input.focus();
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}

function resizeComposer() {
  ui.input.style.height = "auto";
  ui.input.style.height = `${Math.min(ui.input.scrollHeight, 150)}px`;
}

ui.form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(ui.input.value);
});
ui.input.addEventListener("input", resizeComposer);
ui.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    ui.form.requestSubmit();
  }
});
document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => sendMessage(button.dataset.question || ""));
});
document.querySelector("#new-chat").addEventListener("click", newConversation);
document.querySelector("#refresh-conversations").addEventListener("click", loadConversations);
document.querySelector("#mobile-menu").addEventListener("click", () => ui.sidebar.classList.toggle("open"));
document.querySelector("#open-settings").addEventListener("click", () => ui.settings.showModal());
document.querySelector("#demo-login").addEventListener("click", () => {
  demoLogin().catch((error) => showToast(error.message));
});
document.querySelector("#save-token").addEventListener("click", async () => {
  const token = ui.manualToken.value.trim();
  if (!token) return showToast("请先填写 Token");
  saveToken(token);
  try {
    await loadConversations();
    ui.settings.close();
    showToast("Token 已保存到本次浏览器会话");
  } catch (error) {
    showToast(error.message);
  }
});

async function initialize() {
  if (state.token) {
    ui.manualToken.value = state.token;
    await loadConversations();
    if (state.token) return;
  }
  try {
    await demoLogin();
  } catch (error) {
    setConnected(false, error.message);
    ui.settings.showModal();
  }
}

initialize();
