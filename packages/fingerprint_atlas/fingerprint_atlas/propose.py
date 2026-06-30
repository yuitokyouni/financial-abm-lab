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
import re
from typing import Any

import numpy as np

from .db import ensure_proposals_schema, insert_proposal, load_literature, load_runs
from .fingerprint import FEATURE_NAMES, standardize, distance_matrix
from .adapters import MODEL_BOUNDS, PRICELESS_MODELS
from .methods import list_methods


# gpt-oss-120b: OpenAI's open-source 120B model, free tier on Groq. Chosen
# after A/B testing — the only Groq free-tier model whose rationales reflect
# actual ABM mechanism understanding (e.g. naming Cont-Bouchaud percolation
# threshold + predicting power-law cluster sizes). Other Groq free-tier
# options collapse into template Japanese ("〜を目的としています") that the
# validator rejects, so they are not viable substitutes for this task.
#
# Known quirk: gpt-oss-120b occasionally returns malformed JSON under JSON
# mode (Groq 400 'json_validate_failed'). _call_groq retries with a slight
# temperature jitter; usually one retry is enough.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


SYSTEM_PROMPT = """\
You are a research assistant proposing new agent-based model (ABM) parameter
combinations for a financial-market ABM atlas.

You will receive a JSON context describing:
  - implemented_methods    : per-model mechanism descriptions and user notes
  - parameter_bounds       : the (low, high) box already searched per model
  - priceless_models       : list of models that do NOT produce a price/return
                             series — their fingerprint is computed on
                             attendance_excess (2A-N) and behaves differently
  - feature_typical_ranges : per-feature observed range in the current corpus,
                             use these to keep predicted_fingerprint plausible
  - atlas_state            : per-family centroid in *standardised* fingerprint
                             feature space
  - feature_names          : the 9 feature dimensions of every fingerprint
  - sparse_regions         : the 3 most isolated existing runs (potential gaps)
  - literature             : arxiv papers your proposals should cite when the
                             mechanism is genuinely close to a published one

Your task: propose `n` parameter sweeps that would EXTEND THE ATLAS.

Each proposal MUST be a JSON object with this exact shape:

  {
    "type": "param_sweep",
    "target_model": <model name from parameter_bounds>,
    "params": {<flat dict of the model's parameters; MUST cover every key from
               parameter_bounds[target_model]>},
    "rationale": "<2-4 sentences in Japanese. MANDATORY non-empty. Explain
                   (a) WHICH region of fingerprint space this aims at, (b) WHY
                   these param values push there, (c) if applicable, which
                   paper in `literature` inspired the choice.>",
    "predicted_fingerprint": {
        "volatility": <float>, "kurtosis": <float>, "hill_tail_index": <float>,
        "acf_ret_l1": <float>, "acf_absret_mean": <float>, "leverage": <float>,
        "acf_absret_long": <float>, "acf_absret_decay": <float>,
        "agg_kurt_decay": <float>
    },
    "predicted_novelty_distance": <float; the *standardised* L2 distance to the
                                   nearest existing run. Use atlas_state and
                                   feature_typical_ranges to estimate.>,
    "references": [<arxiv_ids picked from literature[]; OR paper citations>]
  }

Constraints, in order of priority:
  1. `params` MUST contain every key in parameter_bounds[target_model].
     Missing keys → your proposal is dropped silently.
  2. Each param value SHOULD lie in [low, high]. Stepping outside by up to ±30%
     is allowed but MUST be justified in `rationale`.
  3. For target_model in priceless_models, the fingerprint is computed on
     `attendance_excess = 2A - N` (units of agents, NOT log-returns).
     - volatility for these is large (often 10-60), not 0.005-0.05.
     - hill_tail_index saturates at 20 (no power-law tail in discrete attendance).
     - acf_absret_* tend to be near 0.
     If you propose a priceless model, your predicted_fingerprint MUST reflect
     this. Do NOT predict volatility ~0.01 for minority_game.
  4. `rationale` MUST be non-empty Japanese. An empty rationale is invalid.
  5. Across the n proposals, prefer diversifying target_model and the region
     of fingerprint space targeted.
  6. references[] is MANDATORY when literature[] in the context is non-empty.
     Pick the paper whose mechanism is closest to your proposal and put its
     arxiv_id in references[]. In `rationale`, explicitly explain HOW your
     proposal relates to that paper (transfer / extension / stress test /
     contrast). A purely-parameter-sweep proposal with no literature link is
     not useful here — re-anchor it to a paper if you must.
  7. `rationale` MUST be specific, NOT a template. Bad rationale (will be
     rejected): "このパラメータスイープは、エージェントとダイナミクスの関係を
     調べることを目的としています". Good rationale: names a target FEATURE
     (e.g. "acf_absret_long > 0.2"), a paper, and a concrete mechanism
     conjecture.

Output: a single JSON object with key "proposals" whose value is an array of
exactly `n` proposal objects. No prose around the JSON.
"""


# Japanese template phrases the LLM defaults to when it has nothing to say.
# Anything containing one of these is treated as a "template rationale" and
# the proposal is rejected by the validator. List grew from a real failed
# run on llama-3.3-70b-versatile.
_RATIONALE_TEMPLATE_BLACKLIST = [
    "を目的としています",        # "the purpose is to ..."
    "関係を調べる",              # "investigate the relationship"
    "影響を調べる",              # "investigate the effect"
    "ダイナミクスを調べる",       # "investigate the dynamics"
    "の理解を深める",            # "deepen understanding"
    "明らかにする",              # "make clear" (used as filler)
]

# Concrete signals that ANY useful rationale should contain at least one of.
# Either an English-language stylized-facts keyword, a Japanese feature term,
# or an explicit arxiv id / numeric target.
_RATIONALE_CONCRETE_KEYWORDS = [
    # English fingerprint vocabulary
    "volatility", "kurtosis", "hill", "leverage", "acf",
    "long memory", "long-memory", "fat tail", "fat-tail",
    "clustering", "regime", "tail index",
    # Japanese fingerprint vocabulary
    "ボラ", "尖度", "裾", "クラスタ", "長期記憶",
    "ファットテール", "レバレッジ", "自己相関",
    # citation markers
    "arXiv:", "arxiv:", "arxiv.org",
]


_ARXIV_ID_RE = re.compile(
    r'(?:arXiv\s*:?\s*|arxiv\s*:?\s*|arxiv\.org/abs/)?'
    r'(\d{4}\.\d{4,5})(v\d+)?',
    re.IGNORECASE,
)


def _arxiv_base(aid: str) -> str:
    """Strip a trailing version suffix from an arxiv ID."""
    return aid.split("v")[0]


def _extract_arxiv_id(reference: str) -> str | None:
    """Return the normalised arxiv ID inside a reference string, or None.

    Handles 'arXiv:2605.00854v1', '2605.00854v1', 'arxiv:2605.00854',
    'https://arxiv.org/abs/2605.00854', '2605.00854'. Free-form citations
    like 'Cont 2001' or 'Lux & Marchesi 2000' return None — they are
    treated as non-arxiv (and therefore unverifiable but not flagged).
    """
    m = _ARXIV_ID_RE.search(reference.strip())
    if not m:
        return None
    base = m.group(1)
    version = m.group(2) or ""
    return base + version


def classify_references(references: list[str], db_path: str) -> dict[str, list[str]]:
    """Bucket every reference into in_db / external_arxiv / non_arxiv.

    in_db          : arxiv id (base, version-stripped) is present in
                     literature_methods.arxiv_id
    external_arxiv : looks like an arxiv id but is NOT in the local DB —
                     the LLM probably pulled it from pre-training; suspect
                     of hallucination
    non_arxiv      : doesn't parse as an arxiv id (e.g. 'Lux & Marchesi 2000');
                     not verifiable here, no warning emitted
    """
    from .db import ensure_literature_schema, load_literature
    # Defensive: the literature_methods table may not exist yet — e.g. on a
    # fresh DB where the user hasn't ingested any arxiv papers. Create it
    # (idempotent) so load_literature returns an empty list rather than
    # raising OperationalError.
    ensure_literature_schema(db_path)
    rows = load_literature(db_path)
    known_bases = {_arxiv_base(r["arxiv_id"]) for r in rows}
    result: dict[str, list[str]] = {"in_db": [], "external_arxiv": [], "non_arxiv": []}
    for ref in references:
        aid = _extract_arxiv_id(ref)
        if aid is None:
            result["non_arxiv"].append(ref)
        elif _arxiv_base(aid) in known_bases:
            result["in_db"].append(ref)
        else:
            result["external_arxiv"].append(ref)
    return result


def _rationale_quality(rat: str) -> tuple[bool, str]:
    """Return (ok, error). Rejects template phrases and rationales lacking
    any concrete signal (no feature name, no citation, no number)."""
    import re
    s = rat.strip()
    for phrase in _RATIONALE_TEMPLATE_BLACKLIST:
        if phrase in s:
            return False, f"rationale contains template phrase {phrase!r}"
    lower = s.lower()
    has_concrete_kw = any(k.lower() in lower for k in _RATIONALE_CONCRETE_KEYWORDS)
    has_number = bool(re.search(r"\d", s))
    if not (has_concrete_kw or has_number):
        return False, ("rationale lacks concrete signal — no feature name, "
                       "no arxiv id, no numeric target")
    return True, ""


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


def _feature_typical_ranges(rows: list[dict]) -> dict[str, list[float]]:
    """Per-feature 10th, 50th, 90th percentile across the population.

    Tells the LLM what a "plausible" value for each feature looks like — a
    direct counter to the empty-rationale / wildly-off-fingerprint failure
    mode observed with the v1 prompt.
    """
    if not rows:
        return {}
    fps = np.vstack([r["fingerprint"] for r in rows])
    out: dict[str, list[float]] = {}
    for i, name in enumerate(FEATURE_NAMES):
        col = fps[:, i]
        finite = col[np.isfinite(col)]
        if finite.size == 0:
            out[name] = [float("nan"), float("nan"), float("nan")]
        else:
            qs = np.quantile(finite, [0.10, 0.50, 0.90])
            out[name] = [round(float(q), 4) for q in qs]
    return out


def _select_literature_for_context(rows: list[dict], top_n: int = 15) -> list[dict]:
    """Pick the top_n papers most relevant to atlas extension.

    Strategy: relevance_score descending, then year descending. Drop papers
    with no extraction yet (no relevance_score → not informative for the LLM).
    Each entry is shrunk to essentials so the context stays small.
    """
    eligible = [r for r in rows
                if r.get("relevance_score") is not None
                and r.get("mechanism_summary")]
    eligible.sort(key=lambda r: (-(r["relevance_score"] or 0), -(r["year"] or 0)))
    out = []
    for r in eligible[:top_n]:
        out.append({
            "arxiv_id": r["arxiv_id"],
            "title": r["title"],
            "year": r["year"],
            "mechanism_summary": r["mechanism_summary"],
            "mechanism_tags": r["mechanism_tags"],
            "stylized_facts_targeted": r["stylized_facts_targeted"],
            "novelty_signal": r["novelty_signal"],
        })
    return out


def summarize_corpus(db_path: str, *, literature_top_n: int = 7) -> dict[str, Any]:
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

    # Literature: load all and pick the top N. The DB may be empty (no
    # ingestion yet) — return [] in that case rather than failing.
    try:
        literature_all = load_literature(db_path)
    except Exception:
        literature_all = []
    literature_for_prompt = _select_literature_for_context(literature_all, top_n=literature_top_n)

    return {
        "implemented_methods": methods_summary,
        "parameter_bounds": {k: {p: list(b) for p, b in v.items()}
                             for k, v in MODEL_BOUNDS.items()},
        "priceless_models": sorted(PRICELESS_MODELS),
        "feature_typical_ranges_pct_10_50_90": _feature_typical_ranges(runs),
        "atlas_state": {
            "n_runs": len(runs),
            "per_family_centroids_in_standardised_space": _per_family_centroids(runs),
        },
        "feature_names": FEATURE_NAMES,
        "sparse_regions": _describe_sparse_regions(runs),
        "literature": literature_for_prompt,
        "n_literature_total": len(literature_all),
    }


def _call_groq(system_prompt: str, user_payload: dict, model: str,
               temperature: float = 0.7, max_retries: int = 2) -> dict:
    """Backwards-compatible alias for `llm_client.call_llm`. Routes to
    OpenAI when `model` is an OpenAI chat model id, otherwise Groq."""
    from .llm_client import call_llm
    return call_llm(system_prompt, user_payload, model,
                    temperature=temperature, max_retries=max_retries,
                    generate_japanese=True,
                    glossary_domain="financial-abm")


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
    # require every key in the model's MODEL_BOUNDS
    required_keys = set(MODEL_BOUNDS[p["target_model"]].keys())
    missing_params = required_keys - set(p["params"].keys())
    if missing_params:
        return False, f"params missing required keys: {sorted(missing_params)}"
    # rationale: must be a non-empty string with concrete content
    rat = p.get("rationale")
    if not isinstance(rat, str) or not rat.strip():
        return False, "rationale is empty or not a string"
    if len(rat.strip()) < 20:
        return False, f"rationale too short ({len(rat.strip())} chars; need >= 20)"
    ok_q, err_q = _rationale_quality(rat)
    if not ok_q:
        return False, err_q
    if "predicted_fingerprint" in p and p["predicted_fingerprint"] is not None:
        pf = p["predicted_fingerprint"]
        if not isinstance(pf, dict):
            return False, "predicted_fingerprint must be a dict"
        missing = set(FEATURE_NAMES) - set(pf.keys())
        if missing:
            return False, f"predicted_fingerprint missing keys: {sorted(missing)}"
    return True, ""


def propose_from_corpus(db_path: str, n: int = 5, *,
                        groq_model: str = DEFAULT_GROQ_MODEL,
                        temperature: float = 0.7,
                        literature_top_n: int = 7,
                        dry_run_payload: dict | None = None
                        ) -> list[dict]:
    """Generate n proposals, validate, write each accepted one to DB.

    literature_top_n : how many papers to include in the LLM context.
                       Trade-off: more papers = better grounding but a larger
                       prompt. Groq's free tier caps gpt-oss-120b at
                       8000 TPM — keep this <= 8 there. For paid tiers
                       (or smaller models with lower per-paper cost) it can
                       go higher.

    dry_run_payload : if provided, skip the LLM call and use this dict as the
                      parsed response. Lets tests exercise the parse/validate/
                      store path without network.
    """
    ensure_proposals_schema(db_path)
    context = summarize_corpus(db_path, literature_top_n=literature_top_n)
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
        accepted_p = {**p, "id": pid}
        # classify citations so the CLI can warn about hallucinated arxiv ids
        refs = p.get("references", [])
        if refs:
            accepted_p["reference_validation"] = classify_references(refs, db_path)
        accepted.append(accepted_p)
    return [{"accepted": accepted, "rejected": rejected,
             "llm_model": groq_model, "n_requested": n}]
