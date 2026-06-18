"""model_contract_v1 — the minimal surface a model must expose to enter the Atlas.

This is the code-side of ``docs/model_contract_v1.md``. Spec 002 §5 defines the
contract; this module makes it executable and gives the conformance ladder
(C0/C1/C2) of ``docs/model_contract_v1.md §6``.

Design discipline (spec 002 §3): the arena begins from a *contract*, not a
leaderboard. A model that satisfies this contract becomes eligible for an Atlas
row; nothing here decides whether the model is *valid* (spec 002 §1 non-goal).

The canonical models in ``abm_models`` expose ``run(*, seed) -> dict`` only — that
is **C0** (deterministic run + emit). They do not expose a B2 observation channel,
so they are *not* C1: this is recorded honestly, never faked (spec 002 §11 / the
order-book channel work in PROV-ABM-atlas Finding 0002 is what unlocks C1).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Protocol, runtime_checkable

import numpy as np


class ConformanceLevel(IntEnum):
    """model_contract_v1 §6 conformance ladder.

    Higher levels are supersets. The Atlas records the *highest* level a model
    actually satisfies — claiming a level a model does not reach is a contract
    violation, not an Atlas decision.
    """

    C0 = 0  # reset / step / emit + determinism → SF battery, replication, variance
    C1 = 1  # + channels / observe / intervene → intervention-response protocol
    C2 = 2  # + provenance (L2) → declared-vs-observed reconciliation (reach audit)


class ContractViolation(Exception):
    """Raised when a model fails a required contract obligation."""


@dataclass(frozen=True, slots=True)
class Intervention:
    """do(channel, scheme, theta) — the B2 observation-channel intervention.

    ``theta == 0`` MUST be the identity (no-op). ``scheme`` is one of the four B2
    schemes (see ``atlas.intervention``). Interventions on undeclared channels do
    not exist at the type level (model_contract_v1 §5).
    """

    channel: str
    scheme: str
    theta: float


@runtime_checkable
class Simulator(Protocol):
    """The full model_contract_v1 surface (target shape, §5).

    Most canonical models satisfy only the C0 subset (``reset``/``emit`` +
    determinism). ``observe``/``intervene`` are C1 and only meaningful when
    ``channels`` is non-empty.
    """

    name: str
    channels: tuple[str, ...]

    def reset(self, seed: int) -> None: ...
    def step(self, action: Any | None = None) -> None: ...
    def observe(self, channel: str) -> float | np.ndarray: ...
    def intervene(self, do: Intervention) -> None: ...
    def emit(self) -> Mapping[str, np.ndarray]: ...
    def emit_prov(self) -> dict[str, Any]: ...


@dataclass(slots=True)
class ContractModel:
    """C0/C2 adapter wrapping an ``abm_models`` model (``run(*, seed) -> dict``).

    Exposes the contract surface for the capabilities the wrapped model actually
    has. ``run(seed)`` becomes ``reset(seed)`` + ``emit()``; provenance is an L2
    sidecar dict. ``observe``/``intervene`` raise unless ``channels`` is non-empty
    (no canonical model declares an *exposed* channel yet).
    """

    model: Any  # an abm_models.ABMModel (has .name and .run(*, seed))
    channels: tuple[str, ...] = ()
    config: Mapping[str, Any] = field(default_factory=dict)
    _seed: int | None = field(default=None, init=False)
    _result: dict[str, Any] | None = field(default=None, init=False)

    @property
    def name(self) -> str:
        return str(getattr(self.model, "name", type(self.model).__name__))

    def reset(self, seed: int) -> None:
        self._seed = int(seed)
        self._result = self.model.run(seed=int(seed))

    def emit(self) -> Mapping[str, np.ndarray]:
        if self._result is None:
            raise ContractViolation("emit() before reset(): call reset(seed) first")
        return {
            k: np.asarray(v)
            for k, v in self._result.items()
            if isinstance(v, (np.ndarray, list))
        }

    def observe(self, channel: str) -> float | np.ndarray:  # pragma: no cover - C1 guard
        raise ContractViolation(
            f"{self.name} declares no exposed channels; observe() is C1 (not satisfied)"
        )

    def intervene(self, do: Intervention) -> None:  # pragma: no cover - C1 guard
        if not self.channels:
            raise ContractViolation(
                f"{self.name} has channels=(); intervene() requires a declared channel"
            )
        raise ContractViolation("C1 intervene() not yet wired for canonical models")

    def emit_prov(self) -> dict[str, Any]:
        """Minimal L2-style provenance sidecar (model_contract_v1 §5)."""
        if self._result is None or self._seed is None:
            raise ContractViolation("emit_prov() before reset()")
        cfg = dict(self.config)
        config_hash = hashlib.sha256(repr(sorted(cfg.items())).encode()).hexdigest()
        digest = _digest_result(self._result)
        return {
            "uuid": str(uuid.uuid4()),
            "model": self.name,
            "config_hash": config_hash,
            "config": cfg,
            "seed": self._seed,
            "output_sha256": digest,
            "reach_claim": "reported",
        }


def _digest_result(result: Mapping[str, Any]) -> str:
    """Stable sha256 over the numeric arrays in a result dict (order-independent)."""
    h = hashlib.sha256()
    for key in sorted(result):
        val = result[key]
        if isinstance(val, (np.ndarray, list)):
            arr = np.ascontiguousarray(np.asarray(val, dtype=np.float64))
            h.update(key.encode())
            h.update(np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0).tobytes())
    return h.hexdigest()


def detect_conformance(cm: ContractModel, *, prov_ok: bool, determinism_ok: bool) -> ConformanceLevel:
    """Highest conformance level a wrapped model actually satisfies.

    C0 requires deterministic emit; C2 additionally requires a provenance sidecar;
    C1 requires a non-empty *exposed* channel surface (no canonical model has one
    yet, so C1 is intentionally unreachable here).
    """
    if not determinism_ok:
        raise ContractViolation(f"{cm.name} is non-deterministic: not even C0")
    level = ConformanceLevel.C0
    # C1 is gated on an exposed channel surface — not declared channels alone.
    # Canonical run(seed) models never expose one, so we do not promote to C1.
    if prov_ok:
        level = max(level, ConformanceLevel.C2)
    return level


def check_determinism(model: Any, *, seed: int = 12345) -> bool:
    """Same (model, seed) → bit-identical numeric output (model_contract_v1 §6.2)."""
    a = ContractModel(model)
    b = ContractModel(model)
    a.reset(seed)
    b.reset(seed)
    return _digest_result(a._result or {}) == _digest_result(b._result or {})
