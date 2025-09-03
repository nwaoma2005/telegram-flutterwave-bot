import os
import logging
import datetime
import psycopg2
from flask import Flask, request, jsonify
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, CallbackQueryHandler
)
import requests
import uuid

# -------------------
# CONFIGURATION
# -------------------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FLW_SECRET_KEY = os.getenv("FLUTTERWAVE_SECRET_KEY")
DB_URL = os.getenv("DATABASE_URL")  # Postgres URL from Render
ADMIN_IDS = [123456789]  # Replace with your Telegram user ID

# -------------------
# LOGGING
# -------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------
# DATABASE SETUP
# -------------------
conn = psycopg2.connect(DB_URL, sslmode='require')
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    subscription_status TEXT DEFAULT 'free',
    vip_expiry TIMESTAMP
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    type TEXT,  -- 'free' or 'vip'
    match_info TEXT,
    outcome TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# -------------------
# FLASK WEBHOOK SETUP
# -------------------
app = Flask(__name__)

@app.route('/flutterwave_webhook', methods=['POST'])
def flutterwave_webhook():
    data = request.json
    tx_ref = data.get('tx_ref')
    status = data.get('status')
    user_id = data.get('customer', {}).get('id')  # Custom field used

    if status == "successful":
        # Update user to VIP
        expiry = datetime.datetime.now() + datetime.timedelta(days=30)
        cur.execute(
            "UPDATE users SET subscription_status='vip', vip_expiry=%s WHERE user_id=%s",
            (expiry, user_id)
        )
        conn.commit()
        logger.info(f"User {user_id} upgraded to VIP until {expiry}")
    return jsonify({"status": "success"}), 200

# -------------------
# TELEGRAM BOT FUNCTIONS
# -------------------
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    # Add user to DB if not exists
    cur.execute("SELECT * FROM users WHERE user_id=%s", (user.id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (user_id, username) VALUES (%s, %s)",
            (user.id, user.username)
        )
        conn.commit()

    keyboard = [
        [InlineKeyboardButton("Free Predictions", callback_data='free')],
        [InlineKeyboardButton("VIP Predictions", callback_data='vip')],
        [InlineKeyboardButton("Subscribe", callback_data='subscribe')],
        [InlineKeyboardButton("History", callback_data='history')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"Welcome {user.first_name}! Choose an option below:",
        reply_markup=reply_markup
    )

def subscribe(update: Update, context: CallbackContext):
    user = update.effective_user
    # Generate unique transaction reference
    tx_ref = str(uuid.uuid4())
    # Create Flutterwave payment link
    payment_link = f"https://checkout.flutterwave.com/v3/payments?tx_ref={tx_ref}&amount=10000&currency=NGN&customer[email]={user.username}@example.com&customize[title]=VIP+Subscription&redirect_url=https://yourbot.com/thankyou?user_id={user.id}"
    update.message.reply_text(f"Click to pay and become VIP: {payment_link}")

def check_vip(user_id):
    cur.execute("SELECT subscription_status, vip_expiry FROM users WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    if not row:
        return False
    status, expiry = row
    if status == "vip" and expiry and expiry > datetime.datetime.now():
        return True
    else:
        # Downgrade expired VIP
        cur.execute(
            "UPDATE users SET subscription_status='free', vip_expiry=NULL WHERE user_id=%s",
            (user_id,)
        )
        conn.commit()
        return False

def today(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    is_vip = check_vip(user_id)
    if is_vip:
        cur.execute("SELECT match_info FROM predictions WHERE type='vip' ORDER BY created_at DESC LIMIT 5")
        tips = cur.fetchall()
        text = "Your VIP predictions:\n" + "\n".join([t[0] for t in tips])
    else:
        cur.execute("SELECT match_info FROM predictions WHERE type='free' ORDER BY created_at DESC LIMIT 2")
        tips = cur.fetchall()
        text = "Your free predictions:\n" + "\n".join([t[0] for t in tips])
        text += "\n\nUpgrade to VIP for more predictions!"
    update.message.reply_text(text)

def history(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cur.execute("SELECT match_info, outcome FROM predictions ORDER BY created_at DESC LIMIT 5")
    rows = cur.fetchall()
    text = "Last 5 predictions:\n" + "\n".join([f"{r[0]} -> {r[1]}" for r in rows])
    update.message.reply_text(text)

def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if query.data == 'free':
        today(update, context)
    elif query.data == 'vip':
        today(update, context)
    elif query.data == 'subscribe':
        subscribe(update, context)
    elif query.data == 'history':
        history(update, context)

def admin_add(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Unauthorized!")
        return
    try:
        type_ = context.args[0].lower()
        match_info = " ".join(context.args[1:])
        cur.execute("INSERT INTO predictions (type, match_info) VALUES (%s, %s)", (type_, match_info))
        conn.commit()
        update.message.reply_text(f"{type_.capitalize()} prediction added!")
    except Exception as e:
        update.message.reply_text(f"Error: {e}")

def admin_broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("Unauthorized!")
        return
    message = " ".join(context.args)
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    for u in users:
        try:
            context.bot.send_message(u[0], message)
        except:
            continue
    update.message.reply_text("Broadcast sent!")

# -------------------
# RUN TELEGRAM BOT
# -------------------
def run_bot():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("subscribe", subscribe))
    dp.add_handler(CommandHandler("today", today))
    dp.add_handler(CommandHandler("history", history))
    dp.add_handler(CommandHandler("add", admin_add))
    dp.add_handler(CommandHandler("broadcast", admin_broadcast))
    dp.add_handler(CallbackQueryHandler(button_callback))
    updater.start_polling()
    updater.idle()

# -------------------
# RUN FLASK & BOT TOGETHER
# -------------------
if __name__ == '__main__':
    Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))