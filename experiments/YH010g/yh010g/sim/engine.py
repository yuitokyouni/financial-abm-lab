"""総会エンジン — ワークストリームB のコア (YH010g_HANDOFF §5)。

YH010 の市場エンジンの総会版: 1ステップ = 「議案生成 → 助言者が推奨 → 投資家が投票
→ 集計」。出力は投資家×議案の投票行列で、実データ (ワークストリームA) と同型 —
共有エンジンの FactorModel / モノカルチャー指標 / 識別器がそのまま適用できる。

生成モデル (正解を仕込める、が本エンジンの存在理由):
  議案の質      mu_j ~ N(0, 1)。sign(mu_j) が「正しい」決議。
  助言者 a の方針ショック  p_aj = rho * g_j + sqrt(1-rho^2) * h_aj
      g_j: 全助言者共有の「共有地図」成分 (rho=1 で助言完全モノカルチャー)
      h_aj: 助言者固有成分
  助言推奨      r_aj = sign(mu_j + sigma_pol * p_aj)
  投資家タイプ:
      follower     : 割当助言者の推奨に常に従う (robo-voting)
      threshold    : 自分のシグナル |x_ij| > tau なら自分の判断、それ以外は助言に従う
      independent  : x_ij = mu_j + sigma_ind * e_ij の符号で投票
IV-1 (助言相関の操作) は n_advisors と rho をパラメータとして動かすことに対応し、
実験スクリプトは共有 `Intervention` API でその操作をテープに記録する。

現段階の単純化 (登録文書で明示すること):
  - 全投資家が全議案に投票 (保有欠測なし)。保有条件付けは将来 feature。
  - 助言者は単一ポリシー次元。ISS規則エンジン (yh010g.policy) の接続は
    属性つき議案生成の導入とセットで行う。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from agora_engine import DecisionMatrix

INVESTOR_TYPES = ("follower", "threshold", "independent")


@dataclass
class InvestorSpec:
    kind: str                 # follower / threshold / independent
    advisor: int | None = None  # follower/threshold の割当助言者 index
    tau: float = 1.0          # threshold 型の自己判断閾値

    def __post_init__(self) -> None:
        if self.kind not in INVESTOR_TYPES:
            raise ValueError(f"unknown investor kind: {self.kind}")
        if self.kind in ("follower", "threshold") and self.advisor is None:
            raise ValueError(f"{self.kind} investor requires advisor index")


@dataclass
class Advisor:
    sigma_pol: float = 1.0    # 方針ショックの相対強度 (0 なら mu をそのまま推奨=完全に正確)


@dataclass
class MeetingSimConfig:
    n_proposals: int = 2000
    n_advisors: int = 2
    rho: float = 0.5              # 助言者間ポリシー重複度 in [0, 1]
    advisor: Advisor = field(default_factory=Advisor)
    investors: list[InvestorSpec] = field(default_factory=list)
    sigma_ind: float = 1.0        # 独立判断のノイズ
    seed: int = 0

    def __post_init__(self) -> None:
        if not (0.0 <= self.rho <= 1.0):
            raise ValueError("rho must be in [0, 1]")
        if self.n_advisors < 1:
            raise ValueError("need at least one advisor")
        for spec in self.investors:
            if spec.advisor is not None and not (0 <= spec.advisor < self.n_advisors):
                raise ValueError(f"advisor index {spec.advisor} out of range")


def mixed_investors(n_follower: int, n_threshold: int, n_independent: int,
                    n_advisors: int, tau: float = 1.0) -> list[InvestorSpec]:
    """追随タイプ混成の標準構成 — follower/threshold は助言者にラウンドロビン割当。"""
    out: list[InvestorSpec] = []
    for i in range(n_follower):
        out.append(InvestorSpec("follower", advisor=i % n_advisors))
    for i in range(n_threshold):
        out.append(InvestorSpec("threshold", advisor=i % n_advisors, tau=tau))
    for _ in range(n_independent):
        out.append(InvestorSpec("independent"))
    return out


@dataclass
class SimResult:
    dm: DecisionMatrix            # 投票行列 (+1/-1、欠測なし)
    mu: np.ndarray                # (P,) 議案の質 (正解)
    recommendations: np.ndarray   # (A, P) 助言推奨 ±1
    shared_map: np.ndarray        # (P,) g_j 共有地図成分 (正解)
    investor_specs: list[InvestorSpec]
    config: MeetingSimConfig
    outcomes: np.ndarray          # (P,) 多数決結果 ±1 (同数は 0)

    @property
    def split_cols(self) -> np.ndarray:
        """ID-g1: 助言者間で推奨が割れた議案のマスク (助言者2以上が前提)。"""
        if self.recommendations.shape[0] < 2:
            return np.zeros(len(self.mu), dtype=bool)
        return ~(self.recommendations == self.recommendations[0:1, :]).all(axis=0)


def simulate(cfg: MeetingSimConfig) -> SimResult:
    if not cfg.investors:
        raise ValueError("no investors configured")
    rng = np.random.default_rng(cfg.seed)
    P, A, N = cfg.n_proposals, cfg.n_advisors, len(cfg.investors)

    mu = rng.normal(size=P)
    g = rng.normal(size=P)                       # 共有地図
    h = rng.normal(size=(A, P))                  # 助言者固有
    policy = cfg.rho * g[None, :] + np.sqrt(1.0 - cfg.rho ** 2) * h
    rec_signal = mu[None, :] + cfg.advisor.sigma_pol * policy
    recs = np.where(rec_signal >= 0, 1.0, -1.0)  # (A, P)

    votes = np.empty((N, P))
    own = mu[None, :] + cfg.sigma_ind * rng.normal(size=(N, P))  # 各投資家の私的シグナル
    for i, spec in enumerate(cfg.investors):
        if spec.kind == "independent":
            votes[i] = np.where(own[i] >= 0, 1.0, -1.0)
        elif spec.kind == "follower":
            votes[i] = recs[spec.advisor]
        else:  # threshold
            follow = np.abs(own[i]) <= spec.tau
            votes[i] = np.where(follow, recs[spec.advisor],
                                np.where(own[i] >= 0, 1.0, -1.0))

    tally = votes.sum(axis=0)
    outcomes = np.sign(tally)

    dm = DecisionMatrix(
        values=votes,
        row_ids=[f"inv{i:03d}_{s.kind[:3]}" for i, s in enumerate(cfg.investors)],
        col_ids=[f"p{j:05d}" for j in range(P)],
    )
    return SimResult(dm=dm, mu=mu, recommendations=recs, shared_map=g,
                     investor_specs=list(cfg.investors), config=cfg, outcomes=outcomes)
