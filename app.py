import os
import json
import hmac
import hashlib
import requests
import time
import logging
from flask import Flask, request, jsonify
from telegram import Bot, TelegramError

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === Environment Variables ===
FLUTTERWAVE_SECRET_KEY = os.getenv("FLUTTERWAVE_SECRET_KEY")
FLUTTERWAVE_WEBHOOK_SECRET = os.getenv("FLUTTERWAVE_WEBHOOK_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")  # Channel ID or username

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# === Flutterwave Bot Class ===
class FlutterwavePaymentBot:
    def __init__(self):
        self.secret_key = FLUTTERWAVE_SECRET_KEY
        self.webhook_secret = FLUTTERWAVE_WEBHOOK_SECRET

    def verify_webhook_signature(self, payload, signature):
        """Check Flutterwave webhook authenticity"""
        if not signature:
            return False
        if signature.startswith("v1="):
            signature = signature[3:]
        expected_signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    def verify_payment(self, transaction_id):
        """Verify Flutterwave payment"""
        url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Payment verification error: {e}")
            return None

    def add_user_to_channel(self, user_id, username=None):
        """Invite user to Telegram channel"""
        try:
            invite_link = bot.create_chat_invite_link(
                chat_id=TELEGRAM_CHANNEL_ID,
                member_limit=1,
                name=f"Payment access for {user_id}"
            )
            message = (
                f"🎉 Hello @{username}! Payment successful!\n\n"
                if username else "🎉 Payment successful!\n\n"
            )
            message += f"Here’s your channel access link:\n{invite_link.invite_link}"
            bot.send_message(chat_id=user_id, text=message)
            return True
        except TelegramError as e:
            logger.error(f"Channel invite error: {e}")
            return False

payment_bot = FlutterwavePaymentBot()

# === Routes ===
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Bot is live"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})

# === Telegram Webhook ===
@app.route(f"/webhook/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json()
    logger.info(f"Telegram update: {update}")

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            bot.send_message(
                chat_id,
                "👋 Welcome! Use /pay to get your payment link."
            )

        elif text == "/pay":
            # Create a Flutterwave payment link
            tx_ref = f"payment_{chat_id}_{int(time.time())}"
            payload = {
                "tx_ref": tx_ref,
                "amount": "500",  # test amount
                "currency": "NGN",
                "redirect_url": "https://your-domain.com/payment-success",
                "customer": {"email": f"user{chat_id}@test.com", "name": f"User_{chat_id}"},
                "meta": {"telegram_user_id": str(chat_id)},
                "customizations": {"title": "Channel Access", "description": "Payment for channel access"}
            }
            headers = {"Authorization": f"Bearer {FLUTTERWAVE_SECRET_KEY}", "Content-Type": "application/json"}
            r = requests.post("https://api.flutterwave.com/v3/payments", json=payload, headers=headers)
            if r.status_code == 200:
                payment_link = r.json()["data"]["link"]
                bot.send_message(chat_id, f"💳 Complete your payment here:\n{payment_link}")
            else:
                bot.send_message(chat_id, "⚠️ Failed to create payment link. Try again.")

    return jsonify({"ok": True})

# === Flutterwave Webhook ===
@app.route("/webhook/flutterwave", methods=["POST"])
def flutterwave_webhook():
    signature = request.headers.get("verif-hash")
    payload = request.get_data()

    if not payment_bot.verify_webhook_signature(payload, signature):
        logger.warning("Invalid webhook signature")
        return jsonify({"error": "Invalid signature"}), 400

    data = request.get_json()
    logger.info(f"Flutterwave event: {data}")

    if data.get("event") == "charge.completed" and data.get("data", {}).get("status") == "successful":
        transaction_id = data["data"].get("id")
        verification = payment_bot.verify_payment(transaction_id)

        if verification and verification.get("status") == "success":
            meta = verification["data"].get("meta", {})
            user_id = int(meta.get("telegram_user_id", 0))
            if user_id:
                payment_bot.add_user_to_channel(user_id)
                return jsonify({"status": "success"})
    return jsonify({"status": "ignored"})

# === Run Server ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))