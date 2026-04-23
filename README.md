# discordbot

Render-ready Discord bot using `discord.py` + Hugging Face Inference.
You can also chat directly in the browser (no Discord client needed).

## Commands

- `!c <message>`: chat with the bot
- `!r`: reset channel memory

## Web Chat

- Open `https://<your-render-service>.onrender.com/`
- Chat directly from browser (desktop or smartphone)
- Health check endpoint: `/health`
- API endpoint: `POST /api/chat` with JSON:
  - `message` (required)
  - `session_id` (optional, for conversation continuity)

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
