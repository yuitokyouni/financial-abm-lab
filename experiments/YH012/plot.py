"""Phase 2+ 用。mid / Δ(t) プロットは Impact 実装後に充実させる。"""

from __future__ import annotations

from pathlib import Path


def plot_mid_placeholder(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# YH012 plot placeholder — Phase 2 で impact Δ(t) を描画する\n",
        encoding="utf-8",
    )
