from __future__ import annotations


def test_build_dashboard_writes_navigable_pages(tmp_path):
    from fingerprint_atlas.dashboard import build_dashboard

    root = tmp_path / "repo"
    (root / "notebooks/atlas_v4").mkdir(parents=True)
    (root / "notebooks/propose_analytics").mkdir(parents=True)
    for relative in [
        "notebooks/atlas_v4/atlas.png",
        "notebooks/atlas_v4/features.png",
        "notebooks/inverse_abm_heatmap.png",
        "notebooks/propose_analytics/prediction_error_over_time.png",
        "notebooks/propose_analytics/prediction_error_by_family.png",
        "notebooks/propose_analytics/novelty_calibration.png",
        "canon_atlas.html",
    ]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    rows = [
        {"year": 1997, "mechanism_tags": "minority-game, learning"},
        {"year": 2024, "mechanism_tags": "order-book"},
    ]
    out = root / "dashboard"
    pages = build_dashboard(rows, str(out), repo_root=str(root))

    assert len(pages) == 3
    index = (out / "index.html").read_text()
    markets = (out / "markets.html").read_text()
    research = (out / "research.html").read_text()
    assert "Research Overview" in index
    assert "2</b><span>papers in corpus" in index
    assert "Market Structure" in markets

    # Self-contained: every asset must be served from same-dir
    # `assets/...` path (no `../` parent traversal). file:// browsers
    # block parent-dir image loads.
    assert "assets/inverse_abm_heatmap.png" in markets
    assert "../notebooks/" not in markets, "no parent-traversal allowed"
    assert "assets/atlas.png" in markets
    assert "Canon Atlas" in research
    # Canon atlas copied into dashboard/ root and linked as same-dir href.
    assert 'href="canon_atlas.html"' in research
    assert "../canon_atlas.html" not in research

    # Subfield catalog renders all 25 entries (static, no canon search).
    assert "Minority Game" in research
    assert "Lux-Marchesi" in research
    assert "Heavy-tailed returns" in research
    assert "Limit order book" in research

    # Assets actually copied into the dashboard folder.
    assets = out / "assets"
    assert assets.exists()
    assert (assets / "atlas.png").exists()
    assert (assets / "inverse_abm_heatmap.png").exists()
    assert (assets / "prediction_error_over_time.png").exists()
    assert (out / "canon_atlas.html").exists()


def test_build_dashboard_handles_missing_assets(tmp_path):
    from fingerprint_atlas.dashboard import build_dashboard

    out = tmp_path / "dashboard"
    build_dashboard([], str(out), repo_root=str(tmp_path))

    assert "Missing asset" in (out / "markets.html").read_text()
    # No canon → embedded shell command hint, not a broken link.
    research = (out / "research.html").read_text()
    assert "Canon atlas not generated" in research
    assert "canon-atlas" in research  # the suggested command


def test_subfield_catalog_includes_all_categories():
    from fingerprint_atlas.dashboard import _subfield_catalog_html
    body = _subfield_catalog_html()
    # category labels appear; one card per subfield (25)
    for cat in ["foundational", "stylized", "microstructure", "behavioral",
                 "network", "crisis", "learning"]:
        assert cat in body
    assert body.count('class="sfcard"') >= 25


def test_coverage_matrix_renders_when_tagged_rows_present(tmp_path,
                                                            monkeypatch):
    """Coverage matrix PNG must be auto-rendered into assets/ when the
    DB has mechanism-tagged rows."""
    from fingerprint_atlas import dashboard

    # Stub out matplotlib-based render so the test stays headless +
    # doesn't need a real corpus shape.
    rendered = {"called": False}

    def fake_render(cov, path):
        from pathlib import Path
        Path(path).write_bytes(b"\x89PNG fake")
        rendered["called"] = True

    monkeypatch.setattr(dashboard, "_ensure_coverage_png",
                         lambda out_dir, rows: (
                             (out_dir / "assets").mkdir(parents=True, exist_ok=True),
                             (out_dir / "assets/coverage_matrix.png").write_bytes(b"px"),
                             "assets/coverage_matrix.png",
                         )[-1])

    out = tmp_path / "dashboard"
    rows = [{"year": 2024, "mechanism_tags": "minority-game",
             "stylized_facts_targeted": "fat-tails"}]
    dashboard.build_dashboard(rows, str(out), repo_root=str(tmp_path))

    research = (out / "research.html").read_text()
    assert "assets/coverage_matrix.png" in research
    assert (out / "assets/coverage_matrix.png").exists()
