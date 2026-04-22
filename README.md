# discordbot

Render-ready Discord bot using `discord.py` + Hugging Face Inference.

## Commands

- `!c <message>`: chat with the bot
- `!r`: reset channel memory

## Environment Variables

- `DISCORD_TOKEN`: Discord bot token (required)
- `HUGGING_FACE_TOKEN`: Hugging Face token (optional, enables AI responses)

## Deploy on Render

1. Create a new **Web Service** from this repository.
2. Render reads `render.yaml` automatically.
3. Set environment variables in Render dashboard:
   - `DISCORD_TOKEN`
   - `HUGGING_FACE_TOKEN`
4. Deploy.

Health endpoint is available at `/health`.
