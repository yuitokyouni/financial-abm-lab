"""EDINET API v2 からの発行体属性抽出 (Task 6 / HANDOFF A-2 の本体)。

conditional 規則 (ISS: ROE 5%・政策保有20% / GL: ROE 8%・縮減計画) の発火に必要な
発行体レベル財務属性を、有価証券報告書 (docTypeCode 120) の XBRL から取得する。

ネットワーク層 (EdinetClient) はローカル実行専用 (EDINET_API_KEY 必須)。
パース・抽出は純粋関数 (parse_edinet_csv / extract_attributes) に分離し、
フィクスチャでテストする — ネットワークなしで抽出ロジックの正しさを保証。

## ローカル実行 (MacBook 等、キーのある環境)
    export EDINET_API_KEY=...        # gitignore された環境で
    uv run python -m yh010g.build_attributes \
        --targets docs/yh010g_validation_targets.csv \
        --out data/processed/yh010g/attributes_edinet.csv
結果 CSV をコミット・プッシュすれば、キーのない環境でも精度検証が回る。

## 要素IDの検証
EDINET タクソノミの要素IDは版により細部が異なりうる。実CSVで確認するには:
    uv run python -m yh010g.edinet dump <docID>    # 全 (要素ID, コンテキスト, 値) を出力
未マッチは extract_attributes が unmatched に記録する (黙って空を返さない)。
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

# --- EDINET タクソノミ要素ID (実CSVで要検証。dump で確認・調整可) ---
# 有報「主要な経営指標等の推移」(サマリ) は ROE・純資産を5年分直接開示する
EL_ROE = "jpcrp_cor:RateOfReturnOnEquitySummaryOfBusinessResults"
EL_NET_ASSETS_SUMMARY = "jpcrp_cor:NetAssetsSummaryOfBusinessResults"
EL_NET_ASSETS_BS = "jppfs_cor:NetAssets"
# 政策保有株式 (純投資目的以外) の貸借対照表計上額合計
EL_POLICY_HOLDINGS = (
    "jpcrp_cor:TotalStandardShareholdingBalanceSheetAmount"
    "SharesOfPurposeOtherThanPureInvestment"
)
# コンテキストの相対年度プレフィックス (当期→4期前)
YEAR_CONTEXTS = ["CurrentYearDuration", "Prior1YearDuration", "Prior2YearDuration",
                 "Prior3YearDuration", "Prior4YearDuration"]
INSTANT_CONTEXTS = ["CurrentYearInstant", "Prior1YearInstant"]

EDINET_BASE = "https://api.edinet-fsa.go.jp/api/v2"
DOCTYPE_YUHO = "120"  # 有価証券報告書


@dataclass
class ExtractedAttributes:
    sec_code: str
    roe_series: list[float] = field(default_factory=list)   # 当期→過去、fraction (0.08=8%)
    net_assets: float | None = None
    policy_holdings: float | None = None
    unmatched: list[str] = field(default_factory=list)

    def to_attr_dict(self) -> dict:
        """policy.engine の requires フィールドへ写像 (空は入れない=未整備)。"""
        d: dict = {}
        roe = [r for r in self.roe_series if r is not None]
        if roe:
            d["roe_latest"] = roe[0]
            d["roe_5y_avg"] = sum(roe) / len(roe)
            # 改善傾向: 直近が5年平均以上 (簡易。登録時に定義固定)
            d["roe_improving"] = roe[0] >= d["roe_5y_avg"]
        if self.policy_holdings is not None and self.net_assets:
            d["policy_holdings_to_net_assets"] = self.policy_holdings / self.net_assets
        return d


def parse_edinet_csv(text: str) -> list[dict]:
    """EDINET CSV (type=5, UTF-16・タブ区切り) → 行 dict のリスト。

    ヘッダ: 要素ID / 項目名 / コンテキストID / 相対年度 / 連結・個別 /
            期間・時点 / ユニットID / 単位 / 値
    """
    lines = text.splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}
    key_el = next((k for k in idx if "要素ID" in k or k.strip() == "要素ID"), None)
    key_ctx = next((k for k in idx if "コンテキスト" in k), None)
    key_val = next((k for k in idx if k.strip() == "値"), None)
    key_cons = next((k for k in idx if "連結" in k), None)
    if key_el is None or key_ctx is None or key_val is None:
        raise ValueError(f"unexpected EDINET CSV header: {header}")
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        if len(cells) <= idx[key_val]:
            continue
        rows.append({
            "element": cells[idx[key_el]].strip(),
            "context": cells[idx[key_ctx]].strip(),
            "consolidated": cells[idx[key_cons]].strip() if key_cons else "",
            "value": cells[idx[key_val]].strip(),
        })
    return rows


def _to_float(s: str) -> float | None:
    s = s.replace(",", "").replace("△", "-").replace("－", "").strip()
    if s in ("", "-", "NA", "―"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pick_by_context(rows: list[dict], element: str, context_prefix: str) -> float | None:
    """要素ID一致かつコンテキストが prefix で始まる値。連結を優先。"""
    cands = [r for r in rows if r["element"] == element and r["context"].startswith(context_prefix)]
    if not cands:
        return None
    cons = [r for r in cands if "NonConsolidated" not in r["context"]]
    chosen = cons[0] if cons else cands[0]
    return _to_float(chosen["value"])


def extract_attributes(rows: list[dict], sec_code: str) -> ExtractedAttributes:
    """パース済み行から発行体属性を抽出。要素未マッチは unmatched に記録。"""
    out = ExtractedAttributes(sec_code=sec_code)

    roe = [_pick_by_context(rows, EL_ROE, ctx) for ctx in YEAR_CONTEXTS]
    # ROE はパーセント表記 (8.5 = 8.5%) → fraction に。None は落とさず後段で除外
    out.roe_series = [r / 100.0 if r is not None else None for r in roe]
    if all(r is None for r in out.roe_series):
        out.unmatched.append(EL_ROE)

    na = _pick_by_context(rows, EL_NET_ASSETS_SUMMARY, "CurrentYearInstant")
    if na is None:
        na = _pick_by_context(rows, EL_NET_ASSETS_BS, "CurrentYearInstant")
    if na is None:
        out.unmatched.append("net_assets")
    out.net_assets = na

    ph = _pick_by_context(rows, EL_POLICY_HOLDINGS, "CurrentYearInstant")
    if ph is None:
        out.unmatched.append(EL_POLICY_HOLDINGS)
    out.policy_holdings = ph
    return out


# ---------------------------------------------------------------------------
# ネットワーク層 (ローカル実行専用・ここではテストしない)
# ---------------------------------------------------------------------------
class EdinetClient:  # pragma: no cover - ネットワーク必須
    def __init__(self, api_key: str | None = None):
        import os
        self.key = api_key or os.environ.get("EDINET_API_KEY", "")
        if not self.key:
            raise RuntimeError(
                "EDINET_API_KEY が未設定。https://api.edinet-fsa.go.jp で発行し環境変数に設定")

    def _get(self, path: str, params: dict) -> bytes:
        import urllib.parse
        import urllib.request
        params = {**params, "Subscription-Key": self.key}
        url = f"{EDINET_BASE}{path}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()

    def list_documents(self, date: str) -> list[dict]:
        """指定日提出の書類一覧 (type=2)。"""
        import json
        data = json.loads(self._get("/documents.json", {"date": date, "type": "2"}))
        return data.get("results", [])

    def find_yuho(self, sec_code: str, dates: list[str]) -> dict | None:
        """証券コード (4桁) の有報を、候補日リストから探す。EDINET secCode は5桁。"""
        target = sec_code[:4]
        for d in dates:
            for doc in self.list_documents(d):
                sc = (doc.get("secCode") or "")[:4]
                if sc == target and doc.get("docTypeCode") == DOCTYPE_YUHO:
                    return doc
        return None

    def download_csv_rows(self, doc_id: str) -> list[dict]:
        """docID の CSV (type=5, ZIP) を取得しパース。主 CSV を結合して返す。"""
        blob = self._get(f"/documents/{doc_id}", {"type": "5"})
        rows: list[dict] = []
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for name in z.namelist():
                if name.endswith(".csv"):
                    text = z.read(name).decode("utf-16")
                    rows.extend(parse_edinet_csv(text))
        return rows


def dump_document(doc_id: str) -> None:  # pragma: no cover
    """実CSVの全 (要素ID, コンテキスト, 値) を出力し要素IDを検証する。"""
    rows = EdinetClient().download_csv_rows(doc_id)
    for r in rows:
        if any(k in r["element"] for k in ("ROE", "RateOfReturn", "NetAssets",
                                           "Shareholding", "PureInvestment")):
            print(f"{r['element']}\t{r['context']}\t{r['value']}")


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "dump":
        dump_document(sys.argv[2])
    else:
        print("usage: python -m yh010g.edinet dump <docID>")
        sys.exit(2)
