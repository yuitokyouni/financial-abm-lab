"""unwind-tape / edinet_fetch の単体テスト(Task D step 1、ネットワーク不要の純関数のみ)。

metadata レベルの前フィルタ・構造検証・売出タグ・secCode 正規化・営業日列挙を検証する。
本文分類(政策保有 判定)と実 API 疎通は対象外(step 2 / Mac 実行)。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import edinet_fetch as ed  # noqa: E402

KW = ["売出"]
IPO_KW = ["新規公開", "新規上場"]
TARGET = ["030", "040", "100"]
ORDS = ["010"]


def _r(**kw):
    base = {"docID": "S1", "docTypeCode": "030", "ordinanceCode": "010",
            "docDescription": "有価証券届出書", "withdrawalStatus": "0"}
    base.update(kw)
    return base


# --- has_uridashi ---------------------------------------------------------

def test_has_uridashi():
    assert ed.has_uridashi("有価証券届出書(有価証券の募集又は売出し)", KW) is True
    assert ed.has_uridashi("株式の売出しに関するお知らせ", KW) is True
    assert ed.has_uridashi("有価証券届出書(有価証券の募集)", KW) is False   # 募集のみ
    assert ed.has_uridashi(None, KW) is False


# --- secCode → 4桁 --------------------------------------------------------

def test_code4():
    assert ed._code4("72030") == "7203"   # EDINET 5桁 → 4桁
    assert ed._code4("6902") == "6902"
    assert ed._code4(None) == ""
    assert ed._code4("") == ""
    assert ed._code4("E01234") == ""      # edinetCode 形式は対象外


# --- result_to_candidate --------------------------------------------------

def test_result_to_candidate_flattens():
    r = _r(secCode="42460", filerName="ダイキョーニシカワ",
           docDescription="有価証券届出書(有価証券の募集又は売出し)",
           submitDateTime="2026-01-07 16:05", parentDocID="S0")
    c = ed.result_to_candidate(r, KW, IPO_KW)
    assert c["code4"] == "4246"
    assert c["submit_date"] == "2026-01-07"
    assert c["submit_datetime"] == "2026-01-07 16:05"
    assert c["has_uridashi"] == "TRUE"
    assert c["is_ipo"] == "FALSE"
    assert c["parentDocID"] == "S0"
    assert set(c.keys()) == set(ed.CANDIDATE_COLUMNS)


def test_is_ipo_tag():
    assert ed.is_ipo("訂正有価証券届出書（新規公開時）", IPO_KW) is True
    assert ed.is_ipo("有価証券届出書（参照方式）", IPO_KW) is False


# --- extract_candidates ---------------------------------------------------

def test_extract_filters_doctype_ordinance_withdrawal():
    results = [
        _r(docID="A", docTypeCode="030", ordinanceCode="010"),  # 事業会社の届出書 → 拾う
        _r(docID="B", docTypeCode="120", ordinanceCode="010"),  # 有価証券報告書 → 除外(docType)
        _r(docID="C", docTypeCode="040", ordinanceCode="010"),  # 訂正届出書 → 拾う
        _r(docID="F", docTypeCode="100", ordinanceCode="010"),  # 発行登録追補 → 拾う
        _r(docID="E", docTypeCode="030", ordinanceCode="030"),  # 投資信託 → 除外(ordinance)
        _r(docID="D", docTypeCode="030", ordinanceCode="010", withdrawalStatus="1"),  # 撤回 → 除外
    ]
    cands = ed.extract_candidates(results, TARGET, ORDS, KW, IPO_KW)
    ids = {c["docID"] for c in cands}
    assert ids == {"A", "C", "F"}


# --- validate_envelope ----------------------------------------------------

def test_validate_ok():
    data = {"metadata": {"status": "200"}, "results": [_r()]}
    results, status = ed.validate_envelope(data)
    assert status == "200" and len(results) == 1


def test_validate_empty_results_ok():
    data = {"metadata": {"status": "404"}, "results": None}
    results, status = ed.validate_envelope(data)
    assert results == [] and status == "404"


def test_validate_schema_change_raises():
    with pytest.raises(ValueError):
        ed.validate_envelope({"metadata": {"status": "200"}, "results": {"not": "a list"}})
    with pytest.raises(ValueError):
        ed.validate_envelope({"results": []})                    # metadata 欠落
    with pytest.raises(ValueError):
        ed.validate_envelope({"metadata": {"status": "200"},
                              "results": [{"docID": "X"}]})        # 必須キー欠落(docTypeCode等)


# --- business_days --------------------------------------------------------

def test_business_days_skips_weekends():
    days = list(ed.business_days(date(2024, 7, 1), date(2024, 7, 7)))  # 月..日
    assert days == [date(2024, 7, d) for d in (1, 2, 3, 4, 5)]         # 土日除外
