"""外部妥当性アンカー④ — 実在 venue/銘柄の較正 registry（research D-B10）。

各較正値は SourcedValue（値 + 出典/換算手順）で持ち、値が未記入（None）の較正を
使おうとすると CalibrationIncomplete を明示で投げる——出典なしの数値を黙って合成値で
埋めない（原則V）。換算チェーンの全文・検算・限界は
`specs/002-exp-b-collusion-harness/calibration.md`。

主アンカー bcs-es-spy の同定戦略（要点）:
  λ・J は BCS 2015 Table I（801 arbs/day、per-arb 利益 median 0.08pt）から直接、
  h は ES 最小 spread（tick 0.25pt → half 0.125pt）、
  ν（noise_rate）は BCS eq.(3)＝本 harness の gm_break_even と同一式を観測 h で閉じて
  同定（ν = α·λ·(J−h)/h）。検算: gm_break_even(λ,J,α=1,ν) = 0.125 が厳密に再現される。
"""
from __future__ import annotations

from dataclasses import dataclass, fields

from .learnconfig import LearnConfig


class CalibrationIncomplete(RuntimeError):
    pass


@dataclass(frozen=True)
class SourcedValue:
    value: float | None
    source: str        # 出典（論文・公表値）と換算手順の要約


@dataclass(frozen=True)
class Calibration:
    """sim パラメータへの mapping（時間単位 = 1 秒、価格単位 = index point）。"""
    name: str
    description: str
    dt: float                      # 解像度（秒）。staleness 窓 = 1 期 = dt
    lambda_jump: SourcedValue      # arb 機会強度（/秒）
    jump_size: SourcedValue        # 機会あたり価格変位 J（point）
    half_spread_ref: SourcedValue  # 観測 half-spread（grid スケール・closure の入力）
    alpha: SourcedValue            # arb 参加確率（1.0 = race は常に解決＝gross 極限）
    fee: SourcedValue              # per-fill 手数料（point 換算）
    noise_rate: SourcedValue       # 非情報 flow 強度（/秒、eq(3) closure）
    batch_grid: tuple[int, ...]    # 検証する N（dt 単位）
    batch_grid_source: str

    def to_config(self, **overrides) -> LearnConfig:
        missing = [f.name for f in fields(self)
                   if isinstance(getattr(self, f.name), SourcedValue)
                   and getattr(self, f.name).value is None]
        if missing:
            raise CalibrationIncomplete(
                f"calibration '{self.name}' に未記入の較正値: {missing}。"
                "原典から数値を確認して registry に記入すること（出典なしで走らせない）。")
        return LearnConfig(
            dt=self.dt,
            lambda_jump=self.lambda_jump.value,
            jump_size=self.jump_size.value,
            alpha=self.alpha.value,
            fee=self.fee.value,
            noise_rate=self.noise_rate.value,
            **overrides,
        )


REGISTRY: dict[str, Calibration] = {
    # 主アンカー（D-B10）: Budish, Cramton & Shim (2015, QJE 130(4), 1547–1621)
    # ES-SPY latency arbitrage。数値の出典・換算・検算の全文は calibration.md。
    "bcs-es-spy": Calibration(
        name="bcs-es-spy",
        description="BCS 2015 ES-SPY latency arbitrage。時間単位=秒、価格単位=ES index "
                    "point。staleness 1 期 = dt = 10ms ≈ 2011 年の median race 時間 7ms。",
        dt=0.01,
        lambda_jump=SourcedValue(
            801.0 / 23_400.0,   # ≈ 0.03423 /s
            "BCS Table I: # of arbs/day mean=801 ÷ 取引時間 6.5h=23,400s（§IV データ窓の"
            "概数換算。観測『機会』率を jump 率に同定＝J>h+閾値の jump のみ数える保守側）"),
        jump_size=SourcedValue(
            0.125 + 0.08,       # = 0.205 pt
            "J = h + per-arb 利益: half-spread 0.125pt + per-arb 利益 median ≈0.08pt"
            "（BCS §V.B/Figure V: 'remarkably constant ... median of about 0.08 index "
            "points per unit traded'。Table I mean=0.09 は代替値）"),
        half_spread_ref=SourcedValue(
            0.125, "ES 最小 tick 0.25pt（BCS §V.B: 'minimum ES bid-ask spread ... 0.25 "
                   "index points'）→ half-spread 0.125pt"),
        alpha=SourcedValue(
            1.0, "BCS の race は常に勝者が解決（snipers の到着は確定的競争）＝gross 抽出"
                 "極限。spec 001/002 の monopolist sniper 仮定と整合"),
        fee=SourcedValue(
            0.0, "BCS の利益推定は exchange fees/rebates を除外（§V.B 脚注13）→ baseline "
                 "f=0。CME 公表 fee schedule の追加は robustness 軸"),
        noise_rate=SourcedValue(
            (801.0 / 23_400.0) * 0.08 / 0.125,   # ≈ 0.02191 /s
            "eq(3) closure: BCS 均衡式 l_invest·s/2 = l_jump·Pr(J>s/2)·E[J−s/2]（本 harness "
            "の gm_break_even と同一式）を観測 h=0.125 で閉じる: ν = α·λ·(J−h)/h。"
            "検算: gm_break_even(λ,J,1,ν)=0.125 を test で pin"),
        batch_grid=(10, 100),
        batch_grid_source="BCS の提案 'to fix ideas, say, 100 milliseconds'（§I）＋ §VII.D "
                          "は最適 interval を特定しない → 100ms(N=10) と 1s(N=100) の 2 点",
    ),
    # 代替: 台湾証券取引所の定期 call auction（実在した batch venue、N の外部値）。
    "twse-call-auction": Calibration(
        name="twse-call-auction",
        description="TWSE 定期 call auction（〜2020-03、約 5 秒間隔で一括約定）。"
                    "batch interval の実在値アンカー。",
        dt=0.01,
        lambda_jump=SourcedValue(None, "未記入: TWSE 個別銘柄の jump 強度（系列推定が必要）"),
        jump_size=SourcedValue(None, "未記入: tick/spread 比から換算"),
        half_spread_ref=SourcedValue(None, "未記入: 銘柄帯の実効 spread"),
        alpha=SourcedValue(None, "未記入"),
        fee=SourcedValue(None, "未記入: TWSE 手数料 + 取引税"),
        noise_rate=SourcedValue(None, "未記入"),
        batch_grid=(500,),
        batch_grid_source="TWSE 旧制度の約 5s 間隔 → dt=10ms で N=500",
    ),
}


def get_calibration(name: str) -> Calibration:
    if name not in REGISTRY:
        raise KeyError(f"unknown calibration '{name}'. available: {sorted(REGISTRY)}")
    return REGISTRY[name]
