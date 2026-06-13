"""Typer CLI skeleton. Phase commands are stubbed and exit with code 2 until landed."""

from __future__ import annotations

from pathlib import Path

import typer

from state_atlas import __version__
from state_atlas.config import load_config

app = typer.Typer(
    help="Market State Atlas - causal embedding + free energy landscape.",
    no_args_is_help=True,
    add_completion=False,
    # rich-formatted help breaks on legacy Windows consoles; plain text is portable.
    rich_markup_mode=None,
    pretty_exceptions_show_locals=False,
)


def _stub(phase: str, name: str) -> None:
    typer.echo(f"[{name}] not implemented yet — lands in {phase}.", err=True)
    raise typer.Exit(code=2)


@app.command()
def version() -> None:
    """Print package version."""
    typer.echo(__version__)


@app.command()
def data(
    config_path: Path = typer.Option("config.yaml", "--config", "-c"),
    force_refresh: bool = typer.Option(False, "--force-refresh", help="Bypass parquet cache"),
) -> None:
    """Fetch & cache multi-asset OHLCV (Phase 1)."""
    cfg = load_config(config_path)
    from state_atlas.data import load_universe

    mdf = load_universe(cfg, force_refresh=force_refresh)
    typer.echo(
        f"[OK] rows={mdf.n_rows} tickers={len(mdf.tickers)} "
        f"range=[{mdf.date_range[0].date()}, {mdf.date_range[1].date()}] "
        f"has_volume={mdf.has_volume}"
    )


@app.command()
def features(
    config_path: Path = typer.Option("config.yaml", "--config", "-c"),
) -> None:
    """Build causal feature matrix with leakage guard (Phase 2)."""
    cfg = load_config(config_path)
    from state_atlas.data import load_universe
    from state_atlas.features import build_features

    mdf = load_universe(cfg)
    fs = build_features(mdf, cfg.features)
    typer.echo(
        f"[OK] features rows={len(fs.df)} cols={fs.n_features} "
        f"range=[{fs.df.index[0].date()}, {fs.df.index[-1].date()}]"
    )


@app.command()
def embed(
    config_path: Path = typer.Option("config.yaml", "--config", "-c"),
    out: Path = typer.Option("artifacts/embed.pt", "--out", "-o"),
) -> None:
    """Fit OOS-projectable embedding (β-VAE) on the universe in config (Phase 3)."""
    cfg = load_config(config_path)
    from state_atlas.data import load_universe
    from state_atlas.embedding import BetaVAEEmbedder
    from state_atlas.features import build_features

    mdf = load_universe(cfg)
    fs = build_features(mdf, cfg.features)
    emb = BetaVAEEmbedder(in_dim=fs.n_features, cfg=cfg.embedding)
    emb.fit(fs.df.values)
    emb.save(out)
    typer.echo(
        f"[OK] β-VAE fit  in_dim={fs.n_features}  latent_dim={cfg.embedding.latent_dim}  "
        f"recon_mse={emb.recon_mse:.4f}  KL_per_dim={emb.kl_per_dim.round(3).tolist()}  "
        f"d_eff(0.1)={emb.effective_dim(0.1)}  saved={out}"
    )


@app.command()
def atlas(
    config_path: Path = typer.Option("config.yaml", "--config", "-c"),
    out: Path = typer.Option("artifacts/atlas.html", "--out", "-o"),
    json_out: Path = typer.Option("artifacts/atlas_report.json", "--json-out"),
    fallback_2d: bool = typer.Option(False, "--fallback-2d"),
) -> None:
    """Full pipeline: data → features → embed → F(z) → 3D HTML + JSON report."""
    cfg = load_config(config_path)
    from state_atlas.pipeline import render_atlas, report_to_json, run_atlas

    result = run_atlas(cfg)
    json_path = report_to_json(result, json_out)
    n_trans = 0 if result.dynamics is None else len(result.dynamics.transitions)
    if result.grid is not None:
        html_path = render_atlas(result, out, fallback_2d=fallback_2d)
        pd = result.persistence_diagram
        pd_str = (
            (", ".join(f"{p:.2f}" for p in pd[:8].tolist()) + ("…" if len(pd) > 8 else ""))
            if len(pd)
            else "(none)"
        )
        typer.echo(
            f"[OK] atlas → {html_path}\n"
            f"     report → {json_path}\n"
            f"     rows={len(result.z)}  input_dim={result.features.n_features}\n"
            f"     raw_minima={result.raw_minima_count}  "
            f"basins(merged)={result.n_basins}  "
            f"basins(effective: persistence≥1.0 ∧ dwell≥21d)={result.n_effective_basins}  "
            f"transitions={n_trans}\n"
            f"     persistence_diagram (top): {pd_str}\n"
            f"     basin_count @ τ: {result.basin_counts_at_thresholds}\n"
            f"     d_eff @ τ: {result.d_eff_at_thresholds}\n"
            f"     d_eff/input_dim: "
            + ", ".join(f"τ={t}:{v:.3f}" for t, v in result.d_eff_over_input_dim.items())
        )
    else:
        typer.echo(
            "[WARN] latent_dim != 2 — no surface rendered. "
            f"d_eff(0.1)={result.embedder.effective_dim(0.1)}"
        )


@app.command("viz-demo")
def viz_demo(
    out: Path = typer.Option("artifacts/atlas_demo.html", "--out", "-o"),
    seed: int = typer.Option(42, "--seed"),
    n_steps: int = typer.Option(4000, "--n-steps"),
    fallback_2d: bool = typer.Option(False, "--fallback-2d"),
) -> None:
    """Render synthetic 2D double-well free-energy surface + trajectory animation."""
    from state_atlas.viz.atlas3d import render_landscape_html
    from state_atlas.viz.landscape import fit_free_energy_2d
    from state_atlas.viz.synthetic import simulate_double_well_2d

    z = simulate_double_well_2d(n_steps=n_steps, seed=seed)
    grid = fit_free_energy_2d(z, grid_size=80)
    written = render_landscape_html(grid, z, out, fallback_2d=fallback_2d)
    typer.echo(f"[OK] wrote {written}")


@app.command("experiment")
def experiment(
    name: str = typer.Argument(..., help="Experiment name (universe-comparison | uc)"),
    config_path: Path = typer.Option("config.yaml", "--config", "-c"),
    universes: str = typer.Option(
        "", "--universes", help="Comma-separated subset (default: all from config)"
    ),
    csv_out: Path = typer.Option("artifacts/universe_comparison.csv", "--csv"),
    html_out: Path = typer.Option("artifacts/universe_comparison.html", "--html"),
) -> None:
    """Run a meta-experiment. Currently: universe-comparison (Phase 4.5)."""
    cfg = load_config(config_path)
    if name in ("universe-comparison", "uc"):
        from state_atlas.experiments.universe_comparison import (
            run_all,
            write_csv,
            write_html,
        )

        subset = [s.strip() for s in universes.split(",") if s.strip()] or None
        reports = run_all(cfg, subset=subset)
        write_csv(reports, csv_out)
        write_html(reports, html_out)
        typer.echo(
            f"[OK] {len(reports)} universes → {csv_out} {html_out}\n"
            + "\n".join(
                f"  {r.universe_id}: rows={r.n_rows} d_eff={r.d_eff} "
                f"basins={r.n_basins} ratio={r.barrier_ratio:.3f} "
                f"sil={('NaN' if (r.silhouette != r.silhouette) else round(r.silhouette, 3))}"
                for r in reports.values()
            )
        )
    else:
        raise typer.BadParameter(f"unknown experiment: {name}")


@app.command()
def backtest(
    config_path: Path = typer.Option("config.yaml", "--config", "-c"),
    train_frac: float = typer.Option(0.7, "--train-frac"),
    forward_days: int = typer.Option(21, "--forward-days"),
    benchmark: str = typer.Option("", "--benchmark", help="Default = first ticker"),
    out: Path = typer.Option("artifacts/backtest_report.txt", "--out", "-o"),
    n_permutations: int = typer.Option(200, "--n-perms"),
) -> None:
    """Walk-forward backtest (Phase 7). Honest 'no edge' reporting by default."""
    cfg = load_config(config_path)
    from state_atlas.backtest import single_split_backtest, write_report
    from state_atlas.data import load_universe

    mdf = load_universe(cfg)
    bench = benchmark or None
    rep = single_split_backtest(
        mdf,
        cfg,
        train_frac=train_frac,
        forward_days=forward_days,
        benchmark_ticker=bench,
        n_permutations=n_permutations,
    )
    write_report(rep, out)
    typer.echo(f"[OK] {rep.summary}")
    typer.echo(f"     report → {out}")


if __name__ == "__main__":
    app()
