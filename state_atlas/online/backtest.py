"""Walk-forward paper backtest of the Phase 8 strategies.

Strict no-leakage protocol per window:

  for each rolling window (train_idx, test_idx):
      atlas      = fit_train_window(op_df.loc[train_idx])
      F_test     = project_new(atlas, log_vix_test, term_slope_test)
      states     = classify_series(F_test, slope_test, atlas)   # causal run-lengths
      for t in test_idx:
          target_t = strategy_fn(state_t, atlas)
          # Execute at close_t: returns realized close_t → close_{t+1}.

Transaction cost = |Δweight| × cost_bps applied per turn per asset.
``slippage_bps`` is identical in form but conceptually separate; total drag
per turn per asset = (cost + slippage) × |Δw|.

null baselines:
  buy_and_hold_svxy  — always 100% SVXY
  naive_always_carry — same as above but rebalanced to 100% SVXY every step
                       (so tcost shows up; useful for honest comparison vs the
                       strategies, which also pay tcost when they switch)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from state_atlas.online.monitor import TrainedAtlas, fit_train_window, project_new
from state_atlas.online.state_machine import State, StateConfig, classify_series
from state_atlas.online.strategy import StrategyConfig

_DEFAULT_STATE_CFG = StateConfig()
_DEFAULT_STRATEGY_CFG = StrategyConfig()

StrategyFn = Callable[[State, TrainedAtlas, StrategyConfig], dict[str, float]]


@dataclass(frozen=True)
class BacktestConfig:
    train_days: int = 252  # 1y train per window
    test_days: int = 252  # 1y test per window
    step_days: int = 63  # roll quarterly
    cost_bps_per_turn: float = 5.0
    slippage_bps_per_turn: float = 5.0


@dataclass
class BacktestResult:
    name: str
    equity: pd.Series  # cumulative equity, starts at 1.0
    daily_returns: pd.Series
    weights: pd.DataFrame  # per-day asset weights
    turnover: float  # average daily |Δw| sum across assets
    metrics: dict


def _annualize_sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    if returns.std() == 0 or len(returns) < 2:
        return float("nan")
    return float(np.sqrt(periods_per_year) * returns.mean() / returns.std())


def _max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return float(dd.min())


def _tail_metric(returns: pd.Series, q: float = 0.01) -> float:
    """Mean return on the worst q-quantile days (CVaR-like)."""
    n = max(1, int(len(returns) * q))
    return float(returns.nsmallest(n).mean())


def _apply_costs(prev_w: dict[str, float], new_w: dict[str, float], cost_bps: float) -> float:
    """Cost drag in fractional terms (per dollar of capital)."""
    keys = set(prev_w) | set(new_w)
    turn = sum(abs(new_w.get(k, 0.0) - prev_w.get(k, 0.0)) for k in keys)
    return turn * cost_bps / 10_000.0


def _simulate(
    asset_returns: pd.DataFrame,
    weight_series: pd.DataFrame,
    cost_bps_per_turn: float,
    slippage_bps_per_turn: float,
    name: str,
) -> BacktestResult:
    """Take weights known at close_t, realize returns over (t, t+1)."""
    common = asset_returns.index.intersection(weight_series.index)
    rets = asset_returns.loc[common].fillna(0.0)
    w = weight_series.loc[common].fillna(0.0)
    # Align asset columns: missing assets default to 0 return / 0 weight.
    assets = sorted(set(rets.columns) | set(w.columns))
    rets = rets.reindex(columns=assets, fill_value=0.0)
    w = w.reindex(columns=assets, fill_value=0.0)

    # daily strategy return = sum_a w_t[a] * r_{t+1}[a] − transaction drag at t
    strat_ret = (w.shift(0) * rets.shift(-1)).sum(axis=1)
    # transaction cost when w changes from t-1 to t (paid at t)
    dw = w.diff().abs().sum(axis=1).fillna(w.iloc[0].abs().sum())
    cost = dw * (cost_bps_per_turn + slippage_bps_per_turn) / 10_000.0
    daily = (strat_ret - cost).dropna()
    equity = (1.0 + daily).cumprod()
    metrics = {
        "sharpe": _annualize_sharpe(daily),
        "ann_return": float((1 + daily.mean()) ** 252 - 1),
        "ann_vol": float(daily.std() * np.sqrt(252)),
        "max_drawdown": _max_drawdown(equity),
        "cvar_1pct": _tail_metric(daily, q=0.01),
        "worst_day": float(daily.min()),
        "best_day": float(daily.max()),
        "n_days": int(len(daily)),
        "avg_daily_turnover": float(dw.mean()),
    }
    return BacktestResult(
        name=name,
        equity=equity,
        daily_returns=daily,
        weights=w,
        turnover=float(dw.mean()),
        metrics=metrics,
    )


def walk_forward_strategy(
    op_df: pd.DataFrame,  # full (log_vix, term_slope) series, daily
    asset_returns: pd.DataFrame,  # per-asset daily simple returns
    strategy_fn: StrategyFn,
    bt_cfg: BacktestConfig,
    state_cfg: StateConfig = _DEFAULT_STATE_CFG,
    strat_cfg: StrategyConfig = _DEFAULT_STRATEGY_CFG,
    name: str = "strategy",
) -> BacktestResult:
    """Roll train→test windows; concatenate test-window weights into one series."""
    idx = op_df.index
    weights_records: list[pd.DataFrame] = []

    start = bt_cfg.train_days
    while start + bt_cfg.test_days <= len(idx):
        train_idx = idx[start - bt_cfg.train_days : start]
        test_end = min(start + bt_cfg.test_days, len(idx))
        test_idx = idx[start:test_end]

        atlas = fit_train_window(op_df.loc[train_idx])
        log_vix_test = op_df.loc[test_idx, "log_vix"].to_numpy()
        slope_test = op_df.loc[test_idx, "term_slope"].to_numpy()
        F_test = project_new(atlas, log_vix_test, slope_test)
        states = classify_series(
            pd.Series(F_test, index=test_idx, name="F"),
            pd.Series(slope_test, index=test_idx, name="slope"),
            atlas,
            state_cfg,
        )

        # Build per-asset weight matrix for the test window.
        row_w = []
        for ts, row in states.iterrows():
            from state_atlas.online.state_machine import State as S

            st = S(
                label=row["label"],
                persistent_stress=bool(row["persistent_stress"]),
                F=float(row["F"]),
                term_slope=float(row["term_slope"]),
                backw_run=int(row["backw_run"]),
                F_p99_run=int(row["F_p99_run"]),
            )
            tw = strategy_fn(st, atlas, strat_cfg)
            row_w.append(pd.Series(tw, name=ts))
        weight_df = pd.DataFrame(row_w)
        weights_records.append(weight_df)

        start += bt_cfg.step_days

    if not weights_records:
        raise RuntimeError("no walk-forward windows fit within the data range")
    weights = pd.concat(weights_records).fillna(0.0)
    weights = weights[~weights.index.duplicated(keep="last")].sort_index()
    return _simulate(
        asset_returns, weights, bt_cfg.cost_bps_per_turn, bt_cfg.slippage_bps_per_turn, name
    )


def buy_and_hold(asset: str, asset_returns: pd.DataFrame, bt_cfg: BacktestConfig) -> BacktestResult:
    """100% one asset, no rebalancing (1 turn at t=0 only)."""
    w = pd.DataFrame(0.0, index=asset_returns.index, columns=[asset])
    w[asset] = 1.0
    return _simulate(
        asset_returns,
        w,
        bt_cfg.cost_bps_per_turn,
        bt_cfg.slippage_bps_per_turn,
        name=f"buy_and_hold_{asset}",
    )


def naive_always_carry(
    asset: str, asset_returns: pd.DataFrame, bt_cfg: BacktestConfig
) -> BacktestResult:
    """Same as buy_and_hold but rebalanced daily — fair tcost comparison."""
    w = pd.DataFrame(0.0, index=asset_returns.index, columns=[asset])
    w[asset] = 1.0
    res = _simulate(
        asset_returns,
        w,
        bt_cfg.cost_bps_per_turn,
        bt_cfg.slippage_bps_per_turn,
        name=f"naive_always_carry_{asset}",
    )
    return res
