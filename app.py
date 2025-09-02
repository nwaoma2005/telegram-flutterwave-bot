import os
import logging
import requests
from flask import Flask, request, jsonify

# ------------------------------------------------
# Logging setup
# ------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ------------------------------------------------
# Flask app
# ------------------------------------------------
app = Flask(__name__)

# ------------------------------------------------
# API Keys (from Render environment variables)
# ------------------------------------------------
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY")
FLW_SECRET_HASH = os.getenv("FLW_SECRET_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# ------------------------------------------------
# Routes
# ------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    logger.info("Health check endpoint hit ✅")
    return jsonify({"status": "running", "message": "Telegram-Flutterwave bot is live 🚀"})

@app.route("/create-payment", methods=["POST"])
def create_payment():
    logger.info("Received request to create a payment link")

    data = request.json
    logger.debug(f"Request body: {data}")

    required = ["amount", "email", "telegram_user_id"]
    if not all(field in data for field in required):
        logger.warning("Missing required fields in /create-payment request")
        return jsonify({"error": "Missing required fields"}), 400

    payload = {
        "tx_ref": f"tx-{os.urandom(8).hex()}",
        "amount": data["amount"],
        "currency": "NGN",
        "redirect_url": "https://yourapp.com/payment-success",
        "customer": {
            "email": data["email"],
            "phonenumber": data.get("phone", "08012345678"),
            "name": data.get("name", "User"),
        },
        "meta": {
            "telegram_user_id": data["telegram_user_id"],
            "telegram_username": data.get("telegram_username", "N/A"),
        },
        "customizations": {
            "title": "Channel Access",
            "description": "Pay to join our private Telegram channel",
        },
    }

    try:
        response = requests.post(
            "https://api.flutterwave.com/v3/payments",
            json=payload,
            headers={"Authorization": f"Bearer {FLW_SECRET_KEY}"}
        )
        response.raise_for_status()
        resp_data = response.json()
        logger.info(f"Payment link created successfully for {data['email']}")

        return jsonify({
            "payment_link": resp_data["data"]["link"],
            "tx_ref": payload["tx_ref"]
        })

    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/webhook/flutterwave", methods=["POST"])
def flutterwave_webhook():
    logger.info("Received Flutterwave webhook")

    signature = request.headers.get("verif-hash")
    if signature != FLW_SECRET_HASH:
        logger.warning("Invalid webhook signature ❌")
        return "Invalid signature", 400

    payload = request.json
    logger.debug(f"Webhook payload: {payload}")

    flw_ref = payload.get("data", {}).get("id")
    if not flw_ref:
        logger.warning("No transaction ID found in webhook")
        return "Invalid payload", 400

    # Verify payment with Flutterwave
    try:
        verify = requests.get(
            f"https://api.flutterwave.com/v3/transactions/{flw_ref}/verify",
            headers={"Authorization": f"Bearer {FLW_SECRET_KEY}"}
        )
        verify.raise_for_status()
        v_data = verify.json()
        logger.debug(f"Verification response: {v_data}")

        if v_data.get("data", {}).get("status") == "successful":
            telegram_user_id = v_data["data"]["meta"].get("telegram_user_id")
            telegram_username = v_data["data"]["meta"].get("telegram_username")

            if not telegram_user_id:
                logger.error("No telegram_user_id in metadata ❌")
                return "Missing Telegram ID", 400

            invite_url = f"https://t.me/{CHANNEL_ID}"
            message = (
                f"✅ Hi {telegram_username}, your payment was successful!\n"
                f"Join the private channel here 👉 {invite_url}"
            )

            telegram_api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            tg_resp = requests.post(
                telegram_api,
                json={"chat_id": telegram_user_id, "text": message}
            )
            logger.info(f"Sent invite to Telegram user {telegram_user_id}, response: {tg_resp.status_code}")

            return "Webhook processed", 200
        else:
            logger.warning(f"Payment not successful: {v_data}")
            return "Payment not successful", 400

    except Exception as e:
        logger.error(f"Error verifying payment: {e}")
        return "Error verifying payment", 500

# ------------------------------------------------
# Run server
# ------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port)