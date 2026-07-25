"""Glass Lewis 日本向けベンチマークポリシーの規則ベース再構成。

出典: 2025 Benchmark Policy Guidelines — Japan (日本語版, glasslewis.com 公開PDF)。
ISS (iss_rules.py) と同じ3分類 (default / conditional / indeterminate)。

ISSとの主要な差分 (ID-g1 推奨分裂の事前予測に使う):
  - 政策保有: 閾値は連結純資産の20%だが例外が厚い (2030年度末までの縮減計画開示、
    10-20%帯では縮減計画または ROE 8%基準で反対を控える)。ISSは20%・例外なし →
    「10-20%帯 × 縮減計画なし × ROE 5-8%帯」で両社の推奨が割れる
  - 女性取締役: 2025年から非プライムも例外なし、2026年からプライム20%要求。
    反対対象は取締役会議長/指名委員長 (ISSは経営トップ) → 対象議案が異なる分裂
  - 退職慰労金: 存在自体で報酬委員全員に反対 (ISSは社外対象者・非開示の場合のみ) →
    社内向け退職慰労金で分裂
  - ROE水準基準: GLは政策保有の例外判定に ROE 8% を使う (ISSの資本生産性基準は5%)
"""

from __future__ import annotations

_GL_2025 = {
    "policy": "gl",
    "policy_year": 2025,
    "applies_from": "2025-01-01",
    "source": "Glass Lewis 2025 Benchmark Policy Guidelines — Japan (日本語版, glasslewis.com)",
    "rules": {
        "financial_statements": {
            "kind": "default", "default": "for",
            "cite": "計算書類: 監査上の重大な問題がない限り原則賛成",
            "exceptions_require": ["audit_opinion_qualified"],
        },
        "dividend": {
            "kind": "default", "default": "for",
            "cite": "剰余金処分: 原則賛成 (配当性向の著しい異常は例外、属性必要)",
            "exceptions_require": ["payout_ratio"],
        },
        "director_election": {
            "kind": "conditional", "default": "for",
            "cite": ("取締役選任: 原則賛成。ただし (i) 買収防衛策を導入・更新している場合は"
                     "取締役会議長 (不在時CEO) に反対、(ii) 政策保有が連結純資産の20%超で"
                     "縮減計画なし→反対 (10-20%帯は縮減計画または5年平均/直近ROE 8%以上で"
                     "反対を控える)、(iii) 性別多様性要件未達→議長/指名委員長に反対 "
                     "(2026年からプライム20%・非プライム1名以上)、(iv) 社外全員の在任12年超"
                     "→議長に反対の場合あり、(v) 出席率75%未満"),
            "conditions": [
                {"id": "pill_adopter_chair", "against_if": "has_poison_pill and is_board_chair",
                 "target": "chair", "requires": ["has_poison_pill", "is_board_chair"]},
                {"id": "allegiant_shares",
                 "against_if": ("policy_holdings_to_net_assets >= 0.20 and not has_reduction_plan"),
                 "target": "responsible_director",
                 "requires": ["policy_holdings_to_net_assets", "has_reduction_plan"]},
                {"id": "allegiant_shares_midband",
                 "against_if": ("0.10 <= policy_holdings_to_net_assets < 0.20 and "
                                "not has_reduction_plan and roe_5y_avg < 0.08 and roe_latest < 0.08"),
                 "target": "responsible_director",
                 "requires": ["policy_holdings_to_net_assets", "has_reduction_plan",
                              "roe_5y_avg", "roe_latest"]},
                {"id": "gender_diversity",
                 "against_if": "n_female_directors_post_agm == 0 and is_board_chair",
                 "target": "chair",
                 "requires": ["n_female_directors_post_agm", "is_board_chair"]},
                {"id": "attendance", "against_if": "is_outside_director and attendance_rate < 0.75",
                 "target": "candidate", "requires": ["is_outside_director", "attendance_rate"]},
            ],
        },
        "auditor_election": {
            "kind": "conditional", "default": "for",
            "cite": ("監査役選任: 原則賛成。監査関連報酬が過半でない・非独立の再任・"
                     "不正会計年度在任・監査役会4回未満等で反対"),
            "conditions": [
                {"id": "outside_auditor_independence",
                 "against_if": "is_outside_auditor and not gl_independent",
                 "target": "candidate", "requires": ["is_outside_auditor", "gl_independent"]},
                {"id": "attendance", "against_if": "is_outside_auditor and attendance_rate < 0.75",
                 "target": "candidate", "requires": ["is_outside_auditor", "attendance_rate"]},
            ],
        },
        "retirement_bonus": {
            "kind": "default", "default": "against",
            "cite": ("退職慰労金: 存在自体を問題視 (報酬委員への反対事由に列挙)。"
                     "支給議案には原則反対 — ISS (社外対象・非開示時のみ反対) より厳格で、"
                     "社内役員向け支給議案が ID-g1 分裂の候補"),
            "exceptions_require": [],
        },
        "poison_pill": {
            "kind": "default", "default": "against",
            "cite": "買収防衛策: 原則反対 (導入・更新企業では取締役会議長への反対助言も併発)",
            "exceptions_require": [],
        },
        "articles": {"kind": "indeterminate", "cite": "定款変更: 内容依存"},
        "compensation": {"kind": "indeterminate",
                         "cite": "報酬関連: 業績連動の設計・開示に依存 (報酬委員向け基準あり)"},
        "capital_policy": {"kind": "indeterminate", "cite": "資本政策: 内容依存"},
        "accounting_auditor": {"kind": "default", "default": "for",
                               "cite": "会計監査人: 原則賛成"},
        "merger": {"kind": "indeterminate", "cite": "買収・合併: 個別審査"},
        "other": {"kind": "indeterminate", "cite": "分類不能"},
        "unknown": {"kind": "indeterminate", "cite": "ラベル未マップ"},
    },
}

_GL_POLICIES = {("gl", 2025): _GL_2025}


def gl_policy(year: int) -> dict:
    key = ("gl", year)
    if key not in _GL_POLICIES:
        raise KeyError(f"GL policy year {year} not encoded (have {sorted(y for _, y in _GL_POLICIES)})")
    return _GL_POLICIES[key]
