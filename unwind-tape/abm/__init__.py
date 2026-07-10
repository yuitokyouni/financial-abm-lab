"""unwind-tape ABM skeleton (research YH009).

A minimal, self-contained agent-based model of a single Japanese-equity name
under a large block sale (政策保有株の売出し). The goal of this package is a
*working skeleton* of the closed-loop microstructure (LOB + ZI/FCN agents +
event execution), not a calibrated model. Parameters are provisional and are
marked with TODO(calibration) throughout.

Dependencies: numpy + Python standard library only. No imports from other
repo code (fully self-contained).
"""

__all__ = [
    "config",
    "order_book",
    "agents",
    "market",
    "experiments",
]
