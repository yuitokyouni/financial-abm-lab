"""P0 re-measurement: ATH construction bug fixed (states.py now guarantees
ATH >= max(price, purchase); no_drawdown ATH==max, drawdown ATH>price, valid in BOTH
gain and loss contexts). Re-measure ATH asymmetry in gain AND loss contexts with the
SAME exploration seed, the CANONICAL clean-probe wording, and bootstrap K=1000. Also
recompute disposition (states were clamped) and behavioral-framing ATH (for the branch).

Writes a NEW run_id (does not overwrite the v1 run). Judgement updated per Yuito:
  loss-context ATH>0 (CI lo>0)  -> ATH effect is loss-conditional -> Stage 2 (loss-cond v_ATH), PASS
  gain-context ATH>0 (CI lo>0)  -> bug-fix changed the gate -> PASS
  both null/neg                 -> true MODEL-baseline attenuation -> P1 (S_purchase pivot)
"""
from __future__ import annotations
import os, sys, json, time, subprocess
# MUST set HF cache + offline BEFORE any transformers/HF import, else AutoTokenizer
# bypasses /workspace/.hf and tries to DOWNLOAD into /root (fills the 7.7G overlay).
os.environ.setdefault("HF_HOME", "/workspace/.hf")
os.environ.setdefault("HF_HUB_CACHE", "/workspace/.hf/hub")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
import numpy as np, yaml

sys.path.insert(0, os.path.dirname(__file__))
from render import build_clean_probe, build_behavioral_probe, state_to_dict
from model import ProbeModel
from freeze_groups import freeze_groups
import states as S, metrics as M

HERE = os.path.dirname(__file__)


def sh(c):
    try: return subprocess.check_output(c, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except Exception as e: return f"<err {e}>"


def jdump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, open(p, "w"), indent=2, default=float)


def main():
    t0 = time.time()
    cfg = yaml.safe_load(open(os.path.join(HERE, "config.yaml")))
    assert cfg["probe"]["canonical_wording"] == "sec1_faithful"  # canonical == build_clean_probe
    nres = cfg["ensemble"]["bootstrap_resamples"]; bseed = cfg["seeds"]["global"]; BS = 16
    git = sh("cd /workspace/speculation-game-info && git rev-parse --short HEAD") or "nogit"
    run_id = time.strftime("%Y%m%d-%H%M%S") + "_" + git + "_P0"
    out = os.path.join(cfg["paths"]["outputs_root"], run_id)
    print(f"[p0] run_id={run_id}", flush=True)

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg["model"]["name"], revision=cfg["model"]["revision"])
    true_ids, false_ids, _ = freeze_groups(tok)
    print("[load] loading model ...", flush=True)
    m = ProbeModel.load(cfg, true_ids=true_ids, false_ids=false_ids)
    print(f"[load] done {time.time()-t0:.0f}s", flush=True)

    coll = S.build_all(cfg)
    rand = coll["random"]["exploration"]
    dp = coll["disposition_pairs"]["exploration"]
    ap = coll["ath_pairs"]["exploration"]

    # ---- clean-probe (canonical) ----
    print("[p0] clean-probe ensemble ...", flush=True)
    rand_res = m.p_sell_batched([build_clean_probe(tok, r["state"]) for r in rand], BS)
    dpg = m.p_sell_batched([build_clean_probe(tok, r["gain"]) for r in dp], BS)
    dpl = m.p_sell_batched([build_clean_probe(tok, r["loss"]) for r in dp], BS)
    apnd = m.p_sell_batched([build_clean_probe(tok, r["no_drop"]) for r in ap], BS)
    apdn = m.p_sell_batched([build_clean_probe(tok, r["dropped_near"]) for r in ap], BS)
    out_mass = [r.out_group_mass for r in rand_res + dpg + dpl + apnd + apdn]

    marg = M.marginal_disposition(rand, [r.p_sell for r in rand_res], nres, bseed)
    pdisp = M.paired_disposition(dp, [r.p_sell for r in dpg], [r.p_sell for r in dpl], nres, bseed)
    cath = M.paired_ath_asymmetry(ap, [r.p_sell for r in apnd], [r.p_sell for r in apdn], nres, bseed)

    # ---- behavioral-framing ATH (same fixed pairs; for the branch) ----
    print("[p0] behavioral-framing ATH ...", flush=True)
    bnd = m.p_sell_batched([build_behavioral_probe(tok, r["no_drop"]) for r in ap], BS)
    bdn = m.p_sell_batched([build_behavioral_probe(tok, r["dropped_near"]) for r in ap], BS)
    bath = M.paired_ath_asymmetry(ap, [r.p_sell for r in bnd], [r.p_sell for r in bdn], nres, bseed)

    c_gain = cath["ath_asymmetry_by_sign"]["gain"]; c_loss = cath["ath_asymmetry_by_sign"]["loss"]
    b_gain = bath["ath_asymmetry_by_sign"]["gain"]; b_loss = bath["ath_asymmetry_by_sign"]["loss"]
    dpx = pdisp["disposition_proxy_paired"]

    def pos(d): return d["mean"] > 0 and d["lo"] > 0
    if pos(c_loss):
        decision = "PASS_STAGE2_LOSS_CONDITIONAL"
        verdict = ("ATH asymmetry is POSITIVE in the (now-valid) LOSS context => ATH effect is "
                   "loss-conditional. Proceed to Stage 2 with v_ATH identification restricted to "
                   "the loss context.")
    elif pos(c_gain):
        decision = "PASS_STAGE2"
        verdict = ("ATH asymmetry POSITIVE in the gain context after the construction fix => gate "
                   "changed; proceed to Stage 2.")
    else:
        decision = "YEE_SHARMA_FALLBACK_CONFIRMED"
        verdict = ("ATH asymmetry NULL/negative in BOTH valid contexts (clean-probe). "
                   + ("behavioral-framing also null in both => " if not (pos(b_gain) or pos(b_loss))
                      else "but behavioral-framing shows a positive context => probe-format suspect; ")
                   + ("true MODEL-baseline attenuation confirmed -> P1: S_purchase pivot "
                      "(disposition is positive, so purchase-reference dependence exists)."
                      if not (pos(b_gain) or pos(b_loss)) else
                      "re-examine clean-probe form before model swap."))

    print(f"[p0] clean ATH gain={c_gain['mean']:+.4f}[{c_gain['lo']:+.4f},{c_gain['hi']:+.4f}] "
          f"loss={c_loss['mean']:+.4f}[{c_loss['lo']:+.4f},{c_loss['hi']:+.4f}]", flush=True)
    print(f"[p0] behav ATH gain={b_gain['mean']:+.4f}[{b_gain['lo']:+.4f},{b_gain['hi']:+.4f}] "
          f"loss={b_loss['mean']:+.4f}[{b_loss['lo']:+.4f},{b_loss['hi']:+.4f}]", flush=True)
    print(f"[p0] disposition paired={dpx['mean']:+.4f}[{dpx['lo']:+.4f},{dpx['hi']:+.4f}]", flush=True)
    print(f"[p0] DECISION={decision}", flush=True)

    omv = np.asarray(out_mass)
    metrics = {
        "out_of_group_mass": {"n": int(len(omv)), "median": float(np.median(omv)),
                              "max": float(omv.max()),
                              "frac_flagged": float((omv > cfg["probe"]["out_of_group_mass_flag"]).mean())},
        "disposition_proxy_paired": dpx, "disposition_proxy_marginal": marg["disposition_proxy"],
        "clean_probe_ath": {"gain": c_gain, "loss": c_loss, "overall": cath["ath_asymmetry"]},
        "behavioral_framing_ath": {"gain": b_gain, "loss": b_loss, "overall": bath["ath_asymmetry"]},
        "n_exploration": {"random": len(rand), "disposition_pairs": len(dp), "ath_pairs": len(ap)},
    }
    jdump(os.path.join(out, "stage1", "metrics.json"), metrics)
    jdump(os.path.join(out, "stage1", "raw_ath_pairs.json"),
          [{"p_nd_clean": a.p_sell, "p_dn_clean": b.p_sell,
            "p_nd_behav": c.p_sell, "p_dn_behav": d.p_sell, "meta": r["meta"],
            "nd_state": state_to_dict(r["no_drop"]), "dn_state": state_to_dict(r["dropped_near"])}
           for r, a, b, c, d in zip(ap, apnd, apdn, bnd, bdn)])
    gate = {"decision": decision, "verdict": verdict, "provisional_v1_decision": "YEE_SHARMA_FALLBACK",
            "rule": "loss-context ATH>0 -> Stage2 loss-conditional; gain>0 -> Stage2; both null -> MODEL-baseline/P1",
            "metrics": metrics, "canonical_wording": "sec1_faithful"}
    jdump(os.path.join(out, "stage0_5_gate", "gate_v2.json"), gate)
    jdump(os.path.join(out, "stage0", "provenance.json"),
          {"run_id": run_id, "git_HEAD": sh("cd /workspace/speculation-game-info && git rev-parse HEAD"),
           "supersedes_ath_of": "20260529-092454_7de0bb4", "config": cfg,
           "note": "P0 ATH-construction-fix re-measurement; canonical wording frozen = sec1_faithful"})
    _report_v2(out, run_id, metrics, decision, verdict, c_gain, c_loss, cath["ath_asymmetry"],
               b_gain, b_loss, dpx, marg["disposition_proxy"])
    print(f"\n[done] P0 {time.time()-t0:.0f}s  out={out}", flush=True)


def _report_v2(out, run_id, metrics, decision, verdict, cg, cl, co, bg, bl, dpx, dm):
    L = [f"# YH008 Stage 1 — REPORT v2 (P0: ATH construction fix re-measurement)", "",
         f"**run_id:** `{run_id}`  ·  supersedes the ATH numbers of `20260529-092454_7de0bb4`.",
         f"**Updated gate:** `{decision}`  (v1 was provisional `YEE_SHARMA_FALLBACK`).", "",
         "## Fix",
         "states.py now guarantees `ATH >= max(price, purchase)` for every state. The ATH "
         "contrast is: no_drawdown `ATH == max(price, purchase)` vs drawdown `ATH > price` — "
         "valid in BOTH gain and loss contexts (the prior loss x price-at-ATH cell was ill-posed: "
         "a loss implies price<purchase<=ATH, so price cannot sit at the all-time high).", "",
         "## ATH asymmetry = P(sell|drawdown) - P(sell|no_drawdown), bootstrap K=1000", "",
         "| framing | context | mean | 95% CI |", "|---|---|---|---|",
         f"| clean-probe (canonical) | gain | {cg['mean']:+.4f} | [{cg['lo']:+.4f}, {cg['hi']:+.4f}] |",
         f"| clean-probe (canonical) | loss | {cl['mean']:+.4f} | [{cl['lo']:+.4f}, {cl['hi']:+.4f}] |",
         f"| clean-probe (canonical) | overall | {co['mean']:+.4f} | [{co['lo']:+.4f}, {co['hi']:+.4f}] |",
         f"| behavioral-framing | gain | {bg['mean']:+.4f} | [{bg['lo']:+.4f}, {bg['hi']:+.4f}] |",
         f"| behavioral-framing | loss | {bl['mean']:+.4f} | [{bl['lo']:+.4f}, {bl['hi']:+.4f}] |",
         "", "## Disposition (recomputed; states clamped for validity)",
         f"- paired = {dpx['mean']:+.4f} [{dpx['lo']:+.4f}, {dpx['hi']:+.4f}]",
         f"- marginal = {dm['mean']:+.4f} [{dm['lo']:+.4f}, {dm['hi']:+.4f}]",
         f"- out-of-group mass: median {metrics['out_of_group_mass']['median']:.2e}, "
         f"max {metrics['out_of_group_mass']['max']:.2e}, flag-rate {metrics['out_of_group_mass']['frac_flagged']:.3f}",
         "", "## Verdict", verdict, "",
         "## Scope", "P0 only (ATH construction fix + re-measure). P1+ (S_purchase pivot / "
         "profile prompting / Gemma) NOT touched — awaiting Yuito."]
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "REPORT_v2.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
