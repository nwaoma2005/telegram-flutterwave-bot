import requests
from flask import Flask, request

app = Flask(__name__)

# Load from environment variables later in Render
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # e.g. @yourchannel or -1001234567890
FLW_SECRET = os.getenv("FLW_SECRET")

@app.route("/")
def home():
    return "Bot is running!", 200

@app.route("/webhook", methods=["POST"])
def flutterwave_webhook():
    data = request.json
    if data['status'] == "successful":
        user_id = data['tx_ref']  # store Telegram user_id as tx_ref
        
        # Generate new invite link
        invite_url = f"https://api.telegram.org/bot{BOT_TOKEN}/exportChatInviteLink"
        invite_link = requests.get(invite_url, params={"chat_id": CHANNEL_ID}).json()['result']
        
        # Send invite link to user
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": user_id,
            "text": f"✅ Payment confirmed!\nHere’s your access link: {invite_link}"
        })
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)