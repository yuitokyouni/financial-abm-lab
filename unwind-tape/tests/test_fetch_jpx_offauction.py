"""unwind-tape / task A — 鮮度アラーム機能のテスト (2026-07-08 review 指摘対応)。

掲載保持は「過去2週間」しかないため、cron/launchd の発火漏れや構造変化を
誰も見ていないと欠測期間が生まれてから気付くことになる。
_check_freshness が正しく古い/欠損 manifest を検知することを検証する。
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from fetch_jpx_offauction import (  # noqa: E402
    _check_freshness, _latest_ok_date_key, _weekdays_between,
)
from datetime import date  # noqa: E402


STORAGE = {"raw_root": "data/raw/jpx_offauction", "manifest_filename": "manifest.jsonl"}


def _write_manifest(root: Path, page: str, entries: list[dict]) -> Path:
    p = root / STORAGE["raw_root"] / page / STORAGE["manifest_filename"]
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return p


def _quiet_logger() -> logging.Logger:
    log = logging.getLogger("test_fetch_jpx_offauction")
    log.setLevel(logging.CRITICAL + 1)  # suppress output during tests
    return log


def test_weekdays_between_same_week():
    # Mon 2026-07-06 -> Wed 2026-07-08 = 2 business days
    assert _weekdays_between(date(2026, 7, 6), date(2026, 7, 8)) == 2


def test_weekdays_between_across_weekend():
    # Fri 2026-07-03 -> Mon 2026-07-06 = 1 business day (weekend doesn't count)
    assert _weekdays_between(date(2026, 7, 3), date(2026, 7, 6)) == 1


def test_latest_ok_date_key_ignores_non_ok_status(tmp_path):
    p = tmp_path / "manifest.jsonl"
    p.write_text(
        json.dumps({"status": "ok", "date_key": "2026-07-01"}) + "\n" +
        json.dumps({"status": "fetch_error", "date_key": "2026-07-06"}) + "\n" +
        json.dumps({"status": "ok", "date_key": "2026-07-03"}) + "\n",
        encoding="utf-8",
    )
    assert _latest_ok_date_key(p) == "2026-07-03"


def test_latest_ok_date_key_missing_file(tmp_path):
    assert _latest_ok_date_key(tmp_path / "does_not_exist.jsonl") is None


def test_check_freshness_flags_stale_page(tmp_path):
    _write_manifest(tmp_path, "pageA", [{"status": "ok", "date_key": "2026-06-19"}])
    now = datetime(2026, 7, 8, 21, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    stale = _check_freshness(tmp_path, STORAGE, ["pageA"], now, 5, _quiet_logger())
    assert stale is True


def test_check_freshness_ok_for_recent_page(tmp_path):
    _write_manifest(tmp_path, "pageA", [{"status": "ok", "date_key": "2026-07-06"}])
    now = datetime(2026, 7, 8, 21, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    stale = _check_freshness(tmp_path, STORAGE, ["pageA"], now, 5, _quiet_logger())
    assert stale is False


def test_check_freshness_flags_never_captured_page(tmp_path):
    (tmp_path / STORAGE["raw_root"] / "pageA").mkdir(parents=True)
    now = datetime(2026, 7, 8, 21, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    stale = _check_freshness(tmp_path, STORAGE, ["pageA"], now, 5, _quiet_logger())
    assert stale is True


def test_check_freshness_multiple_pages_any_stale_triggers_true(tmp_path):
    _write_manifest(tmp_path, "fresh", [{"status": "ok", "date_key": "2026-07-07"}])
    _write_manifest(tmp_path, "stale", [{"status": "ok", "date_key": "2026-06-01"}])
    now = datetime(2026, 7, 8, 21, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    stale = _check_freshness(tmp_path, STORAGE, ["fresh", "stale"], now, 5, _quiet_logger())
    assert stale is True
