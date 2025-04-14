import logging
import smtplib
import nest_asyncio
import threading
import asyncio
import datetime
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import calendar
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
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Ensure your bot token is in environment variables
DEFAULT_CHAT_ID = None
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
DEFAULT_RECIPIENT_EMAIL = os.getenv('DEFAULT_RECIPIENT_EMAIL')

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask App ---
app = Flask(__name__, static_folder='static', template_folder='templates')
application = Application.builder().token(BOT_TOKEN).build()
bot = Bot(token=BOT_TOKEN)

@app.route("/your-webhook-path", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok"

@app.route('/')
def home():
    return "Welcome to the homepage!"

@app.route('/index')
def show_map():
    return render_template('index.html')  # index.html must be in /templates

@app.route('/send-locations-to-user', methods=['POST'])
def receive_location():
    global stored_data
    try:
        data = request.json
        logger.info("Received data from map: %s", data)

        if not all(k in data for k in ("pickup", "destination", "distance", "fare")):
            return jsonify({"error": "Missing fields"}), 400

        stored_data = data
        message = format_location_message(data)

        if DEFAULT_CHAT_ID:
            try:
                # Send location details to the user
                asyncio.run(send_telegram_message(DEFAULT_CHAT_ID, message))

                # Prompt for pickup date after receiving the map data
                asyncio.run(start_date_selection(DEFAULT_CHAT_ID))

                return jsonify({"message": "Data received and forwarded to bot"}), 200
            except Exception as e:
                logger.error(f"Error sending message to Telegram bot: {e}")
                return jsonify({"error": "Failed to send message to Telegram bot"}), 500

        return jsonify({"error": "No chat ID available to send message"}), 400
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": "Internal server error"}), 500


async def start_date_selection(chat_id):
    try:
        # Send a message prompting the user to select a pickup date
        bot = Bot(BOT_TOKEN)
        await bot.send_message(chat_id=chat_id, text="Thanks for providing the location! Now, please select your pickup date:")

        # Trigger the calendar selection
        await show_calendar(None, None)
    except Exception as e:
        logger.error(f"Error starting date selection: {e}")

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
        
        # Join all recipient emails with commas
        msg['To'] = ", ".join(recipient_emails)
        
        # Send the email
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, recipient_emails, text)
        server.quit()
        logger.info('Booking email sent successfully to all recipients!')
    except Exception as e:
        logger.error(f'Error sending email: {e}')

# Store user bookings persistently (using SQLite for simplicity)
import sqlite3

def get_db_connection():
    conn = sqlite3.connect('bookings.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_booking_table():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS bookings (
                        user_id INTEGER PRIMARY KEY,
                        name TEXT,
                        email TEXT,
                        location TEXT,
                        destination TEXT,
                        date TEXT,
                        time TEXT)''')
    conn.commit()
    conn.close()

def store_booking(user_id, booking_details):
    conn = get_db_connection()
    conn.execute('''INSERT INTO bookings (user_id, name, email, location, destination, date, time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (user_id, booking_details['name'], booking_details['email'], booking_details['location'],
                     booking_details['destination'], booking_details['date'], booking_details['time']))
    conn.commit()
    conn.close()

def get_last_booking(user_id):
    conn = get_db_connection()
    booking = conn.execute('''SELECT * FROM bookings WHERE user_id = ? ORDER BY rowid DESC LIMIT 1''', (user_id,)).fetchone()
    conn.close()
    return booking if booking else "No bookings found."

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
    return LOCATION  # Optional: or just wait for map callback


# Calendar and date selection
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

# Handle the selection of a date
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

# Handle confirmation of the date selection
async def confirm_date(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Proceed to the next step (time selection)
    await query.edit_message_text("Great! Now, please choose your pickup time:")
    await time_buttons(update, context)
    return TIME

# Handle editing of the date selection
async def edit_date(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Ask the user to select the date again
    await show_calendar(update, context)
    return DATE

# Time selection buttons function
async def time_buttons(update, context):
    times = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00']
    keyboard = [[InlineKeyboardButton(time, callback_data=f'time_{time}') for time in times]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Check if the update is a callback query or a message
    if update.callback_query:
        await update.callback_query.answer()  # Acknowledge the callback query
        await update.callback_query.edit_message_text("Please select a time for your pickup:", reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text("Please select a time for your pickup:", reply_markup=reply_markup)

# Handle time selection
async def select_time(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_time = query.data.split("_")[1]  # Extract the time from the callback data
    context.user_data['time'] = selected_time  # Save the selected time

    # Confirm the booking
    confirmation_keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_time")],
        [InlineKeyboardButton("❌ Edit", callback_data="edit_time")]
    ]
    reply_markup = InlineKeyboardMarkup(confirmation_keyboard)

    await query.answer()  # Acknowledge the button press
    await query.edit_message_text(f"You've selected the time: {selected_time}\nIs this correct?", reply_markup=reply_markup)
    return TIME

# Handle confirmation of the time selection
async def confirm_time(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Proceed to the next step: finalize the booking
    await query.edit_message_text("You've confirmed your time. We are now finalizing your booking...")

    # Send the booking email
    await finalize_booking(update, context)

# Final step: Sending the booking email
async def finalize_booking(update: Update, context: CallbackContext):
    booking_details = f"""
    Name: {context.user_data.get('name')}
    Email: {context.user_data.get('email')}
    Pickup Location: {context.user_data.get('location')}
    Destination: {context.user_data.get('destination')}
    Pickup Date: {context.user_data.get('date')}
    Time: {context.user_data.get('time')}
    """

    # Get the email address provided by the user
    recipient_email = context.user_data.get('email')  # Use the email entered by the user

    # Send the email to both the user and the default recipient
    recipient_emails = [recipient_email, DEFAULT_RECIPIENT_EMAIL]  # List of recipient emails
    send_booking_email(booking_details, recipient_emails)

  # Check if `update.message` exists, and use `effective_message`
    message = update.effective_message if update.effective_message else None

    if message:
        await message.reply_text("Your booking has been confirmed. We have sent the details to your email and our team. Thank you!")

    # End the conversation
    return ConversationHandler.END



# Handle editing of the time selection
async def edit_time(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Ask the user to select the time again
    await time_buttons(update, context)
    return TIME
# Storage for user bookings (In-memory storage)
user_bookings = {}

# Function to store the user's booking details
def store_booking(user_id, booking_details):
    user_bookings[user_id] = booking_details

# Function to retrieve the user's last booking
def get_last_booking(user_id):
    return user_bookings.get(user_id, "No bookings found.")

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
        # # Set webhook
        # await application.bot.set_webhook("https://compass-georgia.onrender.com/your-webhook-path")

        # Define conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start), CallbackQueryHandler(book, pattern='^start_booking$')],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name)],
                EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email)],
                DATE: [CallbackQueryHandler(select_date, pattern='^day_')],
                TIME: [CallbackQueryHandler(select_time, pattern='^time_')]
            },
            fallbacks=[CallbackQueryHandler(cancel_booking, pattern='^cancel_booking$')]
        )

        # Add handler to the application
        application.add_handler(conv_handler)

        # This is the missing parts
        await application.initialize()
        await application.start()
        application.add_handler(CommandHandler("start", start))
        await application.bot.set_webhook("https://compass-georgia.onrender.com/your-webhook-path")
        logger.info("Telegram bot started!")

    except Exception as e:
        logger.error(f"Error in Telegram bot: {e}")
        raise e


if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()

    # Initialize DB and create table if needed
    create_booking_table()

    async def main():
        # Start Flask using a background thread compatible with asyncio
        loop = asyncio.get_event_loop()

        def start_flask():
            app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True, use_reloader=False)

        flask_thread = threading.Thread(target=start_flask)
        flask_thread.start()

        # Start the Telegram bot
        await telegram_bot()

    asyncio.run(main())

