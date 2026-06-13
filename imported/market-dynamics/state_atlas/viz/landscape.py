"""Re-export shim. The canonical home of FreeEnergyGrid + KDE evaluation is
``state_atlas.density.free_energy``; this module is kept so existing call sites
(viz/atlas3d, Phase 6 stub tests) don't have to change.
"""

from __future__ import annotations

from state_atlas.density.free_energy import FreeEnergyGrid, fit_free_energy_2d

__all__ = ["FreeEnergyGrid", "fit_free_energy_2d"]
