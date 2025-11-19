import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings, Settings
import hmac
import hashlib
import json
import time
from unittest.mock import patch, ANY


def get_test_settings():
    return Settings(
        BITGET_API_KEY="test",
        BITGET_SECRET_KEY="test",
        BITGET_PASSPHRASE="test",
        ALPHAGATE_HMAC_SECRET="test-secret",
    )


app.dependency_overrides[get_settings] = get_test_settings

client = TestClient(app)


def generate_signature(payload: bytes):
    return hmac.new(
        get_test_settings().ALPHAGATE_HMAC_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()


def test_webhook_invalid_signature():
    response = client.post("/webhook", content="test", headers={"X-Hub-Signature": "invalid"})
    assert response.status_code == 200
    assert response.text == ""  # Should silently reject


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


@patch("app.main.place_order")
def test_webhook_valid_signal(mock_place_order):
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
    mock_place_order.assert_called_once_with("BTC/USDT", "buy", 1, ANY, None, None)


@patch("app.main.place_order")
def test_webhook_valid_signal_with_tp_sl(mock_place_order):
    payload = {
        "symbol": "BTC/USDT",
        "side": "buy",
        "entry": 1,
        "tp": 70000,
        "sl": 60000,
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
    mock_place_order.assert_called_once_with(
        "BTC/USDT", "buy", 1, ANY, 70000, 60000
    )
