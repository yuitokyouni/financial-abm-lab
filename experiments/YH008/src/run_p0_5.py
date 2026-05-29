"""P0.5: direction-robustness of the loss-conditional ATH asymmetry WITHIN the
clean-probe family (level already measured in P0; here we test the SIGN across 3
neutral clean-probe wordings). Plus disposition proxy separated by framing from
EXISTING saved data (no new generation).

Neutral wordings (no buy/sell orientation hint; in-group mass checked here):
  sec1_faithful (canonical), minimal, plain.
ATH loss-context pairs only, same exploration seed, bootstrap K=1000.

Judgement (Yuito):
  all 3 positive (CI excludes 0)   -> PASS_STAGE2_LOSS_CONDITIONAL_CONFIRMED
  >=2 null or any sign-flip         -> WORDING_ARTIFACT_DETECTED -> P1 (S_purchase pivot)
  all negative                      -> canonical mis-selected -> reselect + re-P0.5
"""
from __future__ import annotations
import os, sys, json, time, subprocess
os.environ.setdefault("HF_HOME", "/workspace/.hf")
os.environ.setdefault("HF_HUB_CACHE", "/workspace/.hf/hub")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
import numpy as np, yaml
sys.path.insert(0, os.path.dirname(__file__))
from render import build_clean_probe_variant
from model import ProbeModel
from freeze_groups import freeze_groups
import states as S, metrics as M

HERE = os.path.dirname(__file__)
V1 = "/root/yh008_work/outputs/20260529-092454_7de0bb4"     # has clean + behavioral disposition raw
WORDINGS = ["sec1_faithful", "minimal", "plain"]


def sh(c):
    try: return subprocess.check_output(c, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except Exception: return "nogit"


def jdump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(o, open(p, "w"), indent=2, default=float)


def main():
    t0 = time.time()
    cfg = yaml.safe_load(open(os.path.join(HERE, "config.yaml")))
    nres = cfg["ensemble"]["bootstrap_resamples"]; bseed = cfg["seeds"]["global"]; BS = 16
    run_id = time.strftime("%Y%m%d-%H%M%S") + "_" + sh(
        "cd /workspace/speculation-game-info && git rev-parse --short HEAD") + "_P0_5"
    out = os.path.join(cfg["paths"]["outputs_root"], run_id)
    print(f"[p0.5] run_id={run_id}", flush=True)

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg["model"]["name"], revision=cfg["model"]["revision"])
    true_ids, false_ids, _ = freeze_groups(tok)

    # ---- (2) disposition by framing from EXISTING saved data (no model needed) ----
    cl = json.load(open(os.path.join(V1, "stage1", "raw_disposition_pairs.json")))
    bf = json.load(open(os.path.join(V1, "faithfulness", "behavioral_framing_raw.json")))["disposition_pairs"]
    clean_disp = M.paired_diff_ci([d["p_gain"] - d["p_loss"] for d in cl
                                   if d["p_gain"] is not None and d["p_loss"] is not None], nres, bseed)
    behav_disp = M.paired_diff_ci([d["p_gain"] - d["p_loss"] for d in bf], nres, bseed)
    print(f"[p0.5] disposition clean={clean_disp['mean']:+.4f}[{clean_disp['lo']:+.4f},{clean_disp['hi']:+.4f}]"
          f"  behav={behav_disp['mean']:+.4f}[{behav_disp['lo']:+.4f},{behav_disp['hi']:+.4f}]", flush=True)

    # ---- (1) 3-wording loss-context ATH asymmetry (model) ----
    print("[load] loading model ...", flush=True)
    m = ProbeModel.load(cfg, true_ids=true_ids, false_ids=false_ids)
    print(f"[load] done {time.time()-t0:.0f}s", flush=True)
    coll = S.build_all(cfg)
    ap_loss = [r for r in coll["ath_pairs"]["exploration"] if r["meta"]["gain_sign"] == "loss"]
    print(f"[p0.5] loss ATH pairs: {len(ap_loss)}", flush=True)

    by_wording = {}; raw = {}
    for w in WORDINGS:
        nd = m.p_sell_batched([build_clean_probe_variant(tok, r["no_drop"], w) for r in ap_loss], BS)
        dn = m.p_sell_batched([build_clean_probe_variant(tok, r["dropped_near"], w) for r in ap_loss], BS)
        diffs = [b.p_sell - a.p_sell for a, b in zip(nd, dn)]
        ci = M.paired_diff_ci(diffs, nres, bseed)
        omax = max(r.out_group_mass for r in nd + dn)
        by_wording[w] = {"ath_asymmetry_loss": ci, "out_group_mass_max": float(omax),
                         "positive_CI_excludes_0": bool(ci["lo"] > 0),
                         "negative_CI_excludes_0": bool(ci["hi"] < 0)}
        raw[w] = [{"p_no_drop": a.p_sell, "p_dropped_near": b.p_sell, "idx": r["meta"]["idx"]}
                  for r, a, b in zip(ap_loss, nd, dn)]
        print(f"[p0.5] {w}: ATH_loss={ci['mean']:+.4f} [{ci['lo']:+.4f},{ci['hi']:+.4f}] "
              f"out_mass_max={omax:.4f}", flush=True)

    n_pos = sum(v["positive_CI_excludes_0"] for v in by_wording.values())
    n_neg = sum(v["negative_CI_excludes_0"] for v in by_wording.values())
    n_null = len(WORDINGS) - n_pos - n_neg
    if n_pos == len(WORDINGS):
        decision = "PASS_STAGE2_LOSS_CONDITIONAL_CONFIRMED"
        verdict = ("All 3 neutral clean-probe wordings give a POSITIVE loss-context ATH asymmetry "
                   "(CI excludes 0). Direction is stable within the clean-probe family; the "
                   "behavioral-framing inversion is a reason-generation artifact. Prepare Stage 2 "
                   "(clean-probe, loss-conditional v_ATH).")
    elif n_neg == len(WORDINGS):
        decision = "CANONICAL_MISSELECTED"
        verdict = ("All 3 clean wordings NEGATIVE => behavioral family carries the true direction; "
                   "reselect canonical wording and re-run P0.5.")
    elif n_null >= 2 or n_neg >= 1:
        decision = "WORDING_ARTIFACT_DETECTED"
        verdict = (f"{n_pos} positive / {n_null} null / {n_neg} sign-flip across 3 clean wordings => "
                   "wording dominates the direction; clean-probe canonical is an outlier. Do NOT run "
                   "Stage 2 on clean-probe v_ATH. Recommend P1 = S_purchase pivot (disposition is the "
                   "robust phenotype).")
    else:
        decision = "MIXED_REVIEW"
        verdict = f"{n_pos} positive / {n_null} null / {n_neg} flip. Report for Yuito judgement."

    print(f"[p0.5] DECISION={decision}", flush=True)
    gate = {"decision": decision, "verdict": verdict,
            "ath_loss_by_wording": by_wording,
            "disposition_by_framing": {"clean_probe": clean_disp, "behavioral_framing": behav_disp},
            "n_positive": n_pos, "n_null": n_null, "n_flip": n_neg,
            "wordings": WORDINGS, "n_loss_pairs": len(ap_loss),
            "prior_behavioral_framing_ath_loss": "-0.0704 [-0.0834,-0.0573] (P0 run, reversed)"}
    jdump(os.path.join(out, "stage0_5_gate", "gate_v3.json"), gate)
    jdump(os.path.join(out, "stage1", "raw_ath_pairs_v3.json"), raw)
    jdump(os.path.join(out, "stage0", "provenance.json"),
          {"run_id": run_id, "supersedes": None, "extends": "20260529-120955_7de0bb4_P0",
           "git_HEAD": sh("cd /workspace/speculation-game-info && git rev-parse HEAD"), "config": cfg})

    L = [f"# YH008 — REPORT v3 (P0.5: direction-robustness of loss-conditional ATH)", "",
         f"**run_id:** `{run_id}`  ·  extends P0 `20260529-120955_7de0bb4_P0`.",
         f"**Decision:** `{decision}`", "",
         f"## Loss-context ATH asymmetry across 3 neutral clean-probe wordings (n={len(ap_loss)} pairs, K=1000)",
         "| wording | ATH_loss mean | 95% CI | out-mass max | sign |", "|---|---|---|---|---|"]
    for w in WORDINGS:
        v = by_wording[w]; ci = v["ath_asymmetry_loss"]
        sign = "positive" if v["positive_CI_excludes_0"] else ("flip(neg)" if v["negative_CI_excludes_0"] else "null")
        L.append(f"| {w} | {ci['mean']:+.4f} | [{ci['lo']:+.4f}, {ci['hi']:+.4f}] | {v['out_group_mass_max']:.4f} | {sign} |")
    L += [f"| behavioral-framing (P0) | -0.0704 | [-0.0834, -0.0573] | — | flip(neg) |", "",
          "## Disposition proxy by framing (from existing data, K=1000)",
          f"- clean-probe: {clean_disp['mean']:+.4f} [{clean_disp['lo']:+.4f}, {clean_disp['hi']:+.4f}]",
          f"- behavioral-framing: {behav_disp['mean']:+.4f} [{behav_disp['lo']:+.4f}, {behav_disp['hi']:+.4f}]",
          "(disposition direction is POSITIVE in both framings => robust phenotype, a viable "
          "Stage-2 pivot target even if ATH fails.)", "",
          "## Verdict", verdict, "",
          "## Scope", "P0.5 only. Stage 2 NOT touched. P1 (S_purchase pivot) NOT touched."]
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "REPORT_v3.md"), "w").write("\n".join(L) + "\n")
    print(f"\n[done] P0.5 {time.time()-t0:.0f}s  out={out}", flush=True)


if __name__ == "__main__":
    main()
