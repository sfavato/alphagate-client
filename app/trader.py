import ccxt
from app.config import Settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def place_order(
    symbol: str,
    side: str,
    amount: float,
    settings: Settings,
    tp: Optional[float] = None,
    sl: Optional[float] = None,
):
    """
    Places a market order on Bitget with optional take profit and stop loss.
    """
    try:
        exchange = ccxt.bitget({
            'apiKey': settings.BITGET_API_KEY,
            'secret': settings.BITGET_SECRET_KEY,
            'password': settings.BITGET_PASSPHRASE,
        })
        # Set sandbox mode for testing if needed
        # exchange.set_sandbox_mode(True)
        params = {}
        if tp:
            params["takeProfitPrice"] = tp
        if sl:
            params["stopLossPrice"] = sl

        order = exchange.create_market_order(symbol, side, amount, params=params)
        logger.info(f"Order executed successfully for {symbol}")
        return order
    except ccxt.NetworkError:
        logger.error("Bitget API Network Error")
        raise
    except ccxt.ExchangeError:
        logger.error("Bitget API Exchange Error")
        raise
    except Exception:
        logger.error("An unexpected error occurred while placing the order")
        raise
