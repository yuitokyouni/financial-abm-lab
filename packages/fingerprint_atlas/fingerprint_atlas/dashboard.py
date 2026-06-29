"""Static multi-page research dashboard for financial-abm-lab.

Self-contained build: every PNG referenced by a page is copied into
`<out_dir>/assets/<basename>` and embedded with a same-dir relative
path (no `../` traversal). This lets the dashboard render via plain
`open dashboard/index.html` without a local HTTP server — browsers
forbid `file://` parent-directory image loads as a security policy.

Linked HTML artifacts (canon_atlas.html) are copied to the dashboard
root for the same reason.
"""
from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any


_CSS = """
:root{--ink:#17202a;--muted:#65717c;--line:#d8dee4;--paper:#f7f8f9;
--panel:#fff;--green:#18794e;--red:#b42318;--blue:#175cd3;--amber:#b54708}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}
.shell{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:100vh}
aside{background:#111820;color:#fff;padding:22px 16px;position:sticky;top:0;height:100vh}
.brand{font-size:15px;font-weight:700;margin:0 8px 28px}.brand small{display:block;
color:#9ca8b4;font-size:10px;font-weight:500;margin-top:5px}.nav{display:grid;gap:5px}
.nav a{color:#b9c3cc;text-decoration:none;padding:9px 10px;border-radius:5px;
font-size:13px}.nav a:hover,.nav a.active{background:#26313d;color:#fff}
main{min-width:0;padding:30px 34px 48px}.head{display:flex;justify-content:space-between;
align-items:end;border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:22px}
h1{font-size:24px;margin:0 0 5px}h2{font-size:15px;margin:0 0 14px}p{margin:0}
.sub{font-size:12px;color:var(--muted)}.status{font-size:11px;color:var(--muted)}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);
background:var(--panel);margin-bottom:24px}.metric{padding:15px 17px;border-right:1px solid var(--line)}
.metric:last-child{border-right:0}.metric b{display:block;font-size:23px}.metric span{
font-size:11px;color:var(--muted)}.band{margin:0 0 28px}.grid{display:grid;
grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.figure{background:var(--panel);
border:1px solid var(--line);padding:14px}.figure img{display:block;width:100%;height:auto;
max-height:620px;object-fit:contain;background:#fff}.figure figcaption{font-size:12px;
font-weight:650;margin-top:10px}.figure .note{font-size:11px;color:var(--muted);margin-top:4px}
.wide{grid-column:1/-1}.links{display:grid;border-top:1px solid var(--line)}
.links a{display:grid;grid-template-columns:180px 1fr auto;gap:15px;padding:14px 4px;
border-bottom:1px solid var(--line);text-decoration:none;color:var(--ink);align-items:center}
.links a:hover{background:#fff}.links b{font-size:13px}.links span{font-size:11px;
color:var(--muted)}.links i{font-style:normal;color:var(--blue);font-size:12px}
.empty{padding:36px;border:1px dashed #aeb7c0;color:var(--muted);font-size:12px;
background:#fff}.tag{display:inline-block;font-size:10px;padding:3px 6px;border-radius:3px;
background:#e9f0fb;color:#174ea6;margin-left:6px}
.runcmd{display:block;font-family:ui-monospace,Menlo,Monaco,monospace;font-size:11px;
background:#0f1620;color:#dbe2e8;padding:8px 11px;border-radius:4px;margin-top:6px;
overflow-x:auto;white-space:pre}
.sfgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:8px}
.sfcard{background:var(--panel);border:1px solid var(--line);border-left:3px solid;
padding:9px 10px}.sfcard b{display:block;font-size:12px;margin-bottom:2px}
.sfcard .cat{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:0.04em}
.sfcard code{display:block;font-size:10px;background:#f5f5f5;padding:2px 4px;
border-radius:2px;margin-top:4px;color:var(--muted)}
.lookfor{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}
.lookfor summary{cursor:pointer;font-size:11px;color:var(--blue);
font-weight:600;list-style:none;user-select:none}
.lookfor summary::-webkit-details-marker{display:none}
.lookfor summary::before{content:'▸ ';color:var(--muted)}
.lookfor[open] summary::before{content:'▾ '}
.lookfor p{font-size:11px;color:var(--ink);margin-top:6px;line-height:1.55}
.lookfor ul{font-size:11px;color:var(--ink);margin:6px 0 0 0;padding-left:18px;line-height:1.5}
.lookfor li{margin-bottom:3px}
.tech-nav{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 18px;
padding:10px 12px;background:var(--panel);border:1px solid var(--line);
border-radius:4px;font-size:11px}
.tech-nav a{padding:3px 9px;border-radius:12px;text-decoration:none;
color:var(--ink);background:#eef0f3;font-weight:600;border-left:2px solid;
white-space:nowrap}
.tech-nav a:hover{background:#dde2e8}
.tech-nav a .count{margin-left:5px;color:var(--muted);font-weight:400;font-size:10px}
.tech-section{background:var(--panel);border:1px solid var(--line);
border-radius:4px;padding:14px 16px;margin-bottom:14px}
.tech-section h3{font-size:14px;margin:0 0 4px;padding:0;
display:flex;align-items:center;gap:8px}
.tech-section h3 .swatch{display:inline-block;width:10px;height:10px;border-radius:2px}
.tech-section h3 .count{font-size:11px;color:var(--muted);font-weight:400}
.tech-section .desc{font-size:11px;color:var(--muted);margin-bottom:10px;line-height:1.4}
.tech-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.tech-card{background:#fafbfc;border:1px solid var(--line);border-left:3px solid;
padding:8px 10px;font-size:11px;min-width:0}
.tech-card>summary{cursor:pointer;list-style:none;outline:none;user-select:none}
.tech-card>summary::-webkit-details-marker{display:none}
.tech-card>summary::before{content:'▸ ';color:var(--muted);font-size:9px}
.tech-card[open]>summary::before{content:'▾ '}
.tech-card[open]{background:#fff;box-shadow:0 1px 4px rgba(0,0,0,0.06)}
.tech-card b{font-size:11.5px;line-height:1.3;display:block}
.tech-card .purpose{display:block;color:var(--muted);font-size:10.5px;margin-top:3px;
line-height:1.4}
.tech-card .meta{display:flex;gap:6px;margin-top:5px;font-size:9.5px;
color:var(--muted);text-transform:uppercase;letter-spacing:0.04em}
.tech-card .meta span{padding:1px 5px;border-radius:2px;background:#eef0f3}
.tech-card .meta .has{background:#dff3e6;color:#155724}
.tech-card .field{margin-top:6px;font-size:10px}
.tech-card .field-label{font-weight:600;color:var(--muted);text-transform:uppercase;
letter-spacing:0.04em;display:block;margin-bottom:2px}
.tech-card .field ul{margin:0;padding-left:14px;font-size:10.5px;
line-height:1.45;color:var(--ink)}
.tech-card .field li{margin-bottom:2px}
.tech-card .field a{font-size:10.5px;word-break:break-all}
.tech-card code{background:#f5f5f5;padding:1px 4px;border-radius:2px;font-size:10px}
@media(max-width:1000px){.tech-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:650px){.tech-grid{grid-template-columns:1fr}}
@media(max-width:850px){.shell{display:block}aside{position:static;height:auto;padding:14px}
.brand{margin:0 6px 12px}.nav{display:flex;overflow:auto}.nav a{white-space:nowrap}
main{padding:22px 16px}.head{display:block}.status{margin-top:8px}.metrics{grid-template-columns:1fr 1fr}
.metric:nth-child(2){border-right:0}.metric:nth-child(-n+2){border-bottom:1px solid var(--line)}
.grid{grid-template-columns:1fr}.wide{grid-column:auto}.links a{grid-template-columns:1fr}
.sfgrid{grid-template-columns:1fr}}
"""

_CATEGORY_COLOR = {
    "foundational": "#1f77b4", "stylized": "#d62728",
    "microstructure": "#2ca02c", "behavioral": "#9467bd",
    "network": "#ff7f0e", "crisis": "#8c564b", "learning": "#17becf",
}


def _nav(active: str) -> str:
    items = [
        ("index.html", "Overview", "overview"),
        ("markets.html", "Market Structure", "markets"),
        ("research.html", "Research Coverage", "research"),
    ]
    return "".join(
        f'<a class="{"active" if key == active else ""}" href="{href}">{label}</a>'
        for href, label, key in items
    )


def _page(title: str, subtitle: str, active: str, body: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · Financial ABM Lab</title><style>{_CSS}</style></head>
<body><div class="shell"><aside><div class="brand">Financial ABM Lab
<small>RESEARCH CONTROL SURFACE</small></div><nav class="nav">{_nav(active)}</nav></aside>
<main><header class="head"><div><h1>{html.escape(title)}</h1>
<p class="sub">{html.escape(subtitle)}</p></div>
<div class="status">Static snapshot · local workspace</div></header>{body}</main>
</div></body></html>"""


def _copy_asset(out_dir: Path, source: str) -> str | None:
    """Copy `source` into `out_dir/assets/<basename>`; return the
    same-dir-relative href string. Returns None if source doesn't exist.

    Same-dir paths (no `../`) are required so browsers will load images
    via file:// — Chrome / Safari block parent-traversal under
    file:// for security.
    """
    src = Path(source).resolve()
    if not src.exists():
        return None
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    dst = assets / src.name
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, dst)
    return f"assets/{src.name}"


def _copy_html(out_dir: Path, source: str, dest_name: str) -> str | None:
    """Copy a generated HTML (e.g. canon_atlas.html) into the dashboard
    root so it's linkable as a same-dir href. Returns the dest name or None."""
    src = Path(source).resolve()
    if not src.exists():
        return None
    dst = out_dir / dest_name
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, dst)
    return dest_name


def _lookfor_block(lookfor: str | list[str] | None) -> str:
    """Render the collapsible 'What to look for' block.

    `lookfor` may be:
      - None: emits nothing (no toggle)
      - str: one paragraph of guidance
      - list[str]: bulleted points (one per item)
    """
    if not lookfor:
        return ""
    if isinstance(lookfor, str):
        body = f"<p>{html.escape(lookfor)}</p>"
    else:
        items = "".join(f"<li>{html.escape(item)}</li>" for item in lookfor)
        body = f"<ul>{items}</ul>"
    return (
        '<details class="lookfor"><summary>What to look for</summary>'
        f"{body}</details>"
    )


def _figure(out_dir: Path, source: str, title: str, note: str,
            *, wide: bool = False,
            lookfor: str | list[str] | None = None) -> str:
    href = _copy_asset(out_dir, source)
    cls = "figure wide" if wide else "figure"
    if not href:
        return f'<div class="{cls} empty">Missing asset: {html.escape(source)}</div>'
    return (
        f'<figure class="{cls}"><a href="{html.escape(href)}">'
        f'<img src="{html.escape(href)}" alt="{html.escape(title)}"></a>'
        f'<figcaption>{html.escape(title)}</figcaption>'
        f'<p class="note">{html.escape(note)}</p>'
        f'{_lookfor_block(lookfor)}'
        '</figure>'
    )


def _metrics(rows: list[dict[str, Any]]) -> dict[str, int]:
    years = [row.get("year") for row in rows if row.get("year")]
    tags: set[str] = set()
    for row in rows:
        raw_tags = row.get("mechanism_tags") or []
        values = raw_tags if isinstance(raw_tags, list) else raw_tags.split(",")
        tags.update(tag.strip() for tag in values if tag.strip())
    return {
        "papers": len(rows),
        "tagged": sum(bool(row.get("mechanism_tags")) for row in rows),
        "tags": len(tags),
        "span": (max(years) - min(years) + 1) if years else 0,
    }


def _find_canon_atlas(root: Path, explicit: str) -> str | None:
    """Search known locations for the canon-atlas HTML."""
    candidates = [
        Path(explicit) if Path(explicit).is_absolute() else root / explicit,
        root / "canon_atlas.html",
        root / "notebooks/canon_atlas/atlas.html",
        root / "notebooks/canon_atlas.html",
        root / "dashboard/canon_atlas.html",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _ensure_coverage_png(out_dir: Path, rows: list[dict[str, Any]]
                          ) -> str | None:
    """Render the (mechanism × stylized fact) coverage heatmap straight
    into the dashboard's assets directory. No-op if there are no rows.
    Returns the same-dir href, or None on failure."""
    if not rows:
        return None
    try:
        from .coverage import build_coverage, render_heatmap
    except ImportError:
        return None
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    target = assets / "coverage_matrix.png"
    try:
        cov = build_coverage(rows, top_rows=20)
        render_heatmap(cov, str(target))
    except Exception:
        return None
    return f"assets/{target.name}"


_TECHNIQUE_CATEGORY_COLOR = {
    "tail-stats": "#1f77b4",
    "sim-arch": "#2ca02c",
    "decision-rule": "#d62728",
    "validation": "#9467bd",
    "calibration": "#ff7f0e",
    "learning-agent": "#17becf",
}

_TECHNIQUE_CATEGORY_DESC = {
    "tail-stats": "Estimating tail exponents and bootstrap CIs over heavy-tailed returns.",
    "sim-arch": "How the market loop is wired — matching engine, scheduling, message bus.",
    "decision-rule": "The agent's choose-action core: chartist, MG, SG, Brock-Hommes, etc.",
    "validation": "Does the simulator reproduce real markets? Stylized-fact battery + tests.",
    "calibration": "Fit ABM parameters to observed data (grid / NN / ABC / PSO).",
    "learning-agent": "RL + mechanistic interpretability of data-driven agents.",
}


def _technique_card(tech: dict) -> str:
    """One expandable card per technique. Shows name + purpose + a
    counts-meta strip at rest; expands to gotchas / refs / your_impl."""
    color = _TECHNIQUE_CATEGORY_COLOR.get(tech.get("category", ""), "#888")
    name = html.escape(tech["name"])
    purpose = html.escape(tech.get("purpose", ""))

    n_gotchas = len(tech.get("gotchas") or [])
    n_papers = len(tech.get("ref_papers") or [])
    n_repos = len(tech.get("ref_repos") or [])
    has_impl = bool(tech.get("your_impl"))
    meta_chips = []
    if n_gotchas:
        meta_chips.append(f'<span>{n_gotchas} gotchas</span>')
    if n_papers:
        meta_chips.append(f'<span>{n_papers} papers</span>')
    if n_repos:
        meta_chips.append(f'<span>{n_repos} repos</span>')
    if has_impl:
        meta_chips.append('<span class="has">your impl</span>')
    meta_strip = (f'<div class="meta">{"".join(meta_chips)}</div>'
                   if meta_chips else "")

    parts: list[str] = []
    gotchas = tech.get("gotchas") or []
    if gotchas:
        items = "".join(f"<li>{html.escape(g)}</li>" for g in gotchas)
        parts.append(
            f'<div class="field"><span class="field-label">gotchas</span>'
            f'<ul>{items}</ul></div>'
        )
    ref_papers = tech.get("ref_papers") or []
    if ref_papers:
        items = "".join(f'<li><code>{html.escape(p)}</code></li>'
                         for p in ref_papers)
        parts.append(
            f'<div class="field"><span class="field-label">ref papers</span>'
            f'<ul>{items}</ul></div>'
        )
    ref_repos = tech.get("ref_repos") or []
    if ref_repos:
        items = []
        for r in ref_repos:
            href = html.escape(r)
            label = html.escape(r.replace("https://github.com/", "")
                                  .replace("https://", ""))
            items.append(f'<li><a href="{href}" target="_blank">{label}</a></li>')
        parts.append(
            '<div class="field"><span class="field-label">ref repos</span>'
            f'<ul>{"".join(items)}</ul></div>'
        )
    your_impl = tech.get("your_impl")
    if your_impl:
        parts.append(
            '<div class="field"><span class="field-label">your impl</span>'
            f'<code>{html.escape(your_impl)}</code></div>'
        )

    return (
        f'<details class="tech-card" style="border-left-color:{color}">'
        f'<summary><b>{name}</b>'
        f'<span class="purpose">{purpose}</span>'
        f'{meta_strip}</summary>'
        f'{"".join(parts)}</details>'
    )


def _technique_catalog_html() -> str:
    """Catalog of implementation techniques, grouped by category.

    Layout: a small jump-nav strip with category counts, then one
    boxed section per category containing a 3-col grid of cards.
    Each card collapses to name + purpose + counts; click expands.
    """
    try:
        from .techniques import TECHNIQUES
    except ImportError:
        return ""
    by_cat: dict[str, list[dict]] = {}
    for t in TECHNIQUES:
        by_cat.setdefault(t.get("category", "other"), []).append(t)

    cat_order = ["tail-stats", "sim-arch", "decision-rule",
                  "validation", "calibration", "learning-agent"]
    cat_order = [c for c in cat_order if c in by_cat]
    cat_order += [c for c in by_cat if c not in cat_order]

    # Top jump-nav strip: one chip per category, links to anchors.
    nav_chips: list[str] = []
    for cat in cat_order:
        color = _TECHNIQUE_CATEGORY_COLOR.get(cat, "#888")
        nav_chips.append(
            f'<a href="#tech-{html.escape(cat)}" style="border-left-color:{color}">'
            f'{html.escape(cat)}'
            f'<span class="count">{len(by_cat[cat])}</span></a>'
        )
    nav_strip = f'<div class="tech-nav">{"".join(nav_chips)}</div>'

    sections: list[str] = []
    for cat in cat_order:
        color = _TECHNIQUE_CATEGORY_COLOR.get(cat, "#888")
        desc = _TECHNIQUE_CATEGORY_DESC.get(cat, "")
        cards = "".join(_technique_card(t) for t in by_cat[cat])
        sections.append(
            f'<div class="tech-section" id="tech-{html.escape(cat)}">'
            f'<h3><span class="swatch" style="background:{color}"></span>'
            f'{html.escape(cat)}'
            f'<span class="count">· {len(by_cat[cat])} techniques</span></h3>'
            f'<p class="desc">{html.escape(desc)}</p>'
            f'<div class="tech-grid">{cards}</div></div>'
        )

    return nav_strip + "".join(sections)


def _subfield_catalog_html() -> str:
    """Static catalog grid of the 25 subfields. Renders even when no
    canon search has been run — so Research Coverage is never empty."""
    try:
        from .subfields import SUBFIELDS
    except ImportError:
        return ""
    cards = []
    for sf in SUBFIELDS:
        color = _CATEGORY_COLOR.get(sf.get("category", ""), "#888")
        cards.append(
            f'<div class="sfcard" style="border-left-color:{color}">'
            f'<b>{html.escape(sf["name"])}</b>'
            f'<span class="cat">{html.escape(sf.get("category", ""))}</span>'
            f'<code>{html.escape(sf["query"])}</code>'
            f'</div>'
        )
    return '<div class="sfgrid">' + "".join(cards) + '</div>'


def _canon_run_hint() -> str:
    """Inline command snippet so users can copy-paste to (re)generate canon."""
    return (
        '<div class="empty">Canon atlas not generated yet.'
        '<span class="runcmd">uv run python -m fingerprint_atlas.arxiv_cli \\\n'
        '  --db ../test/knowhow/abm_knowhow.db canon-atlas \\\n'
        '  --out canon_atlas.html --auto-ingest-missing</span></div>'
    )


def build_dashboard(rows: list[dict[str, Any]], out_dir: str, *,
                    repo_root: str = ".",
                    canon_atlas: str = "canon_atlas.html") -> list[str]:
    """Generate overview, market-analysis and research-coverage pages.

    Self-contained build: every asset is copied under `<out_dir>/assets/`
    and linked with same-dir paths so file:// access works.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(repo_root).resolve()
    stats = _metrics(rows)
    metric_html = (
        '<section class="metrics">'
        f'<div class="metric"><b>{stats["papers"]}</b><span>papers in corpus</span></div>'
        f'<div class="metric"><b>{stats["tagged"]}</b><span>mechanism-tagged</span></div>'
        f'<div class="metric"><b>{stats["tags"]}</b><span>distinct mechanisms</span></div>'
        f'<div class="metric"><b>{stats["span"]}</b><span>years represented</span></div>'
        '</section>'
    )

    pca_lookfor = [
        "Tight per-family clusters: the model produces a consistent fingerprint "
        "across its parameter sweep (a good calibration target).",
        "Cross-family overlap: different mechanisms producing indistinguishable "
        "surface statistics — a warning that the 6-feature space cannot tell "
        "them apart, so inverse-ABM matching on those features is ambiguous.",
        "Outlier runs sitting far from their family's cluster: parameter "
        "regimes that flip the model into another regime — usually the "
        "interesting boundary cases to investigate.",
        "Direction of separation along PC1 / PC2: which stylized facts "
        "dominate the principal axes (read the loadings to interpret).",
    ]
    distance_lookfor = [
        "Which family wins each regime — crisis windows often match different "
        "families than calm windows, suggesting mechanism switching in the "
        "real market.",
        "Gap between top-1 and top-2 distance: a small gap means low confidence "
        "in the match. Treat the assignment as 'plausible' rather than 'best'.",
        "Rows where every column is roughly equidistant: the 6-feature space "
        "cannot discriminate that period's dynamics — extend features or "
        "add ABM families.",
        "Columns that never win: model families that look nothing like real "
        "markets in any regime — either narrow target use, or miscalibrated.",
    ]

    overview = metric_html + (
        '<section class="band"><h2>Core analysis</h2><div class="grid">'
        + _figure(out, str(root / "notebooks/atlas_v4/atlas.png"),
                  "ABM fingerprint PCA",
                  "Model families in standardized fingerprint space.",
                  lookfor=pca_lookfor)
        + _figure(out, str(root / "notebooks/inverse_abm_heatmap.png"),
                  "Real market × ABM distance",
                  "Nearest model families across observed periods.",
                  lookfor=distance_lookfor)
        + '</div></section><section class="band"><h2>Workstreams</h2><div class="links">'
        '<a href="markets.html"><b>Market Structure</b><span>PCA, feature distributions, '
        'and inverse-ABM distances</span><i>Open →</i></a>'
        '<a href="research.html"><b>Research Coverage</b><span>Canon coverage, coverage '
        'matrix, and proposal evaluation diagnostics</span><i>Open →</i></a></div></section>'
    )

    features_lookfor = [
        "Families with near-zero variance on a feature: the model produces "
        "an essentially constant value regardless of parameters (insensitive "
        "dimension — fingerprint cannot probe that mechanism).",
        "Families whose boxes overlap every other family on a feature: that "
        "feature does not separate them — redundant or weak discriminator.",
        "Long whiskers / outliers: parameter regimes that pull a model into "
        "atypical fingerprint territory — useful for stress-testing the "
        "calibration neighbourhood.",
        "Cross-family ordering inconsistency between features: a family is "
        "highest on one stylized fact but lowest on another — interpret the "
        "trade-off as the mechanism's signature.",
    ]
    markets = (
        '<section class="band"><h2>Fingerprint geometry</h2><div class="grid">'
        + _figure(out, str(root / "notebooks/atlas_v4/atlas.png"),
                  "PCA market atlas",
                  "Two principal components of standardized ABM fingerprints.",
                  wide=True, lookfor=pca_lookfor)
        + _figure(out, str(root / "notebooks/atlas_v4/features.png"),
                  "Feature distributions",
                  "Per-family distributions for fingerprint dimensions.",
                  wide=True, lookfor=features_lookfor)
        + _figure(out, str(root / "notebooks/inverse_abm_heatmap.png"),
                  "Real market × ABM distance heatmap",
                  "Lower distance indicates a closer empirical fingerprint match.",
                  wide=True, lookfor=distance_lookfor)
        + '</div></section>'
    )

    # Canon Atlas link — search multiple known locations, copy to
    # dashboard/ root so the link is same-dir (file:// safe).
    canon_src = _find_canon_atlas(root, canon_atlas)
    if canon_src:
        canon_dest = _copy_html(out, canon_src, "canon_atlas.html")
        canon_block = (
            f'<div class="links"><a href="{html.escape(canon_dest)}">'
            '<b>Canon Atlas</b><span>25 financial-ABM subfields × top-cited '
            'canon, ingestion coverage heatmap</span><i>Open →</i></a></div>'
        )
    else:
        canon_block = _canon_run_hint()

    # Coverage matrix — auto-render from current literature_methods rows.
    coverage_lookfor = [
        "Dense rows (high count across many columns): well-studied mechanisms "
        "the corpus is biased toward. Don't propose new work here without a "
        "differentiator.",
        "Empty columns: stylized facts no paper in the corpus targets — either "
        "blind spots of the field, or under-covered by ingestion. Cross-check "
        "with canon-atlas to disambiguate.",
        "Sparse cells inside otherwise-dense rows: 'this mechanism is well-"
        "studied, but no one has tried it against this stylized fact' — the "
        "most actionable gap to propose into.",
        "Rows whose only tag is a generic OpenAlex concept (e.g. 'Economics'): "
        "LLM mechanism extraction was too shallow for those papers; rerun "
        "extraction with deeper prompts.",
    ]
    cov_href = _ensure_coverage_png(out, rows)
    if cov_href:
        cov_block = (
            f'<figure class="figure wide"><a href="{html.escape(cov_href)}">'
            f'<img src="{html.escape(cov_href)}" alt="Coverage matrix"></a>'
            '<figcaption>Mechanism × stylized fact coverage</figcaption>'
            '<p class="note">Auto-rendered from the current corpus. '
            'Dense rows are well-covered mechanisms; sparse cells are '
            'research gaps to fill.</p>'
            f'{_lookfor_block(coverage_lookfor)}</figure>'
        )
    else:
        cov_block = ('<div class="empty">Coverage matrix unavailable '
                      '— DB has no mechanism-tagged rows yet.</div>')

    pred_time_lookfor = [
        "Downward trend in absolute error: the proposal-quality model is "
        "learning from executed-outcome feedback (good signal).",
        "Shrinking error variance: predictions are becoming more reliable "
        "even if mean error is flat.",
        "Sudden jumps in error: structural breaks — usually the judge model "
        "changed, the corpus shifted, or the scoring metric was redefined. "
        "Annotate the timeline against commit history to confirm.",
        "Clusters of high-error proposals at a single date: a batched run "
        "that targeted an unfamiliar mechanism family.",
    ]
    pred_family_lookfor = [
        "Families with consistently high error: the proposal system's blind "
        "spot — usually under-represented in the corpus or extracted with "
        "shallow mechanism tags.",
        "Families with near-zero error: possibly genuinely easy to predict, "
        "or the model is over-fitted to that family's training proposals.",
        "Wide error boxes (high variance): proposals against this family are "
        "unreliable; needs more ingestion or human review of judge prompts.",
        "Families with no proposals at all (missing box): proposal pipeline "
        "never reaches that family — check the from-corpus sampling weights.",
    ]
    novelty_lookfor = [
        "Points clustering on the diagonal y = x: well-calibrated judge — "
        "predicted novelty matches measured novelty.",
        "Systematic offset above the diagonal: judge over-predicts novelty "
        "(hype bias). Below: judge under-predicts (conservative).",
        "High-leverage outliers: proposals the judge missed (high actual, "
        "low predicted) — extract their patterns into the judge prompt.",
        "Strong vertical bands: predicted scores collapse to a few discrete "
        "values — judge model is under-resolving the novelty dimension.",
    ]

    research = (
        '<section class="band"><h2>Canon atlas</h2>' + canon_block + '</section>'
        '<section class="band"><h2>Coverage matrix</h2>' + cov_block + '</section>'
        '<section class="band"><h2>Subfield catalog</h2>'
        '<p class="sub">25 financial-ABM subfields tracked by canon-atlas. '
        'Run <code>canon-atlas</code> to fill each with its top-cited papers '
        'and ingestion status.</p>' + _subfield_catalog_html() + '</section>'
        '<section class="band"><h2>Technique catalog</h2>'
        '<p class="sub">Implementation techniques (algorithm / sim-arch / '
        'decision-rule / validation / calibration / learning-agent). '
        'Click any card for gotchas, reference papers, and OSS repos.</p>'
        + _technique_catalog_html() + '</section>'
        '<section class="band"><h2>Proposal diagnostics</h2><div class="grid">'
        + _figure(out, str(root / "notebooks/propose_analytics/prediction_error_over_time.png"),
                  "Prediction error over time",
                  "Observed calibration drift across proposals.",
                  lookfor=pred_time_lookfor)
        + _figure(out, str(root / "notebooks/propose_analytics/prediction_error_by_family.png"),
                  "Prediction error by family",
                  "Error distribution grouped by target model.",
                  lookfor=pred_family_lookfor)
        + _figure(out, str(root / "notebooks/propose_analytics/novelty_calibration.png"),
                  "Novelty calibration",
                  "Predicted novelty against executed outcomes.", wide=True,
                  lookfor=novelty_lookfor)
        + '</div></section>'
    )

    pages = {
        "index.html": _page("Research Overview",
                            "Corpus health and high-signal analytical outputs.",
                            "overview", overview),
        "markets.html": _page("Market Structure",
                              "Fingerprint geometry and empirical model matching.",
                              "markets", markets),
        "research.html": _page("Research Coverage",
                               "Canon ingestion, subfield catalog, and proposal "
                               "diagnostics.",
                               "research", research),
    }
    for filename, content in pages.items():
        (out / filename).write_text(content, encoding="utf-8")
    return [str(out / filename) for filename in pages]
