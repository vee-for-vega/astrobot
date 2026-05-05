// AstroBot CLI frontend.
// State machine: locked (password prompt) -> unlocked (chat).
// Talks to /api/* on same origin; auth via Bearer JWT.

const $ = (id) => document.getElementById(id);
const output = $("output");
const input = $("input");
const promptEl = $("prompt");

const state = {
  token: localStorage.getItem("astrobot_token") || null,
  expiresAt: parseInt(localStorage.getItem("astrobot_expires_at") || "0", 10),
  history: [],          // command history (up-arrow recall)
  historyIdx: -1,
  chatHistory: [],      // {role, content} for the bot
  lastResponse: null,   // for `tier`, `sources`, `cost`
  passwordMode: false,
};

function tokenValid() {
  return state.token && Date.now() < state.expiresAt - 30_000;
}

function setLocked(locked) {
  promptEl.textContent = locked ? "password:" : "guest@astrobot:~$";
  input.type = locked ? "password" : "text";
}

function print(text, cls = "") {
  const div = document.createElement("div");
  div.className = `line ${cls}`;
  div.textContent = text;
  output.appendChild(div);
  window.scrollTo(0, document.body.scrollHeight);
}

function printHTML(html, cls = "") {
  const div = document.createElement("div");
  div.className = `line ${cls}`;
  div.innerHTML = html;
  output.appendChild(div);
  window.scrollTo(0, document.body.scrollHeight);
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  const res = await fetch(path, { ...opts, headers });
  const text = await res.text();
  let body;
  try { body = JSON.parse(text); } catch { body = { raw: text }; }
  return { status: res.status, body, retryAfter: res.headers.get("Retry-After") };
}

async function login(password) {
  const { status, body } = await api("/api/login", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
  if (status === 200 && body.token) {
    state.token = body.token;
    state.expiresAt = Date.now() + body.expires_in * 1000;
    localStorage.setItem("astrobot_token", state.token);
    localStorage.setItem("astrobot_expires_at", String(state.expiresAt));
    return true;
  }
  return false;
}

async function ask(question) {
  const { status, body, retryAfter } = await api("/api/chat", {
    method: "POST",
    body: JSON.stringify({ question, history: state.chatHistory }),
  });
  if (status === 401) {
    state.token = null;
    localStorage.removeItem("astrobot_token");
    localStorage.removeItem("astrobot_expires_at");
    print("session expired. type your password to log back in.", "warn");
    state.passwordMode = true;
    setLocked(true);
    return;
  }
  if (status === 429) {
    print(`rate limited. retry in ~${retryAfter}s.`, "warn");
    return;
  }
  if (status === 503) {
    print(body.detail || "LLM budget exhausted and no cached match.", "err");
    return;
  }
  if (status !== 200) {
    print(`error: ${body.detail || body.raw || status}`, "err");
    return;
  }

  state.lastResponse = body;
  state.chatHistory.push({ role: "user", content: question });
  state.chatHistory.push({ role: "assistant", content: body.answer });

  if (body.fallback) {
    print(
      "[budget exhausted today, returning a verified corpus answer. admin will refresh the budget tomorrow.]",
      "warn",
    );
  }

  print(body.answer, "bot");
  print(
    `tier ${body.tier} · sim ${body.similarity.toFixed(3)}` +
    (body.cost_usd ? ` · $${body.cost_usd.toFixed(4)}` : " · cached"),
    "dim",
  );
}

const commands = {
  help() {
    print("commands:", "system");
    print("  help              show this", "system");
    print("  ask <question>    ask the bot (or just type without 'ask')", "system");
    print("  tier              show how the last answer was generated", "system");
    print("  sources           top retrieval matches for the last question", "system");
    print("  stats             daily budget + rate limit info", "system");
    print("  clear             clear the screen", "system");
    print("  logout            forget the session token", "system");
  },
  async ask(rest) {
    if (!rest) { print("usage: ask <question>", "warn"); return; }
    await ask(rest);
  },
  tier() {
    if (!state.lastResponse) { print("no response yet. ask something first.", "dim"); return; }
    const r = state.lastResponse;
    print(`tier:        ${r.tier}`, "system");
    print(`similarity:  ${r.similarity.toFixed(3)}`, "system");
    print(`fallback:    ${r.fallback}`, "system");
    print(`tokens:      ${r.tokens ? `${r.tokens.input} in / ${r.tokens.output} out` : "n/a (cached)"}`, "system");
    print(`cost:        ${r.cost_usd ? `$${r.cost_usd.toFixed(6)}` : "$0.00"}`, "system");
  },
  sources() {
    if (!state.lastResponse) { print("no response yet. ask something first.", "dim"); return; }
    print("retrieval matches:", "system");
    state.lastResponse.sources.forEach((s, i) => {
      print(`  ${i + 1}. (${s.similarity.toFixed(3)})  ${s.question}`, "system");
    });
  },
  async stats() {
    const { status, body } = await api("/api/stats");
    if (status !== 200) { print(`error: ${body.detail || status}`, "err"); return; }
    print(`daily budget:   $${body.daily_budget_usd.toFixed(2)}`, "system");
    print(`spent today:    $${body.spent_usd.toFixed(4)}`, "system");
    print(`remaining:      $${body.remaining_usd.toFixed(4)}`, "system");
    print(`llm disabled:   ${body.llm_disabled}`, "system");
    print(`rate limit:     ${body.rate_limit.requests_per_window} per ${body.rate_limit.window_secs}s`, "system");
  },
  clear() {
    output.innerHTML = "";
  },
  logout() {
    state.token = null;
    state.expiresAt = 0;
    state.chatHistory = [];
    localStorage.removeItem("astrobot_token");
    localStorage.removeItem("astrobot_expires_at");
    print("logged out.", "system");
    state.passwordMode = true;
    setLocked(true);
  },
};

async function handleLine(raw) {
  const line = raw.trim();
  if (!line) return;

  if (state.passwordMode) {
    print("password: " + "*".repeat(line.length));
    const ok = await login(line);
    if (ok) {
      state.passwordMode = false;
      setLocked(false);
      print("authenticated. type 'help' for commands.", "ok");
    } else {
      print("invalid password.", "err");
    }
    return;
  }

  print(`guest@astrobot:~$ ${line}`, "user");
  state.history.push(line);
  state.historyIdx = state.history.length;

  const [cmd, ...rest] = line.split(/\s+/);
  const restStr = rest.join(" ");

  if (commands[cmd]) {
    await commands[cmd](restStr);
  } else {
    // bare text -> treat as a question
    await ask(line);
  }
}

input.addEventListener("keydown", async (e) => {
  if (e.key === "Enter") {
    const value = input.value;
    input.value = "";
    input.disabled = true;
    try {
      await handleLine(value);
    } finally {
      input.disabled = false;
      input.focus();
    }
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (state.passwordMode) return;
    if (state.historyIdx > 0) state.historyIdx--;
    input.value = state.history[state.historyIdx] || "";
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    if (state.passwordMode) return;
    if (state.historyIdx < state.history.length - 1) {
      state.historyIdx++;
      input.value = state.history[state.historyIdx];
    } else {
      state.historyIdx = state.history.length;
      input.value = "";
    }
  }
});

// Always refocus the input when clicking anywhere — feels more terminal-like.
document.addEventListener("click", () => {
  if (!input.disabled) input.focus();
});

// Boot.
(async function init() {
  if (tokenValid()) {
    print("welcome back. session restored.", "ok");
    print("type 'help' for commands.", "system");
    setLocked(false);
  } else {
    state.passwordMode = true;
    setLocked(true);
    print("password required. enter the demo password from the resume.", "system");
  }
})();
