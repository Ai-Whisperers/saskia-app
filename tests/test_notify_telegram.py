"""Tests for app/rms/notify.py — Telegram alert channel (C.1).

Covers: config gate, never-raise, truncation, Sentry hook passthrough,
error-level filtering, and in-process damping.
"""

from __future__ import annotations

import json
import urllib.request
from unittest import mock

import app.rms.notify as notify


def _env(**kw):
    return mock.patch.dict("os.environ", kw, clear=False)


def test_unconfigured_send_returns_false(monkeypatch):
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_CHAT_ID", raising=False)
    assert notify.send_telegram("hola") is False
    assert notify.telegram_configured() is False


def test_send_returns_true_on_200(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "42")

    captured = {}

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data.decode())
        assert timeout == notify._TIMEOUT_S
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert notify.send_telegram("alerta") is True
    assert "bot123:abc/sendMessage" in captured["url"]
    assert captured["payload"]["chat_id"] == "42"
    assert captured["payload"]["text"] == "alerta"


def test_send_never_raises_on_network_error(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "42")

    def boom(req, timeout=None):
        raise OSError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert notify.send_telegram("x") is False


def test_long_text_truncated(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "42")
    seen = {}

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen["text"] = json.loads(req.data.decode())["text"]
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    notify.send_telegram("x" * 9999)
    assert len(seen["text"]) == notify._MAX_LEN
    assert seen["text"].endswith("…")


def test_hook_passes_non_error_events_through():
    evt = {"level": "info", "event_id": "e1"}
    assert notify.sentry_before_send(evt, {}) is evt


def test_hook_mirrors_error_and_returns_event(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "42")
    sent = {}

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        sent["text"] = json.loads(req.data.decode())["text"]
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    notify.sentry_before_send._last_sent = {}
    evt = {
        "level": "error",
        "event_id": "abc123",
        "release": "test@1",
        "exception": {
            "values": [{"type": "ValueError", "value": "algo reventó"}]
        },
        "request": {"url": "https://x.test/ventas"},
        "fingerprint": ["ValueError"],
    }
    out = notify.sentry_before_send(evt, {})
    assert out is evt  # pass-through untouched
    assert "ValueError: algo reventó" in sent["text"]
    assert "https://x.test/ventas" in sent["text"]


def test_hook_damps_repeated_same_fingerprint(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "42")
    calls = {"n": 0}

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    notify.sentry_before_send._last_sent = {}
    evt = {
        "level": "error",
        "event_id": "1",
        "exception": {"values": [{"type": "E", "value": "v"}]},
        "fingerprint": ["same"],
    }
    notify.sentry_before_send(evt, {})
    notify.sentry_before_send(evt, {})
    assert calls["n"] == 1  # second mirror damped
