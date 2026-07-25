"""Standalone smoke test: ``python -m abm.smoke_test``.

Runs the two mandatory checks (closed-loop continuity, and a light exp1 sweep
showing IS monotone in Q/V with a delta estimate). Thin wrapper over run.py so
there is a single source of truth.
"""

from __future__ import annotations

from .run import smoke_closed_loop, smoke_exp1


def main():
    smoke_closed_loop()
    smoke_exp1(n_seeds=20)


if __name__ == "__main__":
    main()
