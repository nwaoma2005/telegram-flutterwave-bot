from flask import Flask, request, jsonify
import requests
import logging
import os
import json
import time
from telegram.ext import Updater, CommandHandler

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- ENV Variables ---
FLW_SECRET_HASH = os.getenv("FLW_SECRET_HASH", "your_real_secret_hash")
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY", "your_real_secret_key")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_INVITE_LINK = os.getenv("CHANNEL_INVITE_LINK", "https://t.me/+yourChannelInvite")

USER_FILE = "users.json"

# --- Save & Load Users ---
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

# --- Telegram Bot Commands ---
def start(update, context):
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    users = load_users()
    users[str(chat_id)] = {"username": username}
    save_users(users)

    update.message.reply_text(
        "👋 Welcome! Your Telegram ID has been saved.\n\n"
        "Use /pay <amount> to generate your payment link.\n"
        "Example: /pay 500"
    )

def pay(update, context):
    chat_id = update.message.chat_id
    users = load_users()

    if len(context.args) == 0:
        update.message.reply_text("⚠️ Please provide an amount. Example: /pay 500")
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        update.message.reply_text("⚠️ Amount must be a number. Example: /pay 500")
        return

    tx_ref = f"tx_{chat_id}_{int(time.time())}"

    # Payment request payload
    payload = {
        "tx_ref": tx_ref,
        "amount": amount,
        "currency": "NGN",
        "redirect_url": "https://yourdomain.com/payment-success",
        "customer": {
            "email": f"user_{chat_id}@example.com",  # Fake email placeholder
            "name": users.get(str(chat_id), {}).get("username", f"User_{chat_id}")
        },
        "meta": {
            "telegram_user_id": str(chat_id)
        },
        "customizations": {
            "title": "Channel Access Payment",
            "description": "Payment for private channel access"
        }
    }

    headers = {
        "Authorization": f"Bearer {FLW_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    resp = requests.post("https://api.flutterwave.com/v3/payments", json=payload, headers=headers)

    if resp.status_code == 200:
        link = resp.json()["data"]["link"]
        update.message.reply_text(f"💳 Click here to pay: {link}")
    else:
        update.message.reply_text("❌ Failed to create payment link. Try again later.")

# --- Setup Bot ---
def setup_bot():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("pay", pay))
    updater.start_polling()
    return updater

# --- Send Telegram Invite ---
def send_telegram_invite(chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"🎉 Payment confirmed!\nHere’s your private channel invite link: {CHANNEL_INVITE_LINK}"
    }
    requests.post(url, json=payload)

# --- Flutterwave Webhook ---
@app.route("/webhook/flutterwave", methods=["POST"])
def flutterwave_webhook():
    received_hash = request.headers.get("verif-hash")
    if not received_hash or received_hash != FLW_SECRET_HASH:
        logging.warning("❌ Invalid webhook signature")
        return jsonify({"status": "error", "message": "Invalid signature"}), 400

    data = request.get_json()
    logging.info(f"Webhook data: {data}")

    tx_status = data.get("status")
    meta = data.get("meta", {})
    chat_id = meta.get("telegram_user_id")

    if tx_status == "successful" and chat_id:
        logging.info(f"✅ Payment success for user {chat_id}")
        send_telegram_invite(chat_id)

    return jsonify({"status": "success"}), 200


if __name__ == "__main__":
    setup_bot()
    app.run(host="0.0.0.0", port=5000)