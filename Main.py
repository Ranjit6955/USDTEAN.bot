import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta

# --- Firebase Initialization ---
# It's recommended to store your Firebase credentials as a secret on your hosting provider (Render).
# For local testing, you can have the 'firebase-credentials.json' file in the same directory.
cred = credentials.Certificate('firebase-credentials.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': "https://usdt-earn-daily-default-rtdb.firebaseio.com/"

  # Replace with your Firebase Realtime Database URL
})

# --- Bot Configuration ---
TELEGRAM_BOT_TOKEN = "7016999277:AAEa5b_-_AxuhXp1U6JeP_eO822ORHHc0L4"  # Replace with your Telegram Bot Token
ADMIN_USER_ID = "5355939885"  # Replace with your Telegram User ID
DEPOSIT_ADDRESS = '0xDFa2ca3b679862809C98A3af3D1787Ad9810569b'

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def get_user_data(user_id):
    """Retrieves user data from Firebase."""
    ref = db.reference(f'users/{user_id}')
    return ref.get()

def update_user_data(user_id, data):
    """Updates user data in Firebase."""
    ref = db.reference(f'users/{user_id}')
    ref.update(data)

def is_admin(user_id):
    """Checks if a user is an admin."""
    return user_id == ADMIN_USER_ID

# --- User Command Handlers ---

async def start(update: Update, context: CallbackContext) -> None:
    """Handles the /start command."""
    user = update.effective_user
    user_id = user.id
    user_data = get_user_data(user_id)

    if not user_data:
        # New user
        new_user_data = {
            'username': user.username,
            'usdt_balance': 0.0,
            'points_balance': 0,
            'last_claim': None,
            'is_banned': False,
            'deposit_made': False
        }
        update_user_data(user_id, new_user_data)
        welcome_message = (
            f"Welcome, {user.first_name}! 🤑\n\n"
            "I am your personal earnings bot.\n\n"
            "Here's how you can earn:\n"
            "1. **Deposit 15 USDT** to start earning a daily income of 0.5 USDT.\n"
            "2. **Watch ads** to earn points, which can be converted to USDT.\n\n"
            "Use the buttons below to navigate."
        )
    else:
        welcome_message = f"Welcome back, {user.first_name}! 👋"

    keyboard = [
        [InlineKeyboardButton("💰 Deposit", callback_data='deposit'), InlineKeyboardButton("💸 Withdraw", callback_data='withdraw')],
        [InlineKeyboardButton("🪙 Claim Daily Income", callback_data='claim'), InlineKeyboardButton("📺 Watch Ad", callback_data='watch_ad')],
        [InlineKeyboardButton("📊 My Balance", callback_data='balance')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def deposit(update: Update, context: CallbackContext) -> None:
    """Handles the /deposit command and button click."""
    query = update.callback_query
    await query.answer()
    deposit_message = (
        "To make a deposit, please send USDT (BEP20) to the following address:\n\n"
        f"`{DEPOSIT_ADDRESS}`\n\n"
        "**Important:**\n"
        "- Send only USDT on the BEP20 (Binance Smart Chain) network.\n"
        "- After making the deposit, please wait for an admin to confirm it.\n"
        "- Once confirmed, your daily earnings will begin."
    )
    await query.edit_message_text(text=deposit_message, parse_mode='Markdown')

async def withdraw(update: Update, context: CallbackContext) -> None:
    """Handles the /withdraw command and button click."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = get_user_data(user_id)

    if not user_data['deposit_made']:
        await query.edit_message_text("You need to make a deposit before you can withdraw.")
        return

    # This is a simplified withdrawal system. In a real-world scenario, you'd have more checks.
    await query.edit_message_text("Please enter your USDT (BEP20) withdrawal address.")
    context.user_data['awaiting_withdrawal_address'] = True


async def claim(update: Update, context: CallbackContext) -> None:
    """Handles the /claim command and button click."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = get_user_data(user_id)

    if not user_data['deposit_made']:
        await query.edit_message_text("You need to make a deposit to start claiming daily income.")
        return

    last_claim_str = user_data.get('last_claim')
    if last_claim_str:
        last_claim_date = datetime.fromisoformat(last_claim_str)
        if datetime.utcnow().date() == last_claim_date.date():
            await query.edit_message_text("You have already claimed your income for today. Please come back tomorrow.")
            return

    # Update user's balance and last claim time
    new_balance = user_data['usdt_balance'] + 0.5
    update_user_data(user_id, {'usdt_balance': new_balance, 'last_claim': datetime.utcnow().isoformat()})
    await query.edit_message_text(f"You have successfully claimed 0.5 USDT! Your new balance is {new_balance:.2f} USDT.")

async def watch_ad(update: Update, context: CallbackContext) -> None:
    """Handles the /watch_ad command and button click."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = get_user_data(user_id)

    new_points = user_data['points_balance'] + 15
    update_user_data(user_id, {'points_balance': new_points})

    await query.edit_message_text(f"You've earned 15 points for watching an ad! Your new point balance is {new_points}.")

async def balance(update: Update, context: CallbackContext) -> None:
    """Handles the /balance command and button click."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = get_user_data(user_id)

    balance_message = (
        f"**Your Balances**\n\n"
        f"USDT: {user_data['usdt_balance']:.2f}\n"
        f"Points: {user_data['points_balance']}"
    )
    await query.edit_message_text(balance_message, parse_mode='Markdown')


# --- Admin Command Handlers ---

async def admin(update: Update, context: CallbackContext) -> None:
    """Main admin command."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    admin_menu = (
        "**Admin Panel**\n\n"
        "Available commands:\n"
        "`/admin_ban <user_id>` - Ban a user\n"
        "`/admin_unban <user_id>` - Unban a user\n"
        "`/admin_set_usdt <user_id> <amount>` - Set USDT balance\n"
        "`/admin_set_points <user_id> <amount>` - Set points balance\n"
        "`/admin_confirm_deposit <user_id>` - Confirm a user's deposit\n"
        "`/admin_confirm_withdrawal <user_id>` - Confirm a user's withdrawal"
    )
    await update.message.reply_text(admin_menu, parse_mode='Markdown')

async def admin_ban(update: Update, context: CallbackContext) -> None:
    """Bans a user."""
    if not is_admin(update.effective_user.id):
        return

    try:
        user_id_to_ban = int(context.args[0])
        update_user_data(user_id_to_ban, {'is_banned': True})
        await update.message.reply_text(f"User {user_id_to_ban} has been banned.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /admin_ban <user_id>")

async def admin_unban(update: Update, context: CallbackContext) -> None:
    """Unbans a user."""
    if not is_admin(update.effective_user.id):
        return

    try:
        user_id_to_unban = int(context.args[0])
        update_user_data(user_id_to_unban, {'is_banned': False})
        await update.message.reply_text(f"User {user_id_to_unban} has been unbanned.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /admin_unban <user_id>")

async def admin_set_usdt(update: Update, context: CallbackContext) -> None:
    """Sets a user's USDT balance."""
    if not is_admin(update.effective_user.id):
        return

    try:
        user_id = int(context.args[0])
        amount = float(context.args[1])
        update_user_data(user_id, {'usdt_balance': amount})
        await update.message.reply_text(f"User {user_id}'s USDT balance set to {amount}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /admin_set_usdt <user_id> <amount>")

async def admin_set_points(update: Update, context: CallbackContext) -> None:
    """Sets a user's points balance."""
    if not is_admin(update.effective_user.id):
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        update_user_data(user_id, {'points_balance': amount})
        await update.message.reply_text(f"User {user_id}'s points balance set to {amount}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /admin_set_points <user_id> <amount>")

async def admin_confirm_deposit(update: Update, context: CallbackContext) -> None:
    """Confirms a user's deposit."""
    if not is_admin(update.effective_user.id):
        return

    try:
        user_id = int(context.args[0])
        update_user_data(user_id, {'deposit_made': True})
        await update.message.reply_text(f"Deposit confirmed for user {user_id}.")
        # You can also notify the user
        await context.bot.send_message(chat_id=user_id, text="Your deposit has been confirmed! You can now start earning daily income.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /admin_confirm_deposit <user_id>")


async def message_handler(update: Update, context: CallbackContext) -> None:
    """Handles regular messages, especially for withdrawal address submission."""
    if context.user_data.get('awaiting_withdrawal_address'):
        withdrawal_address = update.message.text
        user_id = update.effective_user.id
        # In a real application, you would save this request to a separate 'withdrawals' table in Firebase
        # for the admin to process.
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"Withdrawal Request:\nUser ID: {user_id}\nAddress: {withdrawal_address}"
        )
        await update.message.reply_text("Your withdrawal request has been submitted. An admin will process it shortly.")
        context.user_data['awaiting_withdrawal_address'] = False


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # User command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(deposit, pattern='^deposit$'))
    application.add_handler(CallbackQueryHandler(withdraw, pattern='^withdraw$'))
    application.add_handler(CallbackQueryHandler(claim, pattern='^claim$'))
    application.add_handler(CallbackQueryHandler(watch_ad, pattern='^watch_ad$'))
    application.add_handler(CallbackQueryHandler(balance, pattern='^balance$'))

    # Admin command handlers
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("admin_ban", admin_ban))
    application.add_handler(CommandHandler("admin_unban", admin_unban))
    application.add_handler(CommandHandler("admin_set_usdt", admin_set_usdt))
    application.add_handler(CommandHandler("admin_set_points", admin_set_points))
    application.add_handler(CommandHandler("admin_confirm_deposit", admin_confirm_deposit))
    
    # Message handler for withdrawal address
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()


