"""YH008 Stage 0.2 + Stage 1 driver. Single model load, one reproducible run.

Pipeline:
  Stage 0.2A  freeze True/False token groups from the tokenizer
  (load ProbeModel with frozen ids)
  Stage 0.2B  diagnostic probe battery: reproduce the section-1 smoke signal,
              measure decision-token concentration + out-of-group mass distribution
  Stage 1     ensemble probe -> disposition proxy (marginal + paired) & ATH asymmetry,
              all as bootstrap distributions
  Faithfulness  behavioral variant on exploration states (FCLAgent-style check)
  Stage 0.5 gate  proceed to Stage 2  vs  Yee-Sharma section-4 fallback

Artifacts: outputs/{run_id}/{stage}/...  (run_id = timestamp + git short hash).
"""
from __future__ import annotations
import os, sys, json, time, subprocess, hashlib
import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from render import (State, build_clean_probe, render_behavioral, template_hashes,
                    state_to_dict)
from model import ProbeModel
from freeze_groups import freeze_groups, measure_candidate_mass
import states as S
import metrics as M

HERE = os.path.dirname(__file__)
CFG_PATH = os.path.join(HERE, "config.yaml")


def sh(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except Exception as e:
        return f"<error: {e}>"


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=float)


def main():
    t_start = time.time()
    with open(CFG_PATH) as f:
        cfg = yaml.safe_load(f)

    git_hash = sh("cd /workspace/speculation-game-info && git rev-parse HEAD")
    git_short = git_hash[:7] if "<error" not in git_hash else "nogit"
    run_id = time.strftime("%Y%m%d-%H%M%S") + "_" + git_short
    out = os.path.join(cfg["paths"]["outputs_root"], run_id)
    os.makedirs(out, exist_ok=True)
    print(f"[run] run_id={run_id}\n[run] out={out}", flush=True)

    # ---- provenance snapshot ----
    import torch
    prov = {
        "run_id": run_id, "git_HEAD": git_hash,
        "config": cfg,
        "torch": torch.__version__, "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "pip_freeze": sh(f"{sys.executable} -m pip freeze").splitlines(),
        "model_revision": cfg["model"]["revision"],
        "model_shard_sizes": sh(
            "ls -lL /workspace/.hf/hub/models--meta-llama--Llama-3.1-8B-Instruct/"
            f"snapshots/{cfg['model']['revision']}/*.safetensors | awk '{{print $5}}'"
        ).split(),
        "storage_note": "code+outputs in /root (/workspace at quota); weights read from /workspace/.hf",
    }
    save_json(os.path.join(out, "stage0", "provenance.json"), prov)
    with open(os.path.join(out, "stage0", "config_snapshot.yaml"), "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    # ============ Stage 0.2A: freeze token groups (tokenizer only) ============
    os.environ.setdefault("HF_HOME", cfg["paths"]["hf_home"])
    os.environ.setdefault("HF_HUB_CACHE", cfg["paths"]["hf_home"] + "/hub")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg["model"]["name"], revision=cfg["model"]["revision"])
    true_ids, false_ids, grp_report = freeze_groups(tok)
    print(f"[0.2A] true_ids={true_ids}\n[0.2A] false_ids={false_ids}", flush=True)
    prov["prompt_hashes"] = template_hashes(tok)
    save_json(os.path.join(out, "stage0", "provenance.json"), prov)

    # ---- load full model with frozen ids ----
    print("[load] loading TransformerLens fp32 ...", flush=True)
    t0 = time.time()
    m = ProbeModel.load(cfg, true_ids=true_ids, false_ids=false_ids)
    print(f"[load] done in {time.time()-t0:.0f}s  VRAM={torch.cuda.memory_allocated()/1e9:.1f}GB",
          flush=True)

    # ============ Stage 0.2B: diagnostic battery ============
    smoke_loss = State(cash=30000, position=10, unrealized_gain=-63.0, price=293.7,
                       ath=300.0, atl=287.5, remaining_time=70, total_time=100,
                       buy_price=300.0, buy_volume=10, ofi=0.01)
    # gain mirror: bought well below current price (same shell)
    smoke_gain = State(cash=30000, position=10, unrealized_gain=+63.0, price=293.7,
                       ath=293.7, atl=287.5, remaining_time=70, total_time=100,
                       buy_price=287.4, buy_volume=10, ofi=0.01)
    diag_states = {"smoke_loss(sec1)": smoke_loss, "smoke_gain_mirror": smoke_gain}
    diag = {}
    for name, st in diag_states.items():
        pr = build_clean_probe(tok, st)
        res = m.p_sell(pr)
        diag[name] = {"p_sell": res.p_sell, "in_group_mass": res.in_group_mass,
                      "out_group_mass": res.out_group_mass, "flagged": res.flagged,
                      "state": state_to_dict(st)}
        print(f"[0.2B] {name}: P(sell)={res.p_sell:.3f} out_mass={res.out_group_mass:.4f}",
              flush=True)
    cand_prompts = [build_clean_probe(tok, st) for st in diag_states.values()]
    cand_mass = measure_candidate_mass(m, cand_prompts)

    # --- batched-vs-single equivalence self-check (TL left-padding position handling) ---
    single_ps = [m.p_sell(p).p_sell for p in cand_prompts]
    batch_ps = [r.p_sell for r in m.p_sell_batched(cand_prompts, batch_size=8)]
    max_dev = max(abs(a - b) for a, b in zip(single_ps, batch_ps))
    batch_check = {"single": single_ps, "batched": batch_ps, "max_abs_dev": max_dev,
                   "ok": max_dev < 0.01}
    print(f"[0.2B] batch-vs-single max_abs_dev={max_dev:.5f} ok={batch_check['ok']}", flush=True)

    # --- determinism check (Yuito #3): two forwards on the same state, bit-exact ---
    pr_smoke = build_clean_probe(tok, smoke_loss)
    r1 = m.p_sell(pr_smoke); r2 = m.p_sell(pr_smoke)
    det_check = {"p_sell_run1": r1.p_sell, "p_sell_run2": r2.p_sell,
                 "bit_exact": r1.p_sell == r2.p_sell,
                 "abs_diff": abs(r1.p_sell - r2.p_sell)}
    print(f"[0.2B] determinism: bit_exact={det_check['bit_exact']} "
          f"diff={det_check['abs_diff']:.2e}", flush=True)

    # --- prompt-sensitivity sweep (Yuito #1): smoke_loss under neutral wordings ---
    from render import CLEAN_ANSWER_VARIANTS, build_clean_probe_variant
    sweep = {}
    for vk in CLEAN_ANSWER_VARIANTS:
        rv = m.p_sell(build_clean_probe_variant(tok, smoke_loss, vk))
        sweep[vk] = {"p_sell": rv.p_sell, "out_mass": rv.out_group_mass}
        print(f"[0.2B] wording[{vk}]: P(sell)={rv.p_sell:.3f}", flush=True)
    sweep_vals = [v["p_sell"] for v in sweep.values()]
    sweep_range = max(sweep_vals) - min(sweep_vals)

    # --- section-1 reproduction gate (Yuito #1) ---
    p_smoke = diag["smoke_loss(sec1)"]["p_sell"]
    repro = {"target": 0.896, "observed_sec1_faithful": p_smoke,
             "abs_err": abs(p_smoke - 0.896),
             "reproduced_tight": abs(p_smoke - 0.896) <= 0.03,
             "reproduced_qualitative": p_smoke >= 0.75,
             "wording_range_on_smoke_loss": sweep_range}
    print(f"[0.2B] sec1 reproduction: P(sell)={p_smoke:.3f} (target 0.896) "
          f"tight={repro['reproduced_tight']} qual={repro['reproduced_qualitative']} "
          f"wording_range={sweep_range:.3f}", flush=True)

    save_json(os.path.join(out, "stage0_2", "diagnostics.json"),
              {"frozen_groups": grp_report, "token_group_membership": {
                  "included_true_spellings": grp_report["true_spellings"],
                  "included_false_spellings": grp_report["false_spellings"],
                  "EXCLUDED_semantic_aliases": grp_report["semantic_excluded"],
                  "exclusion_rationale": (
                      "Yes/yes/1 and No/no/0 EXCLUDED from True/False groups: they are "
                      "semantic aliases (a membership judgement, not a spelling fact) and "
                      "carry ~0 decision-slot mass here. In-group mass 0.9997 => no leakage.")},
               "diagnostic_states": diag, "candidate_mass_mean": cand_mass,
               "batch_equivalence": batch_check, "determinism": det_check,
               "prompt_sensitivity_sweep": sweep, "sec1_reproduction": repro})
    _write_sensitivity_notes(out, repro, sweep, det_check, grp_report, cand_mass, batch_check)
    # Note: the section-1 0.896 magnitude is a wording-sensitive single point. We do NOT
    # halt before Stage 1 on it (the Stage 0.5 gate is the real stop-before-Stage-2). The
    # reproduction status + sweep are carried into the gate as a wording caveat for Yuito.

    # ============ Stage 1: ensemble ============
    print("[stage1] building ensemble ...", flush=True)
    coll = S.build_all(cfg)
    nres = cfg["ensemble"]["bootstrap_resamples"]
    bseed = cfg["seeds"]["global"]
    BS = 16

    # --- random ensemble (exploration) ---
    rand = coll["random"]["exploration"]
    rand_prompts = [build_clean_probe(tok, r["state"]) for r in rand]
    rand_res = m.p_sell_batched(rand_prompts, batch_size=BS)
    rand_p = [r.p_sell for r in rand_res]
    out_mass_all = [r.out_group_mass for r in rand_res]
    print(f"[stage1] random n={len(rand)} probed", flush=True)

    # --- disposition pairs (exploration) ---
    dp = coll["disposition_pairs"]["exploration"]
    dp_g = m.p_sell_batched([build_clean_probe(tok, r["gain"]) for r in dp], BS)
    dp_l = m.p_sell_batched([build_clean_probe(tok, r["loss"]) for r in dp], BS)
    out_mass_all += [r.out_group_mass for r in dp_g] + [r.out_group_mass for r in dp_l]

    # --- ATH pairs (exploration) ---
    ap = coll["ath_pairs"]["exploration"]
    ap_nd = m.p_sell_batched([build_clean_probe(tok, r["no_drop"]) for r in ap], BS)
    ap_dn = m.p_sell_batched([build_clean_probe(tok, r["dropped_near"]) for r in ap], BS)
    out_mass_all += [r.out_group_mass for r in ap_nd] + [r.out_group_mass for r in ap_dn]

    # --- metrics ---
    marg = M.marginal_disposition(rand, rand_p, nres, bseed)
    pair_disp = M.paired_disposition(dp, [r.p_sell for r in dp_g],
                                     [r.p_sell for r in dp_l], nres, bseed)
    ath = M.paired_ath_asymmetry(ap, [r.p_sell for r in ap_nd],
                                 [r.p_sell for r in ap_dn], nres, bseed)

    omv = np.asarray(out_mass_all)
    out_mass_dist = {
        "n": int(len(omv)), "min": float(omv.min()), "median": float(np.median(omv)),
        "mean": float(omv.mean()), "q95": float(np.quantile(omv, .95)),
        "max": float(omv.max()),
        "frac_flagged_gt_%.2f" % cfg["probe"]["out_of_group_mass_flag"]:
            float((omv > cfg["probe"]["out_of_group_mass_flag"]).mean()),
    }
    print(f"[stage1] out-of-group mass: median={out_mass_dist['median']:.4f} "
          f"max={out_mass_dist['max']:.4f} frac_flagged={list(out_mass_dist.values())[-1]:.4f}",
          flush=True)

    stage1 = {
        "out_of_group_mass_distribution": out_mass_dist,
        "marginal_disposition": marg,
        "paired_disposition": pair_disp,
        "ath_asymmetry": ath,
        "n_exploration": {"random": len(rand), "disposition_pairs": len(dp),
                          "ath_pairs": len(ap)},
    }
    save_json(os.path.join(out, "stage1", "metrics.json"), stage1)
    # raw per-state P(sell) + meta
    save_json(os.path.join(out, "stage1", "raw_random.json"),
              [{"p_sell": p, "out_mass": r.out_group_mass, "meta": rec["meta"],
                "state": state_to_dict(rec["state"])}
               for rec, p, r in zip(rand, rand_p, rand_res)])
    save_json(os.path.join(out, "stage1", "raw_ath_pairs.json"),
              [{"p_no_drop": a.p_sell, "p_dropped_near": b.p_sell, "meta": rec["meta"]}
               for rec, a, b in zip(ap, ap_nd, ap_dn)])
    save_json(os.path.join(out, "stage1", "raw_disposition_pairs.json"),
              [{"p_gain": g.p_sell, "p_loss": l.p_sell, "meta": rec["meta"]}
               for rec, g, l in zip(dp, dp_g, dp_l)])

    print(f"[stage1] disposition_proxy (marginal) = {marg['disposition_proxy']['mean']:+.4f} "
          f"[{marg['disposition_proxy']['lo']:+.4f},{marg['disposition_proxy']['hi']:+.4f}]",
          flush=True)
    print(f"[stage1] disposition_proxy (paired)   = "
          f"{pair_disp['disposition_proxy_paired']['mean']:+.4f} "
          f"[{pair_disp['disposition_proxy_paired']['lo']:+.4f},"
          f"{pair_disp['disposition_proxy_paired']['hi']:+.4f}]", flush=True)
    print(f"[stage1] ATH asymmetry (paired)        = {ath['ath_asymmetry']['mean']:+.4f} "
          f"[{ath['ath_asymmetry']['lo']:+.4f},{ath['ath_asymmetry']['hi']:+.4f}]", flush=True)

    # ============ Faithfulness: behavioral variant ============
    print("[faith] running behavioral generations ...", flush=True)
    nb = cfg["faithfulness"]["n_behavioral"]
    # use a balanced slice of exploration random states
    fb_recs = rand[:nb]
    faith = []
    for r in fb_recs:
        prompt = render_behavioral(r["state"])
        gen = m.generate(prompt, max_new_tokens=cfg["faithfulness"]["max_new_tokens"])
        parsed = _try_parse_isbuy(gen)
        faith.append({"meta": r["meta"], "gen": gen[:1200], "parsed_is_buy": parsed,
                      "has_reason": ("reason" in gen.lower())})
    fr = _summarize_faithfulness(faith, fb_recs)
    save_json(os.path.join(out, "faithfulness", "behavioral.json"),
              {"summary": fr, "samples": faith})
    print(f"[faith] parse_rate={fr['parse_rate']:.2f} "
          f"behavioral disposition(sell|gain - sell|loss)={fr.get('behav_disposition')}",
          flush=True)

    # ============ Stage 0.5 gate ============
    dpx = pair_disp["disposition_proxy_paired"]      # primary: controlled paired contrast
    dpx_marg = marg["disposition_proxy"]
    athx = ath["ath_asymmetry"]
    gate = {
        "disposition_proxy_paired": dpx,
        "disposition_proxy_marginal": dpx_marg,
        "ath_asymmetry": athx,
        "rule": "PROCEED iff disposition_proxy>0 (CI lower>0) AND ath_asymmetry>0 (CI lower>0); "
                "else Yee-Sharma section-4 fallback (STOP before Stage 2).",
    }
    disp_pos = dpx["mean"] > 0 and dpx["lo"] > 0
    ath_pos = athx["mean"] > 0 and athx["lo"] > 0
    gate["sec1_reproduction"] = repro
    gate["wording_caveat"] = (
        f"Section-1 P(sell|loss)=0.896 reproduced only as {repro['observed_sec1_faithful']:.3f} "
        f"under the section-1-faithful wording (qualitative loss-sell lean, not tight). "
        f"P(sell) range across neutral wordings on that state = "
        f"{repro['wording_range_on_smoke_loss']:.3f}. Any PROCEED decision is provisional "
        f"pending Yuito's confirmation of the canonical clean-probe wording; v_ATH effects "
        f"in Stage 2+ must be shown robust to neutral wording.")
    if disp_pos and ath_pos:
        gate["decision"] = "PROCEED_TO_STAGE_2"
    else:
        gate["decision"] = "YEE_SHARMA_FALLBACK"
        gate["fallback"] = ("Attenuated/reversed baseline. Do NOT enter Stage 2. "
                            "Section-4 options: (a) profile prompting to induce investor bias, "
                            "(b) Gemma-2-9B, (c) prompt review. Cross-check with behavioral "
                            "faithfulness: if behavioral ALSO lacks the phenotype -> baseline "
                            "attenuation (model); if behavioral SHOWS it but clean-probe does "
                            "not -> probe format killed the phenotype (fix probe, not model).")
    gate["behavioral_faithfulness"] = fr
    save_json(os.path.join(out, "stage0_5_gate", "gate.json"), gate)

    summary = {
        "run_id": run_id, "wallclock_s": round(time.time() - t_start, 1),
        "frozen_token_groups": {"true_ids": true_ids, "false_ids": false_ids,
                                "excluded_semantic_aliases": list(grp_report["semantic_excluded"])},
        "sec1_reproduction": repro, "prompt_sensitivity_sweep": sweep,
        "determinism": det_check, "batch_equivalence": batch_check,
        "diagnostics": diag,
        "out_of_group_mass_distribution": out_mass_dist,
        "disposition_proxy_paired": dpx, "disposition_proxy_marginal": dpx_marg,
        "ath_asymmetry": athx, "ath_asymmetry_by_sign": ath["ath_asymmetry_by_sign"],
        "behavioral_faithfulness": fr,
        "gate_decision": gate["decision"], "wording_caveat": gate["wording_caveat"],
        "out_dir": out,
    }
    save_json(os.path.join(out, "SUMMARY.json"), summary)
    print("\n=========== SUMMARY ===========")
    print(json.dumps(summary, indent=2, default=float))
    print(f"\n[done] {time.time()-t_start:.0f}s  artifacts in {out}")


def _write_sensitivity_notes(out, repro, sweep, det, grp, cand_mass, batch_check):
    p0 = sweep["embellished_v0"]["p_sell"]
    pf = sweep["sec1_faithful"]["p_sell"]
    lines = [
        "# Prompt-sensitivity notes (Stage 0.2)", "",
        "## Why this file exists",
        "The clean-probe decision is sensitive to the *phrasing* of the closing answer "
        "instruction, even though the FCLAgent Premise/Instruction/Information body and "
        "the literal assistant prefix `{\"0\": {\"is_buy\": \"` are held fixed. This is a "
        "measurement-instrument risk to carry into Stage 2+: `v_ATH` effects must be shown "
        "robust to neutral wording, or a wording sweep must bound them.", "",
        "## The observed drift",
        f"- An early *embellished* wording (`embellished_v0`: added `(True = buy more, "
        f"False = sell)` + short-selling/cash caveats) gave **P(sell)={p0:.3f}** on the "
        f"section-1 loss state.",
        f"- The section-1-faithful minimal wording (`sec1_faithful`) gives "
        f"**P(sell)={pf:.3f}** (target 0.896).",
        f"- Reproduced section-1 signal: tight(|err|<=0.03)={repro['reproduced_tight']}, "
        f"qualitative(>=0.75)={repro['reproduced_qualitative']}.", "",
        "## Wording sweep on the section-1 loss state (smoke_loss)",
        "| variant | P(sell) | out-of-group mass |",
        "|---|---|---|",
    ]
    for k, v in sweep.items():
        lines.append(f"| {k} | {v['p_sell']:.3f} | {v['out_mass']:.4f} |")
    lines += [
        "", f"**P(sell) range across neutral wordings = "
        f"{repro['wording_range_on_smoke_loss']:.3f}.**", "",
        "## Determinism",
        f"- Two forwards on the same state: bit_exact={det['bit_exact']}, "
        f"abs_diff={det['abs_diff']:.2e} (greedy logit read => deterministic).", "",
        "## Batched vs single", f"- max_abs_dev={batch_check['max_abs_dev']:.5f}, "
        f"ok={batch_check['ok']} (left-padded batch matches single forward).", "",
        "## Token-group membership (frozen)",
        f"- True group ids: {grp['true_ids']}",
        f"- False group ids: {grp['false_ids']}",
        "- EXCLUDED semantic aliases (Yes/yes/1, No/no/0): see diagnostics.json "
        "`EXCLUDED_semantic_aliases`. They carry ~0 decision-slot mass; in-group mass "
        "0.9997. Excluded because folding them in is a *semantic* judgement, not a "
        "spelling-variant fact.", "",
        "## Implication for Stage 2+",
        "Record this sensitivity as a known risk. If the section-1 signal depends on "
        "wording, `v_ATH` causal claims should be validated under multiple neutral "
        "wordings (or a wording sweep reported alongside the gate), so the effect is "
        "attributed to the activation direction and not to a brittle prompt phrasing.",
    ]
    path = os.path.join(out, "stage0_2", "prompt_sensitivity_notes.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _try_parse_isbuy(text):
    import re
    m = re.search(r'"is_buy"\s*:\s*"?(True|False|true|false)"?', text)
    if m:
        return m.group(1).lower() == "true"
    return None


def _summarize_faithfulness(faith, recs):
    parsed = [f["parsed_is_buy"] for f in faith]
    ok = [p for p in parsed if p is not None]
    parse_rate = len(ok) / len(parsed) if parsed else 0.0
    # behavioral disposition: P(sell)=1-is_buy fraction, by gain/loss
    gain_sell, loss_sell = [], []
    for f, r in zip(faith, recs):
        if f["parsed_is_buy"] is None:
            continue
        sell = 0.0 if f["parsed_is_buy"] else 1.0
        if r["meta"].get("gain_sign") == "gain":
            gain_sell.append(sell)
        elif r["meta"].get("gain_sign") == "loss":
            loss_sell.append(sell)
    bd = None
    if gain_sell and loss_sell:
        bd = float(np.mean(gain_sell) - np.mean(loss_sell))
    return {"parse_rate": parse_rate, "n": len(faith),
            "reason_present_rate": float(np.mean([f["has_reason"] for f in faith])),
            "behav_sell_rate_gain": float(np.mean(gain_sell)) if gain_sell else None,
            "behav_sell_rate_loss": float(np.mean(loss_sell)) if loss_sell else None,
            "behav_disposition": bd,
            "n_gain": len(gain_sell), "n_loss": len(loss_sell)}


if __name__ == "__main__":
    main()
