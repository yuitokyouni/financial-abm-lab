"""propose — LLM-driven ABM proposal generator.

Pipeline:
  1. `summarize_corpus`  — read methods + runs + the fingerprint atlas, build
                           a compact JSON context (mechanism descriptions,
                           per-family centroids in standardised feature space,
                           parameter bounds already explored, sparse regions).
  2. `propose_from_corpus` — call Groq (free Llama 3.3 70B by default) with
                            a system prompt that asks for `n` structured
                            param-sweep proposals as JSON. Validates each
                            proposal against MODEL_BOUNDS and FEATURE_NAMES.
  3. `store_proposals`   — write validated proposals to the `proposals` table.

The Groq client is the only paid/network step. Everything else is local.

Auth: reads GROQ_API_KEY from the environment. Run `export GROQ_API_KEY=...`
or use GitHub Actions repo secrets.
"""
from __future__ import annotations

import json
import os
from typing import Any

import numpy as np

from .db import ensure_proposals_schema, insert_proposal, load_runs
from .fingerprint import FEATURE_NAMES, standardize, distance_matrix
from .adapters import MODEL_BOUNDS
from .methods import list_methods


DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


SYSTEM_PROMPT = """\
You are a research assistant proposing new agent-based model (ABM) parameter
combinations for a financial-market ABM atlas.

You will receive a JSON context describing:
  - implemented_methods  : per-model mechanism descriptions and user notes
  - parameter_bounds     : the (low, high) box already searched per model
  - atlas_state          : per-family centroid in *standardised* fingerprint
                           feature space, plus average within-family spread
  - feature_names        : the 9 feature dimensions of every fingerprint
  - sparse_regions       : a brief description of where the atlas is empty

Your task: propose `n` parameter sweeps that would EXTEND THE ATLAS.

Each proposal MUST be a JSON object with this exact shape:

  {
    "type": "param_sweep",
    "target_model": <model name from parameter_bounds>,
    "params": {<flat dict of the model's parameters>},
    "rationale": "<1-2 sentences in Japanese on why this proposal is interesting>",
    "predicted_fingerprint": {
        "volatility": <float>, "kurtosis": <float>, "hill_tail_index": <float>,
        "acf_ret_l1": <float>, "acf_absret_mean": <float>, "leverage": <float>,
        "acf_absret_long": <float>, "acf_absret_decay": <float>, "agg_kurt_decay": <float>
    },
    "predicted_novelty_distance": <float, the *standardised* L2 distance to the closest existing run>,
    "references": [<optional arxiv ids or paper citations>]
  }

Constraints, in order of importance:
  1. `params` MUST contain ALL the keys listed in parameter_bounds[target_model].
  2. Each param value SHOULD lie in [low, high] from parameter_bounds. If you
     deliberately step outside, keep within +-30% and explain why in `rationale`.
  3. The proposal SHOULD move toward a sparse region of the atlas. Concretely:
     pick a target_model whose centroid is near one of the sparse_regions, then
     choose params that push its fingerprint further in that direction.
  4. predicted_fingerprint must be your best educated guess of what the run
     will produce. It will be measured against reality.
  5. Diversify: across the n proposals, do NOT repeat the same target_model.
     If n > number_of_models, allow repeats but vary the strategy.

Output: a single JSON object with key "proposals" whose value is an array of
exactly `n` proposal objects. No prose around the JSON.
"""


def _per_family_centroids(rows: list[dict]) -> dict[str, list[float]]:
    """Return per-model centroid in standardised feature space."""
    if not rows:
        return {}
    fps = np.vstack([r["fingerprint"] for r in rows])
    fps_std, _, _ = standardize(fps)
    labels = np.array([r["model_name"] for r in rows])
    centroids: dict[str, list[float]] = {}
    for lab in sorted(set(labels)):
        mask = labels == lab
        c = np.nanmean(fps_std[mask], axis=0)
        centroids[lab] = [round(float(v), 3) for v in c.tolist()]
    return centroids


def _describe_sparse_regions(rows: list[dict], n_regions: int = 3) -> list[dict]:
    """Find sparse regions of the atlas by k-NN density estimation.

    Heuristic: standardise, compute each point's mean k-NN distance, return
    the `n_regions` highest-density-gap points (i.e. the most isolated runs).
    For each report the centre point coords and which family it belongs to.
    """
    if len(rows) < 5:
        return []
    fps = np.vstack([r["fingerprint"] for r in rows])
    fps_std, _, _ = standardize(fps)
    D = distance_matrix(fps_std)
    np.fill_diagonal(D, np.inf)
    k = min(3, len(rows) - 1)
    knn_means = np.sort(D, axis=1)[:, :k].mean(axis=1)
    order = np.argsort(knn_means)[::-1]
    out = []
    for idx in order[:n_regions]:
        out.append({
            "near_family": rows[idx]["model_name"],
            "centre_in_standardised_space": [round(float(v), 3) for v in fps_std[idx].tolist()],
            "isolation_distance": round(float(knn_means[idx]), 3),
        })
    return out


def summarize_corpus(db_path: str) -> dict[str, Any]:
    """Build the JSON context handed to the LLM."""
    runs = load_runs(db_path)
    methods = list_methods(db_path)
    methods_summary = []
    for m in methods:
        methods_summary.append({
            "name": m.name, "kind": m.kind,
            "mechanism": m.mechanism,
            "user_notes": {
                "novelty_notes": m.novelty_notes,
                "mechanism_strengths": m.mechanism_strengths,
                "mechanism_weaknesses": m.mechanism_weaknesses,
                "research_questions": m.research_questions,
                "tags": m.tags,
            } if any([m.novelty_notes, m.mechanism_strengths, m.mechanism_weaknesses,
                      m.research_questions, m.tags]) else None,
        })
    return {
        "implemented_methods": methods_summary,
        "parameter_bounds": {k: {p: list(b) for p, b in v.items()}
                             for k, v in MODEL_BOUNDS.items()},
        "atlas_state": {
            "n_runs": len(runs),
            "per_family_centroids_in_standardised_space": _per_family_centroids(runs),
        },
        "feature_names": FEATURE_NAMES,
        "sparse_regions": _describe_sparse_regions(runs),
    }


def _call_groq(system_prompt: str, user_payload: dict, model: str,
               temperature: float = 0.7) -> dict:
    """Single Groq chat-completion call returning parsed JSON."""
    try:
        from groq import Groq
    except ImportError as e:
        raise ImportError(
            "groq SDK not installed. Add it with `uv add groq` or "
            "`pip install groq`."
        ) from e
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set.")
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    raw = resp.choices[0].message.content
    return json.loads(raw)


def _validate_proposal(p: dict, n_features: int) -> tuple[bool, str]:
    """Lightweight validation. Returns (ok, error_message)."""
    if not isinstance(p, dict):
        return False, "not a dict"
    for k in ("type", "target_model", "params", "rationale"):
        if k not in p:
            return False, f"missing key {k!r}"
    if p["type"] != "param_sweep":
        return False, f"unsupported type {p['type']!r}; expected 'param_sweep'"
    if p["target_model"] not in MODEL_BOUNDS:
        return False, f"unknown target_model {p['target_model']!r}"
    if not isinstance(p["params"], dict) or not p["params"]:
        return False, "params must be a non-empty dict"
    if "predicted_fingerprint" in p and p["predicted_fingerprint"] is not None:
        pf = p["predicted_fingerprint"]
        if not isinstance(pf, dict):
            return False, "predicted_fingerprint must be a dict"
        missing = set(FEATURE_NAMES) - set(pf.keys())
        if missing:
            return False, f"predicted_fingerprint missing keys: {missing}"
    return True, ""


def propose_from_corpus(db_path: str, n: int = 5, *,
                        groq_model: str = DEFAULT_GROQ_MODEL,
                        temperature: float = 0.7,
                        dry_run_payload: dict | None = None
                        ) -> list[dict]:
    """Generate n proposals, validate, write each accepted one to DB.

    dry_run_payload : if provided, skip the LLM call and use this dict as the
                      parsed response. Lets tests exercise the parse/validate/
                      store path without network.
    """
    ensure_proposals_schema(db_path)
    context = summarize_corpus(db_path)
    payload = {"n": n, "task": "propose n param_sweep ABMs to extend the atlas",
               "context": context}
    if dry_run_payload is None:
        response = _call_groq(SYSTEM_PROMPT, payload, groq_model, temperature)
    else:
        response = dry_run_payload
    proposals = response.get("proposals", [])
    if not isinstance(proposals, list):
        raise ValueError(f"LLM returned proposals of type {type(proposals).__name__}; expected list")

    accepted: list[dict] = []
    rejected: list[dict] = []
    for p in proposals:
        ok, err = _validate_proposal(p, len(FEATURE_NAMES))
        if not ok:
            rejected.append({"proposal": p, "error": err})
            continue
        pid = insert_proposal(
            db_path,
            proposal_type=p["type"],
            target_model=p["target_model"],
            params=p["params"],
            rationale=p["rationale"],
            predicted_fingerprint=p.get("predicted_fingerprint"),
            predicted_novelty_distance=p.get("predicted_novelty_distance"),
            references=p.get("references", []),
            llm_model=groq_model,
        )
        accepted.append({**p, "id": pid})
    return [{"accepted": accepted, "rejected": rejected,
             "llm_model": groq_model, "n_requested": n}]
