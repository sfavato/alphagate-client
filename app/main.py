from fastapi import FastAPI, Request, HTTPException, Header, Depends, Response
from app.security import verify_hmac_signature
from app.trader import place_order
from app.config import get_settings, Settings
import logging
import time
import json
from typing import Optional

app = FastAPI()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.post("/webhook")
async def webhook(
    request: Request,
    x_hub_signature: Optional[str] = Header(None),
    settings: Settings = Depends(get_settings),
):
    """
    Receives a trading signal, verifies its authenticity, and executes the trade.
    """
    # Step 1: Verification
    payload = await request.body()
    if not verify_hmac_signature(payload, x_hub_signature, settings):
        # Silently reject invalid signatures
        return Response(status_code=200)

    # Step 2: Filtrage
    data = json.loads(payload)
    if data.get("dust"):
        logger.info("Heartbeat received")
        return {"status": "ok"}

    timestamp = data.get("timestamp")
    if timestamp and (time.time() - timestamp > 60):  # 1 minute expiration
        logger.warning("Expired signal received")
        return Response(status_code=200)

    # Step 3: Trading
    try:
        symbol = data["symbol"]
        side = data["side"]
        amount = data["entry"]
        tp = data.get("tp")
        sl = data.get("sl")
        logger.info(f"Signal received for {symbol}")
        place_order(symbol, side, amount, settings, tp, sl)
        return {"status": "ok"}
    except KeyError:
        logger.error("Invalid payload received")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception:
        logger.error("Error executing order")
        raise HTTPException(status_code=500, detail="Internal server error")
