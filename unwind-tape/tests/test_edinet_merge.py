"""unwind-tape / edinet_merge(Task D step4)の単体テスト。

tier→confidence マッピング、group採番、重複ガード((発行体×条件決定日))、行組立、include 判定。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import edinet_merge as m  # noqa: E402

G_COLS = ["event_group_id", "issuer_code", "issuer_name", "issuer_market",
          "event_tier", "confidence_policy_holding", "ABM_candidate_flag"]
L_COLS = ["event_group_id", "event_leg_id", "status", "sale_route", "seller_type",
          "announce_datetime", "pricing_date", "sold_shares", "quantity_basis",
          "offer_price_JPY", "source_primary_url", "notes"]
W_COLS = ["event_group_id", "event_leg_id", "issuer_code", "issuer_name", "sale_route",
          "announce_datetime", "needs", "pricing_date", "offer_price_JPY",
          "source_docs_to_obtain", "note"]


def test_confidence_from_tier():
    assert m.confidence_from_tier("A_explicit") == "B_strong_inference"
    assert m.confidence_from_tier("B_inference") == "C_possible_only"
    assert m.confidence_from_tier("") == "C_possible_only"


def test_next_group_number():
    assert m.next_group_number([f"G{i:03d}" for i in range(1, 12)]) == 12
    assert m.next_group_number([]) == 1
    assert m.next_group_number(["G001", "bad", "G010"]) == 11


def test_existing_offering_keys_dedup():
    groups = [{"event_group_id": "G003", "issuer_code": "7259", "issuer_name": "アイシン"}]
    legs = [{"event_group_id": "G003", "pricing_date": "2024-07-08"}]
    keys = m.existing_offering_keys(groups, legs)
    assert ("7259", "2024-07-08") in keys
    # 同じ発行体・同じ条件決定日はスキップ対象
    assert m._key("7259", "アイシン", "2024-07-08") in keys
    # 別日なら別 offering(スキップされない)
    assert m._key("7259", "アイシン", "2025-01-01") not in keys


def test_build_rows():
    d = {"tier": "A_explicit", "issuer_code": "4543", "issuer_name": "テルモ株式会社",
         "announce_date": "2024-08-29", "pricing_date": "2024-09-12",
         "sold_shares_est": "73211900", "offer_price_est": "2493.5",
         "edinet_all_docids": "S100AAA S100BBB"}
    g, l, w = m.build_rows(d, "G012", G_COLS, L_COLS, W_COLS)
    assert g["event_group_id"] == "G012"
    assert g["event_tier"] == "Tier2_candidate"
    assert g["confidence_policy_holding"] == "B_strong_inference"
    assert g["ABM_candidate_flag"] == "Maybe"
    assert l["event_leg_id"] == "L001" and l["status"] == "candidate"
    assert l["sale_route"] == "secondary_offering" and l["seller_type"] == "unknown"
    assert l["announce_datetime"] == "2024-08-29" and l["pricing_date"] == "2024-09-12"
    assert l["sold_shares"] == "73211900" and l["quantity_basis"] == "announced_total"
    assert l["offer_price_JPY"] == "2493.5"
    assert l["source_primary_url"] == "EDINET:S100AAA"
    assert w["needs"].startswith("offering")
    assert "S100AAA" in w["source_docs_to_obtain"]


def test_build_rows_blank_optional():
    d = {"tier": "B_inference", "issuer_code": "", "issuer_name": "ＪＸ金属株式会社",
         "announce_date": "2025-02-14", "pricing_date": "2025-03-10",
         "sold_shares_est": "", "offer_price_est": "", "edinet_all_docids": ""}
    g, l, w = m.build_rows(d, "G013", G_COLS, L_COLS, W_COLS)
    assert g["confidence_policy_holding"] == "C_possible_only"
    assert l["sold_shares"] == "" and l["quantity_basis"] == ""   # 空なら埋めない
    assert l["source_primary_url"] == ""


def test_truthy():
    assert m._truthy("Y") and m._truthy("yes") and m._truthy("TRUE") and m._truthy("1")
    assert not m._truthy("") and not m._truthy("N") and not m._truthy("later")
