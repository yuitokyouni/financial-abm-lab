"""Density ρ(z) and free energy F(z) = -log ρ(z). Basin detection."""

from state_atlas.density.free_energy import (
    BasinStats,
    F_along_trajectory,
    FreeEnergyGrid,
    assign_basins,
    barrier_ratio,
    basin_count_at_thresholds,
    basin_dwell_counts,
    basin_stats,
    effective_basin_mask,
    find_local_minima_2d,
    fit_free_energy_2d,
    free_energy_with_basins,
    kramers_lifetime,
    merge_low_persistence_basins,
)

__all__ = [
    "BasinStats",
    "F_along_trajectory",
    "FreeEnergyGrid",
    "assign_basins",
    "barrier_ratio",
    "basin_count_at_thresholds",
    "basin_dwell_counts",
    "basin_stats",
    "effective_basin_mask",
    "find_local_minima_2d",
    "fit_free_energy_2d",
    "free_energy_with_basins",
    "kramers_lifetime",
    "merge_low_persistence_basins",
]
