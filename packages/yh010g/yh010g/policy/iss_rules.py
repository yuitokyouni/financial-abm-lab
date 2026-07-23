"""ISS 日本向け議決権行使助言基準の規則ベース再構成 (YH010g_HANDOFF §4 A-3)。

ポリシー年度ごとにバージョン管理する (年度の取り違えはポリシー改訂イベントスタディの
識別を壊すため致命的)。出典は ISS 公開ポリシー文書 (Japan Proxy Voting Guidelines,
日本語版 PDF) で、各規則に条文の要旨と必要属性 (required_fields) を明記する。

規則の3分類:
  - default: 属性なしで発火するカテゴリ既定 (原則賛成/原則反対)
  - conditional: 発行体・議案属性が揃えば判定が変わる (属性未整備なら既定に留まる)
  - indeterminate: 属性なしでは賛否を出せない (既定なし)

2025年度 (2025-02-01 以降開催の総会に適用) の主要な機械的規則を収録。
発行体属性 (ROE・政策保有比率・女性取締役etc.) は EDINET パイプライン (A-2) の
整備後に conditional 規則が発火する設計。属性が来るまでは coverage を過大に
見せないこと (TwinMarket 禁止則の精神)。
"""

from __future__ import annotations

POLICY_YEARS = {"iss": [2024, 2025]}

_ISS_2025 = {
    "policy": "iss",
    "policy_year": 2025,
    "applies_from": "2025-02-01",
    "source": "ISS Japan Proxy Voting Guidelines 2025 (日本語版, issgovernance.com)",
    "rules": {
        "financial_statements": {
            "kind": "default", "default": "for",
            "cite": "§1 計算書類の承認: 会計監査人の意見不表明等を除き原則賛成",
            "exceptions_require": ["audit_opinion_qualified"],
        },
        "dividend": {
            "kind": "default", "default": "for",
            "cite": "§2 剰余金の処分: 原則賛成 (配当性向等の例外は属性が必要)",
            "exceptions_require": ["payout_ratio", "net_income_sign"],
        },
        "director_election": {
            "kind": "conditional", "default": "for",
            "cite": ("§4 取締役の選任: 原則賛成。ただし (i) 過去5期平均ROE<5%かつ改善傾向なし"
                     "→経営トップ反対, (ii) 政策保有株式が純資産の20%以上→経営トップ反対, "
                     "(iii) 総会後の取締役会に女性取締役ゼロ→経営トップ反対 "
                     "(2027-02以降は10%未満), (iv) 親会社・支配株主を持つ会社の独立社外比率, "
                     "(v) 社外取締役の独立性・出席率75%未満 等"),
            "conditions": [
                {"id": "roe", "against_if": "roe_5y_avg < 0.05 and not roe_improving",
                 "target": "top_management", "requires": ["roe_5y_avg", "roe_improving", "is_top_management"]},
                {"id": "allegiant_shares", "against_if": "policy_holdings_to_net_assets >= 0.20",
                 "target": "top_management", "requires": ["policy_holdings_to_net_assets", "is_top_management"]},
                {"id": "no_female_director", "against_if": "n_female_directors_post_agm == 0",
                 "target": "top_management", "requires": ["n_female_directors_post_agm", "is_top_management"]},
                {"id": "outsider_independence", "against_if": "is_outside_director and not iss_independent",
                 "target": "candidate", "requires": ["is_outside_director", "iss_independent"]},
                {"id": "attendance", "against_if": "is_outside_director and attendance_rate < 0.75",
                 "target": "candidate", "requires": ["is_outside_director", "attendance_rate"]},
            ],
        },
        "auditor_election": {
            "kind": "conditional", "default": "for",
            "cite": "§4系 監査役の選任: 原則賛成。社外監査役の非独立・出席率75%未満で反対",
            "conditions": [
                {"id": "outside_auditor_independence",
                 "against_if": "is_outside_auditor and not iss_independent",
                 "target": "candidate", "requires": ["is_outside_auditor", "iss_independent"]},
                {"id": "attendance", "against_if": "is_outside_auditor and attendance_rate < 0.75",
                 "target": "candidate", "requires": ["is_outside_auditor", "attendance_rate"]},
            ],
        },
        "retirement_bonus": {
            "kind": "conditional", "default": "for",
            "cite": ("§7 退職慰労金: 原則賛成。ただし対象者に社外取締役/社外監査役が含まれる、"
                     "または支給額が (総額・上限含め) 開示されない場合は反対"),
            "conditions": [
                {"id": "outsider_recipient", "against_if": "recipients_include_outsiders",
                 "target": "proposal", "requires": ["recipients_include_outsiders"]},
                {"id": "undisclosed_amount", "against_if": "not amount_disclosed",
                 "target": "proposal", "requires": ["amount_disclosed"]},
            ],
        },
        "poison_pill": {
            "kind": "default", "default": "against",
            "cite": ("§13 買収防衛策: 8項目の形式審査 (独立社外過半数・任期1年・発動水準20%以上・"
                     "有効期限3年以内 等) と個別審査を全て満たす場合を除き原則反対。"
                     "全条件充足は稀であり属性未整備時の既定は反対とする"),
            "exceptions_require": [
                "independent_outsider_majority", "director_term_one_year",
                "trigger_threshold", "expiry_years", "special_committee_independent",
            ],
        },
        "articles": {"kind": "indeterminate",
                     "cite": "§5 定款変更: 内容依存 (買収防衛策関連条項・株主権制限は反対等)"},
        "compensation": {"kind": "indeterminate",
                         "cite": "§8-10 報酬関連: 希薄化・行使価格・付与対象に依存"},
        "capital_policy": {"kind": "indeterminate", "cite": "§12,14 資本政策: 内容依存"},
        "accounting_auditor": {"kind": "default", "default": "for",
                               "cite": "§11 会計監査人の選任: 原則賛成"},
        "merger": {"kind": "indeterminate", "cite": "§14 買収・合併: 個別審査"},
        "other": {"kind": "indeterminate", "cite": "分類不能"},
        "unknown": {"kind": "indeterminate", "cite": "ラベル未マップ"},
    },
}

_ISS_2024 = {
    **_ISS_2025,
    "policy_year": 2024,
    "applies_from": "2024-02-01",
    "source": "ISS Japan Proxy Voting Guidelines 2024 (日本語版, issgovernance.com)",
    # 主要な機械的規則は 2024/2025 で同一 (女性取締役の 10% 化は 2027-02 予告)。
    # 差分が識別に効く場合は改訂条文を個別に上書きすること。
}

_POLICIES = {("iss", 2024): _ISS_2024, ("iss", 2025): _ISS_2025}


def iss_policy(year: int) -> dict:
    key = ("iss", year)
    if key not in _POLICIES:
        raise KeyError(f"ISS policy year {year} not encoded (have {sorted(y for _, y in _POLICIES)})")
    return _POLICIES[key]
