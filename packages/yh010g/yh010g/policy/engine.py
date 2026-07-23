"""推奨再構成エンジン — 議案レコード + 発行体属性 → ISS推奨の再構成。

出力の recommendation:
  'for' / 'against'      : 属性により条件が確定した判定
  'for_default' / 'against_default' : カテゴリ既定 (条件未評価。属性が来れば変わりうる)
  'indeterminate'        : 既定なし・属性不足で判定不能
属性未整備の現段階では *_default と indeterminate のみが出る。coverage の解釈に注意。
"""

from __future__ import annotations

from dataclasses import dataclass

from yh010g.policy.categories import normalize_category
from yh010g.policy.iss_rules import iss_policy
from yh010g.schema import UnifiedRecord, proposal_col_id

_ALLOWED = {"for", "against", "for_default", "against_default", "indeterminate"}


@dataclass
class Recommendation:
    col_id: str
    category: str            # 正準カテゴリ
    recommendation: str      # _ALLOWED のいずれか
    rule_kind: str           # default / conditional / indeterminate
    fired_condition: str | None = None
    missing_fields: tuple = ()


def _eval_condition(cond: dict, attrs: dict) -> tuple[bool | None, tuple]:
    """条件式を属性辞書上で評価。属性不足なら (None, missing)。"""
    missing = tuple(f for f in cond["requires"] if f not in attrs)
    if missing:
        return None, missing
    try:
        result = bool(eval(cond["against_if"], {"__builtins__": {}}, dict(attrs)))  # noqa: S307
    except Exception:
        return None, tuple(cond["requires"])
    return result, ()


def reconstruct_recommendations(
    records: list[UnifiedRecord],
    policy_year: int,
    attributes: dict[str, dict] | None = None,
) -> dict[str, Recommendation]:
    """議案キー (col_id) → Recommendation。

    attributes: col_id または sec_code をキーとする属性辞書 (A-2 パイプラインの出力)。
    同一議案に複数レコード (複数運用機関) があっても推奨は一意 — カテゴリラベルの
    正準化が一致する限り最初のレコードで代表する。カテゴリ不一致は 'unknown' 側を捨て、
    確定カテゴリを優先する。
    """
    attributes = attributes or {}
    pol = iss_policy(policy_year)
    out: dict[str, Recommendation] = {}
    for r in records:
        col = proposal_col_id(r.sec_code, r.meeting_date, r.proposal_no, r.sub_no)
        cat = normalize_category(r.category)
        if col in out and (out[col].category != "unknown" or cat == "unknown"):
            continue
        rule = pol["rules"][cat]
        kind = rule["kind"]
        attrs = {**attributes.get(r.sec_code, {}), **attributes.get(col, {})}
        if kind == "indeterminate":
            out[col] = Recommendation(col, cat, "indeterminate", kind)
            continue
        rec = None
        fired = None
        missing_all: list = []
        for cond in rule.get("conditions", []):
            hit, missing = _eval_condition(cond, attrs)
            if hit is None:
                missing_all.extend(missing)
                continue
            if hit:
                rec, fired = "against", cond["id"]
                break
        if rec is None:
            if rule.get("conditions") and not missing_all:
                rec = rule["default"]          # 全条件を評価し尽くして既定 → 確定判定
            else:
                rec = rule["default"] + "_default"
        assert rec in _ALLOWED
        out[col] = Recommendation(col, cat, rec, kind, fired, tuple(dict.fromkeys(missing_all)))
    return out


def coverage_report(recs: dict[str, Recommendation]) -> dict:
    from collections import Counter
    c = Counter(r.recommendation for r in recs.values())
    k = Counter(r.category for r in recs.values())
    return {"n": len(recs), "by_recommendation": dict(c), "by_category": dict(k)}
