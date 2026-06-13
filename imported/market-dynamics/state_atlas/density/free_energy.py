"""Density ρ(z) → free energy F(z) = -log ρ(z) on a 2D grid, with basin detection.

This module owns the geometric machinery that Phase 4 / 6 / 4.5 all depend on:

- ``fit_free_energy_2d``: gaussian KDE on (N, 2) latent points → F on a regular grid.
  (Causal helper — the caller decides which window to fit.)
- ``find_local_minima_2d``: 8-connected local minima of F on the grid.
- ``assign_basins``: each grid cell is labeled by which minimum its steepest-descent
  trajectory reaches. Pure-numpy; no skimage dependency.
- ``basin_stats``: depth of each basin + barrier height between every adjacent pair,
  plus a convenience ``barrier_ratio`` for the Phase 4.5 universe comparison.

The reused ``FreeEnergyGrid`` dataclass moved here from viz/; ``viz/landscape.py``
is now a re-export shim so existing imports keep working.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import gaussian_kde

# 8-connected neighbor offsets (excludes (0,0)).
_NEIGHBORS: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)


@dataclass(frozen=True)
class FreeEnergyGrid:
    z1: np.ndarray  # (G,) axis-1 grid centers
    z2: np.ndarray  # (G,) axis-2 grid centers
    rho: np.ndarray  # (G, G) density evaluated on meshgrid(z2, z1)
    F: np.ndarray  # (G, G) free energy = -log ρ, shifted so min = 0


@dataclass(frozen=True)
class BasinStats:
    """Result of running basin detection on a FreeEnergyGrid.

    Two different "depth"-like quantities are kept because they answer
    different questions:

    - ``depths[k]`` = F_max_within_basin_k - F_at_min[k].
      The raw extent of the basin's cell set. Useful when there is only one
      basin (no neighbor to saddle against) or to gauge the spread.

    - ``persistence[k]`` = (lowest crossing F to any neighbor) - F_at_min[k].
      The topological persistence: how much you have to raise the water level
      before basin k merges with someone else. ``inf`` if k has no neighbor.
      This is the basin-separation quantity used by Phase 4.5.

    - ``barriers[(a, b)]`` = lowest crossing F between a and b, measured
      ABOVE the lower of the two minima. Keys are sorted (a < b).

    - ``persistence_diagram`` = the sorted-descending persistences of EVERY
      local minimum on the raw F grid, BEFORE the persistence-merge cleanup.
      This is the measurement target the Phase 4.5 universe comparison reports
      directly — collapsing it to a single count throws away the very quantity
      we're trying to measure (see DECISIONS.md "Catch 1"). On a finite KDE
      this includes both genuine basins and noise wobbles; the user reads the
      spectrum, not a thresholded count.
    """

    minima: list[tuple[int, int]]
    labels: np.ndarray
    F_at_min: np.ndarray
    depths: np.ndarray
    persistence: np.ndarray
    barriers: dict[tuple[int, int], float] = field(default_factory=dict)
    persistence_diagram: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))

    @property
    def n_basins(self) -> int:
        return len(self.minima)


# ---------------------------------------------------------------------------
# Density + F evaluation
# ---------------------------------------------------------------------------


def fit_free_energy_2d(
    points: np.ndarray,
    grid_size: int = 80,
    bandwidth: str | float = "scott",
    pad: float = 0.5,
    eps: float = 1e-12,
) -> FreeEnergyGrid:
    """KDE on (N, 2) points → free-energy grid. Caller controls windowing."""
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"points must be shape (N, 2), got {pts.shape}")
    if len(pts) < 4:
        raise ValueError("need at least 4 points to fit a 2D KDE")
    z1_min, z2_min = pts.min(axis=0) - pad
    z1_max, z2_max = pts.max(axis=0) + pad
    z1 = np.linspace(z1_min, z1_max, grid_size)
    z2 = np.linspace(z2_min, z2_max, grid_size)
    Z1, Z2 = np.meshgrid(z1, z2)
    flat = np.vstack([Z1.ravel(), Z2.ravel()])
    kde = gaussian_kde(pts.T, bw_method=bandwidth)
    rho = kde(flat).reshape(Z1.shape)
    F = -np.log(np.maximum(rho, eps))
    F = F - F.min()
    return FreeEnergyGrid(z1=z1, z2=z2, rho=rho, F=F)


# ---------------------------------------------------------------------------
# Basin detection (steepest-descent, no skimage dep)
# ---------------------------------------------------------------------------


def find_local_minima_2d(
    F: np.ndarray,
    exclude_boundary: bool = True,
    tail_quantile: float = 0.9,
) -> list[tuple[int, int]]:
    """Return (row, col) of cells strictly lower than all 8 neighbors.

    Two filters cut KDE noise:
    - Boundary cells are excluded by default — KDE on a padded grid sends
      F → +∞ at the edges, so any minimum is necessarily an interior basin.
    - Cells whose F is above ``tail_quantile`` of the grid's F distribution
      are excluded. In KDE tails ρ ≈ floor(eps) and F flattens at -log(eps);
      floating-point wobble in that plateau seeds spurious minima that
      dominate raw counts (~1000 per 80×80 grid on real data). The data
      distribution itself never sits up there, so a basin candidate there
      is by construction not a regime.
    """
    H, W = F.shape
    F_cap = float(np.quantile(F, tail_quantile)) if 0.0 < tail_quantile < 1.0 else float("inf")
    out: list[tuple[int, int]] = []
    for i in range(H):
        for j in range(W):
            if exclude_boundary and (i == 0 or i == H - 1 or j == 0 or j == W - 1):
                continue
            f = F[i, j]
            if f > F_cap:
                continue
            is_min = True
            for di, dj in _NEIGHBORS:
                ni, nj = i + di, j + dj
                if 0 <= ni < H and 0 <= nj < W and F[ni, nj] < f:
                    is_min = False
                    break
            if is_min:
                out.append((i, j))
    return out


def assign_basins(F: np.ndarray, minima: list[tuple[int, int]]) -> np.ndarray:
    """Label each cell by which minimum it descends to (steepest-descent flow).

    Returns an (H, W) int array. Label k always corresponds to ``minima[k]``;
    cells that hit a plateau or cycle fall back to the *Euclidean nearest*
    minimum so the label set stays exactly ``{0, …, len(minima)-1}``.
    """
    H, W = F.shape
    labels = -np.ones((H, W), dtype=np.int32)
    if not minima:
        return labels
    for k, (mi, mj) in enumerate(minima):
        labels[mi, mj] = k
    min_arr = np.asarray(minima, dtype=int)

    for i in range(H):
        for j in range(W):
            if labels[i, j] >= 0:
                continue
            path: list[tuple[int, int]] = [(i, j)]
            visited: set[tuple[int, int]] = {(i, j)}
            terminal: int = -1
            while True:
                ci, cj = path[-1]
                if labels[ci, cj] >= 0:
                    terminal = int(labels[ci, cj])
                    break
                f = F[ci, cj]
                best: tuple[int, int] | None = None
                best_f = f
                for di, dj in _NEIGHBORS:
                    ni, nj = ci + di, cj + dj
                    if 0 <= ni < H and 0 <= nj < W and F[ni, nj] < best_f:
                        best_f = F[ni, nj]
                        best = (ni, nj)
                if best is None or best in visited:
                    # Plateau / cycle → fall back to Euclidean-nearest minimum.
                    diff = min_arr - np.array([ci, cj])
                    terminal = int(np.argmin((diff**2).sum(axis=1)))
                    break
                path.append(best)
                visited.add(best)
            for p in path:
                labels[p] = terminal
    return labels


def basin_stats(
    grid: FreeEnergyGrid, labels: np.ndarray, minima: list[tuple[int, int]]
) -> BasinStats:
    """Compute per-basin depth, persistence, and pairwise barrier heights."""
    F = grid.F
    n = len(minima)
    F_at_min = np.array([F[i, j] for (i, j) in minima], dtype=float)
    depths = np.zeros(n, dtype=float)
    for k in range(n):
        mask = labels == k
        if mask.any():
            depths[k] = float(F[mask].max() - F_at_min[k])

    # For each adjacent (right + down) pair of cells with different labels,
    # treat the larger of the two F values as a candidate boundary point.
    # Keep the minimum such value per (a, b) pair = "easiest crossing".
    H, W = F.shape
    boundary: dict[tuple[int, int], float] = {}
    for i in range(H):
        for j in range(W):
            a = int(labels[i, j])
            if a < 0:
                continue
            for di, dj in ((0, 1), (1, 0)):
                ni, nj = i + di, j + dj
                if 0 <= ni < H and 0 <= nj < W:
                    b = int(labels[ni, nj])
                    if b >= 0 and a != b:
                        key = (min(a, b), max(a, b))
                        crossing = float(max(F[i, j], F[ni, nj]))
                        if key not in boundary or crossing < boundary[key]:
                            boundary[key] = crossing

    barriers: dict[tuple[int, int], float] = {}
    for (a, b), cross_f in boundary.items():
        barriers[(a, b)] = float(cross_f - min(F_at_min[a], F_at_min[b]))

    # Per-basin persistence: smallest crossing-F to any neighbor, above F_at_min[k].
    persistence = np.full(n, np.inf, dtype=float)
    for (a, b), cross_f in boundary.items():
        p_a = cross_f - F_at_min[a]
        p_b = cross_f - F_at_min[b]
        if p_a < persistence[a]:
            persistence[a] = p_a
        if p_b < persistence[b]:
            persistence[b] = p_b

    return BasinStats(
        minima=minima,
        labels=labels,
        F_at_min=F_at_min,
        depths=depths,
        persistence=persistence,
        barriers=barriers,
    )


def merge_low_persistence_basins(
    grid: FreeEnergyGrid,
    labels: np.ndarray,
    minima: list[tuple[int, int]],
    min_persistence: float = 1.0,
    max_iters: int | None = None,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Iteratively merge any basin whose persistence is below ``min_persistence``.

    Persistence here is the saddle height above the shallower of two adjacent
    minima — the literal water-level rise that destroys the shallower basin.
    A basin with persistence < min_persistence is a KDE wobble, not a regime.
    The shallower basin is folded into the deeper one.

    ``min_persistence`` is in F units (≈ kT for our convention where F = -log ρ);
    1.0 means "the saddle is at least one log-density unit above the minimum,"
    so the shallow well is at most ~e× less likely than the bottom — a low bar
    that nonetheless kills most KDE noise.
    """
    labels = labels.copy()
    minima = list(minima)
    # Each iteration removes exactly one basin, so a safe ceiling scales with
    # the input — KDE noise on real data can seed hundreds of minima before the
    # first cleanup pass settles down.
    if max_iters is None:
        max_iters = max(200, len(minima) * 2)
    for _ in range(max_iters):
        stats = basin_stats(grid, labels, minima)
        if not stats.barriers:
            break
        worst_pair: tuple[int, int] | None = None
        worst_pers = float("inf")
        for (a, b), barrier in stats.barriers.items():
            crossing = barrier + float(min(stats.F_at_min[a], stats.F_at_min[b]))
            shallow_pers = crossing - float(max(stats.F_at_min[a], stats.F_at_min[b]))
            if shallow_pers < worst_pers:
                worst_pers = shallow_pers
                worst_pair = (a, b)
        if worst_pair is None or worst_pers >= min_persistence:
            break
        a, b = worst_pair
        if stats.F_at_min[a] <= stats.F_at_min[b]:
            deeper, shallower = a, b
        else:
            deeper, shallower = b, a
        labels[labels == shallower] = deeper
        minima = [m for k, m in enumerate(minima) if k != shallower]
        labels[labels > shallower] -= 1
    return labels, minima


def barrier_ratio(stats: BasinStats) -> float:
    """``mean(barrier) / mean(depth)``. 0 if no barriers (single basin)."""
    if not stats.barriers or len(stats.depths) == 0:
        return 0.0
    mean_b = float(np.mean(list(stats.barriers.values())))
    mean_d = float(np.mean(stats.depths))
    return mean_b / max(mean_d, 1e-12)


def F_along_trajectory(grid: FreeEnergyGrid, z: np.ndarray) -> np.ndarray:
    """Bilinear-interpolate F at every (z1, z2) point in z.

    Returns a 1-D array F(z(t)). This is the "height" of the latent trajectory
    on the free-energy surface — a continuous stress proxy on the same scale
    as F itself (F = -log ρ, in nats above the global minimum).
    """
    z = np.asarray(z, dtype=float)
    if z.ndim != 2 or z.shape[1] != 2:
        raise ValueError(f"z must be (T, 2), got {z.shape}")
    z1, z2 = grid.z1, grid.z2
    F = grid.F
    ix = np.clip(np.searchsorted(z1, z[:, 0]) - 1, 0, len(z1) - 2)
    iy = np.clip(np.searchsorted(z2, z[:, 1]) - 1, 0, len(z2) - 2)
    x0, x1 = z1[ix], z1[ix + 1]
    y0, y1 = z2[iy], z2[iy + 1]
    tx = np.clip((z[:, 0] - x0) / np.maximum(x1 - x0, 1e-12), 0, 1)
    ty = np.clip((z[:, 1] - y0) / np.maximum(y1 - y0, 1e-12), 0, 1)
    f00 = F[iy, ix]
    f10 = F[iy, ix + 1]
    f01 = F[iy + 1, ix]
    f11 = F[iy + 1, ix + 1]
    return f00 * (1 - tx) * (1 - ty) + f10 * tx * (1 - ty) + f01 * (1 - tx) * ty + f11 * tx * ty


def kramers_lifetime(persistence: np.ndarray) -> np.ndarray:
    """UNCALIBRATED approximate regime half-life from persistence in nats.

    F = -log ρ uses natural log, so a basin with persistence ΔF nats has an
    Arrhenius escape time τ ~ exp(ΔF / kT) — Kramers' formula. We strip the
    prefactor (attempt frequency) and ASSUME kT = 1 and latent diffusion
    D⁽²⁾ ≈ 1 per sample step. Both assumptions are crude; the function
    returns ``exp(persistence)`` and labels it "days" only because the
    sample step is one trading day, NOT because the calibration is real.

    Use this as a comparative scale across basins of the same fit, not as
    an absolute predicted lifetime. The honest calibration requires the
    latent Kramers-Moyal D⁽²⁾(z) — see ``state_atlas.dynamics.latent_dynamics``
    and SPEC §5. A dominant basin whose nominal lifetime exceeds the entire
    observation window is a red flag that the barrier is being measured
    against a phantom KDE minimum, not a real competing regime.

    Reading the scale (with the same caveats):
    - persistence 1.0  → τ ≈ e ≈ 2.7       → barely a regime / KDE noise
    - persistence 3-4  → τ ≈ 20–55         → comparatively metastable
    - persistence > 5  → τ ≈ 150+          → comparatively long-lived
    """
    return np.exp(np.asarray(persistence, dtype=float))


def basin_dwell_counts(point_labels: np.ndarray, n_basins: int) -> np.ndarray:
    """How many trajectory points end up in each basin. Length = n_basins."""
    counts = np.zeros(n_basins, dtype=int)
    if len(point_labels) == 0 or n_basins == 0:
        return counts
    pl = np.asarray(point_labels, dtype=int)
    # Vectorized bincount, guarded against labels outside [0, n_basins).
    in_range = (pl >= 0) & (pl < n_basins)
    if in_range.any():
        counts[: int(pl[in_range].max()) + 1] = np.bincount(pl[in_range], minlength=n_basins)[
            :n_basins
        ]
    return counts


def effective_basin_mask(
    persistence: np.ndarray,
    dwell: np.ndarray,
    min_persistence: float = 1.0,
    min_dwell: int = 21,
) -> np.ndarray:
    """Boolean mask: a basin is "effective" iff BOTH persistence AND dwell pass.

    Either filter alone is gamed. High-persistence basins with dwell=0 are
    phantom KDE minima the trajectory never visits — geometric, not
    statistical. High-dwell basins with persistence=0 are noise wobbles
    inside the dominant region — statistical, not geometric. A regime needs
    both. This is the "consensus" Step 1b-4 recommends in DECISIONS.md.

    ``inf`` persistence (single-basin case, no neighbors) counts as passing
    the persistence filter — the basin is geometrically infinite.
    """
    p = np.asarray(persistence, dtype=float)
    d = np.asarray(dwell, dtype=int)
    p_pass = np.where(np.isfinite(p), p >= min_persistence, True)
    return p_pass & (d >= min_dwell)


def basin_count_at_thresholds(
    persistence_diagram: np.ndarray, thresholds: list[float] | tuple[float, ...]
) -> dict[float, int]:
    """Number of minima with persistence > τ for each τ.

    Reports the count at multiple thresholds because no single threshold is
    privileged (Catch 1 — collapsing to one number throws information away).
    """
    p = np.asarray(persistence_diagram, dtype=float)
    return {float(t): int((p > t).sum()) for t in thresholds}


# ---------------------------------------------------------------------------
# Top-level convenience: latent points → grid + basin stats.
# ---------------------------------------------------------------------------


def free_energy_with_basins(
    points: np.ndarray,
    grid_size: int = 80,
    bandwidth: str | float = "scott",
    pad: float = 0.5,
    min_persistence: float = 1.0,
) -> tuple[FreeEnergyGrid, BasinStats]:
    """Latent points → (F grid, basin stats) with KDE noise suppression.

    The ``min_persistence`` post-process folds away basins whose saddle is less
    than ``min_persistence`` F-units above the basin minimum — gaussian KDE on
    finite samples always seeds a few of these. Set to 0 to skip merging.

    Crucially, the **raw** persistence diagram (every local minimum's
    persistence BEFORE merging) is kept on the returned stats. The merge step
    is for cleaning up labels; the measurement target itself (Catch 1 from
    DECISIONS.md) is the full pre-merge spectrum.
    """
    grid = fit_free_energy_2d(points, grid_size=grid_size, bandwidth=bandwidth, pad=pad)

    # First pass: every local minimum, persistence per basin, no merging.
    raw_minima = find_local_minima_2d(grid.F)
    raw_labels = assign_basins(grid.F, raw_minima)
    raw_stats = basin_stats(grid, raw_labels, raw_minima)
    finite_raw_p = raw_stats.persistence[np.isfinite(raw_stats.persistence)]
    persistence_diagram = np.sort(finite_raw_p)[::-1]  # descending

    # Second pass: merge KDE noise wobbles for downstream labeling.
    if min_persistence > 0 and len(raw_minima) > 1:
        labels, minima = merge_low_persistence_basins(
            grid, raw_labels, raw_minima, min_persistence=min_persistence
        )
    else:
        labels, minima = raw_labels, raw_minima
    merged_stats = basin_stats(grid, labels, minima)

    return grid, BasinStats(
        minima=merged_stats.minima,
        labels=merged_stats.labels,
        F_at_min=merged_stats.F_at_min,
        depths=merged_stats.depths,
        persistence=merged_stats.persistence,
        barriers=merged_stats.barriers,
        persistence_diagram=persistence_diagram,
    )
