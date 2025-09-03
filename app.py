import os
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

@app.route('/', methods=['GET'])
def home():
    """Test endpoint to check if bot is working"""
    
    # Check which environment variables are set
    env_status = {
        "FLUTTERWAVE_SECRET_KEY": "✅ Set" if FLUTTERWAVE_SECRET_KEY else "❌ Missing",
        "FLUTTERWAVE_WEBHOOK_SECRET": "✅ Set" if FLUTTERWAVE_WEBHOOK_SECRET else "❌ Missing", 
        "TELEGRAM_BOT_TOKEN": "✅ Set" if TELEGRAM_BOT_TOKEN else "❌ Missing",
        "TELEGRAM_CHANNEL_ID": "✅ Set" if TELEGRAM_CHANNEL_ID else "❌ Missing"
    }
    
    return jsonify({
        "status": "Bot is running!",
        "environment_variables": env_status,
        "endpoints": {
            "webhook": "/webhook/flutterwave",
            "create_payment": "/create-payment",
            "health": "/health"
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "Bot is running successfully!"
    })

@app.route('/webhook/flutterwave', methods=['POST'])
def flutterwave_webhook():
    """Handle Flutterwave webhook notifications"""
    
    try:
        # Log the incoming request
        logger.info("Webhook received!")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Get the data
        data = request.get_json()
        logger.info(f"Webhook data: {data}")
        
        return jsonify({"status": "webhook received", "message": "Processing successful"})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/test-telegram', methods=['GET'])
def test_telegram():
    """Test Telegram connection"""
    
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN not set"})
    
    try:
        # Test importing telegram
        from telegram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Test bot connection
        me = bot.get_me()
        
        return jsonify({
            "status": "Telegram connection successful!",
            "bot_info": {
                "username": me.username,
                "name": me.first_name,
                "id": me.id
            }
        })
        
    except Exception as e:
        logger.error(f"Telegram test failed: {e}")
        return jsonify({"error": f"Telegram connection failed: {str(e)}"})

if __name__ == '__main__':
    # Log startup info
    logger.info("Starting bot...")
    logger.info(f"Environment variables check:")
    logger.info(f"FLUTTERWAVE_SECRET_KEY: {'Set' if FLUTTERWAVE_SECRET_KEY else 'Missing'}")
    logger.info(f"TELEGRAM_BOT_TOKEN: {'Set' if TELEGRAM_BOT_TOKEN else 'Missing'}")
    
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))