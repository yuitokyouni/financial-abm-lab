"""equivalence_check — SF 等価性検証 + Null-1(spec §14 decision tree の step 1-2)。

校正ループの KPI 計器: 両 SF classifier(LR on SF1-4 / 1D-CNN on returns)で
  - **Null-1**(T* vs T* 異 seed): 両者 50±3% でなければ harness が壊れている(続行不可)。
  - **SF 等価**(T* vs H*): §2.2 の entry condition を機械判定。
    Pass 50-55% / Soft fail 55-60% / Hard fail >60%。

注意: 本ランナーは toy scale(CALIB_MARKET, N=150)。spec §3.1 の paper-grade(N=500,
M=1000)ではない。toy §14 は screening(論文が存在するかのゲート)。

実行: uv run python -m experiments.runners.equivalence_check
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from provabm.capture import CaptureLevel, CaptureSink
from toy.agents.herd import build_herd_population
from toy.agents.trend import build_trend_population
from toy.calibration import CALIB_MARKET, T_STAR_ALPHA, calibrate_sf_equivalent
from toy.classifiers import sf_cnn_cv_accuracy, sf_summary_cv_accuracy
from toy.market import MarketParams, run_simulation
from toy.sf_battery import CALIBRATION_SF, measure_sf_battery

T_D_FULL = 1000  # CNN 入力窓長(spec §6.2、paper-grade)


@dataclass(frozen=True, slots=True)
class RunSet:
    """1 モデル点の M runs。sf: (M,4) SF1-4、ret: (M,T_d) 生 return 窓。"""

    sf: npt.NDArray[np.float64]
    ret: npt.NDArray[np.float64]


def generate_runs(
    model: str,
    mix: tuple[float, float, float],
    *,
    n_runs: int,
    base_seed: int,
    params: MarketParams = CALIB_MARKET,
    hs_range: tuple[int, int] | None = None,
) -> RunSet:
    """(model, mix) で n_runs 回まわし、SF1-4 行列と生 return 窓(末尾 T_d)を集める。"""
    t_d = min(T_D_FULL, params.measure)
    sf_rows: list[list[float]] = []
    ret_rows: list[npt.NDArray[np.float64]] = []
    for ri in range(n_runs):
        ss = np.random.SeedSequence(base_seed + ri).spawn(1 + params.n_agents)
        prng = np.random.default_rng(ss[0])
        agents = (
            build_trend_population(params.n_agents, prng, mix)
            if model == "T"
            else build_herd_population(params.n_agents, prng, mix, hs_range)
        )
        drngs = [np.random.default_rng(s) for s in ss[1:]]
        result = run_simulation(params, agents, drngs, CaptureSink(CaptureLevel.L0))
        sf = measure_sf_battery(result.returns, include_post=False)
        sf_rows.append([sf[k] for k in CALIBRATION_SF])
        r = np.asarray(result.returns, dtype=np.float64)
        window = r[-t_d:] if r.size >= t_d else np.concatenate([np.zeros(t_d - r.size), r])
        ret_rows.append(window)
    return RunSet(
        sf=np.asarray(sf_rows, dtype=np.float64),
        ret=np.asarray(ret_rows, dtype=np.float64),
    )


def _verdict(acc: float) -> str:
    if acc <= 0.55:
        return "PASS"
    if acc <= 0.60:
        return "SOFT-FAIL"
    return "HARD-FAIL"


def _classify(a: RunSet, b: RunSet, *, cnn_epochs: int, seed: int) -> tuple[float, float]:
    """2 つの RunSet を label 0/1 で結合し、LR / CNN の CV accuracy を返す。"""
    sf = np.vstack([a.sf, b.sf])
    ret = np.vstack([a.ret, b.ret])
    y = np.concatenate([np.zeros(len(a.sf), int), np.ones(len(b.sf), int)])
    lr = sf_summary_cv_accuracy(sf, y, seed=seed)
    cnn = sf_cnn_cv_accuracy(ret, y, seed=seed, epochs=cnn_epochs)
    return lr, cnn


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--m", type=int, default=40, help="eval runs / model")
    ap.add_argument("--calib-runs", type=int, default=6, help="calibration runs / candidate")
    ap.add_argument("--cnn-epochs", type=int, default=15)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--measure", type=int, default=0, help=">0 で measure を上書き(smoke)")
    ap.add_argument("--burnin", type=int, default=0, help=">0 で burn_in を上書き(smoke)")
    ap.add_argument(
        "--beta",
        type=float,
        nargs=3,
        default=None,
        help="H の (herder,fund,noise) を直接指定し校正を skip(smoke 用)",
    )
    args = ap.parse_args()

    from dataclasses import replace

    params = CALIB_MARKET
    if args.measure or args.burnin:
        params = replace(
            CALIB_MARKET,
            measure=args.measure or CALIB_MARKET.measure,
            burn_in=args.burnin or CALIB_MARKET.burn_in,
        )
    print(f"[market] N={params.n_agents} burn_in={params.burn_in} measure={params.measure}")

    if args.beta is not None:
        beta = (float(args.beta[0]), float(args.beta[1]), float(args.beta[2]))
        print(f"[calibrate] SKIPPED — fixed H β={beta} (smoke)")
    else:
        print(f"[calibrate] T* α={T_STAR_ALPHA}, coarse grid, n_runs={args.calib_runs} ...")
        pair, _log = calibrate_sf_equivalent(seed=args.seed, n_runs=args.calib_runs, params=params)
        beta = (pair.herd_params["herder"], pair.herd_params["fund"], pair.herd_params["noise"])
        print(f"[calibrate] H* β={tuple(round(b, 3) for b in beta)} dist={pair.distance:.3f}")
        print(f"           T* SF1-4={ {k: round(v, 3) for k, v in pair.sf_t.items()} }")
        print(f"           H* SF1-4={ {k: round(v, 3) for k, v in pair.sf_h.items()} }")

    print(f"[generate] M={args.m} runs each: T*, T*'(Null-1), H* ...")

    def gen(model: str, mix: tuple[float, float, float], off: int) -> RunSet:
        return generate_runs(model, mix, n_runs=args.m, base_seed=args.seed + off, params=params)

    t1 = gen("T", T_STAR_ALPHA, 10_000)
    t2 = gen("T", T_STAR_ALPHA, 20_000)
    h1 = gen("H", beta, 30_000)

    print("[classify] Null-1 (T* vs T*') ...")
    n_lr, n_cnn = _classify(t1, t2, cnn_epochs=args.cnn_epochs, seed=args.seed)
    print("[classify] Equivalence (T* vs H*) ...")
    e_lr, e_cnn = _classify(t1, h1, cnn_epochs=args.cnn_epochs, seed=args.seed)

    print("\n==================== §14 step 1-2 ====================")
    print(
        f"Null-1  (must be 50±3%): LR={n_lr:.3f}  CNN={n_cnn:.3f}  "
        f"-> {'OK' if max(abs(n_lr - 0.5), abs(n_cnn - 0.5)) <= 0.03 else 'BROKEN'}"
    )
    print(
        f"Equiv   (Pass<=0.55):    LR={e_lr:.3f} [{_verdict(e_lr)}]  "
        f"CNN={e_cnn:.3f} [{_verdict(e_cnn)}]"
    )
    overall = (
        "PASS"
        if e_lr <= 0.55 and e_cnn <= 0.55
        else ("SOFT-FAIL" if e_lr <= 0.60 and e_cnn <= 0.60 else "HARD-FAIL")
    )
    print(f"Equivalence verdict (both classifiers): {overall}")
    print("======================================================")
    print(f"注: toy scale (N=150, M={args.m}); paper-grade は N=500/M=1000 で別途事前登録。")


if __name__ == "__main__":
    main()
