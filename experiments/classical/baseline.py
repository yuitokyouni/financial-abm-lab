"""Compatibility aggregate. Canonical entry points are experiments.YH001–YH004."""
from experiments.YH001.baseline import run_baseline as run_cont_bouchaud
from experiments.YH002.baseline import run_baseline as run_lux_marchesi
from experiments.YH003.baseline import run_baseline as run_minority_game
from experiments.YH004.baseline import run_baseline as run_gcmg
from experiments.YH003.baseline import _sigma2_over_N

def run_all(seed: int = 42) -> list[dict]:
    out = [run_cont_bouchaud(seed), run_lux_marchesi(seed), run_minority_game(seed), run_gcmg(seed)]
    for row in out:
        print(row)
    return out

if __name__ == "__main__":
    run_all()
