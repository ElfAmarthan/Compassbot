import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, CallbackQueryHandler
import calendar
import datetime
import re  # For email validation

# Conversation states
NAME, EMAIL, LOCATION, DESTINATION, DATE, TIME = range(6)

# Replace with your credentials
TELEGRAM_API_TOKEN = '7857906048:AAF7Mb6uSVHNadayyU0X_8so1fHz3kwUSqM'
SENDER_EMAIL = 'companytnn90@gmail.com'
SENDER_PASSWORD = 'ncka udhb qryw jwnm'  # Update this securely
DEFAULT_RECIPIENT_EMAIL = 'companytnn90@gmail.com'

# Pickup locations for the user to choose from
pickup_locations = ["Airport", "Hotel", "City Center", "Train Station", "Bus Station"]

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


# Start command to introduce the bot
async def start(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("Start Booking", callback_data='start_booking')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to Compass Georgia! To continue booking, please click the button below to begin.",
        reply_markup=reply_markup
    )

# Main booking flow
async def book(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    await query.edit_message_text("Please provide your name:")
    return NAME

# Collect the name from the user
async def collect_name(update: Update, context: CallbackContext):
    user_name = update.message.text
    context.user_data['name'] = user_name  # Save the name to user_data
    
    # Ask for confirmation
    confirmation_keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_name")],
        [InlineKeyboardButton("❌ Edit", callback_data="edit_name")]
    ]
    reply_markup = InlineKeyboardMarkup(confirmation_keyboard)
    
    await update.message.reply_text(f"Your name is: {user_name}. Is this correct?", reply_markup=reply_markup)
    return NAME

# Handle confirmation of the name selection
async def confirm_name(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Proceed to the next step (email collection)
    await query.edit_message_text("Great! Now, please provide your email address:")
    return EMAIL

# Handle editing of the name
async def edit_name(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Ask the user to enter the name again
    await query.edit_message_text("Please provide your name:")
    return NAME

# Validate email format
def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email)

# Collect the email address
async def collect_email(update: Update, context: CallbackContext):
    email = update.message.text
    if not is_valid_email(email):
        await update.message.reply_text("Invalid email address. Please provide a valid email address:")
        return EMAIL
    context.user_data['email'] = email  # Save the email to user_data
    
    # Ask for confirmation
    confirmation_keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_email")],
        [InlineKeyboardButton("❌ Edit", callback_data="edit_email")]
    ]
    reply_markup = InlineKeyboardMarkup(confirmation_keyboard)
    
    await update.message.reply_text(f"Your email is: {email}. Is this correct?", reply_markup=reply_markup)
    return EMAIL

# Handle confirmation of the email selection
async def confirm_email(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Proceed to the next step (location selection)
    await query.edit_message_text("Got it! Now, please choose your pickup location:", reply_markup=location_buttons())
    return LOCATION

# Handle editing of the email
async def edit_email(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Ask the user to enter the email again
    await query.edit_message_text("Please provide your email address:")
    return EMAIL

# Location buttons function
def location_buttons():
    keyboard = [
        [InlineKeyboardButton("🏖️ **Tbilisi Airport**", callback_data="Airport")],
        [InlineKeyboardButton("🏨 **Kutaisi Airport**", callback_data="Hotel")],
        [InlineKeyboardButton("🌆 **City Center**", callback_data="City Center")],
        [InlineKeyboardButton("🚂 **Train Station**", callback_data="Train Station")],
        [InlineKeyboardButton("🚌 **Bus Station**", callback_data="Bus Station")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Handle location selection
async def select_location(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_location = query.data
    context.user_data['location'] = selected_location  # Save the selected location
    await query.answer()  # Acknowledge the button press

    # Ask for destination
    await query.edit_message_text(f"Selected Pickup Location: {selected_location}\nNow, please type your destination:")
    return DESTINATION

# Collect the destination from the user
async def collect_destination(update: Update, context: CallbackContext):
    user_destination = update.message.text
    context.user_data['destination'] = user_destination  # Save the destination
    
    # Ask for confirmation
    confirmation_keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_destination")],
        [InlineKeyboardButton("❌ Edit", callback_data="edit_destination")]
    ]
    reply_markup = InlineKeyboardMarkup(confirmation_keyboard)
    
    await update.message.reply_text(f"Your destination is: {user_destination}. Is this correct?", reply_markup=reply_markup)
    return DESTINATION

# Handle confirmation of the destination selection
async def confirm_destination(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Proceed to the next step (date selection)
    await query.edit_message_text(f"Great! Now, please choose your pickup date.")
    await show_calendar(update, context)
    return DATE

# Handle editing of the destination
async def edit_destination(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Ask the user to enter the destination again
    await query.edit_message_text("Please type your destination:")
    return DESTINATION

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

# Conversation handler with different steps
conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start), CallbackQueryHandler(book, pattern='^start_booking$')],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name), 
               CallbackQueryHandler(confirm_name, pattern="^confirm_name$"), 
               CallbackQueryHandler(edit_name, pattern="^edit_name$")],
        EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email), 
                CallbackQueryHandler(confirm_email, pattern="^confirm_email$"),
                CallbackQueryHandler(edit_email, pattern="^edit_email$")],
        LOCATION: [CallbackQueryHandler(select_location)],
        DESTINATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_destination),
                      CallbackQueryHandler(confirm_destination, pattern="^confirm_destination$"),
                      CallbackQueryHandler(edit_destination, pattern="^edit_destination$")],
        DATE: [CallbackQueryHandler(select_date, pattern='^day_'),
               CallbackQueryHandler(confirm_date, pattern="^confirm_date$"),
               CallbackQueryHandler(edit_date, pattern="^edit_date$")],
        TIME: [CallbackQueryHandler(select_time, pattern='^time_'),
               CallbackQueryHandler(confirm_time, pattern="^confirm_time$"),
               CallbackQueryHandler(edit_time, pattern="^edit_time$"),
               CallbackQueryHandler(finalize_booking, pattern="^finalize_booking$")],
    },
    fallbacks=[CommandHandler('cancel', lambda update, context: update.message.reply_text("Booking cancelled."))]
)

def main():
    application = Application.builder().token(TELEGRAM_API_TOKEN).build()
    application.add_handler(conversation_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
