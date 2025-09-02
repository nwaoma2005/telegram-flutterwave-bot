import os
import json
import hmac
import hashlib
import requests
import time
from flask import Flask, request, jsonify
from telegram import Bot
from telegram.error import TelegramError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration - Set these as environment variables
FLUTTERWAVE_SECRET_KEY = os.getenv('FLUTTERWAVE_SECRET_KEY')
FLUTTERWAVE_WEBHOOK_SECRET = os.getenv('FLUTTERWAVE_WEBHOOK_SECRET')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')  # Channel username or ID

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

class FlutterwavePaymentBot:
    def __init__(self):
        self.secret_key = FLUTTERWAVE_SECRET_KEY
        self.webhook_secret = FLUTTERWAVE_WEBHOOK_SECRET
        
    def verify_webhook_signature(self, payload, signature):
        """Verify that the webhook is from Flutterwave"""
        if not signature:
            return False
            
        # Remove 'v1=' prefix if present
        if signature.startswith('v1='):
            signature = signature[3:]
            
        # Create hash using webhook secret
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def verify_payment(self, transaction_id):
        """Verify payment with Flutterwave API"""
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
            logger.error(f"Error verifying payment: {e}")
            return None
    
    def add_user_to_channel(self, user_id, username=None):
        """Add user to Telegram private channel"""
        try:
            # Create invite link for the user
            invite_link = bot.create_chat_invite_link(
                chat_id=TELEGRAM_CHANNEL_ID,
                member_limit=1,
                name=f"Payment access for user {user_id}"
            )
            
            # Send invite link to user
            welcome_message = f"🎉 Payment successful! Here's your exclusive access link:\n\n{invite_link.invite_link}\n\nWelcome to the premium channel!"
            if username:
                welcome_message = f"🎉 Hello @{username}! Payment successful!\n\nHere's your exclusive access link:\n{invite_link.invite_link}\n\nWelcome to the premium channel!"
                
            bot.send_message(
                chat_id=user_id,
                text=welcome_message
            )
            
            logger.info(f"Successfully sent invite link to user {user_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Error adding user to channel: {e}")
            # Fallback: try direct add
            try:
                bot.unban_chat_member(chat_id=TELEGRAM_CHANNEL_ID, user_id=user_id)
                bot.send_message(chat_id=user_id, text="Payment successful! You've been added to the channel.")
                return True
            except:
                return False

# Initialize the payment bot
payment_bot = FlutterwavePaymentBot()

@app.route('/', methods=['GET'])
def home():
    """Home endpoint to verify bot is running"""
    return jsonify({
        "status": "Bot is running!",
        "endpoints": {
            "webhook": "/webhook/flutterwave",
            "create_payment": "/create-payment", 
            "health": "/health"
        }
    })

@app.route('/webhook/flutterwave', methods=['POST'])
def flutterwave_webhook():
    """Handle Flutterwave webhook notifications"""
    
    # Get the signature from headers
    signature = request.headers.get('verif-hash')
    payload = request.get_data()
    
    # Verify webhook signature
    if not payment_bot.verify_webhook_signature(payload, signature):
        logger.warning("Invalid webhook signature")
        return jsonify({"error": "Invalid signature"}), 400
    
    try:
        data = request.get_json()
        
        # Check if this is a successful payment
        if data.get('event') == 'charge.completed' and data.get('data', {}).get('status') == 'successful':
            transaction_data = data['data']
            transaction_id = transaction_data.get('id')
            
            # Verify the payment with Flutterwave API
            verification_result = payment_bot.verify_payment(transaction_id)
            
            if verification_result and verification_result.get('status') == 'success':
                payment_data = verification_result['data']
                
                # Extract user information from metadata
                metadata = payment_data.get('meta', {})
                user_id = metadata.get('telegram_user_id')
                username = metadata.get('telegram_username')
                
                if user_id:
                    # Add user to Telegram channel
                    success = payment_bot.add_user_to_channel(user_id, username)
                    
                    if success:
                        logger.info(f"Payment processed and user {user_id} added to channel")
                        return jsonify({"status": "success", "message": "User added to channel"})
                    else:
                        logger.error(f"Failed to add user {user_id} to channel")
                        return jsonify({"status": "error", "message": "Failed to add user to channel"}), 500
                else:
                    logger.warning("No Telegram user ID found in payment metadata")
                    return jsonify({"status": "error", "message": "No user ID in metadata"}), 400
            else:
                logger.warning(f"Payment verification failed for transaction {transaction_id}")
                return jsonify({"status": "error", "message": "Payment verification failed"}), 400
        
        return jsonify({"status": "ignored", "message": "Event not processed"})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/create-payment', methods=['POST'])
def create_payment():
    """Create a payment link with user metadata"""
    
    try:
        data = request.get_json()
        
        # Required parameters
        amount = data.get('amount')
        currency = data.get('currency', 'NGN')
        email = data.get('email')
        telegram_user_id = data.get('telegram_user_id')
        telegram_username = data.get('telegram_username')
        
        if not all([amount, email, telegram_user_id]):
            return jsonify({"error": "Missing required parameters"}), 400
        
        # Create payment payload
        payment_payload = {
            "tx_ref": f"payment_{telegram_user_id}_{int(time.time())}",
            "amount": amount,
            "currency": currency,
            "redirect_url": "https://your-domain.com/payment-success",
            "customer": {
                "email": email,
                "name": telegram_username or f"User_{telegram_user_id}"
            },
            "meta": {
                "telegram_user_id": str(telegram_user_id),
                "telegram_username": telegram_username
            },
            "customizations": {
                "title": "Channel Access Payment",
                "description": "Payment for private channel access"
            }
        }
        
        # Make request to Flutterwave
        headers = {
            "Authorization": f"Bearer {FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            "https://api.flutterwave.com/v3/payments",
            json=payment_payload,
            headers=headers
        )
        
        if response.status_code == 200:
            payment_data = response.json()
            return jsonify({
                "status": "success",
                "payment_link": payment_data['data']['link'],
                "tx_ref": payment_payload['tx_ref']
            })
        else:
            logger.error(f"Flutterwave API error: {response.text}")
            return jsonify({"error": "Failed to create payment"}), 500
            
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    # Validate environment variables
    required_vars = [
        'FLUTTERWAVE_SECRET_KEY',
        'FLUTTERWAVE_WEBHOOK_SECRET', 
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHANNEL_ID'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        exit(1)
    
    app.run(debug=False, host='0.0.0.0', port=5000)