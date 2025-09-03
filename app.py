import os
import json
import hmac
import hashlib
import requests
import time
from flask import Flask, request, jsonify
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Get environment variables
FLUTTERWAVE_SECRET_KEY = os.getenv('FLUTTERWAVE_SECRET_KEY')
FLUTTERWAVE_WEBHOOK_SECRET = os.getenv('FLUTTERWAVE_WEBHOOK_SECRET')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')

class FlutterwavePaymentBot:
    def __init__(self):
        self.secret_key = FLUTTERWAVE_SECRET_KEY
        self.webhook_secret = FLUTTERWAVE_WEBHOOK_SECRET
        
    def verify_webhook_signature(self, payload, signature):
        """Verify that the webhook is from Flutterwave"""
        if not signature or not self.webhook_secret:
            return True  # Allow for testing
            
        if signature.startswith('v1='):
            signature = signature[3:]
            
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def verify_payment(self, transaction_id):
        """Verify payment with Flutterwave API"""
        if not self.secret_key:
            return {"status": "error", "message": "No secret key"}
            
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
    
    def send_telegram_message(self, user_id, message):
        """Send message to user via Telegram"""
        if not TELEGRAM_BOT_TOKEN:
            logger.error("No Telegram bot token")
            return False
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            logger.info(f"Message sent to user {user_id}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def create_invite_link(self, user_id):
        """Create invite link for user to join channel"""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
            return None
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createChatInviteLink"
        data = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "member_limit": 1,
            "name": f"Payment access for user {user_id}"
        }
        
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                return result["result"]["invite_link"]
        except requests.RequestException as e:
            logger.error(f"Failed to create invite link: {e}")
            
        return None

# Initialize the payment bot
payment_bot = FlutterwavePaymentBot()

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with environment variable status"""
    env_status = {
        "FLUTTERWAVE_SECRET_KEY": "✅ Set" if FLUTTERWAVE_SECRET_KEY else "❌ Missing",
        "FLUTTERWAVE_WEBHOOK_SECRET": "✅ Set" if FLUTTERWAVE_WEBHOOK_SECRET else "❌ Missing", 
        "TELEGRAM_BOT_TOKEN": "✅ Set" if TELEGRAM_BOT_TOKEN else "❌ Missing",
        "TELEGRAM_CHANNEL_ID": "✅ Set" if TELEGRAM_CHANNEL_ID else "❌ Missing"
    }
    
    return jsonify({
        "status": "Flutterwave-Telegram Bot is running!",
        "environment_variables": env_status,
        "endpoints": {
            "webhook": "/webhook/flutterwave",
            "create_payment": "/create-payment",
            "health": "/health",
            "test_telegram": "/test-telegram"
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "Bot is running successfully!",
        "timestamp": time.time()
    })

@app.route('/test-telegram', methods=['GET'])
def test_telegram():
    """Test Telegram bot connection"""
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN not set"})
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        result = response.json()
        
        if result.get("ok"):
            bot_info = result["result"]
            return jsonify({
                "status": "Telegram connection successful!",
                "bot_info": {
                    "username": bot_info.get("username"),
                    "name": bot_info.get("first_name"),
                    "id": bot_info.get("id")
                }
            })
        else:
            return jsonify({"error": "Invalid bot token"})
            
    except requests.RequestException as e:
        return jsonify({"error": f"Connection failed: {str(e)}"})

@app.route('/webhook/flutterwave', methods=['POST'])
def flutterwave_webhook():
    """Handle Flutterwave webhook notifications"""
    
    # Get the signature from headers
    signature = request.headers.get('verif-hash')
    payload = request.get_data()
    
    logger.info("Webhook received!")
    logger.info(f"Headers: {dict(request.headers)}")
    
    # Verify webhook signature (skip if no secret set for testing)
    if FLUTTERWAVE_WEBHOOK_SECRET and not payment_bot.verify_webhook_signature(payload, signature):
        logger.warning("Invalid webhook signature")
        return jsonify({"error": "Invalid signature"}), 400
    
    try:
        data = request.get_json()
        logger.info(f"Webhook data: {data}")
        
        # Check if this is a successful payment
        if data.get('event') == 'charge.completed' and data.get('data', {}).get('status') == 'successful':
            transaction_data = data['data']
            transaction_id = transaction_data.get('id')
            
            # Get user information from metadata
            metadata = transaction_data.get('meta', {})
            user_id = metadata.get('telegram_user_id')
            username = metadata.get('telegram_username')
            amount = transaction_data.get('amount')
            currency = transaction_data.get('currency')
            
            logger.info(f"Processing payment for user {user_id}, amount: {amount} {currency}")
            
            if user_id:
                # Create invite link for the user
                invite_link = payment_bot.create_invite_link(user_id)
                
                if invite_link:
                    welcome_message = f"""
🎉 <b>Payment Successful!</b> 🎉

✅ Amount: {amount} {currency}
✅ Transaction ID: {transaction_id}

🔗 <b>Your exclusive channel access:</b>
{invite_link}

Welcome to the premium channel! 🌟
"""
                else:
                    welcome_message = f"""
🎉 <b>Payment Successful!</b> 🎉

✅ Amount: {amount} {currency}
✅ Transaction ID: {transaction_id}

Your payment has been confirmed. Please contact support for channel access.
"""

                # Send welcome message
                success = payment_bot.send_telegram_message(user_id, welcome_message)
                
                if success:
                    logger.info(f"Payment processed and user {user_id} notified")
                    return jsonify({"status": "success", "message": "User notified"})
                else:
                    logger.error(f"Failed to notify user {user_id}")
                    return jsonify({"status": "partial", "message": "Payment verified but notification failed"})
            else:
                logger.warning("No Telegram user ID found in payment metadata")
                return jsonify({"status": "error", "message": "No user ID in metadata"}), 400
        
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
            return jsonify({"error": "Missing required parameters: amount, email, telegram_user_id"}), 400
        
        if not FLUTTERWAVE_SECRET_KEY:
            return jsonify({"error": "Flutterwave secret key not configured"}), 500
        
        # Create payment payload
        payment_payload = {
            "tx_ref": f"payment_{telegram_user_id}_{int(time.time())}",
            "amount": amount,
            "currency": currency,
            "redirect_url": "https://your-success-page.com",
            "customer": {
                "email": email,
                "name": telegram_username or f"User_{telegram_user_id}"
            },
            "meta": {
                "telegram_user_id": str(telegram_user_id),
                "telegram_username": telegram_username or ""
            },
            "customizations": {
                "title": "Premium Channel Access",
                "description": "Payment for exclusive channel access"
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
@app.route('/payment-form', methods=['GET'])
def payment_form():
    return '''[<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generate Payment Link</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #555;
        }
        input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
            box-sizing: border-box;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #4CAF50;
        }
        button {
            width: 100%;
            padding: 15px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 18px;
            cursor: pointer;
            margin-top: 10px;
        }
        button:hover {
            background-color: #45a049;
        }
        button:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
        }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 5px;
            display: none;
        }
        .success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .payment-link {
            word-break: break-all;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
            border: 1px solid #dee2e6;
        }
        .copy-btn {
            width: auto;
            padding: 8px 15px;
            font-size: 14px;
            margin-top: 10px;
            background-color: #007bff;
        }
        .copy-btn:hover {
            background-color: #0056b3;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>💳 Payment Link Generator</h1>
        <p style="text-align: center; color: #666; margin-bottom: 20px;">
            Generate Flutterwave payment links for Telegram channel access
        </p>
        
        <div style="background: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #1976d2;">📋 How to get your Telegram ID:</h3>
            <p style="margin-bottom: 0;">
                1. Open Telegram and search for <strong>@raw_data_bot</strong><br>
                2. Send any message to the bot<br>
                3. Copy your <strong>user_id</strong> from the response<br>
                4. Paste it in the form below
            </p>
        </div>
        
        <form id="paymentForm">
            <div class="form-group">
                <label for="amount">Amount *</label>
                <input type="number" id="amount" name="amount" required min="1" placeholder="1000">
            </div>
            
            <div class="form-group">
                <label for="currency">Currency</label>
                <select id="currency" name="currency">
                    <option value="NGN">NGN (Nigerian Naira)</option>
                    <option value="USD">USD (US Dollar)</option>
                    <option value="GHS">GHS (Ghanaian Cedi)</option>
                    <option value="KES">KES (Kenyan Shilling)</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="email">Customer Email *</label>
                <input type="email" id="email" name="email" required placeholder="customer@example.com">
            </div>
            
            <div class="form-group">
                <label for="telegram_user_id">Telegram User ID *</label>
                <input type="text" id="telegram_user_id" name="telegram_user_id" required placeholder="123456789">
                <small style="color: #666;">Get this by messaging @raw_data_bot on Telegram</small>
            </div>
            
            <div class="form-group">
                <label for="telegram_username">Telegram Username (Optional)</label>
                <input type="text" id="telegram_username" name="telegram_username" placeholder="username (without @)">
            </div>
            
            <button type="submit" id="generateBtn">Generate Payment Link</button>
        </form>
        
        <div id="result" class="result">
            <div id="resultContent"></div>
        </div>
    </div>

    <script>
        document.getElementById('paymentForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const generateBtn = document.getElementById('generateBtn');
            const resultDiv = document.getElementById('result');
            const resultContent = document.getElementById('resultContent');
            
            // Disable button and show loading
            generateBtn.disabled = true;
            generateBtn.textContent = 'Generating...';
            resultDiv.style.display = 'none';
            
            // Get form data
            const formData = {
                amount: parseInt(document.getElementById('amount').value),
                currency: document.getElementById('currency').value,
                email: document.getElementById('email').value,
                telegram_user_id: document.getElementById('telegram_user_id').value,
                telegram_username: document.getElementById('telegram_username').value
            };
            
            try {
                // Make API call to your bot
                const response = await fetch('https://telegram-flutterwave-bot-2.onrender.com/create-payment', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(formData)
                });
                
                const result = await response.json();
                
                if (response.ok && result.status === 'success') {
                    // Success - show payment link
                    resultContent.innerHTML = `
                        <h3>✅ Payment Link Generated Successfully!</h3>
                        <p><strong>Transaction Reference:</strong> ${result.tx_ref}</p>
                        <p><strong>Payment Link:</strong></p>
                        <div class="payment-link">${result.payment_link}</div>
                        <button class="copy-btn" onclick="copyToClipboard('${result.payment_link}')">
                            📋 Copy Link
                        </button>
                    `;
                    resultDiv.className = 'result success';
                } else {
                    // Error
                    resultContent.innerHTML = `
                        <h3>❌ Failed to Generate Payment Link</h3>
                        <p><strong>Error:</strong> ${result.error || 'Unknown error occurred'}</p>
                    `;
                    resultDiv.className = 'result error';
                }
                
            } catch (error) {
                // Network error
                resultContent.innerHTML = `
                    <h3>❌ Network Error</h3>
                    <p><strong>Error:</strong> ${error.message}</p>
                    <p>Make sure your bot is running and try again.</p>
                `;
                resultDiv.className = 'result error';
            }
            
            // Show result and reset button
            resultDiv.style.display = 'block';
            generateBtn.disabled = false;
            generateBtn.textContent = 'Generate Payment Link';
        });
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                alert('Payment link copied to clipboard!');
            }, function(err) {
                console.error('Could not copy text: ', err);
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                alert('Payment link copied to clipboard!');
            });
        }
    </script>
</body>
</html>]'''
if __name__ == '__main__':
    # Log startup info
    logger.info("Starting Flutterwave-Telegram Bot...")
    logger.info(f"FLUTTERWAVE_SECRET_KEY: {'Set' if FLUTTERWAVE_SECRET_KEY else 'Missing'}")
    logger.info(f"TELEGRAM_BOT_TOKEN: {'Set' if TELEGRAM_BOT_TOKEN else 'Missing'}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)