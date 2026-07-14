# Telegram Payment Bot

A Telegram bot imported from GitHub, run as a Replit workflow.

## Telegram Payment Bot (`bot/`)

Sells subscription plans via Razorpay payments, with MongoDB-backed user and payment tracking.

### Stack

- **Python** (python-telegram-bot 21.6)
- **Razorpay** — payment gateway (INR)
- **MongoDB** — stores users, payments, plans, and settings

### How to run

The workflow **"Telegram Payment Bot"** runs `cd bot && python3 main.py`.

It starts a health-check HTTP server on `PORT` (default 8000) alongside the Telegram polling loop.

### Required secrets

| Secret | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `RAZORPAY_KEY_ID` | Razorpay API key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay API key secret |
| `MONGODB_URI` | MongoDB Atlas connection string |

### Bot entry points

- `bot/main.py` — startup, registers all handlers
- `bot/config.py` — env vars, MongoDB client, Razorpay client, plan helpers
- `bot/handlers.py` — all command and callback handlers
- `bot/utils.py` — utility functions

### Admin commands

`/stats`, `/broadcast`, `/check`, `/addbalance`, `/removeplan`, `/newplan`, `/set_freechannel`, `/remove_freechannel`, `/set_tutorial`, `/remove_tutorial`

Admin user IDs are hardcoded in `bot/config.py` (`ADMIN_IDS`).

## Python environment

The bot runs from the `.pythonlibs` virtual environment managed via `pyproject.toml`/`uv.lock` at the project root (dependencies: python-telegram-bot, razorpay, pymongo, dnspython, qrcode, Pillow).

## Deployment

`Dockerfile` only copies and runs `bot/` — a Koyeb (or any Docker-based) deploy needs just the Payment Bot's secrets above (`TELEGRAM_BOT_TOKEN`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `MONGODB_URI`). No second bot token is required.

## User preferences
