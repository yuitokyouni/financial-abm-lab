"""atlas — Intervention Atlas の format scaffold。

**実装は将来。** v0 では `Battery` / `Mechanism` / `Response` の抽象 protocol(型のみ)を置くだけ。
実際の battery 実装・leaderboard・scoring・Type2 survival test はスコープ外(CLAUDE.md)。
詳細は `atlas/README.md`。
"""

from atlas.protocols import Battery, Mechanism, Response, ResponseVector

__all__ = ["Battery", "Mechanism", "Response", "ResponseVector"]
