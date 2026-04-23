import asyncio
import os
import random
import time
from collections import defaultdict, deque
from threading import Lock, Thread
from uuid import uuid4

import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from huggingface_hub import InferenceClient

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

HF_TOKEN = os.getenv("HUGGING_FACE_TOKEN")
HF_MODEL = "openai/gpt-oss-120b:fastest"
client = InferenceClient(token=HF_TOKEN) if HF_TOKEN else None

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
STARTED_AT = time.monotonic()

MAX_HISTORY = 6
conversation_history = defaultdict(lambda: deque(maxlen=MAX_HISTORY * 2))
history_lock = Lock()

SYSTEM_PROMPT = """You are Aegis, a concise chat companion.
Reply in Japanese in 1-2 short sentences (max 3).
Keep a lightly sarcastic but kind tone.
Do not say you are ChatGPT, OpenAI, or a language model.
Do not answer with only "...", "yes", or single-word replies.
"""

CHAT_PAGE = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Aegis Web Chat</title>
  <style>
    :root {
      --bg: #0f172a;
      --panel: #111827;
      --line: #334155;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --user: #1d4ed8;
      --bot: #1f2937;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Noto Sans JP", sans-serif;
      background: radial-gradient(1000px 600px at 20% -10%, #1e293b, var(--bg));
      color: var(--text);
      min-height: 100svh;
      display: grid;
      place-items: center;
      padding: 16px;
    }
    .app {
      width: min(720px, 100%);
      height: min(86svh, 900px);
      border: 1px solid var(--line);
      background: color-mix(in oklab, var(--panel) 92%, black);
      border-radius: 16px;
      display: grid;
      grid-template-rows: auto 1fr auto;
      overflow: hidden;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
    }
    header {
      border-bottom: 1px solid var(--line);
      padding: 12px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    header h1 {
      margin: 0;
      font-size: 15px;
      letter-spacing: 0.2px;
    }
    .muted { color: var(--muted); font-size: 12px; }
    #log {
      overflow-y: auto;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .msg {
      max-width: 82%;
      line-height: 1.45;
      padding: 10px 12px;
      border-radius: 12px;
      white-space: pre-wrap;
      word-break: break-word;
      border: 1px solid color-mix(in oklab, var(--line) 80%, transparent);
    }
    .user { align-self: flex-end; background: var(--user); }
    .bot { align-self: flex-start; background: var(--bot); }
    form {
      border-top: 1px solid var(--line);
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 8px;
      padding: 10px;
    }
    input {
      width: 100%;
      background: #0b1220;
      border: 1px solid var(--line);
      color: var(--text);
      border-radius: 10px;
      padding: 10px 12px;
      outline: none;
    }
    input:focus { border-color: var(--accent); }
    button {
      border: 0;
      border-radius: 10px;
      padding: 0 14px;
      cursor: pointer;
      color: white;
      background: #0ea5e9;
      font-weight: 600;
    }
    button.secondary { background: #475569; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
  </style>
</head>
<body>
  <main class="app">
    <header>
      <h1>Aegis Web Chat</h1>
      <div class="muted" id="status">Ready</div>
    </header>
    <section id="log"></section>
    <form id="chat-form">
      <input id="msg" placeholder="ここに入力してEnter" autocomplete="off" />
      <button id="send" type="submit">Send</button>
      <button id="reset" class="secondary" type="button">Reset</button>
    </form>
  </main>

  <script>
    const log = document.getElementById("log");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("msg");
    const sendBtn = document.getElementById("send");
    const resetBtn = document.getElementById("reset");
    const statusEl = document.getElementById("status");

    const storeKey = "aegis_session_id";
    let sessionId = localStorage.getItem(storeKey) || "";

    function append(role, text) {
      const div = document.createElement("div");
      div.className = "msg " + role;
      div.textContent = text;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
    }

    async function sendMessage(message) {
      sendBtn.disabled = true;
      statusEl.textContent = "Thinking...";
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, session_id: sessionId }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Request failed");
        sessionId = data.session_id || sessionId;
        localStorage.setItem(storeKey, sessionId);
        append("bot", data.reply);
      } catch (err) {
        append("bot", "Error: " + err.message);
      } finally {
        sendBtn.disabled = false;
        statusEl.textContent = "Ready";
        input.focus();
      }
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const message = input.value.trim();
      if (!message) return;
      append("user", message);
      input.value = "";
      await sendMessage(message);
    });

    resetBtn.addEventListener("click", async () => {
      const oldSession = sessionId;
      sessionId = "";
      localStorage.removeItem(storeKey);
      if (!oldSession) {
        append("bot", "Session reset.");
        return;
      }
      await fetch("/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: oldSession }),
      });
      append("bot", "Session reset.");
    });

    append("bot", "Web chat is ready. Say something.");
    input.focus();
  </script>
</body>
</html>
"""

app = Flask(__name__)


@app.get("/")
def index() -> str:
    return CHAT_PAGE


@app.get("/health")
def health() -> tuple[str, int]:
    return "ok", 200


@app.post("/api/chat")
def api_chat() -> tuple[object, int] | object:
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    session_id = str(payload.get("session_id", "")).strip()

    if not message:
        return jsonify({"error": "message is required"}), 400

    if not session_id:
        session_id = uuid4().hex[:12]

    memory_key = f"web:{session_id}"

    if client:
        reply = asyncio.run(call_huggingface(memory_key, message))
    else:
        reply = fallback_reply()

    return jsonify({"session_id": session_id, "reply": reply})


@app.post("/api/reset")
def api_reset() -> tuple[object, int] | object:
    payload = request.get_json(silent=True) or {}
    session_id = str(payload.get("session_id", "")).strip()

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    memory_key = f"web:{session_id}"
    with history_lock:
        conversation_history.pop(memory_key, None)
    return jsonify({"ok": True})


def run_web() -> None:
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)


def split_message(text: str, limit: int = 1900) -> list[str]:
    text = (text or "").strip()
    if not text:
        return ["Now loading words... try again."]
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def is_weak_reply(reply: str) -> bool:
    text = (reply or "").strip().lower().replace("\n", " ")
    weak = {"", ".", "...", "…", "yes", "ok", "k", "うん", "はい", "そう"}
    return text in weak or len(text) < 4


async def generate_reply(
    history: list[dict[str, str]], user_input: str, extra_prompt: str = ""
) -> tuple[str, str | None]:
    if not client:
        return "", None

    system_prompt = SYSTEM_PROMPT
    if extra_prompt:
        system_prompt += "\n" + extra_prompt

    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_input},
    ]

    response = await asyncio.to_thread(
        client.chat_completion,
        model=HF_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=160,
    )

    choice = response.choices[0]
    reply = (choice.message.content or "").strip()
    finish_reason = getattr(choice, "finish_reason", None)
    return reply, finish_reason


async def call_huggingface(memory_key: str, user_input: str) -> str:
    with history_lock:
        history = list(conversation_history[memory_key])

    try:
        reply, finish_reason = await generate_reply(history, user_input)

        if is_weak_reply(reply) or finish_reason == "length":
            reply, _ = await generate_reply(
                history,
                user_input,
                "Keep it short, but finish the sentence naturally in Japanese.",
            )

        if is_weak_reply(reply):
            return random.choice(
                [
                    "もう少し具体的に聞いてください。",
                    "その話、もう一歩だけ詳しく。",
                    "続けましょう。次は何を知りたいですか。",
                ]
            )

        with history_lock:
            conversation_history[memory_key].append({"role": "user", "content": user_input})
            conversation_history[memory_key].append({"role": "assistant", "content": reply})
        return reply

    except Exception as exc:
        print("HF error:", exc)
        return random.choice(
            [
                "今ちょっと調子が悪いです。",
                "少し待ってください。すぐ戻します。",
                "API側が重いみたいです。もう一度どうぞ。",
            ]
        )


def fallback_reply() -> str:
    return random.choice(
        [
            "今は推論サービスに接続できません。",
            "少し時間をおいて、もう一度お願いします。",
            "いまは簡易モードです。",
        ]
    )


def format_uptime(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, sec = divmod(rem, 60)
    return f"{hours:02}:{minutes:02}:{sec:02}"


@bot.command(name="c", aliases=["chat"])
async def chat_command(ctx: commands.Context, *, message: str) -> None:
    memory_key = f"channel:{ctx.channel.id}"

    async with ctx.typing():
        if client:
            reply = await call_huggingface(memory_key, message)
        else:
            reply = fallback_reply()

    for chunk in split_message(reply):
        await ctx.send(chunk)


@bot.command(
    name="status",
    aliases=["\u30b9\u30c6\u30fc\u30bf\u30b9", "st", "s"],
)
async def status_command(ctx: commands.Context) -> None:
    mode = "discord+web" if DISCORD_TOKEN else "web-only"
    hf_state = "ON" if client else "OFF"
    model = HF_MODEL if client else "N/A"
    uptime = format_uptime(time.monotonic() - STARTED_AT)
    with history_lock:
        sessions = len(conversation_history)

    await ctx.send(
        "\n".join(
            [
                "\u7a3c\u50cd\u4e2d\u3067\u3059\u3002",
                f"mode: {mode}",
                f"hf: {hf_state}",
                f"model: {model}",
                f"uptime: {uptime}",
                f"active_sessions: {sessions}",
            ]
        )
    )


@bot.command(name="r", aliases=["reset"])
async def reset_command(ctx: commands.Context) -> None:
    memory_key = f"channel:{ctx.channel.id}"
    with history_lock:
        conversation_history.pop(memory_key, None)
    await ctx.send("このチャンネルの会話履歴をリセットしました。")


@bot.event
async def on_ready() -> None:
    print(f"Logged in as: {bot.user}")
    if client:
        print("Hugging Face token detected")
    else:
        print("No HUGGING_FACE_TOKEN found: fallback mode")


def main() -> None:
    if DISCORD_TOKEN:
        Thread(target=run_web, daemon=True).start()
        bot.run(DISCORD_TOKEN)
    else:
        print("No DISCORD_TOKEN found. Starting in web-chat-only mode.")
        run_web()


if __name__ == "__main__":
    main()
