import ccxt
from app.config import Settings
import logging
from typing import Optional, Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app import notifier

logger = logging.getLogger(__name__)

def _get_exchange(settings: Settings):
    """Helper pour initialiser l'échange de manière cohérente."""
    return ccxt.bitget({
        'apiKey': settings.BITGET_API_KEY,
        'secret': settings.BITGET_SECRET_KEY,
        'password': settings.BITGET_PASSPHRASE,
        'options': {'defaultType': 'swap'}
    })

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout))
)
def place_order(
    symbol: str,
    side: str,
    settings: Settings,
    tp: Optional[float] = None,
    sl: Optional[float] = None,
):
    """
    Configure le levier, calcule la taille de position dynamique et place l'ordre.
    """
    # --- Mission 3 : Filtrage Stratégique ---
    # 1. Vérification Blacklist
    if symbol in settings.SYMBOL_BLACKLIST:
        msg = f"Signal IGNORÉ pour {symbol} (Blacklisté par l'utilisateur)"
        logger.warning(msg)
        notifier.send_notification(settings, msg, level="info")
        return None

    # 2. Vérification Whitelist (si active)
    if settings.SYMBOL_WHITELIST and symbol not in settings.SYMBOL_WHITELIST:
        msg = f"Signal IGNORÉ pour {symbol} (Non présent dans la Whitelist)"
        logger.warning(msg)
        notifier.send_notification(settings, msg, level="info")
        return None

    if settings.DRY_RUN:
        logger.info(
            f"[DRY RUN] Order Intercepted -> Symbol: {symbol}, Side: {side}, Amount: Calculated Dynamically, TP: {tp}, SL: {sl}"
        )
        return {"id": "dry-run-id", "status": "closed", "info": "Simulated Order"}

    try:
        exchange = _get_exchange(settings)

        # 1. Configuration du Levier
        try:
            exchange.set_leverage(settings.DEFAULT_LEVERAGE, symbol)
            logger.info(f"Leverage set to {settings.DEFAULT_LEVERAGE}x for {symbol}")
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}. Continuing with account default.")

        # 2. Récupération du Prix Actuel
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        if not current_price:
            raise ValueError(f"Could not fetch price for {symbol}")

        # 3. Calcul de la Taille de Position (Money Management)
        # On récupère le solde USDT disponible (Free Balance)
        balance = exchange.fetch_balance()
        usdt_free = balance['USDT']['free']

        # Marge à utiliser = Solde Dispo * Pourcentage (ex: 1000$ * 0.05 = 50$)
        margin_to_use = usdt_free * settings.TRADE_ALLOCATION_PERCENT

        # Taille de la position (Notional) = Marge * Levier (ex: 50$ * 10 = 500$)
        position_size_usd = margin_to_use * settings.DEFAULT_LEVERAGE

        # Quantité en Crypto = Taille Position USD / Prix Actuel
        amount = position_size_usd / current_price

        logger.info(f"Calculated size: {amount:.4f} {symbol} (Margin: ${margin_to_use:.2f}, Lev: {settings.DEFAULT_LEVERAGE}x)")

        # 4. Préparation des paramètres TP/SL (Bitget Specific)
        params = {}
        if tp:
            params["takeProfitPrice"] = tp
        if sl:
            params["stopLossPrice"] = sl

        # 5. Exécution de l'Ordre
        order = exchange.create_market_order(symbol, side, amount, params=params)

        # --- Mission 1 : Notification de Succès ---
        success_msg = (
            f"Trade EXÉCUTÉ : {side.upper()} {symbol}\n"
            f"Levier: {settings.DEFAULT_LEVERAGE}x | Taille: {amount:.4f} ({margin_to_use:.2f}$ Marge)"
        )
        logger.info(f"Order executed successfully: {order['id']}")
        notifier.send_notification(settings, success_msg, level="success")

        return order

    except ccxt.InsufficientFunds:
        msg = "Insufficient Funds to execute trade with current allocation settings."
        logger.error(msg)
        notifier.send_notification(settings, f"ÉCHEC CRITIQUE sur {symbol} : {msg}", level="error")
        raise
    except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as e:
        logger.error(f"Bitget API Network Error: {e}")
        raise
    except ccxt.ExchangeError as e:
        msg = f"Bitget API Exchange Error: {e}"
        logger.error(msg)
        notifier.send_notification(settings, f"ÉCHEC CRITIQUE sur {symbol} : {msg}", level="error")
        raise
    except Exception as e:
        msg = f"Unexpected error: {e}"
        logger.error(msg)
        notifier.send_notification(settings, f"ÉCHEC CRITIQUE sur {symbol} : {msg}", level="error")
        raise

def get_status(settings: Settings) -> Dict:
    """Récupère l'état de santé du compte (Solde, Positions ouvertes)."""
    try:
        exchange = _get_exchange(settings)

        # 1. Solde
        balance = exchange.fetch_balance()
        usdt = balance['USDT']

        # 2. Positions
        positions = exchange.fetch_positions()
        active_positions = [
            {
                "symbol": p['symbol'],
                "side": p['side'],
                "size": p['contracts'],
                "entry_price": p['entryPrice'],
                "unrealized_pnl": p['unrealizedPnl'],
                "leverage": p['leverage']
            }
            for p in positions if float(p['contracts']) > 0
        ]

        return {
            "status": "online",
            "balance": {
                "total": usdt['total'],
                "free": usdt['free'],
                "used": usdt['used']
            },
            "open_positions_count": len(active_positions),
            "open_positions": active_positions
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {"status": "error", "message": str(e)}

def emergency_kill_switch(settings: Settings) -> Dict:
    """🚨 KILL SWITCH : Annule tous les ordres et ferme toutes les positions."""
    log = []
    try:
        exchange = _get_exchange(settings)

        # 1. Annuler les ordres en attente (Limit, Stop)
        try:
            exchange.cancel_all_orders()
            log.append("✅ All pending orders cancelled.")
        except Exception as e:
            log.append(f"❌ Failed to cancel orders: {e}")

        # 2. Fermer les positions ouvertes (Market Close)
        positions = exchange.fetch_positions()
        active_pos = [p for p in positions if float(p['contracts']) > 0]

        if not active_pos:
            log.append("ℹ️ No open positions to close.")

        for p in active_pos:
            symbol = p['symbol']
            side = 'sell' if p['side'] == 'long' else 'buy' # On inverse pour fermer
            qty = float(p['contracts'])

            try:
                # reduceOnly=True garantit qu'on ne fait que fermer, pas ouvrir une position inverse
                exchange.create_market_order(symbol, side, qty, params={'reduceOnly': True})
                log.append(f"✅ Closed {symbol} ({p['side']})")
            except Exception as e:
                log.append(f"❌ Failed to close {symbol}: {e}")

        msg = f"🚨 KILL SWITCH ACTIVÉ : {', '.join(log)}"
        notifier.send_notification(settings, msg, level="error") # Using error level for visibility

        return {"action": "KILL_SWITCH_EXECUTED", "log": log}

    except Exception as e:
        logger.critical(f"Kill switch critical failure: {e}")
        notifier.send_notification(settings, f"🚨 KILL SWITCH FAILED: {e}", level="error")
        raise

def generate_report(settings: Settings, days: int = 7) -> Dict:
    """Génère un rapport PnL simple sur les X derniers jours."""
    try:
        exchange = _get_exchange(settings)
        # Note: fetch_my_trades peut être limité dans le temps par l'exchange
        since = exchange.milliseconds() - (days * 24 * 60 * 60 * 1000)
        trades = exchange.fetch_my_trades(since=since)

        total_pnl = 0
        trade_count = len(trades)

        # Calcul simplifié
        return {
            "period_days": days,
            "total_trades_executed": trade_count,
            "note": "Detailed PnL calculation requires ledger access. Check Bitget dashboard for exact realized PnL."
        }
    except Exception as e:
        return {"error": str(e)}
