"""adapters — bridge from `abm_models.REGISTRY` to the fingerprint pipeline.

Three responsibilities:

  1. `MODEL_BOUNDS` — LHS-samplable parameter ranges per model.
  2. `build_model(name, params)` — instantiate the dataclass with sampled params.
  3. `series_for_fingerprint(name, result)` — pull the series the fingerprint
     needs out of the model's result dict. Priceless models (MG/GCMG) use the
     excess-attendance series (2·A − N), which the MG literature itself uses as
     a volatility proxy.

Sizes are *reduced* (T≈2000-3000) so the full 8-model × LHS sweep runs in
minutes for the validation gate. Production calibration sizes can be plugged
in later by overriding bounds.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from abm_models import REGISTRY

PRICELESS_MODELS = {"minority_game", "gcmg"}

#: For models whose wrapper takes a nested `params=Params(...)` dataclass,
#: list which sampled keys belong to the *inner* params object. Anything not
#: in this set is treated as a wrapper-level kwarg.
_NESTED_PARAMS_KEYS: dict[str, set[str]] = {
    "chiarella_iori": {
        # NB: n_steps is set on the wrapper (ChiarellaIori.n_steps), NOT inside
        # CIParams. The wrapper copies it down. So n_steps is INTENTIONALLY
        # excluded from this nested set.
        "fundamental_value", "alpha_fund", "alpha_chart", "alpha_noise",
        "fund_speed", "fund_confidence", "chart_lag", "chart_strength",
        "noise_scale", "tick_size", "spread_ticks", "order_depth",
        "price_impact", "transaction_cost",
    },
    "franke_westerhoff": {
        "fundamental_value", "phi", "chi", "alpha_w", "alpha_o", "alpha_p",
        "sigma_f", "sigma_c", "noise_scale", "price_impact", "tick_size",
        "transaction_cost",
    },
    # lux_marchesi: wrapper takes Params, but our LHS bounds only sweep wrapper-level
    # knobs (n_integer_steps / steps_per_unit / n_c_init), so leave inner set empty.
    "lux_marchesi": set(),
}

#: Per-model parameter bounds for LHS sampling. T-like sizes are kept *small*
#: so the validation-gate pass is ~minutes, not hours. Bounds bracket the
#: regime where each model has been documented to produce its hallmark
#: stylized facts (see each model's reference).
MODEL_BOUNDS: dict[str, dict[str, tuple]] = {
    "speculation_game": {
        "N": (200, 400),
        "M": (3, 5),
        "S": (2, 3),
        "T": (2000, 2500),
        "B": (5, 12),
        "C": (1.5, 4.0),
    },
    "cont_bouchaud": {
        "N": (2000, 5000),
        "c": (0.5, 0.99),
        "a": (0.005, 0.02),
        "lam": (0.5, 2.0),
        "T": (2000, 3000),
    },
    "lux_marchesi": {
        "n_integer_steps": (2000, 3000),
        "steps_per_unit": (50, 100),
        "n_c_init": (30, 200),
    },
    "minority_game": {
        "N": (51, 151),
        "M": (3, 8),
        "S": (2, 4),
        "T": (2000, 3000),
    },
    "gcmg": {
        "N": (51, 151),
        "M": (2, 5),
        "S": (2, 3),
        "T_win": (20, 80),
        "T_total": (2500, 4000),
        "r_min_static": (0.0, 0.05),
    },
    "chiarella_iori": {
        # NOTE: REVERTED from v2. In v2 we widened noise/impact because CI baseline
        # was returning ~0 (degenerate). That was the measuring instrument being
        # bent to the specimen. The right answer is: CI *is* a low-vol thin-tail
        # specimen at default params, and the atlas should *show* that, not hide it.
        "n_steps": (2000, 3000),
        "alpha_fund": (0.2, 0.6),
        "alpha_chart": (0.1, 0.5),
        "alpha_noise": (0.1, 0.4),
        "fund_speed": (0.02, 0.1),
        "chart_strength": (0.3, 1.2),
        "noise_scale": (0.005, 0.02),
    },
    "zero_intelligence": {
        "n_steps": (2000, 3000),
        "n_agents": (50, 200),
        "noise_scale": (0.005, 0.02),
        "tick_size": (0.005, 0.05),
        "price_impact": (0.005, 0.05),
    },
    "franke_westerhoff": {
        "n_steps": (2000, 3000),
        "phi": (0.05, 0.25),
        "chi": (0.5, 2.0),
        "alpha_w": (1.0, 2.5),
        "noise_scale": (0.005, 0.02),
    },
}

#: Integer-valued parameter names (rounded after LHS sampling).
_INT_PARAMS = {
    "N", "M", "S", "T", "B", "T_win", "T_total",
    "n_steps", "n_integer_steps", "steps_per_unit", "n_c_init",
    "n_agents",
}


def sample_params_lhs(model_name: str, n: int, rng: np.random.Generator) -> list[dict[str, Any]]:
    """Latin-hypercube sample n parameter dicts from the bounds for `model_name`."""
    if model_name not in MODEL_BOUNDS:
        raise KeyError(f"no LHS bounds defined for {model_name}")
    bounds = MODEL_BOUNDS[model_name]
    keys = list(bounds.keys())
    d = len(keys)
    cut = np.linspace(0, 1, n + 1)
    u = rng.uniform(size=(n, d))
    pts = cut[:n, None] + u * (1.0 / n)
    for j in range(d):
        rng.shuffle(pts[:, j])

    out: list[dict[str, Any]] = []
    for i in range(n):
        kw: dict[str, Any] = {}
        for j, name in enumerate(keys):
            lo, hi = bounds[name]
            v = float(lo + pts[i, j] * (hi - lo))
            if name in _INT_PARAMS:
                v = int(round(v))
            kw[name] = v
        out.append(kw)
    return out


def build_model(name: str, params: dict[str, Any]):
    """Instantiate REGISTRY[name] with the given params.

    Model-specific quirks absorbed here so the caller passes flat dicts:
      - cont_bouchaud: silence the per-step progress print (report_every huge).
      - chiarella_iori / franke_westerhoff: split flat keys into wrapper kwargs
        + the nested Params dataclass, then build `params=Params(...)`.
    """
    if name not in REGISTRY:
        raise KeyError(f"unknown model {name}; REGISTRY={list(REGISTRY)}")
    cls = REGISTRY[name]
    p = dict(params)
    if name == "cont_bouchaud":
        p.setdefault("report_every", 10 ** 9)
    if name in _NESTED_PARAMS_KEYS and _NESTED_PARAMS_KEYS[name]:
        nested_keys = _NESTED_PARAMS_KEYS[name]
        inner = {k: p.pop(k) for k in list(p) if k in nested_keys}
        if inner:
            if name == "chiarella_iori":
                from abm_models.chiarella_iori import CIParams
                p["params"] = CIParams(**inner)
            elif name == "franke_westerhoff":
                from abm_models.franke_westerhoff import FWParams
                p["params"] = FWParams(**inner)
    return cls(**p)


def series_for_fingerprint(name: str, result: dict[str, Any]) -> tuple[np.ndarray, str]:
    """Return (series, kind) suitable for fingerprint().

    Priceless models (MG/GCMG) feed the *attendance excess* (2·A − N) as their
    series — a coarse but standard MG-literature volatility proxy. Price models
    feed log-returns derived via abm_models.base.returns_of.

    Caller should pass `compute_hill=(kind=="returns")` to `fingerprint()` —
    a power-law tail estimator is meaningless on the discrete-integer
    attendance excess.
    """
    if name in PRICELESS_MODELS:
        att = np.asarray(result["attendance"], dtype=np.float64)
        if "actions" in result and result["actions"].ndim == 2:
            n_players = int(result["actions"].shape[1])
        else:
            n_players = int(2 * att.max() - att.min()) if att.size else 0
            n_players = max(n_players, 1)
        excess = 2.0 * att - n_players
        return excess, "attendance_excess"

    from abm_models.base import returns_of
    r = returns_of(result)
    return np.asarray(r, dtype=np.float64), "returns"
