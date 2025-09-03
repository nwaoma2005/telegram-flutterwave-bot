import os
import json
import logging
from flask import Flask, request, jsonify
import telebot

# ================== CONFIG ==================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8419563253:AAGT9t6T7MJ-3qCDV08gTZLtCsBeEd-hF_Q")
WEBHOOK_URL = f"https://telegram-flutterwave-bot-2.onrender.com/webhook/{TELEGRAM_BOT_TOKEN}"

# Telegram Bot instance
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)

# Flask app
app = Flask(__name__)

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== ROUTES ==================
@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot is running!", 200

@app.route(f"/webhook/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handle Telegram webhook updates"""
    update = request.get_json(force=True)
    logger.info(f"Incoming Telegram update: {json.dumps(update)}")

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            bot.send_message(chat_id, "👋 Welcome! Send /pay to get the payment link.")
        elif text == "/pay":
            # Replace with real Flutterwave link later
            bot.send_message(chat_id, "💳 Use this link to make payment: https://flutterwave.com/pay")
        else:
            bot.send_message(chat_id, "I don’t understand. Use /start or /pay.")

    return jsonify({"ok": True})

# ================== MAIN ==================
if __name__ == "__main__":
    # Remove old webhook first (important)
    bot.remove_webhook()
    # Set new webhook
    bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)