import os import json import hmac import hashlib import requests import time from flask import Flask, request, jsonify import logging

Configure logging

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

app = Flask(name)

Environment variables

FLUTTERWAVE_SECRET_KEY = os.getenv('FLUTTERWAVE_SECRET_KEY') FLUTTERWAVE_WEBHOOK_SECRET = os.getenv('FLUTTERWAVE_WEBHOOK_SECRET') TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')

class FlutterwavePaymentBot: def init(self): self.secret_key = FLUTTERWAVE_SECRET_KEY self.webhook_secret = FLUTTERWAVE_WEBHOOK_SECRET

def verify_webhook_signature(self, payload, signature):
    if not signature or not self.webhook_secret:
        return True
    if signature.startswith('v1='):
        signature = signature[3:]
    expected_signature = hmac.new(
        self.webhook_secret.encode('utf-8'), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

def verify_payment(self, transaction_id):
    if not self.secret_key:
        return {"status": "error", "message": "No secret key"}
    url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
    headers = {"Authorization": f"Bearer {self.secret_key}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error verifying payment: {e}")
        return None

def send_telegram_message(self, chat_id, message):
    if not TELEGRAM_BOT_TOKEN:
        logger.error("No Telegram bot token")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        logger.info(f"Message sent to {chat_id}")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send message: {e}")
        return False

def create_invite_link(self, user_id):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createChatInviteLink"
    data = {"chat_id": TELEGRAM_CHANNEL_ID, "member_limit": 1, "name": f"Access for {user_id}"}
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        result = response.json()
        if result.get("ok"):
            return result["result"]["invite_link"]
    except requests.RequestException as e:
        logger.error(f"Failed to create invite link: {e}")
    return None

payment_bot = FlutterwavePaymentBot()

--- ROOT INFO ---

@app.route('/', methods=['GET']) def home(): env_status = { "FLUTTERWAVE_SECRET_KEY": "✅ Set" if FLUTTERWAVE_SECRET_KEY else "❌ Missing", "FLUTTERWAVE_WEBHOOK_SECRET": "✅ Set" if FLUTTERWAVE_WEBHOOK_SECRET else "❌ Missing", "TELEGRAM_BOT_TOKEN": "✅ Set" if TELEGRAM_BOT_TOKEN else "❌ Missing", "TELEGRAM_CHANNEL_ID": "✅ Set" if TELEGRAM_CHANNEL_ID else "❌ Missing" } return jsonify({ "status": "Bot is running", "environment_variables": env_status, "endpoints": { "home": "/", "health": "/health", "test_telegram": "/test-telegram", "create_payment": "/create-payment", "payment_form": "/payment-form", "webhook_flutterwave": "/webhook/flutterwave", "webhook_telegram": "/telegram-webhook" } })

--- TELEGRAM BOT HANDLER ---

@app.route('/telegram-webhook', methods=['POST']) def telegram_webhook(): data = request.get_json() logger.info(f"Telegram update: {data}")

if "message" in data:
    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if text.startswith("/start"):
        welcome_message = (
            "👋 Welcome to the Premium Access Bot!\n\n"
            "💳 To access our premium Telegram channel, you need to make a payment.\n\n"
            "1️⃣ Click the link below to generate your payment link.\n"
            "2️⃣ Complete the payment securely via Flutterwave.\n"
            "3️⃣ Once confirmed, you will automatically receive the channel invite link.\n\n"
            f"🔗 Payment Form: https://YOUR_DOMAIN/payment-form"
        )
        payment_bot.send_telegram_message(chat_id, welcome_message)

return jsonify({"ok": True})

--- FLUTTERWAVE WEBHOOK HANDLER ---

@app.route('/webhook/flutterwave', methods=['POST']) def flutterwave_webhook(): signature = request.headers.get('verif-hash') payload = request.get_data() if FLUTTERWAVE_WEBHOOK_SECRET and not payment_bot.verify_webhook_signature(payload, signature): return jsonify({"error": "Invalid signature"}), 400

try:
    data = request.get_json()
    if data.get('event') == 'charge.completed' and data.get('data', {}).get('status') == 'successful':
        tx = data['data']
        user_id = tx.get('meta', {}).get('telegram_user_id')
        amount = tx.get('amount')
        currency = tx.get('currency')

        if user_id:
            invite_link = payment_bot.create_invite_link(user_id)
            if invite_link:
                message = (
                    f"🎉 <b>Payment Successful!</b>\n\n"
                    f"✅ Amount: {amount} {currency}\n"
                    f"🔗 Your channel access link: {invite_link}\n\n"
                    "Welcome to the premium channel! 🌟"
                )
                payment_bot.send_telegram_message(user_id, message)
                logger.info(f"Payment processed for {user_id}")
except Exception as e:
    logger.error(f"Error processing webhook: {e}")
    return jsonify({"error": "Internal server error"}), 500

return jsonify({"status": "ok"})

--- CREATE PAYMENT ---

@app.route('/create-payment', methods=['POST']) def create_payment(): try: data = request.get_json() amount = data.get('amount') currency = data.get('currency', 'NGN') email = data.get('email') telegram_user_id = data.get('telegram_user_id') telegram_username = data.get('telegram_username')

if not all([amount, email, telegram_user_id]):
        return jsonify({"error": "Missing required parameters"}), 400

    payment_payload = {
        "tx_ref": f"payment_{telegram_user_id}_{int(time.time())}",
        "amount": amount,
        "currency": currency,
        "redirect_url": "https://YOUR_DOMAIN/health",
        "customer": {"email": email, "name": telegram_username or f"User_{telegram_user_id}"},
        "meta": {"telegram_user_id": str(telegram_user_id), "telegram_username": telegram_username or ""},
        "customizations": {"title": "Premium Channel Access", "description": "Payment for exclusive channel access"}
    }

    headers = {"Authorization": f"Bearer {FLUTTERWAVE_SECRET_KEY}", "Content-Type": "application/json"}
    response = requests.post("https://api.flutterwave.com/v3/payments", json=payment_payload, headers=headers)

    if response.status_code == 200:
        payment_data = response.json()
        return jsonify({"status": "success", "payment_link": payment_data['data']['link'], "tx_ref": payment_payload['tx_ref']})
    else:
        logger.error(f"Flutterwave API error: {response.text}")
        return jsonify({"error": "Failed to create payment"}), 500
except Exception as e:
    logger.error(f"Error creating payment: {e}")
    return jsonify({"error": "Internal server error"}), 500

--- HEALTH CHECK ---

@app.route('/health', methods=['GET']) def health_check(): return jsonify({"status": "healthy", "timestamp": time.time()})

--- TEST TELEGRAM ---

@app.route('/test-telegram', methods=['GET']) def test_telegram(): if not TELEGRAM_BOT_TOKEN: return jsonify({"error": "TELEGRAM_BOT_TOKEN not set"}) url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe" try: response = requests.get(url) response.raise_for_status() return response.json() except requests.RequestException as e: return jsonify({"error": f"Connection failed: {str(e)}"})

--- PAYMENT FORM ---

@app.route('/payment-form', methods=['GET']) def payment_form(): return "<h1>Payment Form Page</h1><p>Use the form to generate payment link.</p>"

if name == "main": logger.info("Starting Flutterwave-Telegram bot service...") logger.info(f"FLUTTERWAVE_SECRET_KEY: {'SET' if FLUTTERWAVE_SECRET_KEY else 'MISSING'}") logger.info(f"FLUTTERWAVE_WEBHOOK_SECRET: {'SET' if FLUTTERWAVE_WEBHOOK_SECRET else 'MISSING'}") logger.info(f"TELEGRAM_BOT_TOKEN: {'SET' if TELEGRAM_BOT_TOKEN else 'MISSING'}") logger.info(f"TELEGRAM_CHANNEL_ID: {'SET' if TELEGRAM_CHANNEL_ID else 'MISSING'}") app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

