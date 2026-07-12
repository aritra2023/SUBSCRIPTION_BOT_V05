# Telegram Payment Bot

A Telegram bot for selling subscription plans via Razorpay payments, with MongoDB-backed user and payment tracking.

## Stack

- **Python** (python-telegram-bot 21.6)
- **Razorpay** — payment gateway (INR)
- **MongoDB** — stores users, payments, plans, and settings

## How to run

The workflow **"Telegram Payment Bot"** runs `cd bot && python3 main.py`.

It starts a health-check HTTP server on `PORT` (default 8000) alongside the Telegram polling loop.

## Required secrets

| Secret | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `RAZORPAY_KEY_ID` | Razorpay API key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay API key secret |
| `MONGODB_URI` | MongoDB Atlas connection string |

## Bot entry points

- `bot/main.py` — startup, registers all handlers
- `bot/config.py` — env vars, MongoDB client, Razorpay client, plan helpers
- `bot/handlers.py` — all command and callback handlers
- `bot/utils.py` — utility functions

## Admin commands

`/stats`, `/broadcast`, `/check`, `/addbalance`, `/removeplan`, `/newplan`, `/set_freechannel`, `/remove_freechannel`, `/set_tutorial`, `/remove_tutorial`

Admin user IDs are hardcoded in `bot/config.py` (`ADMIN_IDS`).

## User preferences
