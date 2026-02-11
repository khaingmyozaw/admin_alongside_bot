"""
VPN Key Generator Telegram Bot

Admin users can create VPN keys from VLESS (3x-ui) and Outline (Marzban) servers.
Non-admin users see a support button.

Plans:
  VLESS:
    🥉 Basic  - 1 device / unlimited / 1 month
    🥈 Silver - 2 devices / unlimited / 1 month
    🥇 Golden - 3 devices / unlimited / 1 month
    Trial      - 1 device / 500MB / 1 day

  Outline:
    🥉 Basic  - unlimited / 1 month
    🥈 Silver - unlimited / 1 month
    🥇 Golden - unlimited / 1 month
    Trial      - 500MB / 1 day
"""

import re
import logging
import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, SUPPORT_USERNAME, is_admin, VLESS_INBOUND_IDS
from vless_api import VlessClient
from marzban_api import MarzbanClient

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── API Clients ──────────────────────────────────────────────────────────────
vless_client = VlessClient()
marzban_client = MarzbanClient()

# ─── Plan Definitions ────────────────────────────────────────────────────────
VLESS_PLANS = {
    "vless_basic": {
        "name": "🥉 Basic",
        "devices": 1,
        "data_gb": 0,  # unlimited
        "expiry_days": 30,
        "description": "1 device • Unlimited data • 1 month",
    },
    "vless_silver": {
        "name": "🥈 Silver",
        "devices": 2,
        "data_gb": 0,
        "expiry_days": 30,
        "description": "2 devices • Unlimited data • 1 month",
    },
    "vless_golden": {
        "name": "🥇 Golden",
        "devices": 3,
        "data_gb": 0,
        "expiry_days": 30,
        "description": "3 devices • Unlimited data • 1 month",
    },
    "vless_trial": {
        "name": "🆓 Trial",
        "devices": 1,
        "data_gb": 0.5,  # 500MB
        "expiry_days": 1,
        "description": "1 device • 500 MB • 1 day",
    },
}

OUTLINE_PLANS = {
    "outline_basic": {
        "name": "🥉 Basic",
        "data_gb": 0,
        "expiry_days": 30,
        "keys": 1,
        "description": "Unlimited data • 1 month",
    },
    "outline_silver": {
        "name": "🥈 Silver",
        "data_gb": 0,
        "expiry_days": 30,
        "keys": 2,
        "description": "Unlimited data • 1 month • 2 Keys",
    },
    "outline_golden": {
        "name": "🥇 Golden",
        "data_gb": 0,
        "expiry_days": 30,
        "keys": 3,
        "description": "Unlimited data • 1 month • 3 Keys",
    },
    "outline_trial": {
        "name": "🆓 Trial",
        "data_gb": 0.5,  # 500MB
        "expiry_days": 1,
        "keys": 1,
        "description": "500 MB • 1 day",
    },
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def sanitize_username(name: str) -> str:
    """Sanitize username: only allow a-z, 0-9, underscore. 3-32 chars."""
    sanitized = re.sub(r"[^a-z0-9_]", "", name.lower())
    if len(sanitized) < 3:
        sanitized = sanitized + "_" + str(int(time.time()) % 10000)
    return sanitized[:32]


def build_admin_keyboard():
    """Build the admin main menu inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🔑 VLESS Key", callback_data="server_vless"),
            InlineKeyboardButton("🔑 Outline Key", callback_data="server_outline"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_user_keyboard():
    """Build the non-admin reply keyboard with support button."""
    keyboard = [
        [KeyboardButton("📞 Get Support")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def build_vless_plans_keyboard():
    """Build VLESS plan selection keyboard."""
    keyboard = [
        [InlineKeyboardButton(f"{p['name']} — {p['description']}", callback_data=key)]
        for key, p in VLESS_PLANS.items()
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def build_outline_plans_keyboard():
    """Build Outline plan selection keyboard."""
    keyboard = [
        [InlineKeyboardButton(f"{p['name']} — {p['description']}", callback_data=key)]
        for key, p in OUTLINE_PLANS.items()
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    user_id = user.id

    if is_admin(user_id):
        text = (
            f"👋 Welcome, **{user.first_name}**!\n\n"
            "You are an **Admin**. Choose a server to create a VPN key:\n"
        )
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=build_admin_keyboard(),
        )
    else:
        text = (
            f"👋 Hello, **{user.first_name}**!\n\n"
            "If you need a VPN key or have any questions, "
            "please contact @mr_zembi."
        )
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=build_user_keyboard(),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    user_id = update.effective_user.id

    if is_admin(user_id):
        text = (
            "🛠 **Admin Commands**\n\n"
            "/start — Show the main menu\n"
            "/help — Show this help message\n"
            "/create\\_vless `<client_name>` `<plan>` — Quick VLESS key\n"
            "/create\\_outline `<client_name>` `<plan>` — Quick Outline key\n\n"
            "**Available plans:** basic, silver, golden, trial\n\n"
            "Or use the inline buttons from /start to create keys interactively."
        )
    else:
        text = (
            "ℹ️ **Help**\n\n"
            "/start — Show the main menu\n"
            "/help — Show this help message\n\n"
            "Use the **📞 Get Support** button to reach our team."
        )

    await update.message.reply_text(text, parse_mode="Markdown")


async def support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the 'Get Support' button press."""
    text = (
        "📞 **Contact Support**\n\n"
        f"Please reach out to our support team:\n"
        f"👉 @{SUPPORT_USERNAME}\n\n"
        "We'll get back to you as soon as possible!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.edit_message_text("⛔️ You don't have permission to do this.")
        return

    data = query.data

    # ── Server selection ──
    if data == "server_vless":
        text = (
            "🔑 **VLESS Server**\n\n"
            "Select a plan to create a VLESS key:"
        )
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=build_vless_plans_keyboard(),
        )

    elif data == "server_outline":
        text = (
            "🔑 **Outline Server**\n\n"
            "Select a plan to create an Outline key:"
        )
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=build_outline_plans_keyboard(),
        )

    elif data == "back_main":
        text = "Choose a server to create a VPN key:"
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=build_admin_keyboard(),
        )

    # ── VLESS plan selection ──
    elif data.startswith("vless_"):
        plan = VLESS_PLANS.get(data)
        if not plan:
            await query.edit_message_text("❌ Invalid plan selected.")
            return

        # Store selected plan and ask for client name
        context.user_data["pending_action"] = "vless_create"
        context.user_data["pending_plan"] = data
        context.user_data["pending_plan_info"] = plan

        text = (
            f"📝 **VLESS — {plan['name']}**\n"
            f"📋 {plan['description']}\n\n"
            "Please enter a **client name** (e.g., `john_doe`):\n"
            "_Only letters, numbers, and underscores allowed._"
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    # ── Outline plan selection ──
    elif data.startswith("outline_"):
        plan = OUTLINE_PLANS.get(data)
        if not plan:
            await query.edit_message_text("❌ Invalid plan selected.")
            return

        context.user_data["pending_action"] = "outline_create"
        context.user_data["pending_plan"] = data
        context.user_data["pending_plan_info"] = plan

        text = (
            f"📝 **Outline — {plan['name']}**\n"
            f"📋 {plan['description']}\n\n"
            "Please enter a **client name** (e.g., `john_doe`):\n"
            "_Only letters, numbers, and underscores allowed._"
        )
        await query.edit_message_text(text, parse_mode="Markdown")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages — process pending actions or support button."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Handle support button for non-admins
    if text == "📞 Get Support":
        await support_message(update, context)
        return

    # Handle pending key creation for admins
    if not is_admin(user_id):
        return

    pending_action = context.user_data.get("pending_action")

    if pending_action == "vless_create":
        await create_vless_key(update, context, text)
    elif pending_action == "outline_create":
        await create_outline_key(update, context, text)


async def create_vless_key(update: Update, context: ContextTypes.DEFAULT_TYPE, client_name: str):
    """Create a VLESS key with the selected plan."""
    plan_info = context.user_data.get("pending_plan_info")
    plan_key = context.user_data.get("pending_plan")
    if not plan_info or not plan_key:
        await update.message.reply_text("❌ No plan selected. Please use /start.")
        return

    # Get the inbound ID for this plan
    inbound_id = VLESS_INBOUND_IDS.get(plan_key)
    if inbound_id is None:
        await update.message.reply_text(f"❌ Invalid plan configuration for {plan_key}.")
        return

    # Clear pending action
    context.user_data.pop("pending_action", None)
    context.user_data.pop("pending_plan", None)
    context.user_data.pop("pending_plan_info", None)

    client_name = sanitize_username(client_name)
    # Add timestamp to make unique
    unique_email = f"{client_name}_{int(time.time()) % 100000}"

    progress_msg = await update.message.reply_text(
        f"⏳ Creating VLESS key for **{client_name}**...\n"
        f"Plan: {plan_info['name']} — {plan_info['description']}",
        parse_mode="Markdown",
    )

    try:
        result = await vless_client.create_client(
            email=unique_email,
            total_gb=plan_info["data_gb"],
            expiry_days=plan_info["expiry_days"],
            limit_ip=plan_info["devices"],
            inbound_id=inbound_id,
        )

        if result.get("success"):
            # Try to get the connection link
            vless_link = await vless_client.get_client_link(result["uuid"], inbound_id=inbound_id)

            data_text = "Unlimited" if plan_info["data_gb"] == 0 else f"{int(plan_info['data_gb'] * 1024)} MB"

            text = (
                f"✅ **VLESS Key Created Successfully!**\n\n"
                f"👤 **Client:** `{client_name}`\n"
                f"📋 **Plan:** {plan_info['name']}\n"
                f"📱 **Devices:** {plan_info['devices']}\n"
                f"📊 **Data:** {data_text}\n"
                f"⏰ **Expiry:** {plan_info['expiry_days']} day(s)\n"
                f"🔑 **UUID:** `{result['uuid']}`\n"
            )

            if vless_link:
                text += f"\n🔗 **Connection Link:**\n`{vless_link}`"
            else:
                text += (
                    f"\n⚠️ Could not auto-generate connection link. "
                    f"Use the UUID above in your VLESS client."
                )

            await progress_msg.edit_text(text, parse_mode="Markdown")
        else:
            await progress_msg.edit_text(
                f"❌ **Failed to create VLESS key.**\n"
                f"Error: {result.get('error', 'Unknown error')}",
                parse_mode="Markdown",
            )
    except Exception as e:
        logger.error(f"Error creating VLESS key: {e}")
        await progress_msg.edit_text(
            f"❌ **Error creating VLESS key:**\n`{str(e)}`",
            parse_mode="Markdown",
        )

    # Show main menu again
    await update.message.reply_text(
        "Choose another action:",
        reply_markup=build_admin_keyboard(),
    )


async def create_outline_key(update: Update, context: ContextTypes.DEFAULT_TYPE, client_name: str):
    """Create an Outline key with the selected plan."""
    plan_info = context.user_data.get("pending_plan_info")
    if not plan_info:
        await update.message.reply_text("❌ No plan selected. Please use /start.")
        return

    # Clear pending action
    context.user_data.pop("pending_action", None)
    context.user_data.pop("pending_plan", None)
    context.user_data.pop("pending_plan_info", None)

    client_name = sanitize_username(client_name)
    key_count = plan_info.get("keys", 1)
    
    progress_msg = await update.message.reply_text(
        f"⏳ Creating {key_count} Outline key(s) for **{client_name}**...\n"
        f"Plan: {plan_info['name']} — {plan_info['description']}",
        parse_mode="Markdown",
    )

    created_users = []
    errors = []

    base_username = f"{client_name}_{int(time.time()) % 100000}"

    for i in range(1, key_count + 1):
        # Append suffix only if more than 1 key, or always to distinguish? 
        # Better to always distinct if multi-key plan.
        current_username = f"{base_username}_{i}" if key_count > 1 else base_username
        
        try:
            result = await marzban_client.create_user(
                username=current_username,
                data_limit_gb=plan_info["data_gb"],
                expiry_days=plan_info["expiry_days"],
            )

            if result.get("success"):
                created_users.append(result)
            else:
                errors.append(f"Key {i}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error creating Outline key {i}: {e}")
            errors.append(f"Key {i}: {str(e)}")

    # ─── Build Success Message ───
    if created_users:
        data_text = "Unlimited" if plan_info["data_gb"] == 0 else f"{int(plan_info['data_gb'] * 1024)} MB"
        
        text = (
            f"✅ **Outline Keys Created Successfully!**\n"
            f"📋 **Plan:** {plan_info['name']}\n"
            f"📊 **Data:** {data_text}\n"
            f"⏰ **Expiry:** {plan_info['expiry_days']} day(s)\n\n"
        )

        for i, user in enumerate(created_users, 1):
            text += f"👤 **User {i}:** `{user['username']}`\n"
            
            # Subscription URL
            sub_url = user.get("subscription_url")
            if sub_url:
                text += f"🔗 **Sub:** `{sub_url}`\n"
            
            # Individual Keys (Links)
            links = user.get("links", [])
            for link in links:
                # Truncate long keys for display if needed, but usually full key is better
                text += f"🔑 `{link}`\n"
            
            text += "────────────────YOUR-VPN-BOT────────────────\n"

        if errors:
            text += "\n⚠️ **Some keys failed:**\n" + "\n".join(errors)

        await progress_msg.edit_text(text, parse_mode="Markdown")

    else:
        # All failed
        await progress_msg.edit_text(
            f"❌ **Failed to create Outline keys.**\n"
            f"Errors:\n" + "\n".join(errors),
            parse_mode="Markdown",
        )

    # Show main menu again
    await update.message.reply_text(
        "Choose another action:",
        reply_markup=build_admin_keyboard(),
    )


# ─── Quick Commands ───────────────────────────────────────────────────────────

async def quick_create_vless(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /create_vless <name> <plan> command."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔️ Admin access required.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /create\\_vless `<client_name>` `<plan>`\n"
            "Plans: basic, silver, golden, trial",
            parse_mode="Markdown",
        )
        return

    client_name = context.args[0]
    plan_key = f"vless_{context.args[1].lower()}"
    plan_info = VLESS_PLANS.get(plan_key)

    if not plan_info:
        await update.message.reply_text(
            "❌ Invalid plan. Available: basic, silver, golden, trial"
        )
        return

    context.user_data["pending_plan"] = plan_key
    context.user_data["pending_plan_info"] = plan_info
    await create_vless_key(update, context, client_name)


async def quick_create_outline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /create_outline <name> <plan> command."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔️ Admin access required.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /create\\_outline `<client_name>` `<plan>`\n"
            "Plans: basic, silver, golden, trial",
            parse_mode="Markdown",
        )
        return

    client_name = context.args[0]
    plan_key = f"outline_{context.args[1].lower()}"
    plan_info = OUTLINE_PLANS.get(plan_key)

    if not plan_info:
        await update.message.reply_text(
            "❌ Invalid plan. Available: basic, silver, golden, trial"
        )
        return

    context.user_data["pending_plan_info"] = plan_info
    await create_outline_key(update, context, client_name)


# ─── Error Handler ────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors gracefully."""
    from telegram.error import Forbidden, NetworkError, TimedOut

    error = context.error

    if isinstance(error, Forbidden):
        logger.warning(f"Bot blocked by user: {error}")
        return
    elif isinstance(error, (NetworkError, TimedOut)):
        logger.warning(f"Network issue: {error}")
        return
    else:
        logger.error(f"Unhandled exception: {error}", exc_info=context.error)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set! Please configure .env file.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("create_vless", quick_create_vless))
    app.add_handler(CommandHandler("create_outline", quick_create_outline))

    # Callback query handler (inline keyboard)
    app.add_handler(CallbackQueryHandler(button_callback))

    # Text message handler (for client name input & support button)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Error handler
    app.add_error_handler(error_handler)

    print("🤖 VPN Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
