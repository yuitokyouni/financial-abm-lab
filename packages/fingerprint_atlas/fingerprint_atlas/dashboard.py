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


def _figure(out_dir: Path, source: str, title: str, note: str,
            *, wide: bool = False) -> str:
    href = _copy_asset(out_dir, source)
    cls = "figure wide" if wide else "figure"
    if not href:
        return f'<div class="{cls} empty">Missing asset: {html.escape(source)}</div>'
    return (
        f'<figure class="{cls}"><a href="{html.escape(href)}">'
        f'<img src="{html.escape(href)}" alt="{html.escape(title)}"></a>'
        f'<figcaption>{html.escape(title)}</figcaption>'
        f'<p class="note">{html.escape(note)}</p></figure>'
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

    overview = metric_html + (
        '<section class="band"><h2>Core analysis</h2><div class="grid">'
        + _figure(out, str(root / "notebooks/atlas_v4/atlas.png"),
                  "ABM fingerprint PCA",
                  "Model families in standardized fingerprint space.")
        + _figure(out, str(root / "notebooks/inverse_abm_heatmap.png"),
                  "Real market × ABM distance",
                  "Nearest model families across observed periods.")
        + '</div></section><section class="band"><h2>Workstreams</h2><div class="links">'
        '<a href="markets.html"><b>Market Structure</b><span>PCA, feature distributions, '
        'and inverse-ABM distances</span><i>Open →</i></a>'
        '<a href="research.html"><b>Research Coverage</b><span>Canon coverage, coverage '
        'matrix, and proposal evaluation diagnostics</span><i>Open →</i></a></div></section>'
    )

    markets = (
        '<section class="band"><h2>Fingerprint geometry</h2><div class="grid">'
        + _figure(out, str(root / "notebooks/atlas_v4/atlas.png"),
                  "PCA market atlas",
                  "Two principal components of standardized ABM fingerprints.",
                  wide=True)
        + _figure(out, str(root / "notebooks/atlas_v4/features.png"),
                  "Feature distributions",
                  "Per-family distributions for fingerprint dimensions.",
                  wide=True)
        + _figure(out, str(root / "notebooks/inverse_abm_heatmap.png"),
                  "Real market × ABM distance heatmap",
                  "Lower distance indicates a closer empirical fingerprint match.",
                  wide=True)
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
    cov_href = _ensure_coverage_png(out, rows)
    if cov_href:
        cov_block = (
            f'<figure class="figure wide"><a href="{html.escape(cov_href)}">'
            f'<img src="{html.escape(cov_href)}" alt="Coverage matrix"></a>'
            '<figcaption>Mechanism × stylized fact coverage</figcaption>'
            '<p class="note">Auto-rendered from the current corpus. '
            'Dense rows are well-covered mechanisms; sparse cells are '
            'research gaps to fill.</p></figure>'
        )
    else:
        cov_block = ('<div class="empty">Coverage matrix unavailable '
                      '— DB has no mechanism-tagged rows yet.</div>')

    research = (
        '<section class="band"><h2>Canon atlas</h2>' + canon_block + '</section>'
        '<section class="band"><h2>Coverage matrix</h2>' + cov_block + '</section>'
        '<section class="band"><h2>Subfield catalog</h2>'
        '<p class="sub">25 financial-ABM subfields tracked by canon-atlas. '
        'Run <code>canon-atlas</code> to fill each with its top-cited papers '
        'and ingestion status.</p>' + _subfield_catalog_html() + '</section>'
        '<section class="band"><h2>Proposal diagnostics</h2><div class="grid">'
        + _figure(out, str(root / "notebooks/propose_analytics/prediction_error_over_time.png"),
                  "Prediction error over time",
                  "Observed calibration drift across proposals.")
        + _figure(out, str(root / "notebooks/propose_analytics/prediction_error_by_family.png"),
                  "Prediction error by family",
                  "Error distribution grouped by target model.")
        + _figure(out, str(root / "notebooks/propose_analytics/novelty_calibration.png"),
                  "Novelty calibration",
                  "Predicted novelty against executed outcomes.", wide=True)
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
