"""capture — ctx 呼び出しの捕捉層(v0: L0-L2)。

設計ノート §4 のレベル梯子に対応する `CaptureLevel`、ctx イベント型、
そして L2 の honest 性確保のための「非 ctx RNG 使用」整合性 lint を提供する。

L3+(静的 AST whitelist / taint / restricted DSL)は **本 v0 ではスコープ外**で、
`CaptureSink` は L3 以上の要求を `NotImplementedError` で明示拒否する(framework-first 禁止)。
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any


class CaptureLevel(IntEnum):
    """設計ノート §4 の L0-L5。v0 が実装するのは L0-L2、L3+ は stub。"""

    L0 = 0  # 自由 ABM(捕捉なし)
    L1 = 1  # Reproducible(seed/依存/入出力 digest)
    L2 = 2  # Instrumented(ctx 主要 API を記録)= adoption engine
    L3 = 3  # Capability(+静的 AST)        — v0 stub
    L4 = 4  # Restricted DSL / exact         — v0 stub
    L5 = 5  # Formal core(Lean)            — v0 stub


class CtxEventKind(StrEnum):
    """ctx 経由の 4 系統(設計ノート §3 の `ctx.*` API)。"""

    OBSERVE = "observe"
    READ_OWN_STATE = "read_own_state"
    RANDOM = "random"
    SUBMIT_ORDER = "submit_order"


@dataclass(frozen=True, slots=True)
class CtxEvent:
    """1 回の ctx 呼び出しの記録。

    `meta` は軽量な JSON 化可能メタのみ(shape/dtype/scalar 等)。生の観測配列そのものは
    記録しない(再現は seed 経由、ここは lineage/reach 用)。
    """

    agent_id: int
    step: int
    kind: CtxEventKind
    key: str
    meta: Mapping[str, Any] = field(default_factory=dict)


class CaptureSink:
    """ctx イベントの蓄積先。L2 でイベントを記録、L0/L1 では記録しない。

    L3 以上は protocol stub のみ(AST whitelist / taint / DSL は持ち越し)。
    """

    def __init__(self, level: CaptureLevel = CaptureLevel.L2) -> None:
        if level >= CaptureLevel.L3:
            raise NotImplementedError(
                f"capture {level.name}: L3+ は protocol stub のみ "
                "(awaiting AST whitelist / taint / restricted DSL)"
            )
        self.level = level
        self._events: list[CtxEvent] = []

    @property
    def events(self) -> tuple[CtxEvent, ...]:
        return tuple(self._events)

    def record(self, event: CtxEvent) -> None:
        # L2 以上でのみ ctx イベントを残す(L0/L1 は再現性 digest のみで本層は no-op)。
        if self.level >= CaptureLevel.L2:
            self._events.append(event)

    def to_records(self) -> list[dict[str, Any]]:
        """parquet 化用のフラットな record 列。"""
        return [
            {
                "agent_id": e.agent_id,
                "step": e.step,
                "kind": e.kind.value,
                "key": e.key,
                "meta": dict(e.meta),
            }
            for e in self._events
        ]

    def __len__(self) -> int:
        return len(self._events)


# --- L2 honest 性整合性 lint ----------------------------------------------
# CLAUDE.md: 「ctx 経由でない RNG の使用を整合性 lint で警告する(L2 でも honest 性確保。
# AST whitelist は L3 まで持ち越し)」。ここでは *警告* のみ(reject は L3)。

_FORBIDDEN_RNG_ROOTS: frozenset[str] = frozenset({"np.random", "numpy.random", "random"})


def _dotted_name(node: ast.AST) -> str | None:
    """`np.random.normal` のような属性チェーンをドット文字列に復元する。"""
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def lint_ctx_purity(source: str, filename: str = "<agent>") -> list[str]:
    """非 ctx RNG(`np.random.*` / `numpy.random.*` / `random.*`)の使用を警告として返す。

    honest 性の最小保証。adversarial な hidden channel は閉じない(それは L3+/§3.2)。
    返り値が空なら ctx-pure(報告ベースで)。
    """
    warnings: list[str] = []
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            dotted = _dotted_name(node)
            if dotted is None:
                continue
            for root in _FORBIDDEN_RNG_ROOTS:
                if dotted == root or dotted.startswith(root + "."):
                    warnings.append(
                        f"{filename}:{node.lineno}: 非 ctx RNG '{dotted}' "
                        "— ctx.random() を使うこと(L2 honest 性)"
                    )
                    break
    return warnings
