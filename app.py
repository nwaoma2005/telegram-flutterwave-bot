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
    
    def send_telegram_message(self, user_id, message, reply_markup=None):
        """Send message to user via Telegram"""
        if not TELEGRAM_BOT_TOKEN:
            logger.error("No Telegram bot token")
            return False
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        if reply_markup:
            data["reply_markup"] = reply_markup
        
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
            "name": f"Payment access for user {user_id}",
            "expire_date": int(time.time()) + (7 * 24 * 60 * 60)  # Expires in 7 days
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
    
    def process_telegram_update(self, update_data):
        """Process incoming Telegram messages"""
        try:
            if "message" not in update_data:
                return
                
            message = update_data["message"]
            user_id = message["from"]["id"]
            username = message["from"].get("username", "")
            first_name = message["from"].get("first_name", "User")
            text = message.get("text", "")
            
            logger.info(f"Message from user {user_id}: {text}")
            
            # Handle /start command
            if text.startswith("/start"):
                welcome_message = f"""
🌟 <b>Welcome to Premium Channel Access Bot!</b> 🌟

Hello {first_name}! 👋

I help you get access to exclusive premium content through secure payments.

<b>📋 How it works:</b>
1️⃣ Click the payment link below
2️⃣ Enter your details and pay securely via Flutterwave  
3️⃣ After successful payment, I'll send you the channel invite link instantly
4️⃣ Join and enjoy exclusive premium content!

<b>🔗 Generate Your Payment Link:</b>
👉 https://telegram-flutterwave-bot-2.onrender.com/payment-form

<b>📝 Important Instructions:</b>
• Get your Telegram ID from @raw_data_bot first
• Use the same email for payment that you'll use for support
• Your channel access link will be sent here after payment
• Links expire in 7 days, so use them quickly!

<b>💳 Secure Payment:</b> All payments processed via Flutterwave - completely safe and secure.

Need help? Just message me anytime! 🚀
"""
                
                # Send welcome message
                self.send_telegram_message(user_id, welcome_message)
                
            # Handle other messages
            else:
                help_message = f"""
Hi {first_name}! 👋

To get access to the premium channel:

1️⃣ <b>Generate payment link:</b>
👉 https://telegram-flutterwave-bot-2.onrender.com/payment-form

2️⃣ <b>Get your Telegram ID from @raw_data_bot</b>

3️⃣ <b>Complete payment</b> - I'll send your channel link instantly!

Type /start to see the full welcome message.
"""
                self.send_telegram_message(user_id, help_message)
                
        except Exception as e:
            logger.error(f"Error processing Telegram update: {e}")

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
        "bot_username": "@payblessedbot",
        "environment_variables": env_status,
        "endpoints": {
            "webhook": "/webhook/flutterwave",
            "telegram_webhook": "/webhook/telegram",
            "create_payment": "/create-payment",
            "payment_form": "/payment-form",
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

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """Handle incoming Telegram messages"""
    try:
        update_data = request.get_json()
        logger.info(f"Telegram webhook received: {update_data}")
        
        payment_bot.process_telegram_update(update_data)
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/webhook/flutterwave', methods=['POST'])
def flutterwave_webhook():
    """Handle Flutterwave webhook notifications"""
    
    # Get the signature from headers
    signature = request.headers.get('verif-hash')
    payload = request.get_data()
    
    logger.info("Flutterwave webhook received!")
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
🎉 <b>PAYMENT SUCCESSFUL!</b> 🎉

✅ <b>Amount:</b> {amount} {currency}
✅ <b>Transaction ID:</b> {transaction_id}
✅ <b>Status:</b> Confirmed

🔗 <b>YOUR EXCLUSIVE CHANNEL ACCESS:</b>

{invite_link}

🌟 <b>Welcome to the Premium Channel!</b> 

<b>⚠️ IMPORTANT:</b>
• This link expires in 7 days
• Click the link above to join instantly  
• Save this message for future reference
• Enjoy exclusive premium content!

Thank you for your payment! 🚀
"""
                    
                    # Also send a simple message with just the link for easy access
                    simple_link_message = f"""
🔗 <b>Quick Access Link:</b>

{invite_link}

Tap to join the premium channel instantly!
"""
                    
                else:
                    welcome_message = f"""
🎉 <b>PAYMENT SUCCESSFUL!</b> 🎉

✅ <b>Amount:</b> {amount} {currency}
✅ <b>Transaction ID:</b> {transaction_id}

Your payment has been confirmed! 

⚠️ There was a technical issue generating your channel link. Please contact support with your transaction ID: {transaction_id}

We'll manually add you to the channel within 24 hours.
"""
                    simple_link_message = "Please contact support for manual channel access."

                # Send both messages
                success1 = payment_bot.send_telegram_message(user_id, welcome_message)
                time.sleep(1)  # Small delay between messages
                success2 = payment_bot.send_telegram_message(user_id, simple_link_message)
                
                if success1 or success2:
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
            "redirect_url": "https://telegram-flutterwave-bot-2.onrender.com/payment-success",
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

@app.route('/payment-success', methods=['GET'])
def payment_success():
    """Success page after payment"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Successful!</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f8ff; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
            h1 { color: #4CAF50; margin-bottom: 20px; }
            .emoji { font-size: 64px; margin: 20px 0; }
            p { font-size: 18px; line-height: 1.6; color: #333; }
            .highlight { background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0; }
            .bot-link { display: inline-block; background: #0088cc; color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; margin: 20px 0; font-size: 18px; }
            .bot-link:hover { background: #006699; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji">🎉</div>
            <h1>Payment Successful!</h1>
            <p>Your payment has been processed successfully.</p>
            
            <div class="highlight">
                <strong>Your channel access link is being sent to you on Telegram right now!</strong>
            </div>
            
            <p>Check your Telegram messages from <strong>@payblessedbot</strong> for your exclusive channel invite link.</p>
            
            <a href="https://t.me/payblessedbot" class="bot-link">Open Telegram Bot</a>
            
            <p><small>If you don't receive the link within 5 minutes, please contact support.</small></p>
        </div>
    </body>
    </html>
    '''

@app.route('/payment-form', methods=['GET'])
def payment_form():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Premium Channel Access</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 20px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 16px;
        }
        .instructions {
            background: #e3f2fd;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 25px;
            border-left: 4px solid #2196f3;
        }
        .instructions h3 {
            margin-top: 0;
            color: #1976d2;
            font-size: 18px;
        }
        .instructions ol {
            margin: 10px 0;
            padding-left: 20px;
        }
        .instructions li {
            margin: 8px 0;
            line-height: 1.5;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #555;
            font-size: 14px;
        }
        input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            box-sizing: border-box;
            transition: border-color 0.3s;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #4CAF50;
        }
        small {
            color: #666;
            font-size: 12px;
            display: block;
            margin-top: 5px;
        }
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 10px;
            transition: all 0.3s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(76, 175, 80, 0.4);
        }
        button:disabled {
            background: #cccccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        .result {
            margin-top: 20px;
            padding: 20px;
            border-radius: 8px;
            display: none;
        }
        .success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .payment-link {
            word-break: break-all;
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border: 1px solid #dee2e6;
            font-family: monospace;
        }
        .copy-btn {
            width: auto;
            padding: 10px 20px;
            font-size: 14px;
            margin-top: 10px;
            background: linear-gradient(135deg, #007bff, #0056b3);
        }
        .emoji {
            font-size: 24px;
            margin-right: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1><span class="emoji">💳</span>Premium Channel Access</h1>
        <p class="subtitle">Secure payment portal for exclusive content access</p>
        
        <div class="instructions">
            <h3><span class="emoji">📋</span>How to Get Your Telegram ID:</h3>
            <ol>
                <li>Open Telegram and search for <strong>@raw_data_bot</strong></li>
                <li>Send any message to the bot (like "hi")</li>
                <li>Copy your <strong>user_id</strong> from the response</li>
                <li>Paste it in the form below</li>
            </ol>
            <p><strong>Note:</strong> After payment, your channel invite link will be sent to your Telegram account instantly!</p>
        </div>
        
        <form id="paymentForm">
            <div class="form-group">
                <label for="amount"><span class="emoji">💰</span>Amount *</label>
                <input type="number" id="amount" name="amount" required min="1" placeholder="Enter amount (e.g., 1000)">
            </div>
            
            <div class="form-group">
                <label for="currency"><span class="emoji">💱</span>Currency</label>
                <select id="currency" name="currency">
                    <option value="NGN">NGN (Nigerian Naira)</option>
                    <option value="USD">USD (US Dollar)</option>
                    <option value="GHS">GHS (Ghanaian Cedi)</option>
                    <option value="KES">KES (Kenyan Shilling)</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="email"><span class="emoji">📧</span>Email Address *</label>
                <input type="email" id="email" name="email" required placeholder="your.email@example.com">
                <small>This will be used for payment confirmation</small>
            </div>
            
            <div class="form-group">
                <label for="telegram_user_id"><span class="emoji">🆔</span>Telegram User ID *</label>
                <input type="text" id="telegram_user_id" name="telegram_user_id" required placeholder="123456789">
                <small>Get this from @raw_data_bot on Telegram</small>
            </div>
            
            <div class="form-group">
                <label for="telegram_username"><span class="emoji">👤</span>Telegram Username (Optional)</label>
                <input type="text" id="telegram_username" name="telegram_username" placeholder="username (without @)">
                <small>Your Telegram username for easier identification</small>
            </div>
            
            <button type="submit" id="generateBtn">
                <span class="emoji">🚀</span>Generate Secure Payment Link
            </button>
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
            generateBtn.innerHTML = '<span class="emoji">⏳</span>Generating Secure Link...';
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
                        <h3><span class="emoji">✅</span>Payment Link Generated Successfully!</h3>
                        <p><strong>Transaction Reference:</strong> ${result.tx_ref}</p>
                        <p><strong>Secure Payment Link:</strong></p>
                        <div class="payment-link">${result.payment_link}</div>
                        <button class="copy-btn" onclick="copyToClipboard('${result.payment_link}')">
                            <span class="emoji">📋</span>Copy Link
                        </button>
                        <p><small><strong>Important:</strong> After successful payment, your channel invite link will be sent to your Telegram account automatically!</small></p>
                    `;
                    resultDiv.className = 'result success';
                } else {
                    // Error
                    resultContent.innerHTML = `
                        <h3><span class="emoji">❌</span>Failed to Generate Payment Link</h3>
                        <p><strong>Error:</strong> ${result.error || 'Unknown error occurred'}</p>
                        <p>Please check your details and try again.</p>
                    `;
                    resultDiv.className = 'result error';
                }
                
            } catch (error) {
                // Network error
                resultContent.innerHTML = `
                    <h3><span class="emoji">🌐</span>Network Error</h3>
                    <p><strong>Error:</strong> ${error.message}</p>
                    <p>Please check your internet connection and try again.</p>
                `;
                resultDiv.className = 'result error';
            }
            
            // Show result and reset button
            resultDiv.style.display = 'block';
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<span class="emoji">🚀</span>Generate Secure Payment Link';
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
</html>'''

if __name__ == '__main__':
    # Log startup info
    logger.info("Starting Flutterwave-Telegram Bot...")
    logger.info(f"FLUTTERWAVE_SECRET_KEY: {'Set' if FLUTTERWAVE_SECRET_KEY else 'Missing'}")
    logger.info(f"TELEGRAM_BOT_TOKEN: {'Set' if TELEGRAM_BOT_TOKEN else 'Missing'}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)