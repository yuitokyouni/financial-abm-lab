"""YH005: CLI ランチャー (既存シリーズ規約のエントリポイント).

Usage:
    cd experiments/YH005
    python run_simulation.py baseline        --seed 777    # §8.4 ベースライン
    python run_simulation.py null_tests      --seed 777    # 論文2 Fig.11 再現
    python run_simulation.py compare_three   --seed 123    # 3 モデル比較

各 mode は baseline.py / null_tests.py / compare_three_models.py の run_* を呼ぶ薄いラッパ。
"""

from __future__ import annotations

import argparse


def main():
    parser = argparse.ArgumentParser(description="YH005 Speculation Game (Lite) launcher")
    parser.add_argument(
        "mode",
        choices=["baseline", "null_tests", "compare_three"],
        help="実行する mode",
    )
    parser.add_argument("--seed", type=int, default=None,
                        help="乱数 seed (mode ごとのデフォルト: baseline/null=777, compare=123)")
    args = parser.parse_args()

    if args.mode == "baseline":
        from baseline import run_baseline
        run_baseline(seed=args.seed if args.seed is not None else 777)
    elif args.mode == "null_tests":
        from null_tests import run_null_tests
        run_null_tests(seed=args.seed if args.seed is not None else 777)
    elif args.mode == "compare_three":
        from compare_three_models import run_compare
        run_compare(seed=args.seed if args.seed is not None else 123)


if __name__ == "__main__":
    main()
