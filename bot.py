import logging
import nest_asyncio
import threading
import asyncio
import os
from flask import Flask, request, jsonify, render_template
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ConversationHandler,
    CallbackQueryHandler, ContextTypes, CallbackContext
)

# --- Conversation states ---
NAME, EMAIL, LOCATION, DESTINATION, DATE, TIME = range(6)

# --- Configuration ---
BOT_TOKEN = os.getenv('BOT_TOKEN', '7857906048:AAF7Mb6uSVHNadayyU0X_8so1fHz3kwUSqM')  # Replace in prod
DEFAULT_CHAT_ID = None

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask App ---
app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/')
def home():
    return "Welcome to the homepage!"

@app.route('/index')
def show_map():
    return render_template('index.html')  # index.html must be in /templates

@app.route('/send-locations-to-user', methods=['POST'])
def receive_location():
    global stored_data
    data = request.json
    logger.info("Received data from map: %s", data)

    if not all(k in data for k in ("pickup", "destination", "distance", "fare")):
        return jsonify({"error": "Missing fields"}), 400

    stored_data = data
    message = format_location_message(data)

    if DEFAULT_CHAT_ID:
        try:
            asyncio.run(send_telegram_message(DEFAULT_CHAT_ID, message))
            return jsonify({"message": "Data received and forwarded to bot"})
        except Exception as e:
            logger.error(f"Error sending message to Telegram bot: {e}")
            return jsonify({"error": "Failed to send message to Telegram bot"}), 500

    return jsonify({"error": "No chat ID available to send message"}), 400

def format_location_message(data):
    return (
        f"📍 <b>Pickup:</b> {data['pickup']['latitude']}, {data['pickup']['longitude']}\n"
        f"🏁 <b>Destination:</b> {data['destination']['latitude']}, {data['destination']['longitude']}\n"
        f"📏 <b>Distance:</b> {data['distance']:.2f} km\n"
        f"💰 <b>Fare:</b> ${data['fare']:.2f}"
    )

async def send_telegram_message(chat_id, text):
    bot = Bot(BOT_TOKEN)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)

# --- Telegram Handlers ---
async def cancel_booking(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("Your booking has been canceled. You can start over anytime 😊")

    keyboard = [
        [InlineKeyboardButton("Start Booking", callback_data='start_booking')],
        [InlineKeyboardButton("Last Booking", callback_data='last_booking')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        "Welcome to Compass Georgia! To start booking, click below. You can also check your last booking.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Start Booking", callback_data='start_booking')],
        [InlineKeyboardButton("Last Booking", callback_data='last_booking')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to Compass Georgia! Click to start booking or see your last booking.",
        reply_markup=reply_markup
    )

async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please provide your name:")
    return NAME

async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text
    context.user_data['name'] = user_name

    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_name")],
        [InlineKeyboardButton("✏ Edit", callback_data="edit_name")],
        [InlineKeyboardButton("❌ Cancel Booking", callback_data="cancel_booking")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Your name is: {user_name}. Is this correct?",
        reply_markup=reply_markup
    )
    return NAME

async def confirm_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Great! Now, please provide your email address:")
    return EMAIL

async def edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please provide your name:")
    return NAME

async def collect_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_email = update.message.text
    context.user_data['email'] = user_email
    global DEFAULT_CHAT_ID
    DEFAULT_CHAT_ID = update.effective_chat.id

    map_url = "https://compass-georgia.onrender.com/index"
    keyboard = [[InlineKeyboardButton("🗺️ Open Map", url=map_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Thanks! Now please select your pickup and destination on the map:",
        reply_markup=reply_markup
    )

    return ConversationHandler.END

# --- Flask Thread ---
def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=port)

# --- Telegram Bot ---
async def telegram_bot():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CallbackQueryHandler(book, pattern='^start_booking$')],
        states={
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name),
                CallbackQueryHandler(confirm_name, pattern='^confirm_name$'),
                CallbackQueryHandler(edit_name, pattern='^edit_name$')
            ],
            EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email),
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_booking, pattern='^cancel_booking$')]
    )

    application.add_handler(conv_handler)
    await application.run_polling()

# --- Entry Point ---
if __name__ == '__main__':
    nest_asyncio.apply()
    threading.Thread(target=run_flask).start()
    asyncio.run(telegram_bot())
