"""calibrate_search — SF-等価 calibration の richer ランダム探索を実行(spec §5.2 拡張)。

T* を固定し H の (β, horizon レンジ) を SF1-4 距離最小化で探索。β 単独 grid では SF1/SF2 が
埋まらなかったため horizon レンジも入れる。coarse(小 M)。

実行: uv run python -m experiments.runners.calibrate_search
"""

from __future__ import annotations

from toy.calibration import calibrate_search


def main() -> None:
    best, sf_t, log = calibrate_search(seed=200, n_trials=60, n_runs=10)
    print("T* SF1-4:", {k: round(v, 3) for k, v in sf_t.items()})
    print(f"trials evaluated: {len(log)}")
    print()
    print("top 6 H candidates by distance:")
    for c in sorted(log, key=lambda x: x.distance)[:6]:
        sf = c.sf_h
        print(
            f"  beta={c.beta} hs={c.hs_range} dist={c.distance:.2f}  "
            f"SF1={sf['SF1']:.2f} SF2={sf['SF2']:.3f} SF3={sf['SF3']:.2f} SF4={sf['SF4']:.2f}"
        )
    print()
    print(f"BEST: beta={best.beta} hs={best.hs_range} dist={best.distance:.2f}")
    print("  H* SF1-4:", {k: round(v, 3) for k, v in best.sf_h.items()})


if __name__ == "__main__":
    main()
