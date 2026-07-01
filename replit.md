# Telegram Payment Bot

Telegram bot with Razorpay payments, UPI QR codes, MongoDB storage, and admin tools.

---

## Koyeb Pe Deploy Karna (Step by Step)

### Step 1 — GitHub pe code upload karo

1. GitHub par ek naya **private repository** banao
2. Is replit ka code us repo mein push karo  
   *(Replit mein upar Git icon se ya shell se `git push` karo)*

### Step 2 — Koyeb account banao

1. [koyeb.com](https://www.koyeb.com) par free account banao
2. Dashboard mein **"Create Service"** click karo
3. **GitHub** select karo → apni repo connect karo

### Step 3 — Service configure karo

| Setting | Value |
|---|---|
| **Runtime** | Python |
| **Build Command** | `pip install -r bot/requirements.txt` |
| **Run Command** | `python3 bot/bot.py` |
| **Instance** | Free (Nano) |
| **Port** | *(khali chhod do — bot ko port ki zarurat nahi)* |

### Step 4 — Environment Variables daalo

Koyeb dashboard mein **"Environment Variables"** section mein ye sab daalo:

| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Apna bot token (BotFather se) |
| `RAZORPAY_KEY_ID` | `rzp_live_xxxxx` |
| `RAZORPAY_KEY_SECRET` | Razorpay secret key |
| `MONGODB_URI` | MongoDB connection string |

### Step 5 — Deploy karo

- **"Deploy"** button click karo
- Koyeb build karega aur bot start ho jaayega
- Logs mein `Bot starting...` dikhega — matlab sab theek hai ✅

### Step 6 — Bot ko hamesha online rakhna

Koyeb free plan mein service **auto-restart** hoti hai agar crash ho.  
Bot polling mode mein chalti hai — koi webhook setup ki zarurat nahi.

---

## Dusre Replit Mein Kaise Run Karo

### Step 1 — Naya Replit banao

1. [replit.com](https://replit.com) par **"Create Repl"** karo
2. Template: **"Blank"** ya **"Python"** choose karo

### Step 2 — Files copy karo

Is replit se sirf ye copy karo:
```
bot/
  bot.py
  requirements.txt
```

### Step 3 — Python packages install karo

Replit Shell mein:
```bash
pip install -r bot/requirements.txt
```

Ya Replit ke **"Packages"** tab se manually install karo:
- `python-telegram-bot==21.6`
- `razorpay==1.4.1`
- `qrcode[pil]==7.4.2`
- `Pillow==10.4.0`
- `pymongo==4.7.3`
- `dnspython==2.6.1`

### Step 4 — Secrets daalo

Replit ke **"Secrets"** tab (🔒 icon) mein ye sab daalo:

| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Apna bot token |
| `RAZORPAY_KEY_ID` | Razorpay key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay secret |
| `MONGODB_URI` | MongoDB URI |

### Step 5 — Run karo

```bash
python3 bot/bot.py
```

Ya Replit mein ek **Workflow** banao:
- Name: `Telegram Bot`
- Command: `cd bot && python3 bot.py`

---

## Bot Commands

| Command | Kaun use kar sakta hai | Kya karta hai |
|---|---|---|
| `/start` | Sab | Bot shuru karo |
| `/stats` | Admin only | Users, payments, revenue dekho |
| `/broadcast` | Admin only | Kisi message ko reply karke sabko bhejo |
| `/check <user_id> <amount>` | Admin only | Kisi user ka payment check karo |

---

## Stack

- **Language**: Python 3.11
- **Bot Framework**: python-telegram-bot 21.6
- **Payments**: Razorpay (Payment Links + UPI QR Code API)
- **Database**: MongoDB (pymongo)
- **QR**: Razorpay QR Code API (cropped to plain QR)

## Admin IDs

- Username: `@aritramahatma`
- User ID: `7342290214`

## User Preferences

- Bot text: Unicode small caps + bold HTML
- No webhooks — polling mode
- Koyeb compatible (long-running process)
