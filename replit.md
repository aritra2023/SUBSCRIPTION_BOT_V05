# Telegram Payment Bot + File Store Bot

Two independent Telegram bots imported from GitHub, run as separate Replit workflows.

## 1. Telegram Payment Bot (`bot/`)

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

## 2. File Store Bot (`filestore_bot/`)

Stores any file type sent by an admin in a private Telegram storage channel, then generates a shareable link (single file or batch) that other users can use to retrieve it.

### Stack

- **Python** (python-telegram-bot 21.6)
- File/batch metadata persisted to local JSON files (`button.json`, `batches.json`, `running_batches.json`) — no database.

### How to run

The workflow **"File Store Bot"** runs `cd filestore_bot && python3 main.py`.

### Required secrets

| Secret | Description |
|---|---|
| `TELEGRAM_DEMO_BOT_TOKEN` | Bot token from @BotFather — must be a different bot than the Payment Bot |

### Bot entry points

- `filestore_bot/main.py` — startup, registers all handlers
- `filestore_bot/config.py` — env vars, storage channel ID, button/batch persistence helpers
- `filestore_bot/handlers.py` — all command and callback handlers

### Admin commands

`/addbutton`, `/removebutton`, `/help` (send a file directly to have the bot store it and generate a link)

Admin user IDs are hardcoded in `filestore_bot/config.py` (`ADMIN_IDS`). Storage channel ID is hardcoded in the same file (`STORAGE_CHANNEL_ID`) — the bot must be an admin of that channel.

## Shared Python environment

Both bots run from the same `.pythonlibs` virtual environment managed via `pyproject.toml`/`uv.lock` at the project root (dependencies: python-telegram-bot, razorpay, pymongo, dnspython, qrcode, Pillow).

## User preferences
