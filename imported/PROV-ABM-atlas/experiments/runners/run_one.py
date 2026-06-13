"""run_one — 1 simulation run のエントリ(Hydra)。

config を合成 → seed 確定 → 集団生成 → run_simulation → parquet + ctx_log + prov.json 出力。
provenance は L2 minimum(spec §13.1)。`reach_claim` は reported 固定。

CLI:
    uv run python -m experiments.runners.run_one              # market=default(spec 値、重い)
    uv run python -m experiments.runners.run_one market=dev   # 小サイズ、秒オーダー
    uv run python -m experiments.runners.run_one agents=H seed=3

注意: market=default は spec 値(N=500 × 11000 step)。L2 capture は per-call 記録のため
大サイズでは ctx_log が巨大化する。full-scale sweep は将来 L1 + ベクトル化カーネルで回す。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf
from provabm.capture import CaptureLevel, CaptureSink
from provabm.provenance import (
    ProvenanceRecorder,
    output_basename,
    prov_path_for,
    seed_dict,
    write_ctx_log_parquet,
)
from toy.agents import make_population
from toy.market import MarketParams, RunResult, run_simulation

_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class RunArtifacts:
    output_path: Path
    ctx_log_path: Path
    prov_path: Path
    n_steps: int
    uuid: str


def _result_frame(result: RunResult) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "step": result.steps,
            "price": result.price,
            "return": result.returns,
            "excess_demand": result.excess_demand,
            "volume": result.volume,
            "agg_action": result.agg_action,
        }
    )


def run(cfg: DictConfig, *, repo: Path | str | None = _REPO_ROOT) -> RunArtifacts:
    """config から 1 run を実行し、出力・ctx_log・prov.json を書いて成果物パスを返す。"""
    params = MarketParams(
        n_agents=int(cfg.market.n_agents),
        lam=float(cfg.market.lam),
        p_star=float(cfg.market.p_star),
        obs_window=int(cfg.market.obs_window),
        burn_in=int(cfg.market.burn_in),
        measure=int(cfg.market.measure),
        init_price=float(cfg.market.init_price),
    )
    seed = int(cfg.seed)

    # seed stream を param 用 1 本 + agent 用 N 本に決定的に分岐(再現性・並列安全)。
    param_ss, *agent_ss = np.random.SeedSequence(seed).spawn(1 + params.n_agents)
    param_rng = np.random.default_rng(param_ss)
    decision_rngs = [np.random.default_rng(s) for s in agent_ss]

    agents = make_population(str(cfg.agents.model), params.n_agents, param_rng)
    capture = CaptureSink(CaptureLevel[str(cfg.capture_level)])

    result = run_simulation(params, agents, decision_rngs, capture)

    # provenance(出力前に開始メタ確定 → config_hash で命名)。
    config_yaml = OmegaConf.to_yaml(cfg, resolve=True)
    recorder = ProvenanceRecorder(
        config_yaml=config_yaml,
        seed=seed_dict(numpy=seed, python=seed, torch=None),
        repo=repo,
    )

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    basename = output_basename(recorder.config_hash_hex, seed, recorder.uuid)
    output_path = out_dir / f"{basename}.parquet"
    ctx_log_path = out_dir / f"{basename}.ctx.parquet"

    _result_frame(result).to_parquet(output_path, index=False)
    write_ctx_log_parquet(capture.to_records(), ctx_log_path)

    prov = recorder.complete(output_path=output_path, ctx_log_path=ctx_log_path)
    prov_path = prov.write(prov_path_for(output_path))

    return RunArtifacts(
        output_path=output_path,
        ctx_log_path=ctx_log_path,
        prov_path=prov_path,
        n_steps=len(result.steps),
        uuid=recorder.uuid,
    )


@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    arts = run(cfg)
    print(f"run {arts.uuid}: {arts.n_steps} steps")
    print(f"  output : {arts.output_path}")
    print(f"  ctx_log: {arts.ctx_log_path}")
    print(f"  prov   : {arts.prov_path}")


if __name__ == "__main__":
    main()
