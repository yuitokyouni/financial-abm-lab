"""Static multi-page research dashboard for financial-abm-lab."""
from __future__ import annotations

import html
import os
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
@media(max-width:850px){.shell{display:block}aside{position:static;height:auto;padding:14px}
.brand{margin:0 6px 12px}.nav{display:flex;overflow:auto}.nav a{white-space:nowrap}
main{padding:22px 16px}.head{display:block}.status{margin-top:8px}.metrics{grid-template-columns:1fr 1fr}
.metric:nth-child(2){border-right:0}.metric:nth-child(-n+2){border-bottom:1px solid var(--line)}
.grid{grid-template-columns:1fr}.wide{grid-column:auto}.links a{grid-template-columns:1fr}}
"""


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


def _asset(out_dir: Path, source: str) -> str | None:
    path = Path(source).resolve()
    if not path.exists():
        return None
    return os.path.relpath(path, out_dir.resolve())


def _figure(out_dir: Path, source: str, title: str, note: str,
            *, wide: bool = False) -> str:
    href = _asset(out_dir, source)
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


def build_dashboard(rows: list[dict[str, Any]], out_dir: str, *,
                    repo_root: str = ".",
                    canon_atlas: str = "canon_atlas.html") -> list[str]:
    """Generate overview, market-analysis and research-coverage pages."""
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
                  "ABM fingerprint PCA", "Model families in standardized fingerprint space.")
        + _figure(out, str(root / "notebooks/inverse_abm_heatmap.png"),
                  "Real market × ABM distance", "Nearest model families across observed periods.")
        + '</div></section><section class="band"><h2>Workstreams</h2><div class="links">'
        '<a href="markets.html"><b>Market Structure</b><span>PCA, feature distributions, '
        'and inverse-ABM distances</span><i>Open →</i></a>'
        '<a href="research.html"><b>Research Coverage</b><span>Canon coverage and proposal '
        'evaluation diagnostics</span><i>Open →</i></a></div></section>'
    )
    markets = (
        '<section class="band"><h2>Fingerprint geometry</h2><div class="grid">'
        + _figure(out, str(root / "notebooks/atlas_v4/atlas.png"),
                  "PCA market atlas", "Two principal components of standardized ABM fingerprints.",
                  wide=True)
        + _figure(out, str(root / "notebooks/atlas_v4/features.png"),
                  "Feature distributions", "Per-family distributions for fingerprint dimensions.",
                  wide=True)
        + _figure(out, str(root / "notebooks/inverse_abm_heatmap.png"),
                  "Real market × ABM distance heatmap",
                  "Lower distance indicates a closer empirical fingerprint match.", wide=True)
        + '</div></section>'
    )
    canon_href = _asset(out, str(root / canon_atlas))
    canon_link = (
        f'<a href="{html.escape(canon_href)}"><b>Canon Atlas</b>'
        '<span>25 financial-ABM subfields and ingestion coverage</span><i>Open →</i></a>'
        if canon_href else
        '<div class="empty">Canon atlas has not been generated.</div>'
    )
    research = (
        '<section class="band"><h2>Coverage</h2><div class="links">'
        + canon_link + '</div></section>'
        '<section class="band"><h2>Proposal diagnostics</h2><div class="grid">'
        + _figure(out, str(root / "notebooks/propose_analytics/prediction_error_over_time.png"),
                  "Prediction error over time", "Observed calibration drift across proposals.")
        + _figure(out, str(root / "notebooks/propose_analytics/prediction_error_by_family.png"),
                  "Prediction error by family", "Error distribution grouped by target model.")
        + _figure(out, str(root / "notebooks/propose_analytics/novelty_calibration.png"),
                  "Novelty calibration", "Predicted novelty against executed outcomes.", wide=True)
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
                               "Canon ingestion and proposal-quality diagnostics.",
                               "research", research),
    }
    for filename, content in pages.items():
        (out / filename).write_text(content, encoding="utf-8")
    return [str(out / filename) for filename in pages]
