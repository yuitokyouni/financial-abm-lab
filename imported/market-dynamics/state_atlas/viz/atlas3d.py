"""3D free-energy surface + trajectory animation, exported as standalone HTML.

Phase 6 stub: given a 2D trajectory ``z(t)`` and the corresponding free-energy
grid, render an interactive plot:

- Surface ``(z1, z2, F)`` colored by F (basins are blue minima)
- Animated marker tracing ``z(t)`` along the surface
- A trailing path of the last ``trail`` points

The real Phase 6 reuses this same function with the VAE-projected z(t) and the
Phase 4 free-energy grid. The "early stub" hooks (DECISIONS.md) are:

  state_atlas/cli.py: atlas viz-demo → render_landscape_html(synthetic z)

2D heatmap fallback (``fallback_2d=True`` in config) drops the Surface trace
for headless / WebGL-unfriendly environments.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from state_atlas.viz.landscape import FreeEnergyGrid


def _height_along_path(grid: FreeEnergyGrid, path: np.ndarray) -> np.ndarray:
    """Thin wrapper around density.F_along_trajectory for the marker height."""
    from state_atlas.density.free_energy import F_along_trajectory

    return F_along_trajectory(grid, path)


def render_landscape_html(
    grid: FreeEnergyGrid,
    trajectory: np.ndarray,
    out_path: str | Path,
    n_frames: int = 60,
    trail: int = 80,
    title: str = "Market State Atlas — synthetic free-energy landscape",
    fallback_2d: bool = False,
) -> Path:
    """Write a standalone HTML file with the F surface and an animated trajectory.

    n_frames controls how many animation steps to bake in (the trajectory is
    sub-sampled uniformly). trail is how many past points to draw as a fading line.
    """
    import plotly.graph_objects as go

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    path = np.asarray(trajectory, dtype=float)
    if path.ndim != 2 or path.shape[1] != 2:
        raise ValueError(f"trajectory must be (T, 2), got {path.shape}")
    heights = _height_along_path(grid, path)

    # Sub-sample frame indices uniformly.
    n_frames = max(2, min(n_frames, len(path)))
    frame_idx = np.linspace(0, len(path) - 1, n_frames, dtype=int)

    surface = go.Surface(
        x=grid.z1,
        y=grid.z2,
        z=grid.F,
        colorscale="Viridis",
        opacity=0.85,
        showscale=True,
        colorbar={"title": "F(z) = -log ρ(z)"},
        name="F(z)",
    )

    def _marker_trace(end: int) -> go.Scatter3d:
        s = max(0, end - trail)
        return go.Scatter3d(
            x=path[s : end + 1, 0],
            y=path[s : end + 1, 1],
            z=heights[s : end + 1] + 0.05,  # tiny lift so marker sits above surface
            mode="lines+markers",
            line={"color": "crimson", "width": 4},
            marker={
                "size": [2] * max(end - s, 0) + [6],
                "color": "crimson",
            },
            name="z(t)",
        )

    initial_marker = _marker_trace(frame_idx[0])
    frames = [go.Frame(data=[surface, _marker_trace(int(i))], name=str(int(i))) for i in frame_idx]

    if fallback_2d:
        # 2D heatmap variant — no Surface, no Scatter3d.
        fig = go.Figure(
            data=[
                go.Heatmap(
                    x=grid.z1,
                    y=grid.z2,
                    z=grid.F,
                    colorscale="Viridis",
                    colorbar={"title": "F(z)"},
                ),
                go.Scatter(
                    x=path[:, 0],
                    y=path[:, 1],
                    mode="lines",
                    line={"color": "crimson", "width": 1.5},
                    name="z(t)",
                ),
            ],
            layout=go.Layout(
                title=title + "  (2D fallback)",
                xaxis_title="z1",
                yaxis_title="z2",
            ),
        )
    else:
        fig = go.Figure(
            data=[surface, initial_marker],
            frames=frames,
            layout=go.Layout(
                title=title,
                scene={
                    "xaxis_title": "z1",
                    "yaxis_title": "z2",
                    "zaxis_title": "F(z)",
                },
                updatemenus=[
                    {
                        "type": "buttons",
                        "showactive": False,
                        "buttons": [
                            {
                                "label": "Play",
                                "method": "animate",
                                "args": [
                                    None,
                                    {
                                        "frame": {"duration": 60, "redraw": True},
                                        "fromcurrent": True,
                                    },
                                ],
                            },
                            {
                                "label": "Pause",
                                "method": "animate",
                                "args": [
                                    [None],
                                    {
                                        "frame": {"duration": 0, "redraw": False},
                                        "mode": "immediate",
                                    },
                                ],
                            },
                        ],
                    }
                ],
            ),
        )

    fig.write_html(str(out_path), include_plotlyjs="cdn", auto_play=False)
    return out_path
