"""モノカルチャー指標 — 定義はこの一箇所のみ (YH010_HANDOFF §7 の規約)。

定義: mu_j (インスタンスの共通ファンダメンタルズ) で条件付けした後の
共有地図因子の分散シェア。すなわち観測セル上で
    index = 1 - SS(x - mu - Z A') / SS(x - mu)
第一近似では mu_j = 列平均 (議案/インスタンス固定効果)。議案属性による
より細かい条件付けは FactorModel 側の mu 推定を拡張して行う (将来 feature)。

YH010 (価格空間) と YH010-g (ガバナンス空間) の両方がこの関数を呼ぶこと。
別実装の複製を作らない。
"""

from __future__ import annotations

from agora_engine.factor_model import FactorFit


def monoculture_index(fit: FactorFit) -> float:
    """mu 条件付け後の因子分散シェア in [0, 1]。

    注意: k を増やせば機械的に増える (PCA の性質)。腕間比較は必ず同一 k で行い、
    絶対水準の解釈には対照系 (独立エージェント腕) との差分を使うこと。
    """
    share = fit.explained_share
    return float(min(max(share, 0.0), 1.0))
