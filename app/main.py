from fastapi import FastAPI, Request, HTTPException, Header, Depends, Response
from fastapi.concurrency import run_in_threadpool
from app.security import verify_hmac_signature
from app import trader
from app.config import get_settings, Settings
import logging
import time
import json
from typing import Optional

app = FastAPI(title="AlphaGate Client")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variable to pause trading after a Kill Switch
TRADING_ENABLED = True

def verify_admin_access(
    x_admin_secret: Optional[str] = Header(None, alias="X-Admin-Secret"),
    settings: Settings = Depends(get_settings)
):
    """
    Simple authentication for admin endpoints using the HMAC secret as a token.
    """
    if not x_admin_secret or x_admin_secret != settings.ALPHAGATE_HMAC_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/")
def read_root():
    return {"status": "AlphaGate Client is Running", "trading_enabled": TRADING_ENABLED}

@app.post("/webhook")
async def webhook(
    request: Request,
    x_hub_signature: Optional[str] = Header(None),
    settings: Settings = Depends(get_settings),
):
    """
    Receives a trading signal, verifies its authenticity, and executes the trade.
    """
    if not TRADING_ENABLED:
        logger.warning("Signal ignored: Trading is DISABLED (Kill Switch active)")
        return {"status": "ignored", "reason": "Kill Switch Active"}

    # Step 1: Verification
    payload = await request.body()
    if not verify_hmac_signature(payload, x_hub_signature, settings):
        # Silently reject invalid signatures
        return Response(status_code=200)

    # Step 2: Filtrage
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
         # Should ideally be 400, but we might want to be silent to scanners
         return Response(status_code=200)

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
        tp = data.get("tp")
        sl = data.get("sl")
        logger.info(f"Signal received for {symbol} (Dry Run: {settings.DRY_RUN})")

        # Offload blocking trader call to threadpool
        await run_in_threadpool(trader.place_order, symbol, side, settings, tp=tp, sl=sl)

        return {"status": "ok"}
    except KeyError:
        logger.error("Invalid payload received")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception:
        logger.error("Error executing order")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/status", dependencies=[Depends(verify_admin_access)])
async def get_system_status(settings: Settings = Depends(get_settings)):
    """Retourne le solde et les positions."""
    return await run_in_threadpool(trader.get_status, settings)

@app.get("/report", dependencies=[Depends(verify_admin_access)])
async def get_performance_report(days: int = 7, settings: Settings = Depends(get_settings)):
    """Génère un rapport d'activité basique."""
    return await run_in_threadpool(trader.generate_report, settings, days)

@app.post("/kill", dependencies=[Depends(verify_admin_access)])
async def execute_kill_switch(
    settings: Settings = Depends(get_settings)
):
    """🚨 ARRÊT D'URGENCE : Stop le trading et ferme tout."""
    global TRADING_ENABLED

    TRADING_ENABLED = False # Bloque les futurs signaux

    result = await run_in_threadpool(trader.emergency_kill_switch, settings)
    result["trading_status"] = "DISABLED"

    logger.critical("KILL SWITCH ACTIVATED BY USER")
    return result

@app.post("/resume", dependencies=[Depends(verify_admin_access)])
def resume_trading(settings: Settings = Depends(get_settings)):
    """Réactive le trading après un Kill Switch."""
    global TRADING_ENABLED
    TRADING_ENABLED = True
    logger.info("Trading manually RESUMED")
    return {"status": "Trading Resumed"}
