import asyncio
import os
import random
from collections import defaultdict, deque
from threading import Thread

import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from huggingface_hub import InferenceClient

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

HF_TOKEN = os.getenv("HUGGING_FACE_TOKEN")
HF_MODEL = "openai/gpt-oss-120b:fastest"
client = InferenceClient(token=HF_TOKEN) if HF_TOKEN else None

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

MAX_HISTORY = 6
conversation_history = defaultdict(lambda: deque(maxlen=MAX_HISTORY * 2))

SYSTEM_PROMPT = """You are Aegis, a concise chat companion.
Reply in Japanese in 1-2 short sentences (max 3).
Keep a lightly sarcastic but kind tone.
Do not say you are ChatGPT, OpenAI, or a language model.
Do not answer with only "...", "yes", or single-word replies.
"""

app = Flask(__name__)


@app.get("/health")
def health() -> tuple[str, int]:
    return "ok", 200


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
                    "まあ、もう少し具体的に聞いてください。",
                    "その話、もう一歩だけ詳しく。",
                    "続けましょう。次は何を知りたいですか。",
                ]
            )

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


@bot.command(name="r", aliases=["reset"])
async def reset_command(ctx: commands.Context) -> None:
    memory_key = f"channel:{ctx.channel.id}"
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
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is missing")

    Thread(target=run_web, daemon=True).start()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
