from flask import Flask, request, jsonify
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
# Your server URL
SERVER_URL = 'http://localhost:3000/receive-locations'

app = Flask(__name__)

# Your bot's Telegram API token and chat_id
BOT_TOKEN = '7857906048:AAF7Mb6uSVHNadayyU0X_8so1fHz3kwUSqM'
CHAT_ID = 'YOUR_CHAT_ID'

def send_message(message):
    url = f"https://api.telegram.org/bot7857906048:AAF7Mb6uSVHNadayyU0X_8so1fHz3kwUSqM/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": message,
    }
    response = requests.get(url, params=params)
    return response.json()

@app.route("/send-locations-to-user", methods=["POST"])
def send_locations():
    data = request.json
    print("Received:", data)

    pickup = data.get("pickup")
    destination = data.get("destination")
    distance = data.get("distance")
    fare = data.get("fare")

    message = (
        f"📍 Pickup: {pickup['latitude']}, {pickup['longitude']}\n"
        f"🏁 Destination: {destination['latitude']}, {destination['longitude']}\n"
        f"📏 Distance: {distance:.2f} km\n"
        f"💰 Fare: ${fare:.2f}"
    )

    telegram_url = f"https://api.telegram.org/bot7857906048:AAF7Mb6uSVHNadayyU0X_8so1fHz3kwUSqM/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}

    try:
        response = requests.post(telegram_url, json=payload)
        print("Telegram Response:", response.text)
        return jsonify({"message": "Sent to Telegram"}), 200
    except Exception as e:
        print("Error sending to Telegram:", e)
        return jsonify({"error": "Failed to send to Telegram"}), 500

if __name__ == "__main__":
    app.run(port=5000)
