# main.py
import logging
import smtplib
import nest_asyncio
import threading
import asyncio
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import calendar
import os

from flask import Flask, request, jsonify, render_template
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)

# --- Constants ---
NAME, EMAIL, LOCATION, DATE, TIME = range(5)
BOT_TOKEN = os.getenv('BOT_TOKEN', 'your-real-token')
SENDER_EMAIL = 'companytnn90@gmail.com'
SENDER_PASSWORD = 'ncka udhb qryw jwnm'
DEFAULT_RECIPIENT_EMAIL = 'companytnn90@gmail.com'
DEFAULT_CHAT_ID = None

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask App ---
app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/')
def home():
    return "Welcome!"

@app.route('/index')
def show_map():
    return render_template('index.html')

@app.route('/send-locations-to-user', methods=['POST'])
def receive_location():
    global DEFAULT_CHAT_ID
    try:
        data = request.json
        if not all(k in data for k in ("pickup", "destination", "distance", "fare")):
            return jsonify({"error": "Missing fields"}), 400

        if DEFAULT_CHAT_ID:
            loop = asyncio.get_event_loop()
            message = format_location_message(data)
            loop.run_until_complete(send_telegram_message(DEFAULT_CHAT_ID, message))
            loop.run_until_complete(show_calendar_for_user(DEFAULT_CHAT_ID))
            return jsonify({"message": "Location and calendar sent"})
        return jsonify({"error": "No chat ID"}), 400
    except Exception as e:
        logger.error(f"Location error: {e}")
        return jsonify({"error": str(e)}), 500

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

async def show_calendar_for_user(chat_id):
    today = datetime.date.today()
    month = today.month
    year = today.year
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    keyboard = [
        [InlineKeyboardButton(str(day), callback_data=f"day_{day}") for day in week if day != 0]
        for week in cal
    ]
    keyboard.append([
        InlineKeyboardButton("⬅️ Previous", callback_data="prev_month"),
        InlineKeyboardButton("Next ➡️", callback_data="next_month")
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    bot = Bot(BOT_TOKEN)
    await bot.send_message(chat_id=chat_id, text=f"📅 Select a date for {month_name} {year}:", reply_markup=reply_markup)

def send_booking_email(booking, recipients):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = 'New Booking'
    msg.attach(MIMEText(f"Booking:\n\n{booking}", 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
        print("Email sent!")
    except Exception as e:
        print("Email error:", e)

# --- Bot Logic ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("Start Booking", callback_data='start_booking')]
    ]
    await update.message.reply_text("Welcome! Click below to start:", reply_markup=InlineKeyboardMarkup(keyboard))

async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("What's your name?")
    return NAME

async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("✅ Name received. Now your email:")
    return EMAIL

async def collect_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DEFAULT_CHAT_ID
    context.user_data['email'] = update.message.text
    DEFAULT_CHAT_ID = update.effective_chat.id

    map_url = "https://compass-georgia.onrender.com/index"
    keyboard = [[InlineKeyboardButton("🗺 Open Map", url=map_url)]]
    await update.message.reply_text("Great! Select pickup & destination:", reply_markup=InlineKeyboardMarkup(keyboard))
    return LOCATION

async def handle_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    now = datetime.datetime.now()

    if 'month' not in context.user_data:
        context.user_data['month'] = now.month
        context.user_data['year'] = now.year

    if data == 'prev_month':
        context.user_data['month'] -= 1
        if context.user_data['month'] < 1:
            context.user_data['month'] = 12
            context.user_data['year'] -= 1
    elif data == 'next_month':
        context.user_data['month'] += 1
        if context.user_data['month'] > 12:
            context.user_data['month'] = 1
            context.user_data['year'] += 1
    elif data.startswith("day_"):
        day = int(data.split("_")[1])
        year = context.user_data['year']
        month = context.user_data['month']
        selected_date = f"{year}-{month:02d}-{day:02d}"
        context.user_data['date'] = selected_date
        await query.edit_message_text(f"📅 Date selected: {selected_date}\nNow enter time (HH:MM):")
        return TIME

    # Re-render calendar
    month = context.user_data['month']
    year = context.user_data['year']
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    keyboard = [
        [InlineKeyboardButton(str(day), callback_data=f"day_{day}") for day in week if day != 0]
        for week in cal
    ]
    keyboard.append([
        InlineKeyboardButton("⬅️ Previous", callback_data="prev_month"),
        InlineKeyboardButton("Next ➡️", callback_data="next_month")
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"📅 Select a date for {month_name} {year}:", reply_markup=reply_markup)
    return DATE

async def collect_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_input = update.message.text.strip()
    logger.info(f"User input time: {time_input}")
    try:
        # Check if time format is correct (HH:MM)
        datetime.datetime.strptime(time_input, "%H:%M")
        context.user_data['time'] = time_input

        # Log the collected time for debugging purposes
        logger.info(f"Collected time: {time_input}")

        # Format the booking summary
        booking_summary = (
            f"✅ <b>Booking Summary:</b>\n\n"
            f"👤 Name: {context.user_data.get('name')}\n"
            f"📧 Email: {context.user_data.get('email')}\n"
            f"📅 Date: {context.user_data.get('date')}\n"
            f"⏰ Time: {context.user_data.get('time')}\n"
        )

        # Send email with booking details
        send_booking_email(booking_summary, [context.user_data['email'], DEFAULT_RECIPIENT_EMAIL])

        # Send confirmation message to the user
        await update.message.reply_text("✅ Booking confirmed! A confirmation email has been sent.")
        
        # End the conversation and return the correct state
        return ConversationHandler.END
    except ValueError:
        # If the time format is invalid, prompt the user again
        await update.message.reply_text("❌ Invalid format. Please use HH:MM (e.g. 14:30).")
        return TIME  # Stay in the TIME state for retry

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Booking process has been cancelled.")
    return ConversationHandler.END


# --- Start Flask in separate thread ---
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, use_reloader=False, port=port, host="0.0.0.0")

# --- Run Bot ---
async def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CallbackQueryHandler(book, pattern='^start_booking$')],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None)],  # Dummy, real one is from Flask
            DATE: [CallbackQueryHandler(handle_calendar)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_time)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_calendar, pattern='^(prev_month|next_month|day_\\d+)$'))
    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()
    threading.Thread(target=run_flask).start()
    asyncio.run(run_bot())
