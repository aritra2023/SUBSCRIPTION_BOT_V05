# Telegram Payment Bot

A Telegram bot that sells subscription plans via Razorpay (INR) and crypto payments, backed by MongoDB.

## Stack

- **Language:** Python 3.11
- **Bot framework:** python-telegram-bot 21.6
- **Payments:** Razorpay (card/UPI/netbanking) + manual crypto (BEP20)
- **Database:** MongoDB (via pymongo)

## Project structure

```
bot/
  main.py       — entry point, registers all handlers and starts polling
  config.py     — env vars, MongoDB client, plan seeds, helper functions
  handlers.py   — all Telegram command and callback handlers
  utils.py      — shared utilities
  requirements.txt
pyproject.toml  — Python dependencies (managed by uv)
```

## How to run

The **Telegram Payment Bot** workflow runs automatically:
```
cd bot && python3 main.py
```

A lightweight HTTP health-check server also starts on `PORT` (default 8000).

## Required secrets

Set these in Replit Secrets before running:

| Secret | Where to get it |
|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather on Telegram |
| `RAZORPAY_KEY_ID` | Razorpay dashboard → API Keys |
| `RAZORPAY_KEY_SECRET` | Razorpay dashboard → API Keys |
| `MONGODB_URI` | MongoDB Atlas → Connect → Drivers |

## Admin commands

Admin user IDs are hardcoded in `config.py` (`ADMIN_IDS`). Key commands:
- `/newplan` — create a subscription plan
- `/editplan` — edit an existing plan
- `/removeplan` — delete a plan
- `/addbalance` — manually credit a user
- `/stats` — show bot statistics
- `/broadcast` — send a message to all users
- `/check` — look up a user
- `/set_freechannel` / `/remove_freechannel` — manage the free channel link
- `/set_tutorial` / `/remove_tutorial` — manage tutorial link

## User preferences
