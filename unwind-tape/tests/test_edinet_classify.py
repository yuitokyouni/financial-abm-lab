"""unwind-tape / edinet_classify の単体テスト(Task D step 2、ネットワーク不要の純関数)。

売出人属性・本文分類(株式売出×政策保有)・tier2 判定・数値正規化・CSV(zip)パースを検証。
実 API 疎通と本文構造の最終確認は --dump(Mac)で行う。
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import edinet_classify as ec  # noqa: E402

CFG = {
    "uridashi_keywords": ["売出"],
    "policy_keywords": ["政策保有", "縮減", "純投資目的以外"],
    "equity_keywords": ["株券", "株式"],
    "bond_only_keywords": ["社債券"],
    "seller_type_rules": {
        "bank": ["銀行"], "insurance": ["生命保険", "損害保険", "保険"],
        "trust": ["信託"], "securities": ["証券"],
        "fund": ["アセットマネジメント", "キャピタル", "ファンド"],
    },
}


def _rows(*pairs):
    return [{"element": f"e{i}", "item": it, "value": v, "source_csv": "x.csv"}
            for i, (it, v) in enumerate(pairs)]


# --- seller type ----------------------------------------------------------

def test_seller_type():
    r = CFG["seller_type_rules"]
    assert ec.classify_seller_type("株式会社三菱UFJ銀行", r) == "bank"
    assert ec.classify_seller_type("日本生命保険相互会社", r) == "insurance"
    assert ec.classify_seller_type("野村アセットマネジメント株式会社", r) == "fund"
    assert ec.classify_seller_type("株式会社デンソー", r) == "business"
    assert ec.classify_seller_type("山田太郎", r) == "other"


# --- _norm_num ------------------------------------------------------------

def test_norm_num():
    assert ec._norm_num("256,373,400株") == "256373400"
    assert ec._norm_num("２，０６９．５") == "2069.5"
    assert ec._norm_num("該当なし") == ""


# --- classify_doc ---------------------------------------------------------

def test_classify_policy_explicit_A():
    rows = _rows(("有価証券の種類", "株券"),
                 ("売出しに関する事項 売出人の氏名又は名称", "株式会社デンソー"),
                 ("売出しの目的", "政策保有株式の縮減の一環として売却"),
                 ("売出株式の数", "256,373,400"),
                 ("売出価格", "2,069.5"))
    r = ec.classify_doc(rows, CFG)
    assert r["is_uridashi"] == "TRUE"
    assert r["is_equity"] == "TRUE"
    assert r["is_bond_only"] == "FALSE"
    assert r["policy_explicit"] == "TRUE"
    assert r["confidence_policy_holding"] == "A_explicit"
    assert r["uridashi_shares"] == "256373400"
    assert r["offer_price_JPY"] == "2069.5"
    assert ec.is_tier2(r)


def test_classify_business_seller_B():
    # 政策保有の明示は無いが、売出人が事業会社 → B_inference
    rows = _rows(("有価証券の種類", "株式"),
                 ("売出人の氏名又は名称", "トヨタ自動車株式会社"),
                 ("売出株式数", "1,000,000"))
    r = ec.classify_doc(rows, CFG)
    assert r["confidence_policy_holding"] == "B_inference"
    assert "business" in r["seller_types"]
    assert ec.is_tier2(r)


def test_classify_fund_seller_not_policy():
    rows = _rows(("有価証券の種類", "株券"),
                 ("売出人の氏名又は名称", "野村アセットマネジメント株式会社"))
    r = ec.classify_doc(rows, CFG)
    assert r["confidence_policy_holding"] == "none"   # ファンド売却=非政策保有
    assert not ec.is_tier2(r)


def test_classify_bond_only_excluded():
    rows = _rows(("有価証券の種類", "社債券"),
                 ("募集の条件", "利率年1.0%"))
    r = ec.classify_doc(rows, CFG)
    assert r["is_bond_only"] == "TRUE"
    assert r["confidence_policy_holding"] == "none"
    assert not ec.is_tier2(r)


def test_classify_boshu_only_not_uridashi():
    # 募集のみ(売出無し)。政策保有語も無い → tier none, is_uridashi FALSE
    rows = _rows(("有価証券の種類", "株券"), ("募集に関する事項", "新株式発行"))
    r = ec.classify_doc(rows, CFG)
    assert r["is_uridashi"] == "FALSE"
    assert not ec.is_tier2(r)


# --- parse_edinet_csv_zip -------------------------------------------------

def test_parse_edinet_csv_zip_utf16_tsv():
    header = "要素ID\t項目名\tコンテキストID\t相対年度\t連結・個別\t期間・時点\tユニットID\t単位\t値"
    body = "jpcrp_X\t売出株式の数\tC\t当期\t連結\t時点\tU\t株\t256,373,400"
    csv_text = header + "\n" + body + "\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL_TO_CSV/jpcrp_X.csv", csv_text.encode("utf-16"))
    rows = ec.parse_edinet_csv_zip(buf.getvalue())
    assert len(rows) == 1
    assert rows[0]["item"] == "売出株式の数"
    assert rows[0]["value"] == "256,373,400"


def test_parse_bad_zip_returns_empty():
    assert ec.parse_edinet_csv_zip(b"not a zip") == []
