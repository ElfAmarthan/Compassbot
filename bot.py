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
                # Get the current event loop and run the tasks asynchronously using await
                loop = asyncio.get_event_loop()

                # Run the tasks directly and await them within the Flask route
                loop.run_until_complete(send_telegram_message(DEFAULT_CHAT_ID, message))
                loop.run_until_complete(show_calendar_for_user(DEFAULT_CHAT_ID))  # Trigger calendar after receiving location data
                
                return jsonify({"message": "Data received and forwarded to bot"})
            except Exception as e:
                logger.error(f"Error sending message to Telegram bot: {e}")
                return jsonify({"error": "Failed to send message to Telegram bot"}), 500

        return jsonify({"error": "No chat ID available to send message"}), 400
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": "Internal server error"}), 500


def format_location_message(data):
    return (
        f"📍 <b>Pickup:</b> {data['pickup']['latitude']}, {data['pickup']['longitude']}\n"
        f"🏁 <b>Destination:</b> {data['destination']['latitude']}, {data['destination']['longitude']}\n"
        f"📏 <b>Distance:</b> {data['distance']:.2f} km\n"
        f"💰 <b>Fare:</b> ${data['fare']:.2f}"
    )
async def show_calendar_for_user(chat_id):
    # Check if query exists; if not, send message directly to the user
    today = datetime.date.today()

    # Set the default year and month for calendar
    month = today.month
    year = today.year
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

    # Send the calendar to the user directly
    try:
        bot = Bot(BOT_TOKEN)
        await bot.send_message(chat_id=chat_id, text=f"Please select a date for {month_name} {year}:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error sending calendar to user: {e}")


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
    context.user_data.clear()
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

    # After email, move to location step
    await collect_location(update, context)
    return EMAIL

async def collect_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    map_url = "https://compass-georgia.onrender.com/index"  # Map interface URL
    keyboard = [[InlineKeyboardButton("🗺️ Open Map", url=map_url)]]  # Map button
    
    await update.message.reply_text(
        "Thanks! Now, please select your pickup and destination on the map:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return LOCATION
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

async def confirm_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Great! Now, please provide your DATE:")
    return DATE

async def edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please provide your Location:")
    return EMAIL


# Calendar and date selection
async def show_calendar(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
    else:
        query = None

    today = datetime.today()

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

    # Navigation buttons for previous and next month
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


# Handle the selection of a month (previous/next)
async def change_month(update: Update, context: CallbackContext):
    query = update.callback_query
    action = query.data

    # Get current month and year from context
    month = context.user_data['month']
    year = context.user_data['year']

    # Change the month based on the action (next or previous month)
    if action == "prev_month":
        if month == 1:  # January
            context.user_data['month'] = 12  # Go to December of the previous year
            context.user_data['year'] = year - 1
        else:
            context.user_data['month'] = month - 1
    elif action == "next_month":
        if month == 12:  # December
            context.user_data['month'] = 1  # Go to January of the next year
            context.user_data['year'] = year + 1
        else:
            context.user_data['month'] = month + 1

    # Refresh the calendar with updated month and year
    await show_calendar(update, context)


# Handle the selection of a date
async def select_date(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_day = query.data.split("_")[1]
    selected_date = f"{context.user_data['year']}-{context.user_data['month']:02d}-{int(selected_day):02d}"
    context.user_data['date'] = selected_date  # Save the selected date
    
    await query.answer()  # Acknowledge the button press

    # Ask for time
    await query.edit_message_text(f"Selected date: {selected_date}\nNow, please type your preferred time:")
    return TIME

# Collect the time from the user
async def collect_time(update: Update, context: CallbackContext):
    user_time = update.message.text.strip()

    # Try to parse the time
    try:
        valid_time = datetime.strptime(user_time, "%H:%M").time()  # 24-hour format
        context.user_data['time'] = user_time  # Save the valid time as a string

        # Ask for confirmation
        confirmation_keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_time")],
            [InlineKeyboardButton("✏ Edit", callback_data="edit_time")],
            [InlineKeyboardButton("❌ Cancel Booking", callback_data="cancel_booking")]
        ]
        reply_markup = InlineKeyboardMarkup(confirmation_keyboard)
        
        await update.message.reply_text(
            f"Your time is: {user_time}. Is this correct?",
            reply_markup=reply_markup
        )
        return TIME

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid time format. Please enter the time in 24-hour format (e.g., 14:30)."
        )
        return TIME  # Ask again
    
# Handle confirmation of the time selection
async def confirm_time(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Finalize the booking
    await finalize_booking(update, context)
    return ConversationHandler.END


# Handle editing of the time
async def edit_time(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Ask the user to enter the time again
    await query.edit_message_text("Please type your preferred time:")
    return TIME


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
    
        
        application = Application.builder().token(BOT_TOKEN).build()

        conv_handler = ConversationHandler(
                entry_points=[CommandHandler('start', start), CallbackQueryHandler(book, pattern='^start_booking$')],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name)],
                EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email)],
                LOCATION: [CallbackQueryHandler(collect_location)],
                DATE: [CallbackQueryHandler(select_date)],
                TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_time)],
            },
            fallbacks=[
                CallbackQueryHandler(confirm_name, pattern='^confirm_name$'),
                CallbackQueryHandler(edit_name, pattern='^edit_name$'),
                CallbackQueryHandler(confirm_time, pattern='^confirm_time$'),
                CallbackQueryHandler(edit_time, pattern='^edit_time$'),
                CallbackQueryHandler(cancel_booking, pattern='^cancel_booking$')

            ]
        )

        application.add_handler(CallbackQueryHandler(change_month, pattern='^(prev_month|next_month)$'))
        application.add_handler(conv_handler)

        application.add_handler(conv_handler)
        await application.run_polling()

# --- Entry Point ---
if __name__ == '__main__':
    try:
        nest_asyncio.apply()
        threading.Thread(target=run_flask).start()
        asyncio.run(telegram_bot())
    except Exception as e:
        logger.error(f"Error in main execution: {e}")