import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin user IDs (comma-separated in .env)
ADMIN_IDS = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_IDS", "").split(",")
    if uid.strip().isdigit()
]

# 3x-ui (VLESS) Panel
VLESS_PANEL_URL = os.getenv("VLESS_PANEL_URL", "http://68.183.184.161:1200/leeblyaml")
VLESS_USERNAME = os.getenv("VLESS_USERNAME", "admin")
VLESS_PASSWORD = os.getenv("VLESS_PASSWORD", "admin")
VLESS_INBOUND_ID = int(os.getenv("VLESS_INBOUND_ID", "1"))

# Marzban (Outline) Panel
MARZBAN_PANEL_URL = os.getenv("MARZBAN_PANEL_URL", "http://165.245.183.72:1200")
MARZBAN_USERNAME = os.getenv("MARZBAN_USERNAME", "admin")
MARZBAN_PASSWORD = os.getenv("MARZBAN_PASSWORD", "admin")

# Support
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "your_support_username")


def is_admin(user_id: int) -> bool:
    """Check if a user ID is in the admin list."""
    return user_id in ADMIN_IDS
