"""設計マップ — 条件セルの集計・比較・チャネル帰属・予算 ledger（specs/002 US2/US3）。

- DesignMapPoint: 地図の 1 点（条件 × セル params × (抽出, markup)±SE × 認定/収束/退出）。
- compare_conditions(): 同一セル・同一 seed 群で {連続, batch×N} × {committed, revisable}
  を回し、markup 差（seed ペア差の SE）と分類 {促進/抑制/無影響}、二力の帰属
  （Δ_total=batch効果, Δ_GP=revisable 世界の batch 効果, Δ_pred=Δ_total−Δ_GP）を出す。
- BudgetLedger: 学習期数の tier 別累計。上限超過の run は起動拒否し、拒否も記録する
  （research D-B9。総 3×10⁹ 期、tier 各 1×10⁹）。
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import numpy as np

from .learnconfig import LearnConfig
from .qlearn import train, _MEASURE_BURN_IN
from .verdict import (CellMeasurement, CollusionVerdict, IRResult, certify,
                      impulse_response, measure)

# US2/US3 の標準条件集合（D-B9 coarse の条件次元）
CONDITIONS: tuple[tuple[str, int, str], ...] = (
    ("continuous", 1, "committed"),
    ("batch", 5, "committed"),
    ("batch", 20, "committed"),
    ("continuous", 1, "revisable"),
    ("batch", 5, "revisable"),
    ("batch", 20, "revisable"),
)


def cell_id(cfg: LearnConfig) -> str:
    mech = "cont" if cfg.mechanism == "continuous" else f"batch{cfg.batch_interval}"
    return (f"{mech}-{cfg.staleness}-lam{cfg.lambda_jump:g}-J{cfg.jump_size:g}"
            f"-fee{cfg.fee:g}-mem{cfg.memory}-n{cfg.n_mm}-{cfg.algo}")


def config_hash(cfg: LearnConfig) -> str:
    """seed を除く全 config フィールドの hash。

    cell_id は表示用の短縮キーで noise_rate/lr/eps_beta/gamma/tie_rule 等が乗らない。
    結果行の同一性・resume の照合はこの hash で行う（override や robustness 変種が
    同一 cell_id を持つことによる衝突 bug class の遮断）。
    """
    d = {k: v for k, v in asdict(cfg).items() if k != "seed"}
    raw = repr(sorted(d.items()))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class DesignMapPoint:
    cell: str
    mechanism: str
    batch_interval: int
    staleness: str
    lambda_jump: float
    jump_size: float
    fee: float
    memory: int
    n_mm: int
    algo: str
    noise_rate: float
    lr: float
    eps_beta: float
    gamma: float
    tie_rule: str
    config_hash: str
    markup_mean: float
    markup_se: float
    extraction_mean: float
    extraction_se: float
    certified: bool
    converged_frac: float
    exited_frac: float
    n_seeds: int
    periods_total: int
    runtime_sec: float


class BudgetExceeded(RuntimeError):
    pass


class BudgetLedger:
    """学習期数の予算台帳（JSON 永続）。charge は run 起動**前**に呼び、超過なら拒否。

    並行性と監査可能性（2026-06-11 incident 対応、findings/0002b 参照）:
    - 全ての更新は lock file + read-modify-write で直列化（lost update の遮断）。
    - **台帳の一次記録は追記専用 journal**（`<path>.journal.jsonl`、1 行 1 イベント）。
      snapshot（JSON の spent）は journal の fold のキャッシュに格下げ——上書きで
      壊れても `rebuild_spent()` で再導出でき、`verify()` で一致を機械検査できる。
      スナップショット上書きは台帳ではない——台帳とは追記ログのことである。
    """

    DEFAULT_CAPS = {"coarse": 1_000_000_000, "dense": 1_000_000_000,
                    "robustness": 1_000_000_000}

    def __init__(self, path: str | Path, caps: dict[str, int] | None = None) -> None:
        self.path = Path(path)
        self.caps = dict(self.DEFAULT_CAPS if caps is None else caps)
        self._reload()

    def _reload(self) -> None:
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.data = {"spent": {t: 0 for t in self.caps}, "refusals": []}
        for t in self.caps:
            self.data["spent"].setdefault(t, 0)

    @contextmanager
    def _locked(self):
        """lock file を握って最新状態を再読込してから更新する（プロセス間直列化）。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(".lock")
        deadline = time.monotonic() + 30.0
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"ledger lock timeout: {lock}（stale なら手で消す）")
                time.sleep(0.05)
        try:
            self._reload()
            yield
        finally:
            os.close(fd)
            os.unlink(lock)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1))

    @property
    def _journal_path(self) -> Path:
        return self.path.with_suffix(".journal.jsonl")

    def _journal_append(self, event: dict) -> None:
        with open(self._journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def baseline(self, note: str) -> None:
        """journal の起点 event。移行時に現 snapshot の spent を ground truth として刻む。"""
        with self._locked():
            self._journal_append({"op": "baseline",
                                  "spent": {k: int(v) for k, v in self.data["spent"].items()},
                                  "note": note})

    def rebuild_spent(self) -> dict[str, int]:
        """journal の fold から spent を導出（journal が台帳、snapshot はキャッシュ）。"""
        spent = {t: 0 for t in self.caps}
        if not self._journal_path.exists():
            return {k: int(v) for k, v in self.data["spent"].items()}  # journal 導入前
        for line in self._journal_path.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            if e["op"] == "baseline":
                spent.update({k: int(v) for k, v in e["spent"].items()})
            elif e["op"] == "charge":
                spent[e["tier"]] += int(e["periods"])
            elif e["op"] in ("refund", "reconcile"):
                spent[e["tier"]] = max(0, spent[e["tier"]] - int(e["periods"]))
        return spent

    def verify(self) -> bool:
        """snapshot(spent) と journal fold の一致を機械検査。"""
        return {k: int(v) for k, v in self.data["spent"].items()} == self.rebuild_spent()

    def charge(self, tier: str, periods: int) -> None:
        with self._locked():
            spent = self.data["spent"][tier]
            if spent + periods > self.caps[tier]:
                self.data["refusals"].append(
                    {"tier": tier, "requested": int(periods),
                     "spent_at_refusal": int(spent), "cap": int(self.caps[tier])})
                self._save()
                self._journal_append({"op": "refusal", "tier": tier,
                                      "periods": int(periods), "spent": int(spent)})
                raise BudgetExceeded(
                    f"tier '{tier}': {spent} + {periods} > cap {self.caps[tier]} "
                    f"(D-B9。拒否は ledger に記録済み)")
            self.data["spent"][tier] = spent + int(periods)
            self._save()
            self._journal_append({"op": "charge", "tier": tier, "periods": int(periods)})

    def refund(self, tier: str, periods: int) -> None:
        """予約（t_max ベース）と実消費の差を返金。"""
        with self._locked():
            self.data["spent"][tier] = max(0, self.data["spent"][tier] - int(periods))
            self._save()
            self._journal_append({"op": "refund", "tier": tier, "periods": int(periods)})

    def reconcile(self, tier: str, periods: int, note: str) -> None:
        """成果物として保持されなかった run の charge を、監査 entry 付きで返金する。

        黙った refund と違い `reconciliations` に {tier, periods, note} を恒久記録する
        （D-B9「数値を黙って変えない」）。適用前提: D-B12 の決定論により、同一の
        事前登録 grid の再実行は bit 同一の再計算であって追加サンプリングではない。
        保持成果物（CSV）が背書きする期数は返金対象にしない。
        """
        with self._locked():
            self.data.setdefault("reconciliations", []).append(
                {"tier": tier, "periods": int(periods), "note": note})
            self.data["spent"][tier] = max(0, self.data["spent"][tier] - int(periods))
            self._save()
            self._journal_append({"op": "reconcile", "tier": tier,
                                  "periods": int(periods), "note": note})

    def audit(self, subject: str, note: str) -> None:
        """監査メモを ledger に恒久記録する（lock 下で消えない）。"""
        with self._locked():
            self.data.setdefault("audits", []).append(
                {"subject": subject, "note": note})
            self._save()
            self._journal_append({"op": "audit", "subject": subject, "note": note})

    @property
    def total_spent(self) -> int:
        return sum(self.data["spent"].values())


def _planned_periods(cfg: LearnConfig) -> int:
    return cfg.t_max + _MEASURE_BURN_IN + cfg.measure_periods


def aggregate_cell(cfg: LearnConfig, cells: list[CellMeasurement],
                   irs: list[IRResult], periods_total: int,
                   runtime_sec: float) -> DesignMapPoint:
    """seed 群の測定を地図の 1 点に集計（逐次 run_cell と並列 runner が共有）。"""
    markups = np.array([m.markup for m in cells])
    extr = np.array([m.extraction_rate for m in cells])
    n = len(cells)
    se = (lambda a: float(a.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0)
    verdict = certify(cells, irs, cfg.markup_floor) if n > 1 else None
    return DesignMapPoint(
        cell=cell_id(cfg), mechanism=cfg.mechanism, batch_interval=cfg.batch_interval,
        staleness=cfg.staleness, lambda_jump=cfg.lambda_jump, jump_size=cfg.jump_size,
        fee=cfg.fee, memory=cfg.memory, n_mm=cfg.n_mm, algo=cfg.algo,
        noise_rate=cfg.noise_rate, lr=cfg.lr,
        eps_beta=cfg.eps_beta, gamma=cfg.gamma, tie_rule=cfg.tie_rule,
        config_hash=config_hash(cfg),
        markup_mean=float(markups.mean()), markup_se=se(markups),
        extraction_mean=float(extr.mean()), extraction_se=se(extr),
        certified=bool(verdict.certified) if verdict else False,
        converged_frac=float(np.mean([m.converged for m in cells])),
        exited_frac=float(np.mean([m.exited for m in cells])),
        n_seeds=n, periods_total=periods_total,
        runtime_sec=runtime_sec,
    )


def run_one_seed(cfg: LearnConfig, seed: int):
    """1 (セル, seed) の train→measure→IR（並列 worker の単位）。

    returns (CellMeasurement, IRResult, actual_periods, runtime_sec)
    """
    t0 = time.perf_counter()
    c = cfg.replace(seed=seed)
    tr = train(c)
    actual = tr.periods_run + _MEASURE_BURN_IN + c.measure_periods
    m = measure(c, tr)
    ir = impulse_response(c, tr)
    return m, ir, actual, time.perf_counter() - t0


def run_cell(cfg: LearnConfig, seeds: list[int],
             ledger: BudgetLedger | None = None, tier: str = "coarse",
             ) -> tuple[DesignMapPoint, list[CellMeasurement], list[IRResult]]:
    """1 条件セルを複数 seed で回し、地図の 1 点に集計する（逐次版）。"""
    t0 = time.perf_counter()
    cells: list[CellMeasurement] = []
    irs: list[IRResult] = []
    periods_total = 0
    for s in seeds:
        planned = _planned_periods(cfg)
        if ledger is not None:
            ledger.charge(tier, planned)
        m, ir, actual, _ = run_one_seed(cfg, s)
        if ledger is not None:
            ledger.refund(tier, planned - actual)
        periods_total += actual
        cells.append(m)
        irs.append(ir)
    point = aggregate_cell(cfg, cells, irs, periods_total,
                           time.perf_counter() - t0)
    return point, cells, irs


def classify_modulation(diffs: np.ndarray) -> str:
    """markup 差（seed ペア差）の分類。促進: mean−2SE>0 / 抑制: mean+2SE<0 / 他: 無影響。"""
    d = np.asarray(diffs, dtype=float)
    if len(d) < 2:
        raise ValueError("classification needs >= 2 paired seeds")
    mean = float(d.mean())
    se = float(d.std(ddof=1) / math.sqrt(len(d)))
    if mean - 2 * se > 0:
        return "促進"
    if mean + 2 * se < 0:
        return "抑制"
    return "無影響"


def compare_conditions(base: LearnConfig, seeds: list[int],
                       conditions: tuple[tuple[str, int, str], ...] = CONDITIONS,
                       ledger: BudgetLedger | None = None, tier: str = "coarse",
                       ) -> dict:
    """同一セル・同一 seed 群・同一 grid で条件集合を比較（US2）。

    returns {
      "points": {cell_id: DesignMapPoint},
      "markups": {(mech, N, staleness): per-seed ndarray},
      "modulation": {(N, staleness): {"diff_mean","diff_se","class"}},   # vs 連続（同 staleness）
      "attribution": {N: {"delta_total","delta_gp","delta_pred", "se_total","se_gp"}},
    }
    """
    points: dict[str, DesignMapPoint] = {}
    markups: dict[tuple, np.ndarray] = {}
    for mech, N, stal in conditions:
        cfg = base.replace(mechanism=mech, batch_interval=N, staleness=stal)
        point, cells, _ = run_cell(cfg, seeds, ledger, tier)
        points[point.cell] = point
        markups[(mech, N, stal)] = np.array([m.markup for m in cells])

    modulation: dict[tuple, dict] = {}
    attribution: dict[int, dict] = {}
    for stal in ("committed", "revisable"):
        if ("continuous", 1, stal) not in markups:
            continue
        base_m = markups[("continuous", 1, stal)]
        for (mech, N, s), m in markups.items():
            if s != stal or mech != "batch":
                continue
            diffs = m - base_m                    # seed ペア差（同一 seed 同士）
            modulation[(N, stal)] = {
                "diff_mean": float(diffs.mean()),
                "diff_se": float(diffs.std(ddof=1) / math.sqrt(len(diffs))),
                "class": classify_modulation(diffs),
            }
    for (mech, N, stal), m in markups.items():
        if mech != "batch" or stal != "committed":
            continue
        if ("batch", N, "revisable") not in markups:
            continue
        d_total = m - markups[("continuous", 1, "committed")]
        d_gp = markups[("batch", N, "revisable")] - markups[("continuous", 1, "revisable")]
        d_pred = d_total - d_gp                  # predation = 総効果 − 監視チャネル（ablation 差分）
        k = math.sqrt(len(d_total))
        attribution[N] = {
            "delta_total": float(d_total.mean()),
            "se_total": float(d_total.std(ddof=1) / k),
            "delta_gp": float(d_gp.mean()),
            "se_gp": float(d_gp.std(ddof=1) / k),
            "delta_pred": float(d_pred.mean()),
            "se_pred": float(d_pred.std(ddof=1) / k),
        }
    return {"points": points, "markups": markups,
            "modulation": modulation, "attribution": attribution}


def coarse_grid(seeds_per_cell: int = 5) -> list[LearnConfig]:
    """D-B9 Tier-1 coarse の条件セル列（72 セル）。総予定期数は test で cap 以下を静的検査。

    (memory, n_mm) は表形式で実行可能な {(1,2),(1,3),(2,2)} のみ——(2,3) は状態数
    15⁶ ≈ 1.1×10⁷ で tabular 不能（D-B9 実装注記参照、関数近似の領分＝scope 外）。
    """
    cells = []
    for lam, J in ((5.0, 1.0), (15.0, 1.5)):
        for fee_mult in (0.0, 0.05):
            for mem, n in ((1, 2), (1, 3), (2, 2)):
                for mech, N, stal in CONDITIONS:
                    cells.append(LearnConfig(
                        dt=1e-2, lambda_jump=lam, jump_size=J, alpha=0.3,
                        noise_rate=1.0, fee=fee_mult * J, mechanism=mech,
                        batch_interval=N, staleness=stal, n_mm=n, memory=mem))
    return cells


def parse_cell_id(cell: str, base: LearnConfig | None = None) -> LearnConfig:
    """cell_id() の逆変換（--around / --headline の入力解釈）。"""
    base = LearnConfig() if base is None else base
    toks = cell.split("-")
    mech_tok, stal = toks[0], toks[1]
    if mech_tok == "cont":
        mech, N = "continuous", 1
    elif mech_tok.startswith("batch"):
        mech, N = "batch", int(mech_tok[len("batch"):])
    else:
        raise ValueError(f"unknown mechanism token: {mech_tok}")
    kv = {}
    for tok in toks[2:-1]:
        for key, cast in (("lam", float), ("J", float), ("fee", float),
                          ("mem", int), ("n", int)):
            if tok.startswith(key):
                kv[key] = cast(tok[len(key):])
                break
        else:
            raise ValueError(f"unknown cell token: {tok}")
    return base.replace(mechanism=mech, batch_interval=N, staleness=stal,
                        lambda_jump=kv["lam"], jump_size=kv["J"], fee=kv["fee"],
                        memory=kv["mem"], n_mm=kv["n"], algo=toks[-1])


def dense_neighbors(center: LearnConfig) -> list[LearnConfig]:
    """Tier-2: 指定セル近傍の局所密 grid（N × vol。それ以外は固定）。"""
    if center.mechanism == "batch":
        n_set = sorted({max(1, center.batch_interval // 2), center.batch_interval,
                        center.batch_interval * 2})
    else:
        n_set = [1]
    out = []
    for n_int in n_set:
        for lam_mult in (0.7, 1.0, 1.4):
            out.append(center.replace(batch_interval=n_int,
                                      lambda_jump=center.lambda_jump * lam_mult))
    return out


def density_spoke(center: LearnConfig) -> list[LearnConfig]:
    """Tier-2: 事象密度スポーク——認定が物理的に可能な regime の探索（finding 0002）。

    baseline 疎度（pn=ν·dt=0.01）では on-path の Q ギャップが報酬ノイズに埋まり、
    policy/cycle いずれの意味でも収束が成立しない（pilot 実測）。noise_rate を上げ
    （fill/期 を増やし）、lr を下げて（平均化を強めて）SNR を確保した世界で gate を
    動かす。(ν=30, lr=0.15) は lr の役割を分離する対照。
    """
    out = []
    for nr, lr in ((10.0, 0.02), (30.0, 0.02), (30.0, 0.15)):
        for mech, N, stal in CONDITIONS:
            out.append(center.replace(noise_rate=nr, lr=lr, mechanism=mech,
                                      batch_interval=N, staleness=stal))
    return out


def robustness_variants(center: LearnConfig,
                        headline_seeds: int = 20) -> list[tuple[LearnConfig, int]]:
    """Tier-3: headline 点の頑健性変種（D-B9）。returns [(cfg, n_seeds)]。

    追加 seed（同設定 ×20）/ SARSA（第2アルゴリズム）/ tie=rotate（D-B8 第2規則）/
    lr・eps_beta・gamma 振り。memory 閾値 sweep は認定通過が前提のため script でなく
    API（verdict.memory_threshold）から行う。
    """
    v: list[tuple[LearnConfig, int]] = [
        (center, headline_seeds),
        (center.replace(algo="sarsa"), headline_seeds),
        (center.replace(tie_rule="rotate"), 5),
        (center.replace(lr=center.lr * 0.5), 5),
        (center.replace(lr=center.lr * 2.0), 5),
        (center.replace(eps_beta=center.eps_beta * 0.5), 5),
        (center.replace(eps_beta=center.eps_beta * 2.0), 5),
        (center.replace(gamma=0.90), 5),
        (center.replace(gamma=0.99), 5),
    ]
    return v


def write_csv(points: list[DesignMapPoint], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(p) for p in points]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def append_csv(point: DesignMapPoint, path: str | Path) -> None:
    """1 点を追記する（crash 耐性: セル完了ごとに永続化、run 全完了を待たない）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    names = [f.name for f in fields(DesignMapPoint)]
    new = not path.exists()
    if not new:
        with open(path, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), None)
        if header != names:
            raise ValueError(
                f"{path} の既存 header が現 schema と不一致——古い CSV へは追記しない。"
                f"別の --out を指定するか退避すること")
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=names)
        if new:
            w.writeheader()
        w.writerow(asdict(point))


def done_keys(path: str | Path) -> tuple[str, set[str]]:
    """既存 out CSV の完了キー集合（resume の skip 照合）。

    returns (mode, keys)。mode = "config_hash"（新 schema、フル構成で照合——override や
    robustness 変種でも衝突しない）または "cell"（hash 列の無い旧 CSV への後方互換）。
    """
    path = Path(path)
    if not path.exists():
        return "config_hash", set()
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if rows and "config_hash" in rows[0]:
        return "config_hash", {r["config_hash"] for r in rows}
    return "cell", {r["cell"] for r in rows}
