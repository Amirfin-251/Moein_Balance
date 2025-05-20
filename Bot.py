import logging
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ConversationHandler, ContextTypes, CallbackQueryHandler
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv 

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Define conversation states
(TRANSACTION_TYPE, RECEIPT_NUM, PACK_NUM, ID_NUM, PURITY, WEIGHT, PARTNER_NAME,
 DEAL_DIRECTION, DEAL_TYPE, AMOUNT, RATE, BUY_PARTNER_NAME, SELL_PARTNER_NAME,
 DESCRIPTION, CONFIRMATION, EDIT_FIELD, EDIT_VALUE, MAIN_MENU) = range(18)

# Define column headers for Google Sheets
HEADERS = [
    "نوع تراکنش", "تاریخ", "شماره سند", "شماره پاکت", "اسم ریگیری", 
    "عیار", "وزن", "طرف حساب", "جهت معامله", "نوع معامله", 
    "مقدار", "نرخ", "طرف خریدار", "طرف  فروشنده", 
    "توضیحات", "زمان ثبت"
]

# Map display field names to actual data keys
FIELD_MAPPING = {
    "شماره سند": "receipt_num",
    "شماره پاکت": "pack_num",
    "اسم ریگیری": "id_num",
    "عیار": "purity",
    "وزن": "weight",
    "طرف حساب": "partner_name",
    "جهت معامله": "deal_direction",
    "نوع معامله": "deal_type",
    "مقدار": "amount",
    "نرخ": "rate",
    "طرف خریدار": "buy_partner_name",
    "طرف فروشنده": "sell_partner_name",
    "توضیحات": "description"
}

# Google Sheets setup
def setup_google_sheets():
    # Google Sheets setup
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Check if we're using environment variable for credentials
    if 'GOOGLE_API_KEY' in os.environ:
        import json
        # Parse JSON from environment variable
        credentials_dict = json.loads(os.environ['GOOGLE_API_KEY'])
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    else:
        # Use local file path (your original code)
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            os.getenv('GOOGLE_API_KEY'), scope)
    client = gspread.authorize(credentials)
    
    try:
        spreadsheet = client.open("Test")
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create("Transaction_Log")
        spreadsheet.share('amir.reihani251@gmail.com', perm_type='user', role='writer')
    
    try:
        worksheet = spreadsheet.worksheet("Transactions")
        # Check if headers exist
        existing_headers = worksheet.row_values(1)
        if not existing_headers or len(existing_headers) < len(HEADERS):
            # Clear first row and add all headers
            if existing_headers:
                worksheet.delete_row(1)
            worksheet.insert_row(HEADERS, 1)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="Transactions", rows=1000, cols=20)
        # Add headers
        worksheet.insert_row(HEADERS, 1)
    
    return worksheet

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send welcome message with buttons instead of command instructions."""
    reply_keyboard = [["شروع"], ["تراکنش جدید"]]
    
    await update.message.reply_text(
        "👋 به سیستم ثبت تراکنش خوش آمدید!\n\n"
        "من به شما کمک می‌کنم انواع مختلف تراکنش را در Google Sheets ثبت کنید.\n"
        "برای شروع روی دکمه شروع و برای ثبت تراکنش جدید روی دکمه تراکنش جدید کلیک کنید.",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )
    
    return MAIN_MENU

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle main menu button presses."""
    text = update.message.text
    
    if text == "شروع":
        # Show welcome message again
        reply_keyboard = [["شروع"], ["تراکنش جدید"]]
        await update.message.reply_text(
            "👋 به سیستم ثبت تراکنش خوش آمدید!\n\n"
            "برای ثبت تراکنش جدید روی دکمه تراکنش جدید کلیک کنید.",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        )
        return MAIN_MENU
    
    elif text == "تراکنش جدید":
        # Start new transaction flow
        return await new_transaction(update, context)
    
    else:
        await update.message.reply_text(
            "لطفا یکی از دکمه‌های موجود را انتخاب کنید."
        )
        return MAIN_MENU

async def new_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the transaction recording process."""
    # Initialize empty dictionary to store transaction data
    context.user_data["transaction"] = {}
    context.user_data["transaction"]["date"] = datetime.now().strftime("%Y-%m-%d")
    
    # Show transaction type options
    reply_keyboard = [["دریافت", "پرداخت"], ["معامله", "حواله"]]
    await update.message.reply_text(
        "نوع تراکنش را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return TRANSACTION_TYPE

async def transaction_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process transaction type and ask relevant next question."""
    transaction_type = update.message.text
    context.user_data["transaction"]["type"] = transaction_type
    
    # Ask for receipt number for most transaction types
    if transaction_type in ["دریافت", "پرداخت", "معامله"]:
        await update.message.reply_text(
            "شماره سند را وارد کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return RECEIPT_NUM
    
    # For Bill type, ask for deal type directly
    elif transaction_type == "حواله":
        reply_keyboard = [["میلیونی", "گرمی", "دلاری", "درهمی"]]
        await update.message.reply_text(
            "نوع حواله را انتخاب کنید:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return DEAL_TYPE
    
    # Fallback
    else:
        await update.message.reply_text("نوع تراکنش نامعتبر است. لطفا دوباره تلاش کنید.")
        return TRANSACTION_TYPE

async def receipt_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process receipt number and ask next question based on transaction type."""
    context.user_data["transaction"]["receipt_num"] = update.message.text
    
    if context.user_data["transaction"]["type"] == "دریافت":
        await update.message.reply_text("شماره پاکت را وارد کنید:")
        return PACK_NUM
    
    elif context.user_data["transaction"]["type"] == "پرداخت":
        await update.message.reply_text("عیار را وارد کنید:")
        return PURITY
    
    elif context.user_data["transaction"]["type"] == "معامله":
        reply_keyboard = [["خرید", "فروش"]]
        await update.message.reply_text(
            "این یک معامله خرید است یا فروش؟",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return DEAL_DIRECTION

async def pack_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process pack number for Receive transactions."""
    context.user_data["transaction"]["pack_num"] = update.message.text
    await update.message.reply_text("اسم ریگیری را وارد کنید:")
    return ID_NUM

async def id_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process ID number for Receive transactions."""
    context.user_data["transaction"]["id_num"] = update.message.text
    await update.message.reply_text("عیار را وارد کنید:")
    return PURITY

async def purity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process purity and ask for weight."""
    context.user_data["transaction"]["purity"] = update.message.text
    await update.message.reply_text("وزن را وارد کنید:")
    return WEIGHT

async def weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process weight and ask for partner name or next relevant field."""
    context.user_data["transaction"]["weight"] = update.message.text
    
    await update.message.reply_text("طرف حساب را وارد کنید:")
    return PARTNER_NAME

async def partner_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process partner name and ask for description."""
    context.user_data["transaction"]["partner_name"] = update.message.text
    
    await update.message.reply_text("توضیحات را وارد کنید (اختیاری):")
    return DESCRIPTION

async def deal_direction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process deal direction (Buy/Sell) for Deal transactions."""
    context.user_data["transaction"]["deal_direction"] = update.message.text
    
    # Ask for deal type
    reply_keyboard = [["میلیونی", "گرمی", "دلاری", "درهمی"]]
    await update.message.reply_text(
        "نوع معامله را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return DEAL_TYPE

async def deal_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process deal type and ask for amount."""
    context.user_data["transaction"]["deal_type"] = update.message.text
    
    # Ask for amount based on the selected deal type
    unit = context.user_data["transaction"]["deal_type"]
    await update.message.reply_text(f"مقدار را  {unit} وارد کنید:")
    return AMOUNT

async def amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process amount and ask for next field based on transaction type."""
    context.user_data["transaction"]["amount"] = update.message.text
    
    if context.user_data["transaction"]["type"] == "معامله":
        await update.message.reply_text("نرخ را وارد کنید:")
        return RATE
    
    elif context.user_data["transaction"]["type"] == "حواله":
        await update.message.reply_text("طرف خریدار را وارد کنید:")
        return BUY_PARTNER_NAME

async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process rate for Deal transactions."""
    context.user_data["transaction"]["rate"] = update.message.text
    
    await update.message.reply_text("طرف حساب را وارد کنید:")
    return PARTNER_NAME

async def buy_partner_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process buy partner name for Bill transactions."""
    context.user_data["transaction"]["buy_partner_name"] = update.message.text
    
    await update.message.reply_text("طرف فروشنده را وارد کنید:")
    return SELL_PARTNER_NAME

async def sell_partner_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process sell partner name for Bill transactions."""
    context.user_data["transaction"]["sell_partner_name"] = update.message.text
    
    await update.message.reply_text("توضیحات را وارد کنید (اختیاری):")
    return DESCRIPTION

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process description and show summary for confirmation."""
    context.user_data["transaction"]["description"] = update.message.text
    
    return await show_transaction_summary(update, context)

async def show_transaction_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show transaction summary for confirmation without changing description."""
    # Build summary message based on transaction type
    transaction = context.user_data["transaction"]
    summary = f"خلاصه تراکنش:\n\n"
    summary += f"نوع: {transaction['type']}\n"
    summary += f"تاریخ: {transaction['date']}\n"
    
    if "receipt_num" in transaction:
        summary += f"شماره سند: {transaction['receipt_num']}\n"
    
    if "pack_num" in transaction:
        summary += f"شماره پاکت: {transaction['pack_num']}\n"
    
    if "id_num" in transaction:
        summary += f"اسم ریگیری: {transaction['id_num']}\n"
    
    if "purity" in transaction:
        summary += f"عیار: {transaction['purity']}\n"
    
    if "weight" in transaction:
        summary += f"وزن: {transaction['weight']}\n"
    
    if "partner_name" in transaction:
        summary += f"طرف حساب: {transaction['partner_name']}\n"
    
    if "deal_direction" in transaction:
        summary += f" جهت معامله: {transaction['deal_direction']}\n"
    
    if "deal_type" in transaction:
        summary += f"نوع معامله: {transaction['deal_type']}\n"
    
    if "amount" in transaction:
        summary += f"مقدار: {transaction['amount']}\n"
    
    if "rate" in transaction:
        summary += f"نرخ: {transaction['rate']}\n"
    
    if "buy_partner_name" in transaction:
        summary += f"طرف خریدار: {transaction['buy_partner_name']}\n"
    
    if "sell_partner_name" in transaction:
        summary += f"طرف فروشنده: {transaction['sell_partner_name']}\n"
    
    summary += f"توضیحات: {transaction['description']}\n"
    
    # Add confirmation buttons
    keyboard = [
        [
            InlineKeyboardButton("تایید", callback_data="confirm"),
            InlineKeyboardButton("ویرایش", callback_data="edit")
        ],
        [InlineKeyboardButton("انصراف", callback_data="cancel")]
    ]
    
    # Check if this is a callback update or a message update
    if update.callback_query:
        await update.callback_query.edit_message_text(
            summary,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            summary,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    return CONFIRMATION

async def confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation callback query with improved sheet writing."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm":
        try:
            # Open the Google Sheet
            worksheet = setup_google_sheets()
            
            # Get headers from the first row
            headers = worksheet.row_values(1)
            
            # Prepare the data as a dictionary
            transaction = context.user_data["transaction"]
            data_dict = {
                "نوع تراکنش": transaction.get("type", ""),
                "تاریخ": transaction.get("date", ""),
                "شماره سند": transaction.get("receipt_num", ""),
                "شماره پاکت": transaction.get("pack_num", ""),
                "اسم ریگیری": transaction.get("id_num", ""),
                "عیار": transaction.get("purity", ""),
                "وزن": transaction.get("weight", ""),
                "طرف حساب": transaction.get("partner_name", ""),
                "جهت معامله": transaction.get("deal_direction", ""),
                "نوع معامله": transaction.get("deal_type", ""),
                "مقدار": transaction.get("amount", ""),
                "نرخ": transaction.get("rate", ""),
                "طرف خریدار": transaction.get("buy_partner_name", ""),
                "طرف فروشنده": transaction.get("sell_partner_name", ""),
                "توضیحات": transaction.get("description", ""),
                "زمان ثبت": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Create a row with values in the correct order based on headers
            row_data = []
            for header in headers:
                row_data.append(data_dict.get(header, ""))
            
            # Add to Google Sheets
            worksheet.append_row(row_data)
            
            await query.edit_message_text("✅ تراکنش با موفقیت در Google Sheets ذخیره شد!")
            
            # Return to main menu with buttons after successful transaction
            reply_keyboard = [["شروع"], ["تراکنش جدید"]]
            await query.message.reply_text(
                "می‌توانید تراکنش جدید ثبت کنید یا به صفحه اصلی برگردید:",
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
            )
            
        except Exception as e:
            logger.error(f"Error saving to Google Sheets: {e}")
            await query.edit_message_text(f"❌ خطا در ذخیره تراکنش: {str(e)}")
        
        context.user_data.clear()
        return MAIN_MENU
    
    elif query.data == "edit":
        # Create a list of fields that can be edited based on transaction type
        transaction = context.user_data["transaction"]
        fields = ["شماره سند", "توضیحات"]
        
        if transaction["type"] == "دریافت":
            fields.extend(["شماره پاکت", "اسم ریگیری", "عیار", "وزن", "طرف حساب"])
        elif transaction["type"] == "پرداخت":
            fields.extend(["عیار", "وزن", "طرف حساب"])
        elif transaction["type"] == "معامله":
            fields.extend(["جهت معامله", "نوع معامله", "مقدار", "نرخ", "طرف حساب"])
        elif transaction["type"] == "حواله":
            fields.extend(["نوع معامله", "مقدار", "طرف خریدار", "طرف فروشنده"])
        
        # Create buttons for each field
        keyboard = []
        for i in range(0, len(fields), 2):
            row = []
            row.append(InlineKeyboardButton(fields[i], callback_data=f"field_{fields[i]}"))
            if i + 1 < len(fields):
                row.append(InlineKeyboardButton(fields[i + 1], callback_data=f"field_{fields[i + 1]}"))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("بازگشت به تأیید", callback_data="back_to_confirm")])
        
        await query.edit_message_text(
            "فیلدی که می‌خواهید ویرایش کنید را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return EDIT_FIELD
    
    elif query.data == "cancel":
        await query.edit_message_text("تراکنش لغو شد.")
        
        # Return to main menu with buttons after cancellation
        reply_keyboard = [["شروع"], ["تراکنش جدید"]]
        await query.message.reply_text(
            "می‌توانید تراکنش جدید ثبت کنید یا به صفحه اصلی برگردید:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        )
        
        context.user_data.clear()
        return MAIN_MENU

async def edit_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle edit field selection with appropriate buttons for certain fields."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_confirm":
        # Go back to confirmation without changes
        return await show_transaction_summary(update, context)
    
    # Extract field name from callback data
    field = query.data.replace("field_", "")
    context.user_data["edit_field"] = field
    
    # Check if this field requires buttons
    if field == "جهت معامله":
        reply_keyboard = [["خرید", "فروش"]]
        await query.edit_message_text(
            f"لطفا مقدار جدید برای {field} را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("خرید", callback_data="edit_value_خرید")],
                [InlineKeyboardButton("فروش", callback_data="edit_value_فروش")]
            ])
        )
        return EDIT_FIELD  # Stay in EDIT_FIELD state but process value in callback
        
    elif field == "نوع معامله":
        await query.edit_message_text(
            f"لطفا مقدار جدید برای {field} را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("میلیونی", callback_data="edit_value_میلیونی")],
                [InlineKeyboardButton("گرمی", callback_data="edit_value_گرمی")],
                [InlineKeyboardButton("دلاری", callback_data="edit_value_دلاری")], [InlineKeyboardButton("درهمی", callback_data="edit_value_درهمی")]
            ])
        )
        return EDIT_FIELD  # Stay in EDIT_FIELD state but process value in callback
    
    else:
        await query.edit_message_text(f"لطفا مقدار جدید برای {field} را وارد کنید:")
        return EDIT_VALUE  # Regular text input field

async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the edited value from text input and return to confirmation."""
    new_value = update.message.text
    field = context.user_data["edit_field"]
    
    # Update the value in user_data
    data_key = FIELD_MAPPING.get(field)
    if data_key:
        context.user_data["transaction"][data_key] = new_value
    
    # Go back to confirmation without changing description
    return await show_transaction_summary(update, context)

async def edit_value_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process edited value from buttons and return to confirmation."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("edit_value_"):
        new_value = query.data.replace("edit_value_", "")
        field = context.user_data["edit_field"]
        
        # Update the value in user_data
        data_key = FIELD_MAPPING.get(field)
        if data_key:
            context.user_data["transaction"][data_key] = new_value
        
        # Go back to confirmation
        return await show_transaction_summary(update, context)
    
    return EDIT_FIELD

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the transaction and return to main menu."""
    reply_keyboard = [["شروع"], ["تراکنش جدید"]]
    await update.message.reply_text(
        "تراکنش لغو شد.",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )
    context.user_data.clear()
    return MAIN_MENU

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

    # Add conversation handler with states
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^(شروع|تراکنش جدید)$"), handle_main_menu)
        ],
        states={
            MAIN_MENU: [MessageHandler(filters.Regex("^(شروع|تراکنش جدید)$"), handle_main_menu)],
            TRANSACTION_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, transaction_type)],
            RECEIPT_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receipt_num)],
            PACK_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, pack_num)],
            ID_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, id_num)],
            PURITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, purity)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, weight)],
            PARTNER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, partner_name)],
            DEAL_DIRECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_direction)],
            DEAL_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_type)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount)],
            RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rate)],
            BUY_PARTNER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_partner_name)],
            SELL_PARTNER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_partner_name)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description)],
            CONFIRMATION: [CallbackQueryHandler(confirmation_callback)],
            EDIT_FIELD: [
                CallbackQueryHandler(edit_field_callback, pattern="^field_|back_to_confirm$"),
                CallbackQueryHandler(edit_value_callback, pattern="^edit_value_")
            ],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()