import hashlib
import hmac
from app.config import Settings


def verify_hmac_signature(payload: bytes, signature: str, settings: Settings) -> bool:
    """
    Verifies the HMAC signature of the payload.
    """
    if not signature:
        return False

    mac = hmac.new(
        settings.ALPHAGATE_HMAC_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256,
    )
    return hmac.compare_digest(mac.hexdigest(), signature)
