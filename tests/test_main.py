import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings, Settings
from app import trader
import hmac
import hashlib
import json
import time
from unittest.mock import patch, ANY, MagicMock

def get_test_settings():
    return Settings(
        BITGET_API_KEY="test",
        BITGET_SECRET_KEY="test",
        BITGET_PASSPHRASE="test",
        ALPHAGATE_HMAC_SECRET="test-secret",
        SYMBOL_BLACKLIST=["DOGE/USDT"],
        SYMBOL_WHITELIST=[], # Empty implies "allow all except blacklist"
        DISCORD_WEBHOOK_URL="http://mock-discord",
    )

def get_test_settings_whitelist():
    return Settings(
        BITGET_API_KEY="test",
        BITGET_SECRET_KEY="test",
        BITGET_PASSPHRASE="test",
        ALPHAGATE_HMAC_SECRET="test-secret",
        SYMBOL_WHITELIST=["BTC/USDT"],
    )

app.dependency_overrides[get_settings] = get_test_settings

client = TestClient(app)

def generate_signature(payload: bytes, settings=None):
    s = settings or get_test_settings()
    return hmac.new(
        s.ALPHAGATE_HMAC_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

# --- Existing Webhook Tests ---

def test_webhook_invalid_signature():
    response = client.post("/webhook", content="test", headers={"X-Hub-Signature": "invalid"})
    assert response.status_code == 200
    assert response.text == ""

def test_webhook_dust_signal():
    payload = {"dust": True}
    payload_bytes = json.dumps(payload).encode()
    signature = generate_signature(payload_bytes)
    response = client.post(
        "/webhook",
        content=payload_bytes,
        headers={"X-Hub-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_webhook_expired_signal():
    payload = {"timestamp": time.time() - 100}
    payload_bytes = json.dumps(payload).encode()
    signature = generate_signature(payload_bytes)
    response = client.post(
        "/webhook",
        content=payload_bytes,
        headers={"X-Hub-Signature": signature},
    )
    assert response.status_code == 200
    assert response.text == ""

@patch("app.trader.place_order")
def test_webhook_valid_signal(mock_place_order):
    # Ensure trading is enabled
    client.post("/resume", headers={"X-Admin-Secret": "test-secret"})

    payload = {
        "symbol": "BTC/USDT",
        "side": "buy",
        "entry": 1,
        "timestamp": time.time(),
    }
    payload_bytes = json.dumps(payload).encode()
    signature = generate_signature(payload_bytes)
    response = client.post(
        "/webhook",
        content=payload_bytes,
        headers={"X-Hub-Signature": signature},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_place_order.assert_called_once_with("BTC/USDT", "buy", ANY, tp=None, sl=None)

# --- New Feature Tests ---

@patch("app.trader.ccxt.bitget")
def test_get_status(mock_bitget):
    mock_exchange = MagicMock()
    mock_bitget.return_value = mock_exchange

    # Mock balance
    mock_exchange.fetch_balance.return_value = {
        'USDT': {'total': 1000, 'free': 900, 'used': 100}
    }
    # Mock positions
    mock_exchange.fetch_positions.return_value = [
        {
            'symbol': 'BTC/USDT', 'side': 'long', 'contracts': 1,
            'entryPrice': 50000, 'unrealizedPnl': 50, 'leverage': 10
        }
    ]

    response = client.get("/status", headers={"X-Admin-Secret": "test-secret"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["balance"]["total"] == 1000
    assert data["open_positions_count"] == 1
    assert data["open_positions"][0]["symbol"] == "BTC/USDT"

@patch("app.trader.ccxt.bitget")
@patch("app.notifier.requests.post") # Mock notification
def test_kill_switch(mock_post, mock_bitget):
    mock_exchange = MagicMock()
    mock_bitget.return_value = mock_exchange

    # Mock positions to close
    mock_exchange.fetch_positions.return_value = [
        {
            'symbol': 'ETH/USDT', 'side': 'long', 'contracts': 2,
            'entryPrice': 3000, 'unrealizedPnl': 10, 'leverage': 5
        }
    ]

    # 1. Call Kill Switch
    response = client.post("/kill", headers={"X-Admin-Secret": "test-secret"})
    assert response.status_code == 200
    assert response.json()["action"] == "KILL_SWITCH_EXECUTED"
    assert response.json()["trading_status"] == "DISABLED"

    # Verify notification sent
    mock_post.assert_called()

    # Verify cancel_all_orders was called
    mock_exchange.cancel_all_orders.assert_called_once()

    # Verify market close order
    # Side should be 'sell' because position is 'long'
    mock_exchange.create_market_order.assert_called_once_with(
        "ETH/USDT", "sell", 2.0, params={'reduceOnly': True}
    )

    # 2. Verify Webhook is blocked
    payload = {"symbol": "BTC/USDT", "side": "buy", "entry": 1, "timestamp": time.time()}
    payload_bytes = json.dumps(payload).encode()
    signature = generate_signature(payload_bytes)

    with patch("app.trader.place_order") as mock_place:
        response = client.post(
            "/webhook",
            content=payload_bytes,
            headers={"X-Hub-Signature": signature},
        )
        assert response.json()["status"] == "ignored"
        mock_place.assert_not_called()

    # 3. Resume Trading
    response = client.post("/resume", headers={"X-Admin-Secret": "test-secret"})
    assert response.json()["status"] == "Trading Resumed"

    # 4. Verify Webhook works again
    with patch("app.trader.place_order") as mock_place:
        response = client.post(
            "/webhook",
            content=payload_bytes,
            headers={"X-Hub-Signature": signature},
        )
        assert response.json()["status"] == "ok"
        mock_place.assert_called_once()

def test_auth_failure():
    response = client.get("/status")
    assert response.status_code == 401

    response = client.post("/kill")
    assert response.status_code == 401

# --- Filtering Tests ---

@patch("app.notifier.requests.post")
def test_blacklist_filtering(mock_post):
    # Settings defined in get_test_settings: Blacklist includes "DOGE/USDT"

    # We need to call place_order directly to test the return value or side effects,
    # as the webhook endpoint catches exceptions and returns status ok usually.
    # But here place_order returns None for filtered symbols.

    settings = get_test_settings()

    # Test Blacklisted Symbol
    result = trader.place_order("DOGE/USDT", "buy", settings)
    assert result is None
    # Verify notification
    mock_post.assert_called()
    assert "IGNORÉ" in mock_post.call_args[1]['json']['content']

@patch("app.notifier.requests.post")
def test_whitelist_filtering(mock_post):
    settings = get_test_settings_whitelist() # Whitelist: ["BTC/USDT"]

    # Test Allowed Symbol
    # We need to mock exchange interactions to prevent real calls
    with patch("app.trader.ccxt.bitget") as mock_bitget:
        mock_exchange = MagicMock()
        mock_bitget.return_value = mock_exchange
        mock_exchange.fetch_ticker.return_value = {'last': 50000}
        mock_exchange.fetch_balance.return_value = {'USDT': {'free': 1000}}
        mock_exchange.create_market_order.return_value = {'id': '123'}

        result = trader.place_order("BTC/USDT", "buy", settings)
        assert result is not None
        assert result['id'] == '123'

    # Test Disallowed Symbol
    result = trader.place_order("ETH/USDT", "buy", settings)
    assert result is None
