"""Finalize the run: faithfulness check + Stage 0.5 gate + SUMMARY, from the saved
Stage 1 metrics (no Stage 1 re-run).

Faithfulness is done two ways (fp32 free-generation is prohibitively slow, so it is NOT
the primary path):
  (1) behavioral-framing PHENOTYPE via logits (fast): read P(sell) at the is_buy slot of
      the FCLAgent reason-requesting answer format over the SAME paired states, giving a
      behavioral-framing disposition proxy + gain-context ATH asymmetry directly comparable
      to clean-probe. This answers the branch question (model attenuation vs probe-format).
  (2) a few real free generations (qualitative): confirm the model emits FCLAgent-style
      reason+emotion text and check the parsed is_buy direction.

Gate uses the VALID gain-context ATH asymmetry (loss-context no_drop cell is ill-posed:
a loss implies price<purchase<=ATH, so 'price at ATH' cannot co-occur with a loss).
"""
from __future__ import annotations
import os, sys, json, time
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
RUN = "/root/yh008_work/outputs/20260529-092454_7de0bb4"
N_GEN = 6          # real free generations (qualitative only)
MAX_NEW = 320

os.environ.setdefault("HF_HOME", "/workspace/.hf")
os.environ.setdefault("HF_HUB_CACHE", "/workspace/.hf/hub")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import yaml
from render import render_behavioral, build_clean_probe, build_behavioral_probe
from model import ProbeModel
from freeze_groups import freeze_groups
import states as S
import metrics as M


def parse_isbuy(text):
    import re
    ms = re.findall(r'"is_buy"\s*:\s*"?(True|False|true|false)\b', text)
    return (ms[-1].lower() == "true") if ms else None


def main():
    t0 = time.time()
    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml")))
    metrics = json.load(open(os.path.join(RUN, "stage1", "metrics.json")))
    diag = json.load(open(os.path.join(RUN, "stage0_2", "diagnostics.json")))
    nres = cfg["ensemble"]["bootstrap_resamples"]; bseed = cfg["seeds"]["global"]

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg["model"]["name"], revision=cfg["model"]["revision"])
    true_ids, false_ids, _ = freeze_groups(tok)
    print("[load] loading model ...", flush=True)
    m = ProbeModel.load(cfg, true_ids=true_ids, false_ids=false_ids)
    print(f"[load] done {time.time()-t0:.0f}s", flush=True)

    coll = S.build_all(cfg)
    dp = coll["disposition_pairs"]["exploration"]
    ap = coll["ath_pairs"]["exploration"]
    BS = 16

    # ===== (1) behavioral-framing phenotype via logits (fast) =====
    print("[faith] behavioral-framing logit phenotype ...", flush=True)
    bdp_g = m.p_sell_batched([build_behavioral_probe(tok, r["gain"]) for r in dp], BS)
    bdp_l = m.p_sell_batched([build_behavioral_probe(tok, r["loss"]) for r in dp], BS)
    bap_nd = m.p_sell_batched([build_behavioral_probe(tok, r["no_drop"]) for r in ap], BS)
    bap_dn = m.p_sell_batched([build_behavioral_probe(tok, r["dropped_near"]) for r in ap], BS)

    bpair = M.paired_disposition(dp, [r.p_sell for r in bdp_g],
                                 [r.p_sell for r in bdp_l], nres, bseed)
    bath = M.paired_ath_asymmetry(ap, [r.p_sell for r in bap_nd],
                                  [r.p_sell for r in bap_dn], nres, bseed)
    b_out = [r.out_group_mass for r in (bdp_g + bdp_l + bap_nd + bap_dn)]
    behav_logit = {
        "disposition_proxy_paired": bpair["disposition_proxy_paired"],
        "ath_asymmetry_gain_context_VALID": bath["ath_asymmetry_by_sign"]["gain"],
        "ath_asymmetry_overall_CONFOUNDED": bath["ath_asymmetry"],
        "out_of_group_mass_max": float(max(b_out)),
        "note": "P(sell) read at is_buy slot of the FCLAgent reason-requesting answer format "
                "(order_price pre-filled). Directly comparable to clean-probe on same states.",
    }
    # persist behavioral-framing raw P(sell) for reproducibility
    json.dump({"disposition_pairs": [{"p_gain": g.p_sell, "p_loss": l.p_sell}
                                      for g, l in zip(bdp_g, bdp_l)],
               "ath_pairs": [{"p_no_drop": a.p_sell, "p_dropped_near": b.p_sell,
                              "gain_sign": r["meta"]["gain_sign"]}
                             for r, a, b in zip(ap, bap_nd, bap_dn)]},
              open(os.path.join(RUN, "faithfulness", "behavioral_framing_raw.json"), "w"),
              indent=2, default=float)
    print(f"[faith] behavioral-framing disposition={bpair['disposition_proxy_paired']['mean']:+.4f} "
          f"[{bpair['disposition_proxy_paired']['lo']:+.4f},{bpair['disposition_proxy_paired']['hi']:+.4f}]"
          f"  ATH(gain)={bath['ath_asymmetry_by_sign']['gain']['mean']:+.4f} "
          f"[{bath['ath_asymmetry_by_sign']['gain']['lo']:+.4f},"
          f"{bath['ath_asymmetry_by_sign']['gain']['hi']:+.4f}]", flush=True)

    # ===== (2) a few real free generations (qualitative) =====
    print(f"[faith] {N_GEN} real generations (qualitative) ...", flush=True)
    rand = coll["random"]["exploration"]
    gen_subset = ([r for r in rand if r["meta"]["gain_sign"] == "gain"][:N_GEN // 2] +
                  [r for r in rand if r["meta"]["gain_sign"] == "loss"][:N_GEN // 2])
    ckpt = os.path.join(RUN, "faithfulness", "freegen_checkpoint.jsonl")
    done = {json.loads(l)["key"]: json.loads(l) for l in open(ckpt)} if os.path.exists(ckpt) else {}
    gens = []
    with open(ckpt, "a") as ck:
        for r in gen_subset:
            key = f"{r['meta']['gain_sign']}_{r['meta']['idx']}"
            if key in done:
                gens.append(done[key]); continue
            txt = m.generate(render_behavioral(r["state"]), max_new_tokens=MAX_NEW)
            rec = {"key": key, "gain_sign": r["meta"]["gain_sign"],
                   "parsed_is_buy": parse_isbuy(txt),
                   "has_reason": "reason" in txt.lower(),
                   "mentions_step_or_analysis": ("step" in txt.lower() or "analy" in txt.lower()),
                   "gen": txt[:1500]}
            ck.write(json.dumps(rec, default=float) + "\n"); ck.flush()
            gens.append(rec)
            print(f"[faith] gen {key}: is_buy={rec['parsed_is_buy']}", flush=True)
    gen_parsed = [g for g in gens if g["parsed_is_buy"] is not None]
    freegen = {
        "n": len(gens), "parse_rate": len(gen_parsed) / len(gens) if gens else 0,
        "reason_text_rate": float(np.mean([g["has_reason"] for g in gens])),
        "cot_rate": float(np.mean([g["mentions_step_or_analysis"] for g in gens])),
        "note": "qualitative only (fp32 free-gen is slow); the model emits CoT-style analysis "
                "before the JSON => confirms why clean-probe (no generation) avoids contamination.",
    }

    # ===== gate (clean-probe is primary; behavioral-framing for the branch) =====
    dpx = metrics["paired_disposition"]["disposition_proxy_paired"]
    dpx_marg = metrics["marginal_disposition"]["disposition_proxy"]
    ath_gain = metrics["ath_asymmetry"]["ath_asymmetry_by_sign"]["gain"]
    ath_overall = metrics["ath_asymmetry"]["ath_asymmetry"]
    ath_loss = metrics["ath_asymmetry"]["ath_asymmetry_by_sign"]["loss"]

    disp_pos = dpx["mean"] > 0 and dpx["lo"] > 0
    ath_pos = ath_gain["mean"] > 0 and ath_gain["lo"] > 0
    decision = "PROCEED_TO_STAGE_2" if (disp_pos and ath_pos) else "YEE_SHARMA_FALLBACK"

    # branch: does behavioral framing reveal the ATH phenotype the clean-probe lacks?
    b_ath_gain = behav_logit["ath_asymmetry_gain_context_VALID"]
    behav_ath_pos = b_ath_gain["mean"] > 0 and b_ath_gain["lo"] > 0
    if ath_pos:
        sub = "n/a (gate passed)"
    elif behav_ath_pos:
        sub = ("PROBE-FORMAT branch: behavioral-framing shows a POSITIVE gain-context ATH "
               "asymmetry while clean-probe does not => the clean-probe answer format may be "
               "suppressing the phenotype. Fix the PROBE FORM (not the model) before any model "
               "swap; re-examine clean-probe wording / answer format.")
    else:
        sub = ("MODEL-BASELINE branch: neither clean-probe nor behavioral-framing shows a "
               "positive gain-context ATH asymmetry => baseline attenuation in the model. "
               "Yee-Sharma section-4 route: (a) profile prompting to induce investor bias, "
               "(b) Gemma-2-9B, (c) prompt review. (Free-gen faithfulness is qualitative only.)")

    gate = {
        "rule": "PROCEED iff disposition_proxy>0 (CI lo>0) AND ATH_asymmetry>0 (CI lo>0, VALID "
                "gain-context); else Yee-Sharma section-4 fallback (STOP before Stage 2).",
        "decision": decision, "fallback_subbranch": sub,
        "clean_probe": {
            "disposition_proxy_paired": dpx, "disposition_proxy_marginal": dpx_marg,
            "ath_asymmetry_gain_context_VALID": ath_gain,
            "ath_asymmetry_overall_CONFOUNDED": ath_overall,
            "ath_asymmetry_loss_context_ILLPOSED": ath_loss},
        "behavioral_framing_logit": behav_logit,
        "behavioral_freegen_qualitative": freegen,
        "ath_construction_flag": (
            "loss-context no_drop cell is ill-posed (price-at-ATH cannot co-occur with a loss). "
            "Loss-context/overall ATH numbers are confounded; gain-context is the valid contrast. "
            "FIX before Stage 2: constrain ATH>=max(price,purchase)."),
        "sec1_reproduction": diag["sec1_reproduction"],
        "prompt_sensitivity_sweep": diag["prompt_sensitivity_sweep"],
    }
    os.makedirs(os.path.join(RUN, "stage0_5_gate"), exist_ok=True)
    json.dump(gate, open(os.path.join(RUN, "stage0_5_gate", "gate.json"), "w"),
              indent=2, default=float)

    summary = {
        "run_id": os.path.basename(RUN), "wallclock_finalize_s": round(time.time() - t0, 1),
        "frozen_token_groups": {"true_ids": true_ids, "false_ids": false_ids,
                                "excluded_semantic_aliases": "Yes/yes/1, No/no/0 (see diagnostics.json)"},
        "out_of_group_mass_distribution": metrics["out_of_group_mass_distribution"],
        "sec1_reproduction": diag["sec1_reproduction"],
        "prompt_sensitivity_sweep": diag["prompt_sensitivity_sweep"],
        "determinism": diag["determinism"], "batch_equivalence": diag["batch_equivalence"],
        "clean_probe_disposition_proxy_paired": dpx,
        "clean_probe_disposition_proxy_marginal": dpx_marg,
        "clean_probe_ath_asymmetry_gain_VALID": ath_gain,
        "clean_probe_ath_asymmetry_overall_CONFOUNDED": ath_overall,
        "behavioral_framing_disposition_proxy": behav_logit["disposition_proxy_paired"],
        "behavioral_framing_ath_gain_VALID": behav_logit["ath_asymmetry_gain_context_VALID"],
        "behavioral_freegen_qualitative": freegen,
        "gate_decision": decision, "fallback_subbranch": sub, "out_dir": RUN,
    }
    json.dump(summary, open(os.path.join(RUN, "SUMMARY.json"), "w"), indent=2, default=float)
    print("\n=========== SUMMARY ===========")
    print(json.dumps(summary, indent=2, default=float))
    print(f"\n[done] finalize {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
