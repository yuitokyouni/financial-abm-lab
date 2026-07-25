"""unwind-tape / edinet_to_worksheet(Task D step3)の単体テスト。

offering クラスタリング(発行体×日付近接)、本文からの発表日/株数/価格 暫定抽出、draft 行組立を検証。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import edinet_to_worksheet as w  # noqa: E402


def _t(code, date, dt, docid, shares="", tier="B_inference", name=""):
    return {"issuer_code": code, "issuer_name": name or f"社{code}", "submit_date": date,
            "docTypeCode": dt, "docID": docid, "uridashi_shares": shares,
            "confidence_policy_holding": tier}


# --- cluster_offerings ----------------------------------------------------

def test_cluster_splits_by_issuer_and_gap():
    rows = [
        _t("7259", "2024-06-27", "030", "A1"),   # アイシン offering1 announce
        _t("7259", "2024-07-08", "190", "A2"),   #            offering1 pricing(11日後)
        _t("7259", "2025-03-01", "030", "A3"),   #            offering2(半年後→別)
        _t("7267", "2024-07-04", "180", "H1"),   # ホンダ 別発行体
    ]
    clusters = w.cluster_offerings(rows, gap_days=45)
    # アイシン2 offering + ホンダ1 = 3 クラスタ
    assert len(clusters) == 3
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 1, 2]   # {A1,A2}=2, {A3}=1, {H1}=1


def test_cluster_same_offering_within_gap():
    rows = [_t("1", "2024-01-05", "030", "a"), _t("1", "2024-01-19", "040", "b")]
    assert len(w.cluster_offerings(rows, 45)) == 1


# --- extract_body_fields --------------------------------------------------

def _body(*pairs, filing=None):
    rows = [{"element": e, "item": it, "value": v} for e, it, v in pairs]
    if filing:
        rows.insert(0, {"element": "jpcrp-esr_cor:FilingDateCoverPage", "item": "提出日、表紙", "value": filing})
    return rows


def test_extract_body_fields():
    rows = _body(
        ("e1", "報告内容", "(2)売出数 7,788,400株 (3)売出価格 5,092円"),
        filing="2024-06-27")
    r = w.extract_body_fields(rows, min_offer_price=50)
    assert r["announce_date"] == "2024-06-27"
    assert r["sold_shares_est"] == "7788400"
    assert r["offer_price_est"] == "5092"


def test_extract_price_filters_small_noise():
    # 「売出価格」近傍に小額(手数料/割引 27.59円)しか無ければ採らない
    rows = _body(("e1", "x", "引受手数料 売出価格 27.59円"))
    assert w.extract_body_fields(rows, min_offer_price=50)["offer_price_est"] == ""


def test_extract_shares_takes_max():
    # 国内+海外の複数記載 → 大きい方(総数寄り)
    rows = _body(("e1", "x", "売出数 7,788,400株 売出数 26,074,100株"))
    assert w.extract_body_fields(rows, 50)["sold_shares_est"] == "26074100"


# --- build_draft_row ------------------------------------------------------

def test_build_draft_row_picks_pricing_and_tier():
    cluster = [
        _t("7259", "2024-06-27", "030", "A1", shares="26074100", tier="A_explicit"),
        _t("7259", "2024-07-08", "190", "A2", shares="7788400", tier="B_inference"),
    ]
    body = {"announce_date": "2024-06-27", "sold_shares_est": "33862500", "offer_price_est": "5092"}
    d = w.build_draft_row(cluster, body)
    assert d["tier"] == "A_explicit"                 # クラスタに A があれば A
    assert d["pricing_date"] == "2024-07-08"         # 値決め(190)の日
    assert d["announce_date"] == "2024-06-27"
    assert d["edinet_pricing_docid"] == "A2"         # 最後の値決め書類
    assert d["sold_shares_est"] == "33862500"        # 本文抽出を優先
    assert d["sale_route"] == "secondary_offering"
    assert d["include"] == ""


def test_build_draft_row_notes_missing_announce():
    cluster = [_t("1", "2024-05-07", "100", "x", shares="1000")]
    d = w.build_draft_row(cluster, {"announce_date": "", "sold_shares_est": "", "offer_price_est": ""})
    assert d["sold_shares_est"] == "1000"            # 本文空 → step2 の株数で補完
    assert "発表日" in d["note"]
