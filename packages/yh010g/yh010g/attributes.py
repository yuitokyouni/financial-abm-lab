"""発行体属性パイプラインの骨格 (Task 6 / HANDOFF A-2)。

conditional 規則 (ISS: ROE 5%・政策保有20%・女性取締役 / GL: ROE 8%・縮減計画・
性別多様性) の発火と、μ 条件付けの精緻化に必要な発行体属性を供給する。

属性スキーマ (policy.engine の conditions[].requires と対応):
  roe_5y_avg, roe_latest, roe_improving          — 有報の連結財務データから
  policy_holdings_to_net_assets, has_reduction_plan — 有報「株式の保有状況」から
  n_female_directors_post_agm                     — 招集通知/コーポレートガバナンス報告書
  is_top_management, is_board_chair, is_outside_director, attendance_rate 等 — 候補者属性

供給経路は2つ:
  1. load_attributes_csv: 手動整備した CSV (少数の検証議案・パイロット向け)
  2. EDINET API v2 (書類一覧・XBRL取得): 大規模整備向け。**APIキーが必要**
     (https://api.edinet-fsa.go.jp / 環境変数 EDINET_API_KEY)。XBRL からの
     ROE・政策保有の抽出器は未実装 — 本モジュールはインターフェースの正本。
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

EDINET_BASE = "https://api.edinet-fsa.go.jp/api/v2"

NUMERIC_FIELDS = {
    "roe_5y_avg", "roe_latest", "policy_holdings_to_net_assets",
    "attendance_rate", "n_female_directors_post_agm",
}
BOOL_FIELDS = {
    "roe_improving", "has_reduction_plan", "has_poison_pill",
    "is_top_management", "is_board_chair", "is_outside_director",
    "is_outside_auditor", "iss_independent", "gl_independent",
    "recipients_include_outsiders", "amount_disclosed",
    "audit_opinion_qualified",
}


def load_attributes_csv(path: str | Path) -> dict[str, dict]:
    """手動整備 CSV → 属性辞書 {key: {field: value}}。

    key 列は sec_code (発行体レベル) または col_id (議案レベル)。
    それ以外の列は属性。空セルは「未整備」としてスキップ (0 と区別する)。
    """
    out: dict[str, dict] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get("key") or "").strip()
            if not key:
                continue
            attrs: dict = {}
            for field, raw in row.items():
                if field == "key" or raw is None or str(raw).strip() == "":
                    continue
                s = str(raw).strip()
                if field in BOOL_FIELDS:
                    attrs[field] = s.lower() in ("1", "true", "yes", "y", "はい")
                elif field in NUMERIC_FIELDS:
                    attrs[field] = float(s)
                else:
                    attrs[field] = s
            out[key] = attrs
    return out


def edinet_api_key() -> str:
    """EDINET API v2 のキー。未設定なら明示的に失敗する (黙って空データを返さない)。"""
    key = os.environ.get("EDINET_API_KEY", "")
    if not key:
        raise RuntimeError(
            "EDINET_API_KEY が未設定。https://api.edinet-fsa.go.jp で発行し "
            "環境変数に設定すること (Task 6 の EDINET 経路はキー必須)")
    return key


def fetch_document_list(date: str) -> dict:  # pragma: no cover - ネットワーク必須
    """EDINET 書類一覧 API (type=2)。有報・臨報の docID 探索の入口。"""
    import json
    import urllib.request
    url = f"{EDINET_BASE}/documents.json?date={date}&type=2&Subscription-Key={edinet_api_key()}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)
