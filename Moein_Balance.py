import logging
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
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
 DEAL_DIRECTION, DEAL_TYPE, AMOUNT, RATE, GIVER_PARTNER_NAME, RECEIVER_PARTNER_NAME,
 DESCRIPTION, CONFIRMATION, EDIT_FIELD, EDIT_VALUE, MAIN_MENU) = range(18)

# Define column headers for Google Sheets
HEADERS = [
    "نوع تراکنش", "تاریخ", "شماره سند", "شماره پاکت", "اسم ریگیری", 
    "عیار", "وزن", "طرف حساب", "جهت معامله", "نوع معامله", 
    "مقدار", "نرخ", "طرف پرداخت کننده", "طرف دریافت کننده", 
    "توضیحات", "زمان ثبت"
]

# Define callback prefixes for better organization
CB_TRANSACTION_TYPE = "type_"
CB_DEAL_DIRECTION = "dir_"
CB_DEAL_TYPE = "dealtype_"
CB_EDIT_FIELD = "field_"
CB_EDIT_VALUE = "edit_value_"
CB_PARTNER_NAME = "partner_"
CB_GIVER_PARTNER = "giver_partner_"
CB_RECEIVER_PARTNER = "receiver_partner_"

# Define persistent menu that will always be available
MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["🆕 تراکنش جدید"],
    ["🏠 بازگشت به صفحه اصلی", "❌ انصراف"]
], resize_keyboard=True)

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
    "طرف پرداخت کننده": "giver_partner_name",
    "طرف دریافت کننده": "receiver_partner_name",
    "توضیحات": "description"
}

# Google Sheets setup
def setup_google_sheets():
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
        if not existing_headers or existing_headers != HEADERS:
            # Clear first row and add all headers
            if existing_headers:
                worksheet.delete_row(1)
            # Use update to set headers in the first row
            worksheet.update('A1', [HEADERS])
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="Transactions", rows=1000, cols=20)
        # Add headers
        worksheet.update('A1', [HEADERS])
    
    return worksheet

def get_last_number_from_other_sheet(cell: str) -> str:
    """Read a specific cell from another worksheet (e.g., 'GreenLand')."""
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

    spreadsheet = client.open("Test")
    worksheet_toread = spreadsheet.worksheet("GreenLand")  # Change to your worksheet name
    return worksheet_toread.acell(cell).value

# Add these functions to fetch and update partner names

def get_partner_names_from_sheet():
    """Fetch partner names from the GreenLand worksheet."""
    try:
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
        spreadsheet = client.open("Test")
        worksheet = spreadsheet.worksheet("GreenLand")
        # Find the column by header name instead of assuming position
        headers = worksheet.row_values(1)
        
        try:
            # Find column index for "نام مشتری"
            header_index = headers.index("نام مشتری") + 1  # Convert to 1-based index for gspread
            
            # If found, get values from that column
            if header_index:
                partner_column = worksheet.col_values(header_index)
                # Remove header and empty values
                partner_names = [name for name in partner_column[1:] if name.strip()]
                
                # Add logging to help debug
                logger.info(f"Found {len(partner_names)} partner names: {partner_names[:5]}...")
                return partner_names
            else:
                logger.error(f"Header 'نام مشتری' not found in worksheet. Available headers: {headers}")
                return []
        except ValueError:
            logger.error(f"Header 'نام مشتری' not found in worksheet. Available headers: {headers}")
            return []
        except Exception as e:
            logger.error(f"Error fetching partner names: {e}")
            return []
    except gspread.exceptions.WorksheetNotFound:
        logger.error(f"Worksheet 'Green land' not found. Please check the name.")
        return []
    except Exception as e:
        logger.error(f"Error connecting to sheet: {e}")
        return []

def add_partner_name_to_sheet(name):
    """Add a new partner name to the GreenLand worksheet."""
    try:
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
        spreadsheet = client.open("Test")
        worksheet = spreadsheet.worksheet("GreenLand")
        
        # Find the "نام مشتری" column
        try:
            # Find the column by header name instead of assuming position
            headers = worksheet.row_values(1)
            # Find column index for "نام مشتری"
            header_index = headers.index("نام مشتری") + 1  # Convert to 1-based index for gspread
            partner_column = worksheet.col_values(header_index)[1:]
            # Check if name already exists
            if name in partner_column:
                return False
            
            # Find the first empty cell in the column
            next_row = len(partner_column) + 2  # +2 because col_values skips header and gspread is 1-based
            worksheet.update_cell(next_row, header_index, name)
            return True
        except ValueError:
            logger.error(f"Header 'نام مشتری' not found in worksheet. Available headers: {headers}")
            return False
        except Exception as e:
            logger.error(f"Error adding partner name: {e}")
            return False
    except Exception as e:
        logger.error(f"Error connecting to sheet: {e}")
        return False

def create_partner_buttons(partner_names, prefix):
    """Create inline keyboard buttons for partner names."""
    keyboard = []
    # Show partners in rows of 2
    for i in range(0, len(partner_names), 2):
        row = [InlineKeyboardButton(partner_names[i], callback_data=f"{prefix}{partner_names[i]}")]
        if i + 1 < len(partner_names):
            row.append(InlineKeyboardButton(partner_names[i+1], callback_data=f"{prefix}{partner_names[i+1]}"))
        keyboard.append(row)
    
    # Add button to enter custom name
    keyboard.append([InlineKeyboardButton("➕ افزودن نام جدید", callback_data=f"{prefix}ADD_NEW")])
    
    return keyboard

def to_english_number(s):
    """Convert Persian/Arabic digits in a string to English digits."""
    if not isinstance(s, str):
        return s
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    arabic_digits = '٠١٢٣٤٥٦٧٨٩'
    english_digits = '0123456789'
    table = {}
    for p, e in zip(persian_digits, english_digits):
        table[ord(p)] = e
    for a, e in zip(arabic_digits, english_digits):
        table[ord(a)] = e
    return s.translate(table)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send welcome message with a single start button."""
    # Clear any existing data
    context.user_data.clear()
    
    start_keyboard = ReplyKeyboardMarkup([["🚀 شروع"]], resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 به سیستم ثبت تراکنش خوش آمدید!\n\n"
        "من به شما کمک می‌کنم انواع مختلف تراکنش را در Google Sheets ثبت کنید.\n"
        "برای شروع روی دکمه زیر کلیک کنید.",
        reply_markup=start_keyboard
    )
    
    return MAIN_MENU

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle main menu interactions."""
    # Handle both message and callback inputs
    if update.message:
        text = update.message.text
    else:
        # In case this is called from a callback
        text = "🏠 بازگشت به صفحه اصلی"
    
    if "شروع" in text:
        # Show main menu options
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=MENU_KEYBOARD
        )
        return MAIN_MENU
        
    elif "تراکنش جدید" in text:
        # Start a new transaction while keeping the menu visible
        return await new_transaction(update, context)
        
    elif "انصراف" in text:
        # Cancel current operation
        context.user_data.clear()
        await update.message.reply_text(
            "عملیات لغو شد. می‌توانید تراکنش جدید ثبت کنید.",
            reply_markup=MENU_KEYBOARD
        )
        return MAIN_MENU
        
    elif "بازگشت به صفحه اصلی" in text:
        # Return to main menu
        context.user_data.clear()
        await update.message.reply_text(
            "به صفحه اصلی بازگشتید. می‌توانید تراکنش جدید ثبت کنید.",
            reply_markup=MENU_KEYBOARD
        )
        return MAIN_MENU
        
    else:
        # Unexpected input
        await update.message.reply_text(
            "لطفاً از دکمه‌های موجود استفاده کنید.",
            reply_markup=MENU_KEYBOARD
        )
        return MAIN_MENU

async def new_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start transaction with inline keyboard while keeping persistent menu."""
    # Initialize transaction data
    context.user_data["transaction"] = {}
    context.user_data["transaction"]["date"] = datetime.now().strftime("%Y-%m-%d")
    
    # Use inline keyboard for options while keeping the persistent menu visible
    inline_keyboard = [
        [
            InlineKeyboardButton("دریافت", callback_data=f"{CB_TRANSACTION_TYPE}دریافت"),
            InlineKeyboardButton("پرداخت", callback_data=f"{CB_TRANSACTION_TYPE}پرداخت")
        ],
        [
            InlineKeyboardButton("معامله", callback_data=f"{CB_TRANSACTION_TYPE}معامله"),
            InlineKeyboardButton("حواله", callback_data=f"{CB_TRANSACTION_TYPE}حواله")
        ]
    ]
    
    await update.message.reply_text(
        "لطفاً نوع تراکنش را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )
    
    return TRANSACTION_TYPE

async def handle_transaction_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle transaction type selection from inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    # Get transaction type from callback data
    transaction_type = query.data.replace(CB_TRANSACTION_TYPE, "")
    context.user_data["transaction"]["type"] = transaction_type
    
    # Get last number from sheet if applicable
    cell_map = {"دریافت": "A2", "پرداخت": "B2", "معامله": "C2"}
    last_num = None
    if cell := cell_map.get(transaction_type):
        try:
            last_num = get_last_number_from_other_sheet(cell)
        except Exception:
            pass
    
    # Ask for receipt number or continue flow based on transaction type
    if transaction_type in ["دریافت", "پرداخت", "معامله"]:
        msg = "شماره سند را وارد کنید:"
        if last_num:
            msg = f"آخرین شماره سند ثبت شده: {last_num}\n{msg}"
        await query.message.reply_text(msg)
        return RECEIPT_NUM
    
    elif transaction_type == "حواله":
        inline_keyboard = [
            [
                InlineKeyboardButton("AED", callback_data=f"{CB_DEAL_TYPE}AED"),
                InlineKeyboardButton("Milion", callback_data=f"{CB_DEAL_TYPE}Milion")
            ],
            [
                InlineKeyboardButton("Gold gr", callback_data=f"{CB_DEAL_TYPE}Gold gr"),
                InlineKeyboardButton("USD", callback_data=f"{CB_DEAL_TYPE}USD")
            ]
        ]
        
        await query.message.reply_text(
            "نوع حواله را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        return DEAL_TYPE
    
    # Fallback
    else:
        await query.message.reply_text("نوع تراکنش نامعتبر است. لطفا دوباره تلاش کنید.")
        return TRANSACTION_TYPE

async def receipt_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process receipt number and ask next question based on transaction type."""
    # Ignore menu commands (they're handled by the conversation handler)
    if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
        return

    context.user_data["transaction"]["receipt_num"] = to_english_number(update.message.text)
    
    if context.user_data["transaction"]["type"] == "دریافت":
        await update.message.reply_text("شماره پاکت را وارد کنید:")
        return PACK_NUM
    
    elif context.user_data["transaction"]["type"] == "پرداخت":
        await update.message.reply_text("عیار را وارد کنید:")
        return PURITY
    
    elif context.user_data["transaction"]["type"] == "معامله":
        inline_keyboard = [
            [InlineKeyboardButton("Buy", callback_data=f"{CB_DEAL_DIRECTION}Buy")],
            [InlineKeyboardButton("Sell", callback_data=f"{CB_DEAL_DIRECTION}Sell")]
        ]
        await update.message.reply_text(
            "لطفا جهت معامله مشخص کنید؟",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        return DEAL_DIRECTION

async def pack_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process pack number for Receive transactions."""
    # Ignore menu commands
    if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
        return

    context.user_data["transaction"]["pack_num"] = to_english_number(update.message.text)
    await update.message.reply_text("اسم ریگیری را وارد کنید:")
    return ID_NUM

async def id_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process ID number for Receive transactions."""
    # Ignore menu commands
    if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
        return

    context.user_data["transaction"]["id_num"] = to_english_number(update.message.text)
    await update.message.reply_text("عیار را وارد کنید:")
    return PURITY

async def purity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process purity and ask for weight."""
    # Ignore menu commands
    if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
        return

    context.user_data["transaction"]["purity"] = to_english_number(update.message.text)
    await update.message.reply_text("وزن را وارد کنید:")
    return WEIGHT

async def weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process weight and ask for partner name or next relevant field."""
    # Ignore menu commands
    if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
        return

    context.user_data["transaction"]["weight"] = to_english_number(update.message.text)
    
    # Explicitly call show_partner_selection instead of just asking for input
    return await show_partner_selection(
        update, context, 
        "طرف حساب", 
        CB_PARTNER_NAME, 
        PARTNER_NAME
    )

async def show_partner_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, title: str, callback_prefix: str, next_state: int) -> int:
    """Show partner selection buttons with debugging."""
    logger.info(f"Fetching partner names for {title}")
    partner_names = get_partner_names_from_sheet()
    
    logger.info(f"Found {len(partner_names)} partner names")
    
    if not partner_names:
        logger.warning("No partner names found in sheet")
        # If no partners found, go directly to text input
        if update.callback_query:
            await update.callback_query.message.reply_text(f"{title} را وارد کنید:")
        else:
            await update.message.reply_text(f"{title} را وارد کنید:")
        context.user_data["current_partner_field"] = title
        context.user_data["next_state"] = next_state
        return next_state
    
    # Create buttons with partner names
    keyboard = create_partner_buttons(partner_names, callback_prefix)
    logger.info(f"Created keyboard with {len(keyboard)} rows")
    
    try:
        if update.callback_query:
            await update.callback_query.message.reply_text(
                f"{title} را انتخاب کنید یا نام جدید اضافه کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                f"{title} را انتخاب کنید یا نام جدید اضافه کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        logger.info("Successfully sent partner selection message")
    except Exception as e:
        logger.error(f"Error sending partner selection: {e}")
    
    context.user_data["current_partner_field"] = title
    context.user_data["next_state"] = next_state
    return next_state

async def handle_partner_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, field_name: str) -> int:
    """Handle partner selection from buttons."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Determine which prefix we're dealing with
    prefix = ""
    if callback_data.startswith(CB_PARTNER_NAME):
        prefix = CB_PARTNER_NAME
    elif callback_data.startswith(CB_GIVER_PARTNER):
        prefix = CB_GIVER_PARTNER
    elif callback_data.startswith(CB_RECEIVER_PARTNER):
        prefix = CB_RECEIVER_PARTNER
    
    selection = callback_data.replace(prefix, "")
    
    if selection == "ADD_NEW":
        # User wants to add a new partner
        await query.message.reply_text(f"لطفا {context.user_data['current_partner_field']} جدید را وارد کنید:")
        context.user_data["adding_new_partner"] = True
        return context.user_data["next_state"]
    else:
        # User selected an existing partner
        context.user_data["transaction"][field_name] = selection
        
        # Determine next state based on the transaction flow
        if field_name == "partner_name":
            await query.message.reply_text("توضیحات را وارد کنید (اختیاری):")
            return DESCRIPTION
        elif field_name == "giver_partner_name":
            return await show_partner_selection(
                update, context, 
                "به چه کسی پرداخت می کنید؟", 
                CB_RECEIVER_PARTNER, 
                RECEIVER_PARTNER_NAME 
            )
        elif field_name == "receiver_partner_name":
            await query.message.reply_text("توضیحات را وارد کنید (اختیاری):")
            return DESCRIPTION
        
async def partner_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process partner name input or show partner selection."""
    # If this is a text message and we were adding a new partner
    if update.message and context.user_data.get("adding_new_partner"):
        # Ignore menu commands
        if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
            return
        
        new_partner = update.message.text
        context.user_data["transaction"]["partner_name"] = new_partner
        
        # Add the new partner to the sheet
        success = add_partner_name_to_sheet(new_partner)
        if success:
            await update.message.reply_text(f"نام '{new_partner}' به لیست مشتریان اضافه شد.")
        
        # Clear the flag
        context.user_data["adding_new_partner"] = False
        
        # Continue to description
        await update.message.reply_text("توضیحات را وارد کنید (اختیاری):")
        return DESCRIPTION
    
    # If this is a fresh request, show partner selection
    elif update.message and not context.user_data.get("adding_new_partner"):
        # Ignore menu commands
        if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
            return
            
        # This is a direct text entry without selecting from the list
        context.user_data["transaction"]["partner_name"] = update.message.text
        
        # Continue to description
        await update.message.reply_text("توضیحات را وارد کنید (اختیاری):")
        return DESCRIPTION
    
    # Initial partner name request - show selection buttons
    return await show_partner_selection(
        update, context, 
        "طرف حساب", 
        CB_PARTNER_NAME, 
        PARTNER_NAME
    )

async def handle_deal_direction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process deal direction from callback."""
    query = update.callback_query
    await query.answer()
    
    deal_direction = query.data.replace(CB_DEAL_DIRECTION, "")
    context.user_data["transaction"]["deal_direction"] = deal_direction
    
    # Ask for deal type
    inline_keyboard = [
        [
            InlineKeyboardButton("AED", callback_data=f"{CB_DEAL_TYPE}AED"),
            InlineKeyboardButton("Gold Milion", callback_data=f"{CB_DEAL_TYPE}Gold Milion")
        ],
        [
            InlineKeyboardButton("Gold gr", callback_data=f"{CB_DEAL_TYPE}Gold gr"),
            InlineKeyboardButton("USD", callback_data=f"{CB_DEAL_TYPE}USD")
        ]
    ]
    
    await query.message.reply_text(
        "نوع معامله را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )
    return DEAL_TYPE

async def handle_deal_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process deal type from callback."""
    query = update.callback_query
    await query.answer()
    
    deal_type = query.data.replace(CB_DEAL_TYPE, "")
    context.user_data["transaction"]["deal_type"] = deal_type
    
    # Ask for amount based on the selected deal type
    await query.message.reply_text(f"مقدار را {deal_type} وارد کنید:")
    return AMOUNT

async def amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process amount and ask for next field based on transaction type."""
    # Ignore menu commands
    if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
        return

    context.user_data["transaction"]["amount"] = to_english_number(update.message.text)
    
    if context.user_data["transaction"]["type"] == "معامله":
        await update.message.reply_text("نرخ را وارد کنید:")
        return RATE
    
    elif context.user_data["transaction"]["type"] == "حواله":
        logger.info("Bill transaction, now showing buy partner selection")
        # Show buy partner selection
        return await show_partner_selection(
            update, context, 
            "از چه کسی دریافت می کنید؟", 
            CB_GIVER_PARTNER, 
            GIVER_PARTNER_NAME
        )

async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process rate for Deal transactions."""
    # Ignore menu commands
    if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
        return

    context.user_data["transaction"]["rate"] = to_english_number(update.message.text)
    logger.info("Rate processed, now showing partner selection")
    
    # Show partner selection instead of asking for text input
    return await show_partner_selection(
        update, context, 
        "طرف حساب", 
        CB_PARTNER_NAME, 
        PARTNER_NAME
    )

async def giver_partner_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process buy partner name input or show partner selection."""
    # If this is a text message and we were adding a new partner
    if update.message and context.user_data.get("adding_new_partner"):
        # Ignore menu commands
        if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
            return
        
        new_partner = update.message.text
        context.user_data["transaction"]["giver_partner_name"] = new_partner
        
        # Add the new partner to the sheet
        success = add_partner_name_to_sheet(new_partner)
        if success:
            await update.message.reply_text(f"نام '{new_partner}' به لیست مشتریان اضافه شد.")
        
        # Clear the flag
        context.user_data["adding_new_partner"] = False
        
        # Continue to sell partner name
        return await show_partner_selection(
            update, context, 
            "به چه کسی پرداخت می کنید؟", 
            CB_RECEIVER_PARTNER, 
            RECEIVER_PARTNER_NAME
        )
    
    # If this is a fresh request, show partner selection
    elif update.message and not context.user_data.get("adding_new_partner"):
        # Ignore menu commands
        if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
            return
            
        # This is a direct text entry without selecting from the list
        context.user_data["transaction"]["giver_partner_name"] = update.message.text
        
        # Continue to sell partner name
        return await show_partner_selection(
            update, context, 
            "به چه کسی پرداخت می کنید؟", 
            CB_RECEIVER_PARTNER, 
            RECEIVER_PARTNER_NAME
        )
    
    # Initial buy partner name request - show selection buttons
    return await show_partner_selection(
        update, context, 
        "از چه کسی دریافت می کنید؟", 
        CB_GIVER_PARTNER, 
        GIVER_PARTNER_NAME
    )

async def receiver_partner_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process sell partner name input or show partner selection."""
    # If this is a text message and we were adding a new partner
    if update.message and context.user_data.get("adding_new_partner"):
        # Ignore menu commands
        if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
            return
        
        new_partner = update.message.text
        context.user_data["transaction"]["receiver_partner_name"] = new_partner
        
        # Add the new partner to the sheet
        success = add_partner_name_to_sheet(new_partner)
        if success:
            await update.message.reply_text(f"نام '{new_partner}' به لیست مشتریان اضافه شد.")
        
        # Clear the flag
        context.user_data["adding_new_partner"] = False
        
        # Continue to description
        await update.message.reply_text("توضیحات را وارد کنید (اختیاری):")
        return DESCRIPTION
    
    # If this is a fresh request, show partner selection
    elif update.message and not context.user_data.get("adding_new_partner"):
        # Ignore menu commands
        if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
            return
            
        # This is a direct text entry without selecting from the list
        context.user_data["transaction"]["receiver_partner_name"] = update.message.text
        
        # Continue to description
        await update.message.reply_text("توضیحات را وارد کنید (اختیاری):")
        return DESCRIPTION
    
    # Initial sell partner name request - show selection buttons
    return await show_partner_selection(
        update, context, 
        "به چه کسی پرداخت می کنید؟", 
        CB_RECEIVER_PARTNER, 
        RECEIVER_PARTNER_NAME
    )

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process description and show summary for confirmation."""
    # Ignore menu commands
    if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
        return

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
        summary += f"جهت معامله: {transaction['deal_direction']}\n"
    
    if "deal_type" in transaction:
        summary += f"نوع معامله: {transaction['deal_type']}\n"
    
    if "amount" in transaction:
        summary += f"مقدار: {transaction['amount']}\n"
    
    if "rate" in transaction:
        summary += f"نرخ: {transaction['rate']}\n"
    
    if "giver_partner_name" in transaction:
        summary += f"طرف پرداخت کننده: {transaction['giver_partner_name']}\n"
    
    if "receiver_partner_name" in transaction:
        summary += f"طرف دریافت کننده: {transaction['receiver_partner_name']}\n"
    
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
            
           # Find the next empty row
            all_values = worksheet.get_all_values()
            next_row = len(all_values) + 1  # 1-based index for sheets
            
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
                "طرف پرداخت کننده": transaction.get("giver_partner_name", ""),
                "طرف دریافت کننده": transaction.get("receiver_partner_name", ""),
                "توضیحات": transaction.get("description", ""),
                "زمان ثبت": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            logger.info(f"Sheet headers: {HEADERS}")
            logger.info(f"Data dict keys: {list(data_dict.keys())}")
            # Convert numeric fields to numbers if possible
            numeric_fields = [
                "شماره سند", "شماره پاکت", "عیار", "وزن", "مقدار", "نرخ"
            ]
            for field in numeric_fields:
                value = data_dict.get(field, "")
                if isinstance(value, str) and value.strip() != "":
                    try:
                        # Try to convert to int first, then fall back to float if necessary
                        num = int(value.replace(",", ""))
                    except ValueError:
                        try:
                            num = float(value.replace(",", ""))
                        except ValueError:
                            num = value  # Leave as is if conversion fails
                    data_dict[field] = num

            # Create a row with values in the correct order based on headers
            row_data = []
            for header in HEADERS:
                row_data.append(data_dict.get(header, ""))
            
            # # Add to Google Sheets
            # worksheet.append_row(row_data)
            # Update specific cells in the next empty row (ensure same order as HEADERS)
            cell_range = f"A{next_row}:P{next_row}"  # A-P covers 16 columns
            worksheet.update(cell_range, [row_data])

            await query.edit_message_text("✅ تراکنش با موفقیت در Google Sheets ذخیره شد!")
            
            # Return to main menu with buttons after successful transaction
            await query.message.reply_text(
                "می‌توانید تراکنش جدید ثبت کنید یا به صفحه اصلی برگردید.",
                reply_markup=MENU_KEYBOARD
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
            fields.extend(["نوع معامله", "مقدار", "طرف پرداخت کننده", "طرف دریافت کننده"])
        
        # Create buttons for each field
        keyboard = []
        for i in range(0, len(fields), 2):
            row = []
            row.append(InlineKeyboardButton(fields[i], callback_data=f"{CB_EDIT_FIELD}{fields[i]}"))
            if i + 1 < len(fields):
                row.append(InlineKeyboardButton(fields[i + 1], callback_data=f"{CB_EDIT_FIELD}{fields[i + 1]}"))
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
        await query.message.reply_text(
            "می‌توانید تراکنش جدید ثبت کنید یا به صفحه اصلی برگردید.",
            reply_markup=MENU_KEYBOARD
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
    field = query.data.replace(CB_EDIT_FIELD, "")
    context.user_data["edit_field"] = field
    
    # Check if this field requires buttons
    if field == "جهت معامله":
        await query.edit_message_text(
            f"لطفا مقدار جدید برای {field} را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Buy", callback_data=f"{CB_EDIT_VALUE}Buy")],
                [InlineKeyboardButton("Sell", callback_data=f"{CB_EDIT_VALUE}Sell")]
            ])
        )
        return EDIT_FIELD  # Stay in EDIT_FIELD state but process value in callback
        
    elif field == "نوع معامله":
        await query.edit_message_text(
            f"لطفا مقدار جدید برای {field} را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Gold gr", callback_data=f"{CB_EDIT_VALUE}Gold gr")],
                [InlineKeyboardButton("Gold Milion", callback_data=f"{CB_EDIT_VALUE}Gold Milion")],
                [InlineKeyboardButton("AED", callback_data=f"{CB_EDIT_VALUE}AED")],
                [InlineKeyboardButton("USD", callback_data=f"{CB_EDIT_VALUE}USD")]
            ])
        )
        return EDIT_FIELD  # Stay in EDIT_FIELD state but process value in callback
    
    else:
        await query.edit_message_text(f"لطفا مقدار جدید برای {field} را وارد کنید:")
        return EDIT_VALUE  # Regular text input field

async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the edited value from text input and return to confirmation."""
    # Ignore menu commands
    if update.message.text in ["🆕 تراکنش جدید", "🏠 بازگشت به صفحه اصلی", "❌ انصراف"]:
        return

    new_value = update.message.text
    field = context.user_data["edit_field"]
    # If the field is numeric, convert to English digits
    numeric_fields = ["شماره سند", "شماره پاکت", "عیار", "وزن", "مقدار", "نرخ"]
    if field in numeric_fields:
        new_value = to_english_number(new_value)
    
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
    
    if query.data.startswith(CB_EDIT_VALUE):
        new_value = query.data.replace(CB_EDIT_VALUE, "")
        field = context.user_data["edit_field"]
        
        # Update the value in user_data
        data_key = FIELD_MAPPING.get(field)
        if data_key:
            context.user_data["transaction"][data_key] = new_value
        
        # Go back to confirmation
        return await show_transaction_summary(update, context)
    
    return EDIT_FIELD

async def cancel_from_any_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Universal cancel handler for any state."""
    context.user_data.clear()
    
    await update.message.reply_text(
        "عملیات لغو شد. شما می‌توانید تراکنش جدیدی ثبت کنید.",
        reply_markup=MENU_KEYBOARD
    )
    
    return MAIN_MENU

def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

    # Add conversation handler with states
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^(🚀 شروع|🆕 تراکنش جدید|❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu)
        ],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^(🚀 شروع|🆕 تراکنش جدید|❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu)
            ],
            TRANSACTION_TYPE: [
                CallbackQueryHandler(handle_transaction_type_callback, pattern=f"^{CB_TRANSACTION_TYPE}"),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            RECEIPT_NUM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), receipt_num),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            PACK_NUM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), pack_num),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            ID_NUM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), id_num),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            PURITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), purity),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), weight),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            PARTNER_NAME: [
                CallbackQueryHandler(
                    lambda u, c: handle_partner_selection(u, c, "partner_name"), 
                    pattern=f"^{CB_PARTNER_NAME}"
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), partner_name),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            DEAL_DIRECTION: [
                CallbackQueryHandler(handle_deal_direction_callback, pattern=f"^{CB_DEAL_DIRECTION}"),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            DEAL_TYPE: [
                CallbackQueryHandler(handle_deal_type_callback, pattern=f"^{CB_DEAL_TYPE}"),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), amount),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), rate),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            GIVER_PARTNER_NAME: [
                CallbackQueryHandler(
                    lambda u, c: handle_partner_selection(u, c, "giver_partner_name"), 
                    pattern=f"^{CB_GIVER_PARTNER}"
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), giver_partner_name),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            RECEIVER_PARTNER_NAME: [
                CallbackQueryHandler(
                    lambda u, c: handle_partner_selection(u, c, "receiver_partner_name"), 
                    pattern=f"^{CB_RECEIVER_PARTNER}"
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), receiver_partner_name),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), description),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            CONFIRMATION: [
                CallbackQueryHandler(confirmation_callback),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            EDIT_FIELD: [
                CallbackQueryHandler(edit_field_callback, pattern=f"^{CB_EDIT_FIELD}|back_to_confirm$"),
                CallbackQueryHandler(edit_value_callback, pattern=f"^{CB_EDIT_VALUE}"),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
            EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی|🆕 تراکنش جدید)$"), edit_value),
                MessageHandler(filters.Regex("^(❌ انصراف|🏠 بازگشت به صفحه اصلی)$"), handle_main_menu),
                MessageHandler(filters.Regex("^🆕 تراکنش جدید$"), new_transaction)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_from_any_state)],
        allow_reentry=True
    )

    application.add_handler(conv_handler)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()