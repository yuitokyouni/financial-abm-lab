"""Cont-Bouchaud (1997) percolation model of herding in financial markets.

Reference: Cont & Bouchaud (1997) "Herd behavior and aggregate fluctuations
in financial markets", Macroeconomic Dynamics 4(2), 170-196.
"""

from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components


def _cluster_sizes(N: int, c: float, rng: np.random.Generator) -> np.ndarray:
    """Generate an Erdős-Rényi graph and return connected component sizes.

    Vectorized: sample edge count from binomial, then draw edge positions.
    """
    p = c / N
    n_possible = N * (N - 1) // 2
    n_edges = rng.binomial(n_possible, p)

    if n_edges == 0:
        return np.ones(N, dtype=np.int64)

    # Sample edge indices without replacement from upper triangle
    edge_indices = rng.choice(n_possible, size=n_edges, replace=False)

    # Convert flat upper-triangle index to (i, j)
    # For upper triangle: flat index k maps to row i where
    # i = N - 2 - floor(sqrt(-8*k + 4*N*(N-1) - 7) / 2 - 0.5)
    # j = k + i + 1 - N*(N-1)/2 + (N-i)*((N-i)-1)/2
    rows = (
        N
        - 2
        - np.floor(
            np.sqrt(-8.0 * edge_indices + 4.0 * N * (N - 1) - 7.0) / 2.0 - 0.5
        ).astype(np.int64)
    )
    cols = (
        edge_indices
        + rows
        + 1
        - (N * (N - 1) // 2)
        + ((N - rows) * ((N - rows) - 1) // 2)
    ).astype(np.int64)

    # Symmetrize
    all_rows = np.concatenate([rows, cols])
    all_cols = np.concatenate([cols, rows])
    data = np.ones(len(all_rows), dtype=np.int8)
    adj = csr_matrix((data, (all_rows, all_cols)), shape=(N, N))

    _, labels = connected_components(adj, directed=False)
    return np.bincount(labels)


def simulate(
    N: int = 10000,
    c: float = 0.9,
    a: float = 0.01,
    lam: float = 1.0,
    T: int = 50000,
    seed: int = 42,
    report_every: int = 5000,
) -> dict:
    """Run the Cont-Bouchaud model.

    Each timestep: new random graph → clusters → random buy/sell/wait → excess demand.
    Returns dict with keys: returns, cluster_sizes
    """
    rng = np.random.default_rng(seed)
    returns = np.empty(T)
    cluster_sizes_all: list[np.ndarray] = []

    for t in range(T):
        if report_every and t % report_every == 0:
            print(f"  step {t}/{T}")

        sizes = _cluster_sizes(N, c, rng)
        cluster_sizes_all.append(sizes)

        n_clusters = len(sizes)
        u = rng.random(n_clusters)
        actions = np.where(u < a, 1, np.where(u < 2 * a, -1, 0))

        excess_demand = np.sum(sizes * actions)
        returns[t] = excess_demand / lam

    all_sizes = np.concatenate(cluster_sizes_all)
    return {"returns": returns, "cluster_sizes": all_sizes}
