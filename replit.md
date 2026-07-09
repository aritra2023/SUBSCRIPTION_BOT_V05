# Telegram Payment Bot

A Telegram bot for selling premium channel subscriptions via Razorpay (card/UPI) and cryptocurrency (BNB Smart Chain).

## Stack
- **Language:** Python 3.11
- **Framework:** python-telegram-bot 21.6
- **Database:** MongoDB (via pymongo)
- **Payments:** Razorpay + manual crypto (BEP20)

## Project structure
```
bot/
  main.py        — entry point; starts health server + bot polling
  config.py      — env vars, Razorpay client, MongoDB collections, seed plans
  handlers.py    — all command & callback handlers
  utils.py       — helpers (save_user, record_payment, etc.)
  requirements.txt
```

## How to run
The workflow **Telegram Payment Bot** runs `cd bot && python3 main.py`.

A health-check HTTP server starts on `PORT` (default 8000) alongside the bot.

## Required secrets
| Secret | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `RAZORPAY_KEY_ID` | Razorpay API key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay API key secret |
| `MONGODB_URI` | MongoDB connection string |

## Admin config (in config.py)
- `ADMIN_USERNAME` / `ADMIN_IDS` — Telegram username & user ID with admin access
- `PREMIUM_CHANNEL_LINK` — invite link given to paying users
- `CRYPTO_ADDRESS` / `CRYPTO_NETWORK` — BEP20 address for crypto payments

## User preferences
<!-- Add preferences here as needed -->
