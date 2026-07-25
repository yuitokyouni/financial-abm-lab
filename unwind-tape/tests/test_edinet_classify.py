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
    "policy_keywords": ["政策保有", "縮減", "純投資目的以外", "主要株主の異動"],
    "uridashi_equity_phrases": ["株式の売出", "普通株式の売出", "株券の売出"],
    "uridashi_na_markers": ["該当事項はありません", "該当なし"],
    "bond_markers": ["社債券", "無担保社債"],
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


# --- classify_doc(実データ=テキストブロック構造に合わせる) ------------------

def test_classify_equity_uridashi_aisin_like():
    # 訂正臨時報告書(190)。値は自由文(テキストブロック)に埋まる
    rows = _rows(
        ("会社名、表紙", "株式会社アイシン"),
        ("提出理由 [テキストブロック]",
         "2024年６月27日開催の取締役会において決議された当社普通株式の売出し（引受人の買取引受による売出し）"),
        ("報告内容 [テキストブロック]",
         "(1)株式の種類 当社普通株式 (2)売出数 7,788,400株 (3)売出価格 5,092円"),
    )
    r = ec.classify_doc(rows, CFG)
    assert r["is_equity_uridashi"] == "TRUE"
    assert r["is_bond"] == "FALSE"
    assert r["uridashi_shares"] == "7788400"
    assert r["offer_price_JPY"] == ""       # 価格は自動抽出しない(転記で確定)
    assert r["confidence_policy_holding"] == "B_inference"   # 政策保有語なし → 人が確認
    assert ec.is_tier2(r)


def test_classify_policy_explicit_A():
    rows = _rows(
        ("提出理由 [テキストブロック]", "政策保有株式の縮減の一環として当社普通株式の売出しを行う"),
        ("報告内容 [テキストブロック]", "(2)売出数 1,000,000株"),
    )
    r = ec.classify_doc(rows, CFG)
    assert r["is_equity_uridashi"] == "TRUE"
    assert r["policy_explicit"] == "TRUE"
    assert r["confidence_policy_holding"] == "A_explicit"
    assert ec.is_tier2(r)


def test_classify_bond_skylark_like():
    # 発行登録追補(100)だが中身は社債。売出要項=該当なし → 株式売出でない
    rows = _rows(
        ("発行登録の対象とした募集（売出）有価証券の種類、表紙", "社債"),
        ("新規発行社債 [テキストブロック]", "第１回無担保社債（社債間限定同順位特約付）"),
        ("売出要項 [テキストブロック]", "第２【売出要項】　該当事項はありません。"),
    )
    r = ec.classify_doc(rows, CFG)
    assert r["is_equity_uridashi"] == "FALSE"
    assert r["is_bond"] == "TRUE"
    assert r["confidence_policy_holding"] == "none"
    assert not ec.is_tier2(r)


def test_classify_boshu_only_not_uridashi():
    # 募集のみ(新株発行)。「株式の売出」表現なし → none
    rows = _rows(("有価証券の種類", "株券"), ("募集の条件 [テキストブロック]", "新株式発行 公募増資"))
    r = ec.classify_doc(rows, CFG)
    assert r["is_equity_uridashi"] == "FALSE"
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


def test_parse_strips_surrounding_quotes():
    # EDINET CSV は各フィールドがダブルクォート囲み → csv.reader で剥がす(発表日抽出の前提)
    header = '"要素ID"\t"項目名"\t"値"'
    body = '"jpcrp_cor:FilingDateCoverPage"\t"提出日、表紙"\t"2024-06-27"'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL_TO_CSV/x.csv", (header + "\n" + body + "\n").encode("utf-16"))
    rows = ec.parse_edinet_csv_zip(buf.getvalue())
    assert rows[0]["element"] == "jpcrp_cor:FilingDateCoverPage"   # クォート無し
    assert rows[0]["value"] == "2024-06-27"
    assert rows[0]["element"].endswith("FilingDateCoverPage")       # step3 の発表日抽出が効く


def test_parse_bad_zip_returns_empty():
    assert ec.parse_edinet_csv_zip(b"not a zip") == []
