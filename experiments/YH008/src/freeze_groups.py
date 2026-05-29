"""Stage 0.2 part A: inspect tokenizer, measure decision-slot mass per candidate
spelling across a diagnostic battery, and FREEZE the True/False token groups.

Decision rule (deterministic, not tuned):
  - a candidate enters a group only if it is a SINGLE token id;
  - True-group = case/whitespace variants of "true"; False-group = variants of "false";
  - semantic aliases (Yes/yes/1 ; No/no/0) are EXCLUDED and flag-reported: they carry
    ~0 decision-slot mass here AND folding them in is a semantic judgement, not a
    spelling-variant fact. (If they ever carry real mass, this must be revisited.)
The frozen set + the measured mass table are saved as an artifact.
"""
from __future__ import annotations
import torch

TRUE_SPELLINGS = ["True", " True", "true", " true", "TRUE", " TRUE"]
FALSE_SPELLINGS = ["False", " False", "false", " false", "FALSE", " FALSE"]
SEMANTIC_TRUE = ["Yes", " Yes", "yes", " yes", "1", " 1"]
SEMANTIC_FALSE = ["No", " No", "no", " no", "0", " 0"]


def _single_id(tok, s):
    ids = tok.encode(s, add_special_tokens=False)
    return ids[0] if len(ids) == 1 else None


def freeze_groups(tokenizer):
    """Return (true_ids, false_ids, report). Uses only the tokenizer."""
    report = {"true_spellings": {}, "false_spellings": {},
              "semantic_excluded": {}, "rule": (
                  "single-token case/whitespace variants of true/false only; "
                  "Yes/No/1/0 excluded (semantic alias, ~0 mass)")}
    true_ids, false_ids = [], []
    for s in TRUE_SPELLINGS:
        i = _single_id(tokenizer, s)
        report["true_spellings"][s] = i
        if i is not None:
            true_ids.append(i)
    for s in FALSE_SPELLINGS:
        i = _single_id(tokenizer, s)
        report["false_spellings"][s] = i
        if i is not None:
            false_ids.append(i)
    for s in SEMANTIC_TRUE + SEMANTIC_FALSE:
        report["semantic_excluded"][s] = _single_id(tokenizer, s)
    # dedupe (some spellings can share an id after normalization)
    true_ids = sorted(set(true_ids))
    false_ids = sorted(set(false_ids))
    overlap = set(true_ids) & set(false_ids)
    report["overlap_ids"] = sorted(overlap)
    report["true_ids"] = true_ids
    report["false_ids"] = false_ids
    return true_ids, false_ids, report


@torch.no_grad()
def measure_candidate_mass(model_obj, prompts):
    """Mean decision-slot probability of each candidate spelling + the semantic
    aliases across `prompts`. model_obj is a ProbeModel (uses its tokenizer/model)."""
    tok = model_obj.tokenizer
    allc = TRUE_SPELLINGS + FALSE_SPELLINGS + SEMANTIC_TRUE + SEMANTIC_FALSE
    cand_ids = {c: _single_id(tok, c) for c in allc}
    acc = {c: [] for c in allc}
    for p in prompts:
        toks, mask = model_obj._to_tokens(p)
        logits = model_obj.model(toks, attention_mask=mask)
        probs = torch.softmax(logits[0, -1].float(), dim=-1)
        for c, i in cand_ids.items():
            acc[c].append(probs[i].item() if i is not None else float("nan"))
    import numpy as np
    return {c: (float(np.nanmean(v)) if len(v) else float("nan")) for c, v in acc.items()}
