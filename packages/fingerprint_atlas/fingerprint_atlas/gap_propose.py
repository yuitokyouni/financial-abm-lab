"""gap_propose — turn a detected research gap into a structured proposal.

Pipeline:
  1. gap_finder identifies an under-explored cell (e.g. 'Prospect theory ×
     regime-switching: 21 papers in the subfield, 0 targeting that fact').
  2. This module asks the LLM to draft a concrete experiment closing the
     gap: which ABM family to deploy, what params, what mechanism would
     produce the missing fact, what to measure, what corpus references
     motivate the design.
  3. The result is validated and inserted into the `proposals` table with
     `proposal_type='gap_mine'` so downstream (propose CLI, dashboard)
     can list / execute it like any other proposal.

The LLM call is routed through llm_client.call_llm with
generate_japanese=True, so glossary rules apply (no '富動学' / '指紋',
'動学' banned, plain-Japanese gloss for opaque concepts).
"""
from __future__ import annotations

import json
import re
from typing import Any

from .llm_client import call_llm


DEFAULT_LLM_MODEL = "openai/gpt-oss-120b"


_SYSTEM_PROMPT = """あなたは金融エージェントベース・モデル研究の専門家。

ユーザのコーパスから検出された「研究空白 (gap)」を1つ渡される。
あなたの仕事は、その空白を埋める concrete な実験提案を1つ生成すること。

入力に含まれるもの:
  gap_view: 'A' | 'B' | 'C' (検出 view 種別)
  subfield_or_family: 行ラベル (分野名 or ABM 家系名)
  stylized_fact: 列ラベル (target したい事実)
  evidence: 1行説明
  available_families: 使える ABM 家系のリスト
    各 entry に `params_allowed` (この family の registry が受け付ける
    param key と範囲) と `mechanism` が付く
  feature_names: 市場特徴量ベクトルの 9 成分(predicted_fingerprint の key)
  already_used_families: 同バッチで既に proposal target にしたキー(多様化のため)
  related_papers: コーパス内の関連論文 (arxiv_id + title)

出力 JSON:
{
  "target_model": "<available_families の中の key>",
  "params": {<params_allowed の key だけを使う dict、範囲も尊重>},
  "rationale": "<2-4 文の日本語。(a) なぜこの空白が面白いか、(b) 想定機構、
                 (c) 評価基準/期待される結果 を含める。MANDATORY>",
  "predicted_fingerprint": {<feature_names の各 key に float 値。MANDATORY 非 null。
                             仮説の方向が出る成分(例: long-memory なら acf_absret_long,
                             acf_absret_decay)に具体値を入れ、無関係な成分は
                             既存値の近似で良いが必ず全 9 成分を埋める>},
  "references": [<arxiv_id か 'oa:Wxxx'、related_papers の中だけから最大3つ>]
}

絶対に守る制約 (違反すると validate で reject される):
1. `params` の key は target_model の `params_allowed` に含まれる key だけ。
   新規パラメータ (memory_exponent 等) を勝手に作らない。提案する機構が
   既存パラメータで表現できないなら rationale に「impl 拡張が必要」と
   明示すること。
2. `predicted_fingerprint` は MANDATORY 非 null。feature_names の 9 成分
   すべてに float 値を入れる。仮説と無関係な成分は 0 や中央値で良いが
   key は省略しない。
3. `references` は related_papers のリストにある arxiv_id だけを使う。
   LLM 内部知識からの hallucination は禁止。
4. `target_model` は available_families の key だけ。'new' は禁止
   (run できないため)。
5. `already_used_families` に含まれる key は **可能なら避ける**。
   同じ家系を連続提案しないように、同じ gap でも同等に妥当な別家系が
   あればそちらを選ぶ。

家系選択の指針:
- 認知バイアス系 → speculation_game (3層認知)
- 戦略切替/ヘテロジニアス → franke_westerhoff or lux_marchesi
- 群集行動 → kirman_ant (将来) or lux_marchesi
- LOB / 価格形成 → chiarella_iori
- 構造的 null として → zero_intelligence
"""


def _summarise_families(families: list[dict],
                         model_bounds: dict[str, dict] | None = None
                         ) -> list[dict]:
    """Compact family entries for the prompt. When `model_bounds` is
    supplied, attach the per-family `params_allowed` dict so the LLM
    cannot fabricate new param keys."""
    out: list[dict] = []
    for f in families:
        item = {
            "key": f["key"], "name": f["name"],
            "mechanism": f.get("mechanism", "")[:200],
        }
        if model_bounds is not None:
            bounds = model_bounds.get(f["key"])
            if bounds is not None:
                item["params_allowed"] = {
                    k: list(v) if isinstance(v, tuple) else v
                    for k, v in bounds.items()
                }
            else:
                # Family in catalog but no LHS bounds → no registry entry,
                # so the LLM can't usefully propose params for it.
                item["params_allowed"] = {}
                item["impl_status"] = "not-in-registry"
        out.append(item)
    return out


def _summarise_papers(papers: list[dict], n: int = 8) -> list[dict]:
    """Compact paper records for the LLM context (top-N by cite count).

    Sort key is the cite count alone — tuple comparison would fall
    through to the dict on ties and raise TypeError on Python 3.11+.
    """
    keyed = []
    for p in papers:
        cite = p.get("oa_cited_by_count") or 0
        keyed.append((cite, {
            "arxiv_id": p.get("arxiv_id"),
            "title": (p.get("title") or "")[:120],
            "year": p.get("year"),
            "cite": cite,
        }))
    keyed.sort(key=lambda kv: kv[0], reverse=True)
    return [k[1] for k in keyed[:n]]


def build_proposal_payload(gap: dict, *,
                            corpus_papers: list[dict],
                            families: list[dict],
                            model_bounds: dict[str, dict] | None = None,
                            feature_names: list[str] | None = None,
                            already_used_families: list[str] | None = None,
                            ) -> dict:
    """Assemble the user payload for the LLM, scoped to a single gap.

    `model_bounds` (adapters.MODEL_BOUNDS) lets the LLM see the exact
    param keys + ranges each family registers, so it stops inventing
    new param names. `feature_names` enforces all 9 components in the
    predicted_fingerprint. `already_used_families` is a soft-diversity
    hint for the batch caller.
    """
    return {
        "gap_view": gap.get("view"),
        "subfield_or_family": gap.get("row"),
        "stylized_fact": gap.get("col"),
        "evidence": gap.get("why", ""),
        "row_total_papers": int(gap.get("row_total", 0)),
        "available_families": _summarise_families(families, model_bounds),
        "feature_names": list(feature_names or []),
        "already_used_families": list(already_used_families or []),
        "related_papers": _summarise_papers(corpus_papers, n=8),
    }


def propose_from_gap(gap: dict, *,
                      corpus_papers: list[dict],
                      families: list[dict],
                      model_bounds: dict[str, dict] | None = None,
                      feature_names: list[str] | None = None,
                      already_used_families: list[str] | None = None,
                      llm_model: str = DEFAULT_LLM_MODEL,
                      temperature: float = 0.6,
                      dry_run_response: dict | None = None) -> dict:
    """Generate a proposal JSON for a single gap.

    Returns the validated proposal dict. Raises ValueError if the LLM
    output is malformed and unrecoverable.

    Constraints applied during validation:
      - target_model must be in `families` (no 'new')
      - rationale must be non-empty
      - if `model_bounds` is supplied: params keys must be a subset of
        the target family's allowed param keys
      - if `feature_names` is supplied: predicted_fingerprint must
        cover all 9 components (no nulls / missing keys)
    """
    payload = build_proposal_payload(
        gap, corpus_papers=corpus_papers, families=families,
        model_bounds=model_bounds, feature_names=feature_names,
        already_used_families=already_used_families,
    )
    if dry_run_response is not None:
        result = dry_run_response
    else:
        result = call_llm(
            _SYSTEM_PROMPT, payload, llm_model,
            temperature=temperature, max_retries=2,
            generate_japanese=True, glossary_domain="financial-abm",
        )
    target = result.get("target_model")
    rationale = (result.get("rationale") or "").strip()
    if not target:
        raise ValueError("LLM returned no target_model")
    if not rationale:
        raise ValueError("LLM returned empty rationale (mandatory field)")
    family_keys = {f["key"] for f in families}
    if target not in family_keys:
        raise ValueError(f"target_model {target!r} not in available "
                          f"families {sorted(family_keys)} "
                          f"('new' is no longer accepted)")
    params = result.get("params") or {}
    if model_bounds is not None and target in model_bounds:
        allowed = set(model_bounds[target].keys())
        bad = [k for k in params if k not in allowed]
        if bad:
            raise ValueError(
                f"params include keys not in registry for "
                f"{target}: {bad}. Allowed: {sorted(allowed)}")
    predicted_fp = result.get("predicted_fingerprint")
    if feature_names:
        if predicted_fp is None or not isinstance(predicted_fp, dict):
            raise ValueError("predicted_fingerprint is mandatory non-null")
        missing = [n for n in feature_names if predicted_fp.get(n) is None]
        if missing:
            raise ValueError(
                f"predicted_fingerprint missing values for: {missing}")
    references_raw = [r for r in (result.get("references") or [])
                       if isinstance(r, str) and r]
    # Filter references to those actually in the corpus that was shown to
    # the LLM. Anything outside is treated as hallucination and dropped.
    corpus_ids: set[str] = set()
    for p in corpus_papers or []:
        aid = (p.get("arxiv_id") or "").strip()
        if aid:
            corpus_ids.add(aid)
            # Also accept the base form (without version suffix).
            corpus_ids.add(re.sub(r"v\d+$", "", aid))
        oa = (p.get("oa_paper_id") or "").strip()
        if oa:
            corpus_ids.add(oa)
            if not oa.startswith("oa:") and oa.startswith("W"):
                corpus_ids.add(f"oa:{oa}")
    references = [r for r in references_raw if r in corpus_ids]
    return {
        "target_model": target,
        "params": params,
        "rationale": rationale,
        "predicted_fingerprint": predicted_fp,
        "predicted_novelty_distance": result.get("predicted_novelty_distance"),
        "references": references,
        "llm_model": llm_model,
        # provenance: which gap produced this
        "_gap": {
            "view": gap.get("view"),
            "row": gap.get("row"),
            "col": gap.get("col"),
            "salience": gap.get("salience"),
        },
    }


def insert_gap_proposal(db_path: str, proposal: dict) -> int:
    """Persist a gap-derived proposal into the `proposals` table.

    Uses proposal_type='gap_mine' so downstream tools can distinguish
    these from regular `from-corpus` proposals.
    """
    from .db import ensure_proposals_schema, insert_proposal
    ensure_proposals_schema(db_path)
    # Encode the source gap into the params so the executor sees full
    # context; downstream filters can read params['_gap'] if needed.
    params = dict(proposal.get("params") or {})
    if proposal.get("_gap"):
        params.setdefault("_gap", proposal["_gap"])
    pid = insert_proposal(
        db_path,
        proposal_type="gap_mine",
        target_model=proposal["target_model"],
        params=params,
        rationale=proposal["rationale"],
        predicted_fingerprint=proposal.get("predicted_fingerprint"),
        predicted_novelty_distance=proposal.get("predicted_novelty_distance"),
        references=proposal.get("references") or [],
        llm_model=proposal["llm_model"],
    )
    return pid


def _tags_to_text(value: Any) -> str:
    """Normalise mechanism_tags (which load_literature returns as a list)
    OR oa_concepts (string) into a single lowercase haystack."""
    if isinstance(value, list):
        return " ".join(str(v) for v in value).lower()
    return str(value or "").lower()


def _scope_corpus_to_gap(rows: list[dict], row_label: str) -> list[dict]:
    """Pick the papers most relevant to the gap's row label so the LLM
    has focused context instead of all 400+ papers.
    Heuristic: include a paper if any token of the row label substring-
    matches its mechanism_tags or oa_concepts (case-insensitive)."""
    tokens = [t for t in (row_label or "").lower().split() if len(t) > 2]
    if not tokens:
        return list(rows)[:30]
    out: list[dict] = []
    for p in rows:
        haystack = (_tags_to_text(p.get("mechanism_tags")) + " "
                     + _tags_to_text(p.get("oa_concepts")))
        if any(tok in haystack for tok in tokens):
            out.append(p)
    return out


def propose_from_top_gaps(db_path: str, *,
                           rows: list[dict],
                           runs: list[dict],
                           top_n: int = 5,
                           llm_model: str = DEFAULT_LLM_MODEL,
                           dry_run: bool = False
                           ) -> list[dict]:
    """End-to-end: run gap-mine, take top-N, generate proposals, insert.

    Returns the list of created proposal dicts (with `id` set when not
    dry-running).
    """
    from .gap_finder import find_gaps
    from .abm_families import ABM_FAMILIES
    from .adapters import MODEL_BOUNDS
    from .fingerprint import FEATURE_NAMES

    _views, top = find_gaps(rows, runs, top_n=top_n)
    # Only surface families that actually have a registry impl (LHS bounds)
    # so the LLM can't pick targets the executor can't run.
    runnable_families = [f for f in ABM_FAMILIES if f["key"] in MODEL_BOUNDS]
    used: list[str] = []
    created: list[dict] = []
    for g in top:
        gap_dict = {
            "view": g.view, "row": g.row, "col": g.col,
            "value": g.value, "salience": g.salience,
            "row_total": g.row_total, "col_total": g.col_total,
            "why": g.why,
        }
        relevant = _scope_corpus_to_gap(rows, g.row)[:30]
        try:
            proposal = propose_from_gap(
                gap_dict, corpus_papers=relevant,
                families=runnable_families,
                model_bounds=MODEL_BOUNDS,
                feature_names=list(FEATURE_NAMES),
                already_used_families=list(used),
                llm_model=llm_model,
            )
        except Exception as exc:
            created.append({"_gap": gap_dict, "error": str(exc)})
            continue
        used.append(proposal["target_model"])
        if not dry_run:
            try:
                pid = insert_gap_proposal(db_path, proposal)
                proposal["id"] = pid
            except Exception as exc:
                proposal["insert_error"] = str(exc)
        created.append(proposal)
    return created
