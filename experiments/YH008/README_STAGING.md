# YH008 Stage 0.2 + Stage 1 — staging directory

**Why this lives in `/root` and not the repo:** the `/workspace` moosefs volume is at
its hard disk quota (Errno 122 EDQUOT) — every write there produces a 0-byte file (this
also truncated the YH008 spec PDFs/MD and ~1876 working-tree files, and blocks git's
index.lock). `/root` is writable but the overlay only has ~7.7 G free, which is fine for
Stage 1 (code + small JSON + per-state P(sell); no activation cache needed until Stage 2).
The 15 G model weights are **read** (not written) from the existing cache at
`/workspace/.hf/hub/models--meta-llama--Llama-3.1-8B-Instruct/` (reads are unaffected by
the quota). Yuito chose "stage in /root, move later".

## Layout
```
/root/yh008_work/
  src/
    config.yaml        # per-run config (ranges centered on FCLAgent 4.1; thresholds frozen)
    render.py          # state -> prompt (behavioral + clean-probe + wording variants)
    model.py           # backend-neutral API (TL now; nnsight swappable): p_sell/cache/hook
    states.py          # ensemble + paired-state generators, exploration/held-out split
    metrics.py         # disposition proxy, ATH asymmetry, bootstrap CIs
    freeze_groups.py   # Stage 0.2A: freeze True/False token groups from tokenizer
    run_all.py         # driver: Stage 0.2 -> Stage 1 -> faithfulness -> Stage 0.5 gate
  outputs/{run_id}/    # artifacts (run_id = timestamp + git short hash)
    stage0/            # provenance.json, config_snapshot.yaml
    stage0_2/          # diagnostics.json, prompt_sensitivity_notes.md
    stage1/            # metrics.json, raw_random.json, raw_*_pairs.json
    faithfulness/      # behavioral.json
    stage0_5_gate/     # gate.json
    SUMMARY.json
```

## Reproduce
```
cd /root/yh008_work/src
HF_HOME=/workspace/.hf python run_all.py     # single model load, ~15 min on A100-80GB
```

## Relocating into the repo once the quota is raised
```
rsync -a /root/yh008_work/src/      <repo>/experiments/YH008/src/
rsync -a /root/yh008_work/outputs/  <repo>/experiments/YH008/outputs/
```
Nothing under `/root/yh008_work` touches the repo or any of Yuito's data; the move is a
straight copy. The model revision is pinned in config.yaml
(`0e9e39f249a16976918f6564b8830bc894c89659`).
