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
  available_families: 使える ABM 家系のリストと機構説明
  related_papers: コーパス内の関連論文 (arxiv_id + title)

出力 JSON:
{
  "target_model": "<available_families の中の key、または'new'>",
  "params": {<想定パラメータ dict、未知なら空 {}>},
  "rationale": "<2-4 文の日本語。(a) なぜこの空白が面白いか、(b) 想定機構、
                 (c) 評価基準/期待される結果 を含める。MANDATORY>",
  "predicted_fingerprint": {<feature_name: 推定値>} or null,
  "references": [<arxiv_id か 'oa:Wxxx'、related_papers から最大3つ>]
}

注意:
- rationale は空にしない。empty rationale は invalid。
- target_model は available_families から選ぶ。'new' は本当に既存家系に
  fit しない時のみ。
- 'Prospect theory × regime-switching' のような認知バイアス × レジーム
  系では `speculation_game` が natural target になりやすい。
- 引用 (references) は LLM が知っている論文ではなく、related_papers に
  実在する arxiv_id だけを使う(hallucination 禁止)。
"""


def _summarise_families(families: list[dict]) -> list[dict]:
    return [{"key": f["key"], "name": f["name"],
              "mechanism": f.get("mechanism", "")[:200]}
             for f in families]


def _summarise_papers(papers: list[dict], n: int = 8) -> list[dict]:
    """Compact paper records for the LLM context (top-N by cite count)."""
    keyed = []
    for p in papers:
        cite = p.get("oa_cited_by_count") or 0
        keyed.append((cite, {
            "arxiv_id": p.get("arxiv_id"),
            "title": (p.get("title") or "")[:120],
            "year": p.get("year"),
            "cite": cite,
        }))
    keyed.sort(reverse=True)
    return [k[1] for k in keyed[:n]]


def build_proposal_payload(gap: dict, *,
                            corpus_papers: list[dict],
                            families: list[dict]) -> dict:
    """Assemble the user payload for the LLM, scoped to a single gap."""
    return {
        "gap_view": gap.get("view"),
        "subfield_or_family": gap.get("row"),
        "stylized_fact": gap.get("col"),
        "evidence": gap.get("why", ""),
        "row_total_papers": int(gap.get("row_total", 0)),
        "available_families": _summarise_families(families),
        "related_papers": _summarise_papers(corpus_papers, n=8),
    }


def propose_from_gap(gap: dict, *,
                      corpus_papers: list[dict],
                      families: list[dict],
                      llm_model: str = DEFAULT_LLM_MODEL,
                      temperature: float = 0.6,
                      dry_run_response: dict | None = None) -> dict:
    """Generate a proposal JSON for a single gap.

    Returns the validated proposal dict. Raises ValueError if the LLM
    output is malformed and unrecoverable.
    """
    payload = build_proposal_payload(gap, corpus_papers=corpus_papers,
                                       families=families)
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
    if target != "new" and target not in family_keys:
        raise ValueError(f"target_model {target!r} not in available "
                          f"families {sorted(family_keys)} or 'new'")
    references = [r for r in (result.get("references") or [])
                   if isinstance(r, str) and r]
    return {
        "target_model": target,
        "params": result.get("params") or {},
        "rationale": rationale,
        "predicted_fingerprint": result.get("predicted_fingerprint"),
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

    _views, top = find_gaps(rows, runs, top_n=top_n)
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
                families=list(ABM_FAMILIES), llm_model=llm_model,
            )
        except Exception as exc:
            created.append({"_gap": gap_dict, "error": str(exc)})
            continue
        if not dry_run:
            pid = insert_gap_proposal(db_path, proposal)
            proposal["id"] = pid
        created.append(proposal)
    return created
