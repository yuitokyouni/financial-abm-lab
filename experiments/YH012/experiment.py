"""YH012 WorldExperiment — lobcore Experiment を薄いラッパで包む。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from lobcore import BatchAdapter, ExperimentMeta, Kernel, KernelConfig, write_log_file
from lobcore.experiment import ExperimentResult
from lobcore.log import LOG_DTYPE

from .agents import AgentParams, SharedFundamental, build_world_agents
from .metrics import WorldStats, compute_world_stats
from .version import default_lobcore_root, lobcore_git_hash


def _kernel_log(kernel: Kernel) -> np.ndarray:
    raw = kernel.log_bytes()
    if not raw:
        return np.empty(0, dtype=LOG_DTYPE)
    return np.frombuffer(raw, dtype=LOG_DTYPE).copy()


@dataclass
class WorldRunResult:
    result: ExperimentResult
    stats: WorldStats
    fundamental: SharedFundamental


class WorldExperiment:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.seed = int(config["seed"])
        self.end_time = int(config["end_time"])
        self.rule = str(config.get("rule", "price_time"))
        agents_cfg = config.get("agents", {})
        self.n_f = int(agents_cfg.get("n_fundamentalist", 20))
        self.n_c = int(agents_cfg.get("n_chartist", 30))
        self.n_n = int(agents_cfg.get("n_noise", 50))
        self.params = AgentParams(
            mean_wakeup=float(config.get("mean_wakeup", 800)),
            band=int(config.get("band", 30)),
            qty_min=int(config.get("qty_min", 1)),
            qty_max=int(config.get("qty_max", 5)),
            noise_offset_max=int(config.get("noise_offset_max", 15)),
            chartist_lookback=int(config.get("chartist_lookback", 3)),
        )
        self.f0 = int(config.get("f0", 10_000))
        # 時刻ステップあたり。大きすぎると mid が追従できず相関が壊れる
        self.f_sigma = float(config.get("f_sigma", 0.25))
        self.noise_take_prob = float(config.get("noise_take_prob", 0.15))
        self.chartist_take_prob = float(config.get("chartist_take_prob", 0.25))
        self.lobcore_root = Path(
            config.get("lobcore_root") or default_lobcore_root()
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> WorldExperiment:
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cls(cfg)

    def run(self) -> WorldRunResult:
        fundamental = SharedFundamental(f0=self.f0, sigma=self.f_sigma)
        agents = build_world_agents(
            n_f=self.n_f,
            n_c=self.n_c,
            n_n=self.n_n,
            fundamental=fundamental,
            params=self.params,
            noise_take_prob=self.noise_take_prob,
            chartist_take_prob=self.chartist_take_prob,
        )

        cfg = KernelConfig()
        cfg.end_time = self.end_time
        cfg.master_seed = self.seed
        kernel = Kernel(cfg)
        market_ids = [kernel.add_market(self.rule)]

        adapter = BatchAdapter(agents, strict=False)
        ids = kernel.add_batch_agents(adapter.step, len(agents))
        adapter.bind_kernel(kernel)
        # f_t を run 前に確定（sentinel）。エージェント起床より前に消費し切る。
        fundamental.prepare(kernel, self.end_time)

        for aid in ids:
            kernel.schedule_wakeup(1, aid)
        kernel.run()

        version = lobcore_git_hash(self.lobcore_root)
        meta = ExperimentMeta(
            master_seed=self.seed,
            allocation_rule=self.rule,
            n_agents=len(agents),
            n_markets=len(market_ids),
            end_time=self.end_time,
            lobcore_version=version,
            agent_config={
                "yh012": "phase1_world",
                "n_fundamentalist": self.n_f,
                "n_chartist": self.n_c,
                "n_noise": self.n_n,
                "mean_wakeup": self.params.mean_wakeup,
                "band": self.params.band,
                "f0": self.f0,
                "f_sigma": self.f_sigma,
                "config": self.config,
            },
        )
        state_hash = 0
        for mid in market_ids:
            state_hash ^= kernel.market_state_hash(mid)

        result = ExperimentResult(log=_kernel_log(kernel), meta=meta, state_hash=state_hash)
        stats = compute_world_stats(result.log, fundamental.values)
        return WorldRunResult(result=result, stats=stats, fundamental=fundamental)

    def save_log(self, path: str | Path, run: WorldRunResult) -> None:
        write_log_file(str(path), run.result.meta, run.result.log)
