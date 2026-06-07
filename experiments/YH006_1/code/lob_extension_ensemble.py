"""S5.8 LOB extension runner — C2/C3 × T=10000 × 数 seed (Mac 側専用).

S5.8 plan §2.2 (v1.1 で S3 等価チェックを前倒し):
  1. S3 等価チェック (fail-fast、~7 分): C3 seed=1000 を override main_steps=1500
     で 1 回走らせ、archived S3 出力 (data/C3/) と semantic 一致確認。
     override=1500 == S3 default が成立しなければ、PAMS のどこかに run 長が
     前半 [0,1500] に漏れる経路がある = 12 trial (2h) を走らせる前に止める
  2. determinism guard: C3 seed=1000 を main_steps=3000 (短縮版) で 2 回独立 run、
     4 parquet sha256 + rt_df semantic 比較 (override 機構 + worker の決定性)
  3. C2/C3 × seed 1000-1005 を main_steps=10000 で並列実行、
     `data/{cond}_T10k/` に 4 schema parquet 出力

集計 (KM 延長 + H_frozen / H_transient 判定) は Windows 側
`survival_extension.py` (S5.8 §2.3) の分業。

Run (Mac):
  cd experiments/YH006_1
  python -m code.lob_extension_ensemble --determinism-only   # guard のみ
  python -m code.lob_extension_ensemble                      # 12 trial
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from config import CONDITIONS, ENSEMBLE_SEED_BASE  # noqa: E402
from parallel import run_parallel_trials, default_n_workers  # noqa: E402

DATA_DIR = YH006_1 / "data"
LOGS_DIR = YH006_1 / "logs"

CONDS_DEFAULT = ["C2", "C3"]
N_SEEDS_DEFAULT = 6           # S5.8 plan §1.2 — 方向判定には 6 seed で十分
MAIN_STEPS_DEFAULT = 10_000   # T=5000 は nested で読む (plan §1.1)
GUARD_MAIN_STEPS = 3_000      # determinism guard は短縮版


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S5.8")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S5.8_lob_extension.log", encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def out_dir_for(cond: str, main_steps: int) -> Path:
    """T 別の出力 dir。main_steps=10000 → data/C2_T10k/ (S5.8 plan §2.1)。"""
    return DATA_DIR / f"{cond}_T{main_steps // 1000}k"


# ---------------------------------------------------------------------------
# Determinism guard — main_steps override 経路 (S5.8 plan §2.2 / 停止トリガー 1)
# ---------------------------------------------------------------------------

def _hash_parquet(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def determinism_guard_extension(
    cond: str, seed: int, main_steps: int, logger: logging.Logger,
) -> bool:
    """cond seed を main_steps 短縮版で 2 回独立 run、bit/semantic 一致確認。

    lob_ensemble.determinism_guard_lob と同 protocol、main_steps override 経路のみ
    異なる (override が RNG 消費順を変えないかの検証が本 guard の目的)。
    """
    from run_experiment import run_lob_trial
    a_dir = DATA_DIR / "_guard_ext_a"
    b_dir = DATA_DIR / "_guard_ext_b"
    a_dir.mkdir(parents=True, exist_ok=True)
    b_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"[guard] extension determinism: {cond} seed={seed} "
        f"main_steps={main_steps} × 2 runs"
    )
    run_lob_trial(cond, seed, main_steps=main_steps).to_parquets(a_dir)
    run_lob_trial(cond, seed, main_steps=main_steps).to_parquets(b_dir)

    all_match = True
    for prefix in ("trial", "agents", "lifetimes", "wealth_ts"):
        fname = f"{prefix}_{seed:04d}.parquet"
        ha, hb = _hash_parquet(a_dir / fname), _hash_parquet(b_dir / fname)
        match = ha == hb
        all_match = all_match and match
        logger.info(
            f"[guard] {fname}: {'MATCH' if match else 'MISMATCH'} "
            f"(a={ha[:16]}... b={hb[:16]}...)"
        )

    cols_rt = ["agent_id", "rt_idx", "t_open", "t_close", "horizon",
               "direction", "q", "delta_g"]
    rt_a = pd.read_parquet(a_dir / f"trial_{seed:04d}.parquet")[cols_rt].to_numpy()
    rt_b = pd.read_parquet(b_dir / f"trial_{seed:04d}.parquet")[cols_rt].to_numpy()
    semantic_match = np.array_equal(rt_a, rt_b)
    logger.info(f"[guard] rt_df semantic: {'PASS' if semantic_match else 'FAIL'}")

    if not all_match and not semantic_match:
        logger.error("[guard] determinism FAILED (sha256 + semantic both fail)")
        return False
    if not all_match:
        logger.warning("[guard] sha256 mismatch but semantic match — PASS 扱い (S3 と同)")
    return True


# ---------------------------------------------------------------------------
# S3 等価チェック (S5.8 plan v1.1 P1) — override=1500 == archived S3 を fail-fast
# ---------------------------------------------------------------------------

def s3_equivalence_check(
    cond: str, seed: int, logger: logging.Logger,
) -> bool:
    """override main_steps=1500 の 1 run が archived S3 出力と semantic 一致するか。

    determinism guard (main_steps=3000) は S3 参照を持たないため、
    『override 経路が default 経路と同一』はこのチェックだけが確定させる。
    比較は semantic (rt_df 全列 + lifetimes の (t_birth, t_end, censored) 集合) —
    parquet metadata 差で sha256 が割れても中身一致なら PASS (S3 guard と同規約)。
    """
    from run_experiment import run_lob_trial
    ref_dir = DATA_DIR / cond
    ref_trial = ref_dir / f"trial_{seed:04d}.parquet"
    ref_lt = ref_dir / f"lifetimes_{seed:04d}.parquet"
    if not (ref_trial.exists() and ref_lt.exists()):
        logger.error(f"[s3-check] archived S3 data なし: {ref_trial}")
        return False

    logger.info(f"[s3-check] {cond} seed={seed} を override main_steps=1500 で実行")
    out_dir = DATA_DIR / "_guard_s3_equiv"
    out_dir.mkdir(parents=True, exist_ok=True)
    run_lob_trial(cond, seed, main_steps=1500).to_parquets(out_dir)

    cols_rt = ["agent_id", "rt_idx", "t_open", "t_close", "horizon",
               "direction", "q", "delta_g"]
    rt_new = pd.read_parquet(out_dir / f"trial_{seed:04d}.parquet")[cols_rt].to_numpy()
    rt_ref = pd.read_parquet(ref_trial)[cols_rt].to_numpy()
    rt_match = np.array_equal(rt_new, rt_ref)

    cols_lt = ["t_birth", "t_end", "censored"]
    lt_new = pd.read_parquet(out_dir / f"lifetimes_{seed:04d}.parquet")
    lt_ref = pd.read_parquet(ref_lt)
    lt_match = (
        sorted(map(tuple, lt_new[cols_lt].to_numpy().tolist()))
        == sorted(map(tuple, lt_ref[cols_lt].to_numpy().tolist()))
    )
    logger.info(
        f"[s3-check] rt_df ({len(rt_new)} vs {len(rt_ref)} rows): "
        f"{'MATCH' if rt_match else 'MISMATCH'} | "
        f"lifetimes ({len(lt_new)} vs {len(lt_ref)}): "
        f"{'MATCH' if lt_match else 'MISMATCH'}"
    )
    return rt_match and lt_match


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conds", type=str, default=",".join(CONDS_DEFAULT))
    parser.add_argument("--seed-base", type=int, default=ENSEMBLE_SEED_BASE)
    parser.add_argument("--n-seeds", type=int, default=N_SEEDS_DEFAULT)
    parser.add_argument("--main-steps", type=int, default=MAIN_STEPS_DEFAULT)
    parser.add_argument("--n-workers", type=int, default=None)
    parser.add_argument("--skip-determinism", action="store_true")
    parser.add_argument("--determinism-only", action="store_true")
    parser.add_argument("--skip-s3-check", action="store_true",
                        help="S3 等価チェック (override=1500 == archived S3) を skip")
    args = parser.parse_args()

    logger = setup_logger()
    n_workers = args.n_workers or default_n_workers()
    seeds: List[int] = list(range(args.seed_base, args.seed_base + args.n_seeds))
    conds = [c.strip() for c in args.conds.split(",") if c.strip()]
    for c in conds:
        assert CONDITIONS[c].world == "lob", f"{c} is not LOB cond"
        assert CONDITIONS[c].q_rule != "const", \
            f"{c}: S5.8 は baseline cond のみ (ablation cond は scope 外)"

    logger.info("=" * 70)
    logger.info(
        f"S5.8 LOB extension — conds={conds}, seeds={seeds}, "
        f"main_steps={args.main_steps}, n_workers={n_workers}"
    )
    logger.info("=" * 70)

    guard_cond = "C3" if "C3" in conds else conds[0]

    # ----- Step A0: S3 等価チェック (P1、fail-fast、~7 分) -----
    s3_pass = True
    if not args.skip_s3_check:
        s3_pass = s3_equivalence_check(guard_cond, args.seed_base, logger)
        if not s3_pass:
            logger.error(
                "S3 等価チェック FAILED — override=1500 != archived S3。"
                "run 長が前半 [0,1500] に漏れる経路あり、12 trial を中止して "
                "Yuito 相談 (plan §4)"
            )
            return

    # ----- Step A: determinism guard (main_steps override 経路、短縮版) -----
    determinism_pass = True
    if not args.skip_determinism:
        determinism_pass = determinism_guard_extension(
            guard_cond, args.seed_base, GUARD_MAIN_STEPS, logger,
        )
        if not determinism_pass:
            logger.error("Determinism guard FAILED — aborting (Yuito 相談、plan §4)")
            return

    if args.determinism_only:
        logger.info("--determinism-only mode、guard のみ完了して終了")
        return

    # ----- Step B: 12 trial 並列実行 -----
    runtimes = {}
    for cond in conds:
        cond_dir = out_dir_for(cond, args.main_steps)
        results = run_parallel_trials(
            cond, seeds, cond_dir, n_workers, logger,
            main_steps=args.main_steps,
        )
        runtimes[cond] = {str(s): rt for (s, rt, _, _, err) in results if err is None}
        errs = [(s, err) for (s, rt, _, _, err) in results if err]
        if errs:
            logger.error(f"[main] {cond}: {len(errs)} trial errored — 確認要")
        # plan §4 停止トリガー: > 4 時間/trial
        slow = [s for (s, rt, _, _, err) in results if err is None and rt > 4 * 3600]
        if slow:
            logger.error(
                f"[main] {cond}: seeds {slow} が 4 時間/trial 超過 — "
                f"stop trigger (plan §4)、Yuito 相談"
            )

    summary = {
        "stage": "S5.8-mac",
        "conds": conds,
        "seeds": seeds,
        "main_steps": args.main_steps,
        "guard_main_steps": GUARD_MAIN_STEPS,
        "n_workers": n_workers,
        "s3_equivalence_pass": s3_pass,
        "determinism_pass": determinism_pass,
        "runtimes_sec": runtimes,
        "timestamp": datetime.now().isoformat(),
    }
    with open(LOGS_DIR / "S5.8_mac_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"summary written: {LOGS_DIR / 'S5.8_mac_summary.json'}")

    logger.info("=" * 70)
    logger.info("S5.8 LOB extension (sim part) complete.")
    logger.info("git add data/ logs/ && git commit && git push → Windows 側で")
    logger.info("python -m code.survival_extension を実行する。")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
