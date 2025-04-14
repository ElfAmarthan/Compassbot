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
    Application, CommandHandler, MessageHandler, filters, ConversationHandler,
    CallbackQueryHandler, ContextTypes, CallbackContext
)

# --- Conversation states ---
NAME, EMAIL, LOCATION, DESTINATION, DATE, TIME = range(6)

# --- Configuration ---
BOT_TOKEN = os.getenv('BOT_TOKEN', '7857906048:AAEDeeaKvLzyl6zNzhNd8Afe9lLrGF9Yw5s')  # Replace with your actual bot token
DEFAULT_CHAT_ID = None
SENDER_EMAIL = 'companytnn90@gmail.com'
SENDER_PASSWORD = 'ncka udhb qryw jwnm'  # Update this securely
DEFAULT_RECIPIENT_EMAIL = 'companytnn90@gmail.com'

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

# New dict to keep context per user chat ID
user_contexts = {}

@app.route('/send-locations-to-user', methods=['POST'])
def receive_location():
    global user_contexts
    data = request.json
    chat_id = data.get("chat_id")  # Include this in frontend map POST

    if not chat_id or chat_id not in user_contexts:
        return jsonify({"error": "Invalid or missing chat ID"}), 400

    if not all(k in data for k in ("pickup", "destination", "distance", "fare")):
        return jsonify({"error": "Missing fields"}), 400

    # Store in user's context
    user_contexts[chat_id]['location'] = data['pickup']
    user_contexts[chat_id]['destination'] = data['destination']
    user_contexts[chat_id]['distance'] = data['distance']
    user_contexts[chat_id]['fare'] = data['fare']

    asyncio.run(send_telegram_message(chat_id, format_location_message(data)))
    asyncio.run(show_calendar(chat_id))  # Custom function to trigger calendar

    return jsonify({"message": "Location data received and processed"})


def format_location_message(data):
    return (
        f"📍 <b>Pickup:</b> {data['pickup']['latitude']}, {data['pickup']['longitude']}\n"
        f"🏁 <b>Destination:</b> {data['destination']['latitude']}, {data['destination']['longitude']}\n"
        f"📏 <b>Distance:</b> {data['distance']:.2f} km\n"
        f"💰 <b>Fare:</b> ${data['fare']:.2f}"
    )

async def send_telegram_message(chat_id, text):
    bot = Bot(BOT_TOKEN)
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error sending message to Telegram: {e}")
        raise e

# Function to send the booking details via email
def send_booking_email(booking_details, recipient_emails):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['Subject'] = 'New Booking Received'
    
    # Email body
    body = f"New transportation booking details:\n\n{booking_details}"
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Setup the SMTP server
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        # Join all recipient emails with commas, so it's a single string
        msg['To'] = ", ".join(recipient_emails)  # Ensure it's a string, not a tuple
        
        # Send the email
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, recipient_emails, text)
        server.quit()
        print('Booking email sent successfully to all recipients!')
    except Exception as e:
        print(f'Error sending email: {e}')

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

async def collect_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_email = update.message.text
    context.user_data['email'] = user_email

    # After email, move to location step
    await collect_location(update, context)
    return LOCATION

async def collect_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    map_url = "https://compass-georgia.onrender.com/index"  # Map interface URL
    keyboard = [[InlineKeyboardButton("🗺️ Open Map", url=map_url)]]  # Map button
    
    await update.message.reply_text(
        "Thanks! Now, please select your pickup and destination on the map:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return LOCATION

async def show_calendar(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
    else:
        query = None

    today = datetime.date.today()

    if 'year' not in context.user_data or 'month' not in context.user_data:
        context.user_data['year'] = today.year
        context.user_data['month'] = today.month

    month = context.user_data['month']
    year = context.user_data['year']
    month_name = calendar.month_name[month]
    cal = calendar.monthcalendar(year, month)

    keyboard = []
    for week in cal:
        row = []
        for day in week:
            if day != 0:
                row.append(InlineKeyboardButton(str(day), callback_data=f"day_{day}"))
        keyboard.append(row)

    navigation = [
        [InlineKeyboardButton("⬅️ Previous Month", callback_data="prev_month"),
         InlineKeyboardButton("Next Month ➡️", callback_data="next_month")]
    ]
    keyboard.extend(navigation)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(f"Please select a date for {month_name} {year}:", reply_markup=reply_markup)
    else:
        await update.message.reply_text(f"Please select a date for {month_name} {year}:", reply_markup=reply_markup)

async def select_date(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_day = query.data.split("_")[1]
    selected_date = f"{context.user_data['year']}-{context.user_data['month']:02d}-{int(selected_day):02d}"

    context.user_data['date'] = selected_date
    await query.answer()  # Acknowledge the button press

    # Ask for confirmation
    confirmation_keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_date")],
        [InlineKeyboardButton("❌ Edit", callback_data="edit_date")]
    ]
    reply_markup = InlineKeyboardMarkup(confirmation_keyboard)
    
    await query.edit_message_text(f"Your selected date is: {selected_date}. Is this correct?", reply_markup=reply_markup)
    return DATE

async def confirm_date(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Proceed to the next step (time selection)
    await query.edit_message_text("Great! Now, please choose your pickup time:")
    await time_buttons(update, context)
    return TIME

async def time_buttons(update, context):
    now = datetime.datetime.now()
    available_times = [f"{now.hour + i}:00" for i in range(1, 5)]  # Example available times

    keyboard = [[InlineKeyboardButton(time, callback_data=f"time_{time}")] for time in available_times]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Select your pickup time:", reply_markup=reply_markup)

async def select_time(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_time = query.data.split("_")[1]
    context.user_data['time'] = selected_time

    confirmation_keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_time")],
        [InlineKeyboardButton("❌ Edit", callback_data="edit_time")]
    ]
    reply_markup = InlineKeyboardMarkup(confirmation_keyboard)

    await query.answer()  # Acknowledge the button press
    await query.edit_message_text(f"You've selected the time: {selected_time}\nIs this correct?", reply_markup=reply_markup)
    return TIME

async def confirm_time(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Proceed to the next step: finalize the booking
    await query.edit_message_text("You've confirmed your time. We are now finalizing your booking...")

    # Send the booking email
    await finalize_booking(update, context)

async def finalize_booking(update: Update, context: CallbackContext):
    booking_details = f"""
    Name: {context.user_data.get('name')}
    Email: {context.user_data.get('email')}
    Pickup Location: {context.user_data.get('location')}
    Destination: {context.user_data.get('destination')}
    Pickup Date: {context.user_data.get('date')}
    Time: {context.user_data.get('time')}
    """

    recipient_email = context.user_data.get('email')  # Use the email entered by the user

    recipient_emails = [recipient_email, DEFAULT_RECIPIENT_EMAIL]  # List of recipient emails
    send_booking_email(booking_details, recipient_emails)

    message = update.effective_message if update.effective_message else None

    if message:
        await message.reply_text("Your booking has been confirmed. We have sent the details to your email and our team. Thank you!")

    return ConversationHandler.END

# --- Flask Thread ---
def run_flask():
    try:
        port = int(os.environ.get('PORT', 5000))
        app.run(debug=True, use_reloader=False, host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Error running Flask app: {e}")
        raise e

# --- Telegram Bot ---
async def telegram_bot():
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start), CallbackQueryHandler(book, pattern='^start_booking$')],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name),
                       CallbackQueryHandler(confirm_name, pattern='^confirm_name$'),
                      ],
                EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email)],
                DATE: [CallbackQueryHandler(select_date, pattern='^day_'),
                       CallbackQueryHandler(confirm_date, pattern="^confirm_date$"),
                       ],
                TIME: [CallbackQueryHandler(select_time, pattern='^time_'),
                       CallbackQueryHandler(confirm_time, pattern="^confirm_time$"),
                       CallbackQueryHandler(finalize_booking, pattern="^finalize_booking$")],
            },
            fallbacks=[CallbackQueryHandler(cancel_booking, pattern='^cancel_booking$')]
        )

        application.add_handler(conv_handler)
        await application.run_polling()
    except Exception as e:
        logger.error(f"Error in Telegram bot: {e}")
        raise e

# --- Entry Point ---
if __name__ == '__main__':
    try:
        nest_asyncio.apply()
        threading.Thread(target=run_flask).start()
        asyncio.run(telegram_bot())
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
