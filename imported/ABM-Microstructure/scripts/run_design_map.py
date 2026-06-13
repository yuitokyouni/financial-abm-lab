"""tiered grid runner — 設計マップの実行入口（specs/002 US3、research D-B9）。

usage:
  python scripts/run_design_map.py --tier coarse --out results/coarse.csv \
      --budget-ledger results/budget.json
  python scripts/run_design_map.py --tier dense --around <cell-id> ...
  python scripts/run_design_map.py --tier robustness --headline <id>[,<id>...] ...
  python scripts/run_design_map.py --cell bcs-es-spy --out results/calib.csv ...

予算（学習期数）は BudgetLedger が enforce。超過する run は起動拒否され、拒否も
ledger に記録される。--t-max/--seeds/--limit は smoke 用の縮小オーバーライド
（本番予算見積りは LearnConfig 既定の t_max 基準）。

crash 耐性: セルが完了するたび --out に追記し（全完了を待たない）、再実行時は
既存 --out に載っているセルを skip する（resume）。skip の照合キーは **config_hash**
（seed を除く全 config フィールドの hash、CSV に永続化）——cell id に乗らない軸
（--noise-rate/--lr override、robustness 変種の eps_beta/gamma/tie_rule）でも
衝突しない。hash 列の無い旧 CSV へは cell id 照合に後方互換 fallback し、その場合
cell id が一意でない job 列は起動拒否する。worker プロセス喪失は当該 job だけ
落として続行し、charge は ledger に残る（lost compute の正直な記帳。大規模喪失は
BudgetLedger.reconcile で監査 entry 付きで精算する）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microstructure.calibrations import get_calibration  # noqa: E402
from microstructure.designmap import (BudgetExceeded, BudgetLedger, aggregate_cell,  # noqa: E402
                                      append_csv, cell_id, coarse_grid, config_hash,
                                      dense_neighbors, density_spoke, done_keys,
                                      parse_cell_id, robustness_variants, run_cell,
                                      run_one_seed, _planned_periods)


def _with_overrides(center, args):
    """cell id に乗らない軸（noise_rate, lr）の中心セル override。適用内容は log に出す。"""
    ov = {}
    if args.noise_rate is not None:
        ov["noise_rate"] = args.noise_rate
    if args.lr is not None:
        ov["lr"] = args.lr
    if ov:
        print(f"[center] overrides applied: {ov}", flush=True)
        center = center.replace(**ov)
    return center


def _seed_job(job_idx: int, cfg, seed: int):
    """並列 worker の単位（job_idx でセルを識別——robustness 変種は cell_id が
    衝突しうるため index キー）。"""
    m, ir, actual, rt = run_one_seed(cfg, seed)
    return job_idx, seed, m, ir, actual, rt


def _run_parallel(jobs, ledger, tier, workers, out):
    """親プロセスが ledger を専有（charge は submit 前・refund は完了時）。

    セル完了ごとに out へ追記。worker 喪失は当該 job のみ落として続行する
    （charge は残る——lost compute の正直な記帳。resume で再実行可能）。
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed
    points = []
    groups: dict[int, dict] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {}
        for j, (cfg, n_seeds) in enumerate(jobs):
            stop = False
            for s in range(n_seeds):
                planned = _planned_periods(cfg)
                try:
                    ledger.charge(tier, planned)
                except BudgetExceeded as e:
                    print(f"[budget] submission stopped at job {j}: {e}", flush=True)
                    stop = True
                    break
                futs[ex.submit(_seed_job, j, cfg, s)] = (j, planned)
            if stop:
                break
        for fut in as_completed(futs):
            jf, planned = futs[fut]
            try:
                j, seed, m, ir, actual, rt = fut.result()
            except Exception as e:
                print(f"[crash] job {jf} ({cell_id(jobs[jf][0])}) worker lost: {e!r}"
                      f" — charge は残る。resume で再実行", flush=True)
                continue
            ledger.refund(tier, planned - actual)
            g = groups.setdefault(j, {})
            g[seed] = (m, ir, actual, rt)
            cfg, n_seeds = jobs[j]
            if len(g) == n_seeds:
                ss = sorted(g)
                point = aggregate_cell(cfg, [g[k][0] for k in ss], [g[k][1] for k in ss],
                                       sum(g[k][2] for k in ss), sum(g[k][3] for k in ss))
                points.append(point)
                append_csv(point, out)
                print(f"[{len(points)}/{len(jobs)}] {point.cell}"
                      f" markup={point.markup_mean:.3f}±{point.markup_se:.3f}"
                      f" extr={point.extraction_mean:.4f} cert={point.certified}"
                      f" conv={point.converged_frac:.1f}"
                      f" ({point.runtime_sec:.0f}s cpu)", flush=True)
    return points


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", choices=["coarse", "dense", "robustness"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget-ledger", required=True)
    ap.add_argument("--around", help="dense: 中心 cell-id")
    ap.add_argument("--noise-rate", type=float,
                    help="中心セルの noise_rate override（cell id に乗らない軸。"
                         "density spoke の認定セルを headline に指す用）")
    ap.add_argument("--lr", type=float, help="中心セルの lr override（同上）")
    ap.add_argument("--dense-axis", choices=["nvol", "density"], default="nvol",
                    help="dense の軸: nvol=N×vol 近傍 / density=事象密度スポーク（finding 0002）")
    ap.add_argument("--headline", help="robustness: cell-id（カンマ区切り）")
    ap.add_argument("--cell", help="較正セル名（calibrations REGISTRY）")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--t-max", type=int, help="smoke 用に t_max を縮小")
    ap.add_argument("--limit", type=int, help="smoke 用にセル数を制限")
    ap.add_argument("--parallel", type=int, default=1,
                    help="(セル,seed) 単位の process 並列数（ledger は親が専有）")
    args = ap.parse_args(argv)

    if args.cell:
        calib = get_calibration(args.cell)
        base = calib.to_config()
        jobs = [(base.replace(mechanism="continuous", batch_interval=1), args.seeds)]
        jobs += [(base.replace(mechanism="batch", batch_interval=n), args.seeds)
                 for n in calib.batch_grid]
        jobs += [(cfg.replace(staleness="revisable"), s) for cfg, s in list(jobs)]
        tier = "robustness"
    elif args.tier == "coarse":
        jobs = [(cfg, args.seeds) for cfg in coarse_grid()]
        tier = "coarse"
    elif args.tier == "dense":
        if not args.around:
            ap.error("--tier dense requires --around <cell-id>")
        center = _with_overrides(parse_cell_id(args.around), args)
        builder = density_spoke if args.dense_axis == "density" else dense_neighbors
        jobs = [(cfg, args.seeds) for cfg in builder(center)]
        tier = "dense"
    elif args.tier == "robustness":
        if not args.headline:
            ap.error("--tier robustness requires --headline <cell-id,...>")
        jobs = []
        for cid in args.headline.split(","):
            jobs += robustness_variants(_with_overrides(parse_cell_id(cid.strip()), args))
        tier = "robustness"
    else:
        ap.error("either --tier or --cell is required")
        return 2

    if args.limit:
        jobs = jobs[: args.limit]
    if args.t_max:
        jobs = [(cfg.replace(t_max=args.t_max,
                             stable_window=min(cfg.stable_window, args.t_max // 4),
                             measure_periods=min(cfg.measure_periods, args.t_max // 10)),
                 s) for cfg, s in jobs]

    skipped = 0
    mode, done = done_keys(args.out)
    if done:
        keyf = config_hash if mode == "config_hash" else (lambda cfg: cell_id(cfg))
        ids = [keyf(cfg) for cfg, _ in jobs]
        if len(set(ids)) != len(ids):
            print(f"[resume] {mode} が一意でない job 列は resume 不可。"
                  f"既存 {args.out} を退避してから再実行すること", flush=True)
            return 2
        before = len(jobs)
        jobs = [(cfg, s) for cfg, s in jobs if keyf(cfg) not in done]
        skipped = before - len(jobs)
        print(f"[resume] {skipped}/{before} cells already in {args.out} — skipped"
              f" (key={mode})", flush=True)

    ledger = BudgetLedger(args.budget_ledger)
    if args.parallel > 1:
        points = _run_parallel(jobs, ledger, tier, args.parallel, args.out)
    else:
        points = []
        for i, (cfg, n_seeds) in enumerate(jobs):
            try:
                point, _, _ = run_cell(cfg, list(range(n_seeds)), ledger, tier)
            except BudgetExceeded as e:
                print(f"[budget] STOP at job {i}/{len(jobs)}: {e}")
                break
            points.append(point)
            append_csv(point, args.out)
            print(f"[{i + 1}/{len(jobs)}] {point.cell} markup={point.markup_mean:.3f}"
                  f"±{point.markup_se:.3f} extr={point.extraction_mean:.4f}"
                  f" cert={point.certified} conv={point.converged_frac:.1f}"
                  f" ({point.runtime_sec:.1f}s)", flush=True)
    print(f"done: {len(points)} new points (+{skipped} resumed) → {args.out}; "
          f"budget spent {ledger.total_spent:,} periods "
          f"({len(ledger.data['refusals'])} refusals)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
