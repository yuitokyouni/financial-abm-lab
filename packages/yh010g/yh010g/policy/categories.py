"""議案分類の正規化 — 会社別ラベル → 正準カテゴリ。

観測ラベルは 2026-07-23 のパイロット行列 (8社・2024Q2/2025Q2) から採取。
7社は共通系ラベル (ICJ 系と推察)、ニッセイのみ独自ラベル。
未知ラベルは 'unknown' に落とし、エンジンが unmapped ラベルを記録する。
"""

from __future__ import annotations

import unicodedata

CANONICAL_CATEGORIES = [
    "financial_statements",   # 計算書類の承認
    "dividend",               # 剰余金の処分
    "director_election",      # 取締役の選解任
    "auditor_election",       # 監査役の選解任
    "compensation",           # 役員報酬 (報酬枠・ストックオプション等を含む)
    "retirement_bonus",       # 退職慰労金
    "articles",               # 定款変更
    "poison_pill",            # 買収防衛策
    "capital_policy",         # 資本政策 (自己株式取得・第三者割当等)
    "accounting_auditor",     # 会計監査人の選解任
    "merger",                 # 合併・買収・組織再編
    "other",
    "unknown",
]

_LABEL_MAP = {
    # 共通系 (amova/daiwa/mufg_am/mufg_trust/nomura/smdam/smtam)
    "取締役の選解任": "director_election",
    "監査役の選解任": "auditor_election",
    "剰余金の処分": "dividend",
    "役員報酬": "compensation",
    "定款に関する議案": "articles",
    "その他資本政策に関する議案": "capital_policy",
    "その他 資本政策に関する議案": "capital_policy",
    "退任役員の退職慰労金の支給": "retirement_bonus",
    "退職慰労金の支給": "retirement_bonus",
    "買収防衛策の導入・更新・廃止": "poison_pill",
    "会計監査人の選解任": "accounting_auditor",
    "計算書類の承認": "financial_statements",
    "合併・企業再編に関する議案": "merger",
    "組織再編に関する議案": "merger",
    "その他": "other",
    "その他の議案": "other",
    # ニッセイ独自ラベル
    "取締役の選任等に関する議案": "director_election",
    "監査役の選任等に関する議案": "auditor_election",
    "利益処分に関する議案": "dividend",
    "役員報酬に関する議案": "compensation",
    "定款変更に関する議案": "articles",
    "役員退職慰労金に関する議案": "retirement_bonus",
    "役職員のインセンティブ向上に関する議案": "compensation",
    "買収防衛策に関する議案": "poison_pill",
    "会計監査人の選任に関する議案": "accounting_auditor",
    "自己株式取得に関する議案": "capital_policy",
    "合併等に関する議案": "merger",
}


def normalize_category(label: str) -> str:
    s = unicodedata.normalize("NFKC", str(label)).strip()
    return _LABEL_MAP.get(s, "unknown")
