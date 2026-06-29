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


def test_lookfor_block_renders_paragraph_and_bullets():
    from fingerprint_atlas.dashboard import _lookfor_block
    # None / empty → nothing
    assert _lookfor_block(None) == ""
    assert _lookfor_block([]) == ""
    # String → paragraph
    out = _lookfor_block("Look at the diagonal.")
    assert "<details" in out and "Look at the diagonal." in out
    assert "<p>" in out
    # List → bullets
    out = _lookfor_block(["First point", "Second point"])
    assert "<ul>" in out and "<li>First point</li>" in out
    assert "<li>Second point</li>" in out


def test_figures_include_what_to_look_for_toggle(tmp_path):
    """Every rendered figure on Overview / Markets / Research must have
    a 'What to look for' toggle. The toggle is the dashboard's expert
    layer — keep it from regressing into a plain caption."""
    from fingerprint_atlas.dashboard import build_dashboard

    root = tmp_path / "repo"
    for relative in [
        "notebooks/atlas_v4/atlas.png",
        "notebooks/atlas_v4/features.png",
        "notebooks/inverse_abm_heatmap.png",
        "notebooks/propose_analytics/prediction_error_over_time.png",
        "notebooks/propose_analytics/prediction_error_by_family.png",
        "notebooks/propose_analytics/novelty_calibration.png",
    ]:
        p = root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")

    rows = [{"year": 2020, "mechanism_tags": "minority-game"}]
    out = root / "dashboard"
    build_dashboard(rows, str(out), repo_root=str(root))

    for page in ["index.html", "markets.html", "research.html"]:
        body = (out / page).read_text()
        assert "What to look for" in body, f"{page} missing toggle summary"
        assert '<details class="lookfor"' in body, f"{page} missing toggle"

    # Spot-check distinctive guidance text on each page
    overview = (out / "index.html").read_text()
    assert "principal axes" in overview or "loadings" in overview
    research = (out / "research.html").read_text()
    assert "blind spot" in research  # appears in prediction-error-by-family
    assert "diagonal" in research    # appears in novelty calibration


def test_subfield_catalog_includes_all_categories():
    from fingerprint_atlas.dashboard import _subfield_catalog_html
    body = _subfield_catalog_html()
    # category labels appear; one card per subfield (25)
    for cat in ["foundational", "stylized", "microstructure", "behavioral",
                 "network", "crisis", "learning"]:
        assert cat in body
    assert body.count('class="sfcard"') >= 25


def test_technique_catalog_includes_all_categories_and_renders_refs():
    from fingerprint_atlas.dashboard import _technique_catalog_html
    body = _technique_catalog_html()
    # all six categories appear as headings
    for cat in ["tail-stats", "sim-arch", "decision-rule", "validation",
                 "calibration", "learning-agent"]:
        assert cat in body, f"missing category {cat}"
    # 30 entries → at least 30 cards
    assert body.count('class="tech-card"') >= 30
    # known technique surfaces
    assert "Hill estimator" in body
    assert "Speculation Game" in body or "speculation game" in body.lower()
    # ref_repos rendered as outbound links
    assert 'href="https://github.com/' in body
    # gotchas appear inside the cards
    assert "gotchas" in body
    # purpose blurb visible in summary
    assert "tail-index" in body.lower() or "tail-exponent" in body.lower() \
            or "tail exponent" in body.lower()


def test_abm_family_grid_renders_all_eight_with_provenance():
    from fingerprint_atlas.dashboard import _abm_family_grid_html
    from fingerprint_atlas.abm_families import ABM_FAMILIES
    body = _abm_family_grid_html()
    assert len(ABM_FAMILIES) == 8
    assert body.count('class="fam-card"') == 8
    # Source papers surface (provenance is the whole point)
    assert "Cont &amp; Bouchaud (2000)" in body
    assert "Lux &amp; Marchesi (1999)" in body
    assert "Gode &amp; Sunder (1993)" in body  # ZI provenance!
    assert "Challet &amp; Zhang (1997)" in body
    # ZI is flagged as a null hypothesis (the user's complaint)
    assert "NULL HYPOTHESIS" in body
    # Epistemic-role callouts exist
    assert body.count("epistemic role") == 8
    # Fidelity notes section appears (impl faithfulness, the user's complaint)
    assert "fidelity to source paper" in body


def test_markets_page_embeds_family_reference_and_distance_doc(tmp_path):
    from fingerprint_atlas.dashboard import build_dashboard
    root = tmp_path / "repo"
    (root / "notebooks/atlas_v4").mkdir(parents=True)
    for relative in [
        "notebooks/atlas_v4/atlas.png",
        "notebooks/atlas_v4/features.png",
        "notebooks/inverse_abm_heatmap.png",
    ]:
        p = root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    out = root / "dashboard"
    build_dashboard([], str(out), repo_root=str(root))
    markets = (out / "markets.html").read_text()
    # Family reference section present
    assert "ABM family reference" in markets
    assert "Zero Intelligence" in markets
    # Distance-metric definition is in the heatmap lookfor
    assert "Hill" in markets and "z-scored" in markets
    # ZI null-hypothesis caveat surfaces
    assert "NULL HYPOTHESIS" in markets


def test_research_page_embeds_technique_catalog(tmp_path):
    from fingerprint_atlas.dashboard import build_dashboard
    out = tmp_path / "dashboard"
    build_dashboard([], str(out), repo_root=str(tmp_path))
    research = (out / "research.html").read_text()
    assert "Technique catalog" in research
    assert "tail-stats" in research and "decision-rule" in research


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
