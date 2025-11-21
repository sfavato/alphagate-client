import logging
import requests
from app.config import Settings

logger = logging.getLogger(__name__)

def send_notification(settings: Settings, message: str, level: str = "info"):
    """
    Envoie une notification sur Discord (et/ou Telegram) de manière sécurisée.
    """
    prefix = "✅ " if level == "success" else "❌ " if level == "error" else "ℹ️ "
    formatted_msg = f"**[AlphaGate]** {prefix}{message}"

    # 1. Discord Webhook (Le plus simple et rapide)
    if settings.DISCORD_WEBHOOK_URL:
        try:
            payload = {"content": formatted_msg}
            requests.post(settings.DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to send Discord notification: {e}")

    # 2. Telegram (Si configuré)
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": formatted_msg}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to send Telegram notification: {e}")
