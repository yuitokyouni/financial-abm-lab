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
    assert "../notebooks/inverse_abm_heatmap.png" in markets
    assert "Canon Atlas" in research
    assert "../canon_atlas.html" in research


def test_build_dashboard_handles_missing_assets(tmp_path):
    from fingerprint_atlas.dashboard import build_dashboard

    out = tmp_path / "dashboard"
    build_dashboard([], str(out), repo_root=str(tmp_path))

    assert "Missing asset" in (out / "markets.html").read_text()
    assert "Canon atlas has not been generated" in (
        out / "research.html"
    ).read_text()
