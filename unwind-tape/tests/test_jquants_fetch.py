"""unwind-tape / jquants_fetch クライアントの回帰テスト。

- 永続的な 4xx(429 を除く)はリトライしない。存在しない銘柄コードで 400 が返ったとき
  4回バックオフして無駄に待つ(体感 30 秒の stall)ことを防ぐ。5xx/429/接続断は従来どおりリトライ。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import jquants_fetch as jf  # noqa: E402


class _Resp:
    def __init__(self, status: int):
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            e = requests.HTTPError(str(self.status_code))
            e.response = self
            raise e

    def json(self):
        return {"data": []}


class _Session:
    def __init__(self, status: int):
        self.status = status
        self.calls = 0
        self.headers: dict = {}

    def get(self, *a, **k):
        self.calls += 1
        return _Resp(self.status)


def _client(status: int, monkeypatch) -> jf.JQuantsClient:
    monkeypatch.setattr(jf.time, "sleep", lambda *a, **k: None)   # テストを速く
    c = jf.JQuantsClient()
    c.credential = "k"
    c.auth_mode = "v2_api_key"
    c.session = _Session(status)
    return c


def test_get_does_not_retry_400(monkeypatch):
    c = _client(400, monkeypatch)
    with pytest.raises(requests.HTTPError):
        c._get("/equities/bars/daily", {"code": "132"})
    assert c.session.calls == 1        # 400 は永続 → 1回で諦める


def test_get_does_not_retry_404(monkeypatch):
    c = _client(404, monkeypatch)
    with pytest.raises(requests.HTTPError):
        c._get("/equities/bars/daily", {"code": "9999"})
    assert c.session.calls == 1


def test_get_retries_500(monkeypatch):
    c = _client(500, monkeypatch)
    with pytest.raises(requests.HTTPError):
        c._get("/equities/bars/daily", {"code": "7203"})
    # 5xx はリトライ対象: 初回 + DEFAULT_RETRIES 回
    assert c.session.calls == jf.DEFAULT_RETRIES + 1
