"""genealogy — forward-citation tree from a canonical paper.

Start from a 'root' paper (typically a subfield's canon, found via
openalex.find_canon_papers). Walk forward citations 1-2 hops via
openalex.find_citing_papers. Lay out as an interactive HTML force graph:
nodes coloured by primary concept, sized by log(cited_by_count), x-axis
biased by publication year so the tree reads left→right in time.

No new dependencies — pure Python HTML/JS using the vis-network library
loaded from a CDN. Each render writes a self-contained .html the user
opens in any browser.

Why interactive? Citation networks have too many edges to read at PNG
resolution; users need zoom + hover-for-title.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any

from .openalex import find_citing_papers, sleep_for_rate_limit


def build_tree(root_oa_id: str, *, root_arxiv_id: str | None,
                root_title: str | None, root_year: int | None,
                root_cit: int | None,
                depth: int = 2, per_node: int = 20,
                min_cited_by: int = 0,
                sleep: float = 0.5) -> dict[str, Any]:
    """Walk forward citations from `root_oa_id` to depth `depth`. Each
    level keeps the top `per_node` most-cited descendants of each parent.

    Returns: {nodes: [...], edges: [...]} where each node has
    {id, label, year, cited_by_count, concept, depth} and each edge has
    {source, target}.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    nodes[root_oa_id] = {
        "id": root_oa_id,
        "label": (root_title or root_oa_id)[:80],
        "arxiv_id": root_arxiv_id,
        "year": root_year,
        "cited_by_count": root_cit or 0,
        "concept": "root",
        "depth": 0,
    }
    frontier = [root_oa_id]
    for d in range(1, depth + 1):
        next_frontier: list[str] = []
        for parent_id in frontier:
            children = find_citing_papers(parent_id, n=per_node,
                                            min_cited_by=min_cited_by)
            for child in children:
                cid = child.get("oa_paper_id")
                if not cid:
                    continue
                if cid not in nodes:
                    primary_concept = (child.get("concepts") or ["other"])[0]
                    nodes[cid] = {
                        "id": cid,
                        "label": (child.get("title") or cid)[:80],
                        "arxiv_id": child.get("arxiv_id"),
                        "year": child.get("year"),
                        "cited_by_count": child.get("cited_by_count") or 0,
                        "concept": primary_concept,
                        "depth": d,
                    }
                    next_frontier.append(cid)
                edges.append({"source": parent_id, "target": cid})
            if sleep:
                sleep_for_rate_limit(sleep)
        frontier = next_frontier
        if not frontier:
            break
    return {"nodes": list(nodes.values()), "edges": edges}


def filter_tree(tree: dict[str, Any], keywords: list[str],
                exclude_keywords: list[str] | None = None) -> dict[str, Any]:
    """Keep topical branches and merge duplicate OpenAlex title records."""
    terms = [term.strip().casefold() for term in keywords if term.strip()]
    excluded = [
        term.strip().casefold()
        for term in (exclude_keywords or [])
        if term.strip()
    ]
    if not terms:
        return tree

    parents: dict[str, set[str]] = {}
    for edge in tree["edges"]:
        parents.setdefault(edge["target"], set()).add(edge["source"])

    def matches(node: dict) -> bool:
        text = f"{node.get('label') or ''} {node.get('concept') or ''}".casefold()
        return (
            any(term in text for term in terms)
            and not any(term in text for term in excluded)
        )

    kept_ids = {
        node["id"] for node in tree["nodes"]
        if node.get("depth") == 0 or matches(node)
    }
    # Reject a matching descendant when every parent branch was rejected.
    for node in sorted(tree["nodes"], key=lambda item: item.get("depth", 0)):
        if node.get("depth") and node["id"] in kept_ids:
            if not any(parent in kept_ids for parent in parents.get(node["id"], ())):
                kept_ids.remove(node["id"])

    canonical: dict[str, str] = {}
    by_title: dict[str, dict] = {}
    for node in tree["nodes"]:
        if node["id"] not in kept_ids:
            continue
        title_key = re.sub(r"\W+", " ", node.get("label") or "").strip().casefold()
        existing = by_title.get(title_key)
        if existing is None:
            by_title[title_key] = node
            canonical[node["id"]] = node["id"]
        elif (node.get("cited_by_count") or 0) > (
                existing.get("cited_by_count") or 0):
            canonical[existing["id"]] = node["id"]
            canonical[node["id"]] = node["id"]
            by_title[title_key] = node
        else:
            canonical[node["id"]] = existing["id"]

    kept_nodes = list(by_title.values())
    kept_node_ids = {node["id"] for node in kept_nodes}
    edge_pairs = {
        (canonical.get(edge["source"], edge["source"]),
         canonical.get(edge["target"], edge["target"]))
        for edge in tree["edges"]
        if edge["source"] in kept_ids and edge["target"] in kept_ids
    }
    kept_edges = [
        {"source": source, "target": target}
        for source, target in sorted(edge_pairs)
        if source != target
        and source in kept_node_ids
        and target in kept_node_ids
    ]
    return {"nodes": kept_nodes, "edges": kept_edges}


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif; }}
  #info {{ position: fixed; top: 8px; left: 8px; background: rgba(255,255,255,0.92);
           padding: 8px 12px; border-radius: 6px; max-width: 420px;
           font-size: 12px; line-height: 1.5; box-shadow: 0 2px 6px rgba(0,0,0,0.12);
           pointer-events: none; }}
  #legend {{ position: fixed; bottom: 8px; left: 8px; background: rgba(255,255,255,0.92);
             padding: 8px 12px; border-radius: 6px; font-size: 11px;
             max-height: 40vh; overflow-y: auto; box-shadow: 0 2px 6px rgba(0,0,0,0.12); }}
  #net {{ width: 100vw; height: 100vh; }}
  .swatch {{ display: inline-block; width: 12px; height: 12px;
             border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
</style>
</head>
<body>
<div id="info"><b>{title}</b><br>{n_nodes} papers, {n_edges} citations.<br>
hover for details · scroll to zoom · drag to pan</div>
<div id="legend"><b>concept</b><br>{legend_rows}</div>
<div id="net"></div>
<script>
const data = {data_json};
const palette = {palette_json};
const nodes = new vis.DataSet(data.nodes.map(n => ({{
  id: n.id,
  label: n.year ? (n.year + ' · ' + (n.label.length > 40 ? n.label.slice(0,40)+'…' : n.label)) : n.label,
  title: (n.label + '\n' + (n.year||'?') + '  ·  ' + n.cited_by_count + ' cites\nconcept: ' + n.concept
          + (n.arxiv_id ? '\narxiv: ' + n.arxiv_id : '')),
  value: Math.log(1 + (n.cited_by_count||0)),
  color: palette[n.concept] || '#888',
  level: n.depth,
  font: {{ size: 11 }},
}})));
const edges = new vis.DataSet(data.edges.map(e => ({{
  from: e.source, to: e.target, arrows: 'to',
  width: 0.4, color: {{ color: 'rgba(120,120,120,0.35)', highlight: '#333' }},
}})));
const container = document.getElementById('net');
const network = new vis.Network(container, {{nodes, edges}}, {{
  layout: {{ hierarchical: {{ enabled: true, direction: 'LR',
                              sortMethod: 'directed', levelSeparation: 200,
                              nodeSpacing: 90 }} }},
  physics: {{ hierarchicalRepulsion: {{ nodeDistance: 100 }} }},
  interaction: {{ hover: true, navigationButtons: true, tooltipDelay: 100 }},
  nodes: {{ shape: 'dot', scaling: {{ min: 6, max: 30 }} }},
}});
</script>
</body>
</html>"""


def _build_palette(nodes: list[dict]) -> dict[str, str]:
    """Stable colour mapping by concept name."""
    # tab20-ish colours, picked for distinguishability on white background
    palette_pool = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
        "#c49c94", "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5",
    ]
    from collections import Counter
    by_freq = Counter(n.get("concept", "other") for n in nodes)
    mapping: dict[str, str] = {"root": "#000000"}
    for i, (concept, _) in enumerate(by_freq.most_common()):
        if concept == "root":
            continue
        mapping[concept] = palette_pool[i % len(palette_pool)]
    return mapping


def render_html(tree: dict[str, Any], out_path: str, *,
                 title: str = "Citation genealogy") -> None:
    """Write a self-contained HTML file rendering the tree as an
    interactive vis-network force graph."""
    palette = _build_palette(tree["nodes"])
    from collections import Counter
    counts = Counter(n.get("concept", "other") for n in tree["nodes"])
    legend_rows = []
    for concept, c in counts.most_common(20):
        sw = palette.get(concept, "#888")
        legend_rows.append(
            f'<div><span class="swatch" style="background:{sw}"></span>'
            f'{html.escape(concept)} ({c})</div>'
        )
    html_out = _HTML_TEMPLATE.format(
        title=html.escape(title),
        n_nodes=len(tree["nodes"]),
        n_edges=len(tree["edges"]),
        legend_rows="".join(legend_rows),
        data_json=json.dumps(tree),
        palette_json=json.dumps(palette),
    )
    with open(out_path, "w") as fh:
        fh.write(html_out)
