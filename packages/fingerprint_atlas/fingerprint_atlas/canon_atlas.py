"""canon_atlas — sweep all subfields, run canon detection, render heatmap.

For each entry in subfields.SUBFIELDS:
  1. find_canon_papers(query, n=N)   ← OpenAlex top-cited under that phrase
  2. flag which arxiv ids are already in the local literature DB
  3. compute coverage % = in-DB-count / canon-count

Output: a single self-contained HTML with
  - a heatmap-style grid of all subfields (coverage % colored)
  - per-subfield sections listing top-N canon papers (year, cites, in-DB
    badge, arxiv link, OpenAlex link)

The goal is to surface where the lab is well-equipped (canon ingested)
vs where it's flying blind (canon papers we haven't seen). The next
research direction is to plug those gaps.
"""
from __future__ import annotations

import html
import os
import re
from typing import Any

from .openalex import find_canon_papers, sleep_for_rate_limit
from .subfields import SUBFIELDS, Subfield


_CATEGORY_COLOR = {
    "foundational": "#1f77b4",
    "stylized": "#d62728",
    "microstructure": "#2ca02c",
    "behavioral": "#9467bd",
    "network": "#ff7f0e",
    "crisis": "#8c564b",
    "learning": "#17becf",
}


def _arxiv_base(arxiv_id: str | None) -> str | None:
    if not arxiv_id:
        return None
    return re.sub(r"v\d+$", "", arxiv_id.strip())


def build_atlas(subfields: list[Subfield], *, db_arxiv_ids: set[str],
                 n_per_subfield: int = 8, year_max: int | None = None,
                 sleep: float = 0.5) -> list[dict[str, Any]]:
    """Return one record per subfield with its canon papers + DB coverage.

    db_arxiv_ids is the set of base arxiv ids already in literature_methods
    (stripped of version suffixes). Each canon paper is annotated with
    in_db=True iff its arxiv_id (base form) is in that set.
    """
    db_set = {_arxiv_base(a) for a in db_arxiv_ids if a}
    atlas: list[dict[str, Any]] = []
    for sf in subfields:
        papers = find_canon_papers(sf["query"], n=n_per_subfield,
                                    year_max=year_max)
        annotated: list[dict[str, Any]] = []
        n_in_db = 0
        for p in papers:
            base = _arxiv_base(p.get("arxiv_id"))
            in_db = bool(base) and base in db_set
            if in_db:
                n_in_db += 1
            annotated.append({
                "oa_paper_id": p.get("oa_paper_id"),
                "arxiv_id": p.get("arxiv_id"),
                "title": p.get("title"),
                "year": p.get("year"),
                "cited_by_count": p.get("cited_by_count") or 0,
                "doi": p.get("doi"),
                "in_db": in_db,
            })
        n_canon = len(annotated)
        # Coverage definition: of canon papers that exist on arxiv, how
        # many do we already have. Canon papers with no arxiv presence
        # (journal-only books like Bouchaud-Potters) are excluded from
        # the denominator — we can't ingest them so they shouldn't lower
        # the score.
        n_on_arxiv = sum(1 for p in annotated if p["arxiv_id"])
        coverage = (n_in_db / n_on_arxiv) if n_on_arxiv else None
        atlas.append({
            "key": sf["key"],
            "name": sf["name"],
            "category": sf.get("category", "other"),
            "query": sf["query"],
            "seed_arxiv": sf.get("seed_arxiv"),
            "papers": annotated,
            "n_canon": n_canon,
            "n_in_db": n_in_db,
            "n_on_arxiv": n_on_arxiv,
            "coverage": coverage,
        })
        if sleep:
            sleep_for_rate_limit(sleep)
    return atlas


def _coverage_color(coverage: float | None) -> str:
    """White (0%) → green (100%), with grey for None (no arxiv canon)."""
    if coverage is None:
        return "#e8e8e8"
    # Linear blend white → #2ca02c
    r0, g0, b0 = 255, 255, 255
    r1, g1, b1 = 44, 160, 44
    t = max(0.0, min(1.0, coverage))
    r = int(r0 + (r1 - r0) * t)
    g = int(g0 + (g1 - g0) * t)
    b = int(b0 + (b1 - b0) * t)
    return f"rgb({r},{g},{b})"


def _arxiv_link(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{arxiv_id}"


_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ margin: 0 auto; max-width: 1280px; padding: 24px;
          font-family: -apple-system, BlinkMacSystemFont, Helvetica, Arial,
                       'Hiragino Sans', sans-serif; color: #1a1a1a;
          background: #fafafa; }}
  h1 {{ font-size: 22px; margin: 0 0 8px; }}
  .subtitle {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(5, 1fr);
           gap: 8px; margin-bottom: 32px; }}
  .cell {{ position: relative; padding: 10px; border-radius: 6px;
           border: 1px solid #ddd; font-size: 11px;
           cursor: pointer; transition: transform 0.15s; }}
  .cell:hover {{ transform: scale(1.03); box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
  .cat-stripe {{ position: absolute; top: 0; left: 0; bottom: 0;
                  width: 4px; border-radius: 6px 0 0 6px; }}
  .name {{ font-weight: 600; margin-bottom: 4px; margin-left: 8px;
            min-height: 28px; line-height: 1.2; }}
  .pct {{ font-size: 18px; font-weight: 700; margin-left: 8px; }}
  .frac {{ font-size: 10px; color: #555; margin-left: 8px; }}
  details {{ margin: 16px 0; background: #fff; border: 1px solid #ddd;
              border-radius: 6px; }}
  summary {{ padding: 12px 16px; cursor: pointer; font-weight: 600;
              list-style: none; }}
  summary::-webkit-details-marker {{ display: none; }}
  summary::before {{ content: '▸ '; color: #999; }}
  details[open] summary::before {{ content: '▾ '; }}
  .meta {{ font-weight: 400; color: #666; font-size: 12px; margin-left: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th, td {{ padding: 6px 12px; text-align: left;
            border-top: 1px solid #eee; vertical-align: top; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  .badge {{ display: inline-block; padding: 1px 6px; border-radius: 3px;
            font-size: 10px; font-weight: 600; }}
  .badge-in {{ background: #d4edda; color: #155724; }}
  .badge-out {{ background: #f8d7da; color: #721c24; }}
  .badge-no-arxiv {{ background: #e8e8e8; color: #555; }}
  a {{ color: #1f77b4; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .legend {{ font-size: 11px; color: #555; margin-top: 8px; }}
  .legend-swatch {{ display: inline-block; width: 12px; height: 12px;
                     border-radius: 2px; margin: 0 4px 0 12px;
                     vertical-align: middle; }}
</style>
</head><body>
<h1>{title}</h1>
<div class="subtitle">{subtitle}</div>

<div class="grid">{cells}</div>

<div class="legend"><b>category</b>{cat_legend}</div>
<div class="legend"><b>coverage</b>
  <span class="legend-swatch" style="background:#fff;border:1px solid #ccc"></span>0%
  <span class="legend-swatch" style="background:#85cb85"></span>50%
  <span class="legend-swatch" style="background:#2ca02c"></span>100%
  <span class="legend-swatch" style="background:#e8e8e8"></span>no arxiv canon
</div>

<h2 style="margin-top:32px;font-size:18px">subfield detail</h2>
{sections}

</body></html>
"""


def _render_cell(entry: dict[str, Any]) -> str:
    cov = entry["coverage"]
    bg = _coverage_color(cov)
    pct_txt = "—" if cov is None else f"{int(round(cov * 100))}%"
    frac_txt = (f"{entry['n_in_db']} / {entry['n_on_arxiv']} on arxiv "
                f"(of {entry['n_canon']})")
    cat_color = _CATEGORY_COLOR.get(entry["category"], "#888")
    name = html.escape(entry["name"])
    key = entry["key"]
    return (f'<a href="#sub-{key}" style="text-decoration:none;color:inherit">'
            f'<div class="cell" style="background:{bg}">'
            f'<div class="cat-stripe" style="background:{cat_color}"></div>'
            f'<div class="name">{name}</div>'
            f'<div class="pct">{pct_txt}</div>'
            f'<div class="frac">{frac_txt}</div>'
            f'</div></a>')


def _render_section(entry: dict[str, Any]) -> str:
    cat_color = _CATEGORY_COLOR.get(entry["category"], "#888")
    rows = []
    for p in entry["papers"]:
        if p["in_db"]:
            badge = '<span class="badge badge-in">in DB</span>'
        elif p["arxiv_id"]:
            badge = '<span class="badge badge-out">missing</span>'
        else:
            badge = '<span class="badge badge-no-arxiv">no arxiv</span>'
        title_link = html.escape(p["title"] or "")
        if p["arxiv_id"]:
            title_link = (f'<a href="{_arxiv_link(p["arxiv_id"])}" '
                          f'target="_blank">{title_link}</a>')
        elif p["doi"]:
            title_link = (f'<a href="{html.escape(p["doi"])}" '
                          f'target="_blank">{title_link}</a>')
        year_txt = str(p["year"]) if p["year"] else "—"
        rows.append(
            f"<tr><td>{badge}</td>"
            f"<td>{year_txt}</td>"
            f"<td>{p['cited_by_count']:,}</td>"
            f"<td>{title_link}</td>"
            f"<td>{html.escape(p['arxiv_id'] or '')}</td></tr>"
        )
    cov = entry["coverage"]
    cov_txt = "—" if cov is None else f"{int(round(cov * 100))}%"
    meta = (f'coverage <b>{cov_txt}</b> · '
            f'{entry["n_in_db"]} / {entry["n_on_arxiv"]} on-arxiv in DB · '
            f'{entry["n_canon"]} canon total · '
            f'query: <code>{html.escape(entry["query"])}</code>')
    return (f'<details id="sub-{entry["key"]}">'
            f'<summary><span style="display:inline-block;width:8px;height:8px;'
            f'border-radius:50%;background:{cat_color};margin-right:8px;'
            f'vertical-align:middle"></span>'
            f'{html.escape(entry["name"])}'
            f'<span class="meta">{meta}</span></summary>'
            f'<table><thead><tr><th>status</th><th>year</th><th>cites</th>'
            f'<th>title</th><th>arxiv</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></details>')


def _render_cat_legend() -> str:
    parts = []
    for cat, color in _CATEGORY_COLOR.items():
        parts.append(f'<span class="legend-swatch" style="background:{color}">'
                      f'</span>{cat}')
    return "".join(parts)


def render_html(atlas: list[dict[str, Any]], out_path: str, *,
                 title: str = "Financial-ABM canon atlas") -> None:
    """Write a self-contained HTML page rendering the atlas."""
    total_canon = sum(e["n_canon"] for e in atlas)
    total_in_db = sum(e["n_in_db"] for e in atlas)
    total_on_arxiv = sum(e["n_on_arxiv"] for e in atlas)
    overall = (total_in_db / total_on_arxiv) if total_on_arxiv else 0.0
    subtitle = (f"{len(atlas)} subfields · {total_canon} canon papers · "
                f"{total_in_db} / {total_on_arxiv} on-arxiv in DB · "
                f"overall coverage <b>{int(round(overall * 100))}%</b>")
    cells = "".join(_render_cell(e) for e in atlas)
    sections = "".join(_render_section(e) for e in atlas)
    body = _HTML_TEMPLATE.format(
        title=html.escape(title),
        subtitle=subtitle,
        cells=cells,
        sections=sections,
        cat_legend=_render_cat_legend(),
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".",
                exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write(body)


def missing_arxiv_ids(atlas: list[dict[str, Any]]) -> list[str]:
    """Return arxiv_ids of canon papers that are on arxiv but NOT in our DB.

    Use with arxiv_ingest.ingest_arxiv_ids to plug gaps in one shot."""
    out: list[str] = []
    seen: set[str] = set()
    for entry in atlas:
        for p in entry["papers"]:
            aid = _arxiv_base(p.get("arxiv_id"))
            if aid and not p["in_db"] and aid not in seen:
                out.append(aid)
                seen.add(aid)
    return out
