import discord
import openai
import os
import asyncio
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

sessions = {}

@tree.command(name="chat", description="Chat with ChatGPT")
async def chat_command(interaction: discord.Interaction, prompt: str):
    user_id = interaction.user.id
    await interaction.response.defer()

    if user_id not in sessions:
        sessions[user_id] = []

    sessions[user_id].append({"role": "user", "content": prompt})

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=sessions[user_id]
    )

    reply = response.choices[0].message.content
    sessions[user_id].append({"role": "assistant", "content": reply})

    await interaction.followup.send(reply)

    async def clear_session():
        await asyncio.sleep(300)  # 5分後にセッション削除
        if user_id in sessions:
            del sessions[user_id]

    asyncio.create_task(clear_session())

@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")

client.run(TOKEN)
