"""IV-1 実験: 助言者数 × ポリシー重複度の操作 → モノカルチャー指標と厚生の応答。

実行: uv run python -m yh010g.sim.experiment
出力: data/processed/yh010g/iv1_report.json (介入は共有 Intervention API で記録)

介入→応答→識別の三つ組 (TwinMarket 禁止則):
  介入   = advisor_correlation (n_advisors, rho)
  応答   = モノカルチャー指標 (k=1)・情報集約効率・選択品質
  識別   = ID-g1 (推奨分裂列上の因子が助言者割当を回復するか) は tests 側で検証
数値は装置検証の記述統計であり、厚生比較の主張は実データ較正+事前登録後に行う。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from agora_engine import Intervention, fit_pca_em, git_sha, monoculture_index, utcnow_iso
from yh010g.sim.engine import Advisor, MeetingSimConfig, mixed_investors, simulate
from yh010g.sim.welfare import aggregation_efficiency, selection_quality

OUT_DIR = Path("data/processed/yh010g")

# 追随タイプ混成の2設定 (docs/2026-07-23-YH010g-share-and-novelty-survey.md の較正方針):
#   jp: 資産運用業協会2025 — 機械的追従はほぼ皆無、執行委託・閾値的利用が主
#   us: Matsusaka & Shu — robo-voting 33% (2021)
MIXES = {
    "jp": {"n_follower": 1, "n_threshold": 14, "n_independent": 5},
    "us": {"n_follower": 7, "n_threshold": 8, "n_independent": 5},
}


def run_sweep(n_proposals: int = 4000, seeds: tuple = (0, 1, 2, 3, 4)) -> dict:
    arms = []
    for mix_name, mix in MIXES.items():
        for n_adv in (1, 2, 5):
            for rho in (0.0, 0.5, 0.9):
                arms.append({"mix": mix_name, "n_advisors": n_adv, "rho": rho, **mix})

    results = []
    for arm in arms:
        iv = Intervention(t=0, type="advisor_correlation", target="market",
                          params={"n_advisors": arm["n_advisors"], "rho": arm["rho"],
                                  "mix": arm["mix"]})
        vals = {"monoculture_k1": [], "agg_eff": [], "sel_q": []}
        for seed in seeds:
            cfg = MeetingSimConfig(
                n_proposals=n_proposals, n_advisors=arm["n_advisors"], rho=arm["rho"],
                advisor=Advisor(sigma_pol=1.0),
                investors=mixed_investors(arm["n_follower"], arm["n_threshold"],
                                          arm["n_independent"], arm["n_advisors"]),
                seed=seed)
            res = simulate(cfg)
            dmf = res.dm.filter_cols(min_observed=2, min_minority_share=0.05)
            vals["monoculture_k1"].append(monoculture_index(fit_pca_em(dmf, k=1, max_iter=80)))
            vals["agg_eff"].append(aggregation_efficiency(res))
            vals["sel_q"].append(selection_quality(res))
        summary = {m: {"mean": float(np.mean(v)), "se": float(np.std(v, ddof=1) / np.sqrt(len(v)))}
                   for m, v in vals.items()}
        results.append({"arm": arm, "intervention": iv.to_dict(), "metrics": summary,
                        "n_seeds": len(seeds)})

    report = {
        "experiment": "IV-1 advisor correlation sweep",
        "created_at": utcnow_iso(),
        "code_sha": git_sha(),
        "n_proposals": n_proposals,
        "arms": results,
        "note": "装置検証の記述統計。厚生比較の主張は実データ較正+事前登録後。",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "iv1_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def _print_table(report: dict) -> None:
    print(f"{'mix':<4}{'A':>3}{'rho':>5} | {'monoculture':>12} {'agg_eff':>9} {'sel_q':>8}")
    for r in report["arms"]:
        a, m = r["arm"], r["metrics"]
        print(f"{a['mix']:<4}{a['n_advisors']:>3}{a['rho']:>5.1f} | "
              f"{m['monoculture_k1']['mean']:>7.3f}±{m['monoculture_k1']['se']:.3f} "
              f"{m['agg_eff']['mean']:>8.3f} {m['sel_q']['mean']:>8.3f}")


if __name__ == "__main__":
    _print_table(run_sweep())
