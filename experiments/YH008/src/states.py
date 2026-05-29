"""states.py -- synthetic single-turn state ensemble + paired-state generators.

Produces three structured collections (all centered on FCLAgent section 4.1 ranges,
see config.yaml `states`):

  random_states     : marginal ensemble covering gain/loss x near/far ATH, for the
                      marginal disposition distribution.
  disposition_pairs : (gain_state, loss_state) differing ONLY in purchase price
                      (=> sign of unrealized gain), everything else held fixed.
                      Controlled disposition contrast.
  ath_pairs         : (no_drop_state, dropped_near_state) differing ONLY in ATH,
                      holding current price + unrealized gain fixed. Controlled
                      ATH-asymmetry contrast (fixed research decision: vary ATH only).

Each record is {"state": State, "meta": {...}}. An exploration/held-out split is made
once with a fixed seed BEFORE any analysis; held-out is reserved for Stage 3.
"""
from __future__ import annotations
import numpy as np
from render import State


def _round_state(price, position, purchase, ath, atl, cash, ofi, remaining, total):
    ug = position * (price - purchase)
    return State(
        cash=float(cash), position=int(position), unrealized_gain=float(ug),
        price=float(price), ath=float(ath), atl=float(atl),
        remaining_time=int(remaining), total_time=int(total),
        buy_price=float(purchase), buy_volume=int(position), ofi=float(ofi),
    )


def _sample_common(rng, cfg):
    s = cfg["states"]
    price = rng.uniform(s["current_price"]["low"], s["current_price"]["high"])
    position = int(rng.integers(s["position"]["low"], s["position"]["high"] + 1))
    cash = rng.uniform(s["cash"]["low"], s["cash"]["high"])
    ofi = rng.uniform(s["ofi"]["low"], s["ofi"]["high"])
    remaining = int(rng.integers(s["remaining_time"]["low"], s["remaining_time"]["high"] + 1))
    total = int(s["total_time"])
    atl = price * rng.uniform(s["ath"]["atl_frac"]["low"], s["ath"]["atl_frac"]["high"])
    return price, position, cash, ofi, remaining, total, atl


def _purchase_for(rng, cfg, price, sign):
    gl = cfg["states"]["gain_loss"]
    if sign == "gain":
        mult = rng.uniform(gl["gain_mult"]["low"], gl["gain_mult"]["high"])  # <1
    else:
        mult = rng.uniform(gl["loss_mult"]["low"], gl["loss_mult"]["high"])  # >1
    return price * mult


def _ath_for(rng, cfg, price, cond, purchase=0.0):
    """ATH for a (price, purchase) context. ENFORCES ATH >= max(price, purchase):
    you cannot have bought above the all-time high, and price cannot exceed it.
    no_drop   -> ATH == max(price, purchase)  (no drawdown beyond the reference high)
    dropped_near/far -> ATH > price (a salient peak above the reference), >= max(price,purchase)."""
    a = cfg["states"]["ath"]
    base = max(price, purchase)
    if cond == "no_drop":
        return base, price / base
    if cond == "dropped_near":
        near = rng.uniform(a["dropped_near_nearness"]["low"], a["dropped_near_nearness"]["high"])
    elif cond == "far":
        near = rng.uniform(a["far_nearness"]["low"], a["far_nearness"]["high"])
    else:
        raise ValueError(cond)
    ath = max(base / near, base * 1.001)   # ATH = base/nearness, strictly above the reference
    return ath, price / ath


def make_random_states(cfg, seed):
    rng = np.random.default_rng(seed)
    n = cfg["ensemble"]["n_random"]
    dead = cfg["states"]["gain_loss"]["deadband_gain_abs"]
    recs = []
    conds = ["no_drop", "dropped_near", "far"]
    for i in range(n):
        sign = "gain" if rng.random() < 0.5 else "loss"
        cond = conds[int(rng.integers(0, 3))]
        price, position, cash, ofi, remaining, total, atl = _sample_common(rng, cfg)
        purchase = _purchase_for(rng, cfg, price, sign)
        ath, near = _ath_for(rng, cfg, price, cond, purchase=purchase)
        st = _round_state(price, position, purchase, ath, atl, cash, ofi, remaining, total)
        if abs(st.unrealized_gain) <= dead:
            continue
        recs.append({"state": st, "meta": {
            "kind": "random", "gain_sign": sign, "ath_cond": cond,
            "nearness": round(near, 4), "idx": i}})
    return recs


def make_disposition_pairs(cfg, seed):
    """gain vs loss differing ONLY in purchase price (everything else identical)."""
    rng = np.random.default_rng(seed)
    n = cfg["ensemble"]["n_random"] // 2
    recs = []
    for i in range(n):
        price, position, cash, ofi, remaining, total, atl = _sample_common(rng, cfg)
        p_gain = _purchase_for(rng, cfg, price, "gain")
        p_loss = _purchase_for(rng, cfg, price, "loss")
        # neutral ATH context for the disposition contrast: a high above both legs'
        # references (>= max(price, p_loss) so both legs are valid with the SAME ATH).
        ath, near = _ath_for(rng, cfg, price, "dropped_near", purchase=max(p_gain, p_loss))
        g = _round_state(price, position, p_gain, ath, atl, cash, ofi, remaining, total)
        l = _round_state(price, position, p_loss, ath, atl, cash, ofi, remaining, total)
        recs.append({"gain": g, "loss": l, "meta": {
            "kind": "disposition_pair", "nearness": round(near, 4), "idx": i}})
    return recs


def make_ath_pairs(cfg, seed):
    """no_drawdown vs drawdown differing ONLY in ATH, for both gain and loss contexts.
    Both states are VALID (ATH >= max(price, purchase)):
      no_drawdown : ATH = max(price, purchase)  (the only high is the reference itself)
      drawdown    : ATH > price (a salient peak above the reference)
    Holds (price, purchase => unrealized_gain) fixed; varies ONLY ATH. Works in BOTH
    gain and loss contexts (fixes the prior ill-posed loss x price-at-ATH cell)."""
    rng = np.random.default_rng(seed)
    n = cfg["ensemble"]["n_paired_ath"]
    recs = []
    for sign in ("gain", "loss"):
        for i in range(n):
            price, position, cash, ofi, remaining, total, atl = _sample_common(rng, cfg)
            purchase = _purchase_for(rng, cfg, price, sign)
            ath_nd, near_nd = _ath_for(rng, cfg, price, "no_drop", purchase=purchase)
            ath_dn, near_dn = _ath_for(rng, cfg, price, "dropped_near", purchase=purchase)
            nd = _round_state(price, position, purchase, ath_nd, atl, cash, ofi, remaining, total)
            dn = _round_state(price, position, purchase, ath_dn, atl, cash, ofi, remaining, total)
            recs.append({"no_drop": nd, "dropped_near": dn, "meta": {
                "kind": "ath_pair", "gain_sign": sign,
                "nearness_no_drop": round(near_nd, 4),
                "nearness_dropped": round(near_dn, 4), "idx": i}})
    return recs


def split_exploration_holdout(recs, holdout_frac, seed):
    """Index-based split with fixed seed. Returns (exploration, holdout)."""
    rng = np.random.default_rng(seed)
    idx = np.arange(len(recs))
    rng.shuffle(idx)
    n_hold = int(round(len(recs) * holdout_frac))
    hold = set(idx[:n_hold].tolist())
    expl = [r for j, r in enumerate(recs) if j not in hold]
    held = [r for j, r in enumerate(recs) if j in hold]
    return expl, held


def build_all(cfg):
    """Build every collection with config seeds and split each into exploration/held-out.
    Held-out tuples must not share (price, purchase, ATH) with exploration by construction
    here they are independently sampled, so overlap probability is ~0 (continuous)."""
    s = cfg["seeds"]["ensemble"]
    hf = cfg["ensemble"]["holdout_frac"]
    sp = cfg["seeds"]["split"]
    out = {}
    for name, recs in [
        ("random", make_random_states(cfg, s)),
        ("disposition_pairs", make_disposition_pairs(cfg, s + 1)),
        ("ath_pairs", make_ath_pairs(cfg, s + 2)),
    ]:
        expl, held = split_exploration_holdout(recs, hf, sp)
        out[name] = {"exploration": expl, "holdout": held, "n_total": len(recs)}
    return out
