import os
import hmac
import hashlib
import logging
from flask import Flask, request, render_template, jsonify
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler

# ==============================
# Config
# ==============================
TELEGRAM_BOT_TOKEN = "8419563253:AAGT9t6T7MJ-3qCDV08gTZLtCsBeEd-hF_Q"
FLW_SECRET_HASH = os.getenv("FLW_SECRET_HASH", "Blessed0704")  # must match Flutterwave dashboard

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ==============================
# Telegram Bot Handlers
# ==============================
dispatcher = Dispatcher(bot, None, workers=0)

def start(update, context):
    """Handles /start command"""
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name

    welcome_text = (
        f"👋 Hello {username}!\n\n"
        "Welcome to the Flutterwave Payment Bot.\n\n"
        "👉 Use the payment form to make a test payment:\n"
        "https://telegram-flutterwave-bot-2.onrender.com/payment-form"
    )
    context.bot.send_message(chat_id=user_id, text=welcome_text)

dispatcher.add_handler(CommandHandler("start", start))

# ==============================
# Telegram Webhook
# ==============================
@app.route(f"/webhook/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handles Telegram updates"""
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

# ==============================
# Payment Form (Frontend)
# ==============================
@app.route("/payment-form")
def payment_form():
    return render_template("payment_form.html")

# ==============================
# Flutterwave Webhook
# ==============================
@app.route("/webhook/flutterwave", methods=["POST"])
def flutterwave_webhook():
    """Handles Flutterwave payment webhook"""
    signature = request.headers.get("verif-hash")
    if not signature or signature != FLW_SECRET_HASH:
        logging.warning("Invalid webhook signature")
        return jsonify({"status": "error", "message": "Invalid signature"}), 400

    data = request.get_json()
    logging.info(f"Webhook received: {data}")

    # You can send Telegram notification here
    chat_id = <PUT_YOUR_TELEGRAM_CHAT_ID_HERE>  # optional
    try:
        bot.send_message(chat_id=chat_id, text=f"💰 Payment received: {data}")
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")

    return jsonify({"status": "success"}), 200

# ==============================
# Root route
# ==============================
@app.route("/")
def home():
    return "✅ Telegram + Flutterwave bot is running!"

# ==============================
# Main entry
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)