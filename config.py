import os
import logging
from dotenv import load_dotenv
from datetime import timezone, timedelta

# ==================================================
# LOGGING SETUP
# ==================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logging.getLogger('discord').setLevel(logging.ERROR)

# ==================================================
# CONFIGURATION
# ==================================================
load_dotenv()

class Config:
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID") or 0)

    ALLOWED_USERS = [
        int(uid.strip())
        for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
        if uid.strip() and uid.strip().isdigit()
    ]

    BASE_URL = os.getenv("BANK_API_URL")
    THAI_TZ = timezone(timedelta(hours=7))

    BANKS = [
        {"code": "006", "name": "KTB (กรุงไทย)"},
        {"code": "014", "name": "SCB (ไทยพาณิชย์)"},
        {"code": "004", "name": "KBANK (กสิกร)"},
        {"code": "034", "name": "BAAC (ธกส.)"},
        {"code": "998", "name": "ThaiPost (ปณ.)"},
        {"code": "709", "name": "CS (Counter)"},
        {"code": "030", "name": "GSB (ออมสิน)"},
    ]

    @classmethod
    def validate(cls):
        if not cls.TOKEN:
            raise ValueError("❌ DISCORD_BOT_TOKEN not found in .env")
        if cls.CHANNEL_ID == 0:
            raise ValueError("❌ DISCORD_CHANNEL_ID not found or invalid in .env")
        if not cls.BASE_URL:
            raise ValueError("❌ BANK_API_URL not found in .env")
        logging.info("✅ Config validated successfully")