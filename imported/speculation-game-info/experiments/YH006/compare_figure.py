"""YH006 比較図生成 — 2×2 (world × wealth) layout.

3 つの figure を生成:

  1. yh006_comparison_2x2.png   (Option A): 2×2 grid + C1 side
       面接スライド用、2 軸 (world, wealth) の独立効果が一目で読める
  2. yh006_comparison_5col.png  (Option B): 5 列横並び
       従来 4-column layout の素直な拡張
  3. yh006_appendix_N_scaling.png: 旧 N=1000 C0 ref vs N=100 C0u
       finite-size 効果の補遺、本論 2×2 から分離

データ schema:
  - raw (pkl): C1/C2/C3 の `{cond}_result.pkl` (LOB 側、PAMS 経由) +
    c0u/c0p の `{cond}_result.pkl` (aggregate 側、aggregate_sim 経由)
  - metrics-only (JSON): 旧 YH005_1 の N=1000 reference
    (`load_c0_reference_1000()`)

panel 関数は raw/metrics の dispatch を内部で処理。pkl 不在時は
"missing" placeholder を表示し他 condition の描画を妨げない。

SPEC §9: 共通 analysis/ から stylized facts を import し、本ファイルで
独自の解析関数を新規実装しない。

Run:
  cd experiments/YH006
  python compare_figure.py
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "YH005"))
sys.path.insert(0, str(HERE))

from load_c0 import (  # noqa: E402
    load_c0_reference_1000,
    load_c0p,
    load_c0u,
)


# ---------------------------------------------------------------------------
# Conditions, metrics, layouts (構造化、ハードコードリスト不使用)
# ---------------------------------------------------------------------------

CONDITIONS: Dict[str, Dict[str, Any]] = {
    "c0u": {
        "label": "C0u\nagg × uniform",
        "world": "agg", "wealth": "uni", "kind": "main",
        "pkl": "c0u_result.pkl", "json": "c0u_metrics.json",
    },
    "c0p": {
        "label": "C0p\nagg × Pareto",
        "world": "agg", "wealth": "par", "kind": "main",
        "pkl": "c0p_result.pkl", "json": "c0p_metrics.json",
    },
    "c1": {
        "label": "C1\nLOB FCN null",
        "world": "lob", "wealth": "—", "kind": "null",
        "pkl": "C1_result.pkl", "json": None,
    },
    "c2": {
        "label": "C2\nLOB × uniform",
        "world": "lob", "wealth": "uni", "kind": "main",
        "pkl": "C2_result.pkl", "json": None,
    },
    "c3": {
        "label": "C3\nLOB × Pareto",
        "world": "lob", "wealth": "par", "kind": "main",
        "pkl": "C3_result.pkl", "json": None,
    },
    "c0_ref_1000": {
        "label": "C0 ref\n(N=1000, agg × uni)",
        "world": "agg", "wealth": "uni", "kind": "reference",
        "pkl": None, "json": "__yh005_1__",  # special: phase1_metrics.json
    },
}


def _load_one(name: str, outputs_dir: Path) -> Tuple[Optional[str], Optional[Any]]:
    """Return (kind, data) or (None, None) if not found.

    kind ∈ {"raw", "metrics"}.
    """
    spec = CONDITIONS[name]
    pkl_name = spec.get("pkl")
    if pkl_name:
        p = outputs_dir / pkl_name
        if p.exists():
            with open(p, "rb") as f:
                return "raw", pickle.load(f)
    json_name = spec.get("json")
    if json_name == "__yh005_1__":
        try:
            return "metrics", load_c0_reference_1000()
        except FileNotFoundError:
            return None, None
    if json_name:
        p = outputs_dir / json_name
        if p.exists():
            with open(p) as f:
                return "metrics", json.load(f)
    return None, None


def _load_all(outputs_dir: Path) -> Dict[str, Tuple[Optional[str], Optional[Any]]]:
    return {name: _load_one(name, outputs_dir) for name in CONDITIONS}


# ---------------------------------------------------------------------------
# Panel functions — kind ('raw' | 'metrics') を内部で dispatch
# ---------------------------------------------------------------------------

def _missing(ax: plt.Axes, msg: str = "data missing") -> None:
    ax.text(0.5, 0.5, msg, ha="center", va="center",
            transform=ax.transAxes, fontsize=8, color="#888")
    ax.set_xticks([]); ax.set_yticks([])


def _panel_wealth(ax: plt.Axes, kind: Optional[str], data: Any) -> Optional[Dict]:
    if data is None:
        _missing(ax); return None
    if kind == "metrics":
        w = data["wealth"]
        alpha = w["alpha_hill_xmin_p90"]
        xmin = w["xmin_p90"]
        n_tail = w["n_tail"]
        n = w["num_agents"]
        max_w = w.get("max_wealth", xmin * 3)
        x_line = np.logspace(np.log10(max(xmin, 1)), np.log10(max(max_w, xmin * 1.1)), 50)
        y_line = (n_tail / n) * (x_line / max(xmin, 1)) ** (-alpha)
        ax.loglog(x_line, y_line, "r--", linewidth=1.2,
                  label=f"α={alpha:.2f}\nmedian={w['median_wealth']:.0f}\nmax={w['max_wealth']:.0f}")
        ax.legend(loc="upper right", fontsize=7)
        ax.set_xlabel("wealth", fontsize=8)
        ax.set_ylabel("CCDF", fontsize=8)
        return {"alpha": alpha, "median": w["median_wealth"], "max": w["max_wealth"]}
    # raw: ndarray を直接プロット
    arr = np.asarray(data["final_wealth"], dtype=np.float64)
    pos = arr[arr > 0]
    if pos.size < 2:
        _missing(ax, f"no positive wealth\n(min={arr.min():.0f})")
        return {"alpha": float("nan"), "num_positive": int(pos.size)}
    sorted_w = np.sort(pos)
    n = sorted_w.size
    ccdf = 1.0 - np.arange(n) / n
    ax.loglog(sorted_w, ccdf, marker=".", linestyle="none", markersize=2.5)
    xmin = float(np.percentile(pos, 90))
    tail = pos[pos >= xmin]
    alpha = float("nan")
    if tail.size >= 2 and xmin > 0:
        log_ratio = np.log(tail / xmin).mean()
        if log_ratio > 0:
            alpha = 1.0 / log_ratio
            x_line = np.logspace(np.log10(xmin), np.log10(sorted_w.max()), 50)
            y_line = (tail.size / n) * (x_line / xmin) ** (-alpha)
            ax.loglog(x_line, y_line, "r--", linewidth=1.0, label=f"α={alpha:.2f}")
            ax.legend(loc="upper right", fontsize=7)
    ax.set_xlabel("wealth", fontsize=8)
    ax.set_ylabel("CCDF", fontsize=8)
    return {
        "alpha": float(alpha),
        "median": float(np.median(pos)),
        "max": float(pos.max()),
        "num_positive": int(n),
    }


def _panel_horizon(ax: plt.Axes, kind: Optional[str], data: Any) -> Optional[Dict]:
    if data is None:
        _missing(ax); return None
    if kind == "metrics":
        h = data["horizon"]
        ax.text(0.5, 0.6,
                f"K={h['num_round_trips']:,}\n"
                f"median={h['median_horizon']:.1f}\n"
                f"mean={h['mean_horizon']:.2f}\n"
                f"max={h['max_horizon']}",
                ha="center", va="center", transform=ax.transAxes, fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        return h
    rt = data["round_trips"]
    if rt["open_t"].size == 0:
        _missing(ax, "no round-trips"); return {"num_round_trips": 0}
    horizon = (rt["close_t"] - rt["open_t"]).astype(np.int64)
    horizon = horizon[horizon > 0]
    if horizon.size == 0:
        _missing(ax, "all horizon ≤ 0"); return {"num_round_trips": 0}
    h_min = max(1, int(horizon.min())); h_max = int(horizon.max())
    bins = np.array([h_min, h_min + 1]) if h_max <= h_min else \
        np.logspace(np.log10(h_min), np.log10(h_max + 1), 30)
    counts, edges = np.histogram(horizon, bins=bins)
    centers = 0.5 * (edges[:-1] + edges[1:])
    nz = counts > 0
    ax.loglog(centers[nz], counts[nz], marker="o", linestyle="-", markersize=3)
    ax.set_xlabel("horizon (steps)", fontsize=8)
    ax.set_ylabel("count", fontsize=8)
    return {
        "num_round_trips": int(horizon.size),
        "median_horizon": float(np.median(horizon)),
        "mean_horizon": float(horizon.mean()),
        "max_horizon": int(horizon.max()),
    }


def _panel_deltaG(ax: plt.Axes, kind: Optional[str], data: Any) -> Optional[Dict]:
    if data is None:
        _missing(ax); return None
    if kind == "metrics":
        d = data["deltaG_vs_horizon"]
        ax.text(0.5, 0.6,
                f"corr(|ΔG|, h) = {d['corr_horizon_abs_dG']:.3f}\n"
                f"mean|ΔG|={d['mean_abs_dG']:.2f}\n"
                f"frac+={d['frac_positive_dG']:.3f}\n"
                f"frac−={d['frac_negative_dG']:.3f}",
                ha="center", va="center", transform=ax.transAxes, fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        return d
    rt = data["round_trips"]
    if rt["open_t"].size == 0:
        _missing(ax, "no round-trips"); return {"num_round_trips": 0}
    horizon = (rt["close_t"] - rt["open_t"]).astype(np.int64)
    dG = rt["delta_G"].astype(np.float64)
    mask = horizon > 0
    horizon = horizon[mask]; dG = dG[mask]
    if horizon.size == 0:
        _missing(ax, "no round-trips"); return {"num_round_trips": 0}
    ax.hexbin(horizon, dG, gridsize=30, bins="log", cmap="viridis", mincnt=1)
    ax.axhline(0, color="red", linewidth=0.6, alpha=0.6)
    ax.set_xlabel("horizon", fontsize=8)
    ax.set_ylabel("ΔG", fontsize=8)
    abs_dG = np.abs(dG)
    corr = float(np.corrcoef(horizon.astype(np.float64), abs_dG)[0, 1]) if horizon.size > 1 else float("nan")
    ax.text(0.97, 0.03, f"corr={corr:.3f}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8,
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=1.5))
    return {
        "num_round_trips": int(horizon.size),
        "corr_horizon_abs_dG": corr,
        "mean_abs_dG": float(abs_dG.mean()),
        "frac_positive_dG": float((dG > 0).mean()),
        "frac_negative_dG": float((dG < 0).mean()),
    }


def _panel_hold(ax: plt.Axes, kind: Optional[str], data: Any) -> Optional[Dict]:
    if data is None:
        _missing(ax); return None
    if kind == "metrics":
        h = data["hold_ratio"]
        ratios = {k: float(h.get(k, 0.0)) for k in ("idle", "active_hold", "passive_hold", "buy", "sell")}
    else:
        nb = np.asarray(data["num_buy"], dtype=np.float64)
        ns = np.asarray(data["num_sell"], dtype=np.float64)
        na = np.asarray(data["num_active_hold"], dtype=np.float64)
        np_ = np.asarray(data["num_passive_hold"], dtype=np.float64)
        N_est = int((nb + ns + na + np_).max()) if nb.size else 0
        if N_est == 0:
            _missing(ax, "no SG activity"); return {"N_est": 0}
        ni = np.clip(N_est - (nb + ns + na + np_), 0.0, None)
        ratios = {
            "idle": float(ni.mean() / N_est),
            "active_hold": float(na.mean() / N_est),
            "passive_hold": float(np_.mean() / N_est),
            "buy": float(nb.mean() / N_est),
            "sell": float(ns.mean() / N_est),
        }
    labels = ["idle", "active_hold", "passive_hold", "buy", "sell"]
    colors = ["#cccccc", "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    bottom = 0.0
    for lab, col in zip(labels, colors):
        v = ratios[lab]
        ax.bar(0, v, bottom=bottom, color=col, width=0.5, edgecolor="white", linewidth=0.3)
        bottom += v
    ax.set_xticks([])
    ax.set_ylim(0, 1)
    ax.set_ylabel("share", fontsize=8)
    ax.text(1.05, 0.5,
            "\n".join(f"{k[:7]}={v:.2f}" for k, v in ratios.items()),
            transform=ax.transAxes, fontsize=6.5, va="center")
    return ratios


def _panel_order_ts(ax: plt.Axes, kind: Optional[str], data: Any) -> Optional[Dict]:
    if data is None:
        _missing(ax); return None
    if kind == "metrics":
        o = data["order_size"]
        ax.text(0.5, 0.6,
                f"mean(small)={o['mean_small']:.0f}\n"
                f"mean(medium)={o['mean_medium']:.2f}\n"
                f"mean(large)={o['mean_large']:.2f}\n"
                f"peak(large)={o['peak_large']}",
                ha="center", va="center", transform=ax.transAxes, fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        return o
    sz = data["num_orders_by_size"]
    T = sz.shape[0]
    x = np.arange(T)
    ax.plot(x, sz[:, 0], color="#1f77b4", linewidth=0.4, label="small")
    ax.plot(x, sz[:, 1], color="#ff7f0e", linewidth=0.4, label="medium")
    ax.plot(x, sz[:, 2], color="#d62728", linewidth=0.6, label="large")
    ax.legend(fontsize=6.5, loc="upper right")
    ax.set_xlabel("step", fontsize=8)
    ax.set_ylabel("# orders", fontsize=8)
    return {
        "mean_small": float(sz[:, 0].mean()),
        "mean_medium": float(sz[:, 1].mean()),
        "mean_large": float(sz[:, 2].mean()),
        "peak_small": int(sz[:, 0].max()),
        "peak_medium": int(sz[:, 1].max()),
        "peak_large": int(sz[:, 2].max()),
    }


METRICS = [
    {"key": "wealth",   "label": "Fig A: wealth CCDF",       "fn": _panel_wealth},
    {"key": "horizon",  "label": "Fig B: round-trip horizon", "fn": _panel_horizon},
    {"key": "deltaG",   "label": "Fig C: |ΔG| vs horizon",   "fn": _panel_deltaG},
    {"key": "hold",     "label": "Fig D: hold ratio",         "fn": _panel_hold},
    {"key": "order_ts", "label": "Fig E: order size ts",      "fn": _panel_order_ts},
]


# ---------------------------------------------------------------------------
# Figure 1: 2×2 + C1 side (Option A)
# ---------------------------------------------------------------------------

def render_2x2(loaded: Dict, out_path: Path) -> Dict[str, Dict]:
    """各 metric を「2×2 + C1 side」mini-grid で描画、5 metric 縦に積む。

    レイアウト (per metric block, 2 rows × 3 cols):
        [C0u  ] [C0p  ] [    ]
        [C2   ] [C3   ] [ C1 ] <- C1 spans both inner rows
    """
    fig = plt.figure(figsize=(13, 26))
    outer = fig.add_gridspec(len(METRICS), 1, hspace=0.55)
    out_metrics: Dict[str, Dict] = {name: {} for name in CONDITIONS}

    for mi, metric in enumerate(METRICS):
        inner = outer[mi].subgridspec(2, 3, width_ratios=[1, 1, 0.7],
                                      hspace=0.3, wspace=0.35)
        ax_c0u = fig.add_subplot(inner[0, 0])
        ax_c0p = fig.add_subplot(inner[0, 1])
        ax_c2 = fig.add_subplot(inner[1, 0])
        ax_c3 = fig.add_subplot(inner[1, 1])
        ax_c1 = fig.add_subplot(inner[:, 2])
        slots = [
            ("c0u", ax_c0u), ("c0p", ax_c0p),
            ("c2",  ax_c2),  ("c3",  ax_c3),
            ("c1",  ax_c1),
        ]
        for name, ax in slots:
            kind, data = loaded[name]
            try:
                m = metric["fn"](ax, kind, data)
            except Exception as e:
                _missing(ax, f"err: {e}")
                m = {"error": str(e)}
            if m is not None:
                out_metrics[name][metric["label"]] = m

        # cell labels (top row only) and row label (left col only)
        ax_c0u.set_title("C0u  agg × uniform", fontsize=9, color="#0a4")
        ax_c0p.set_title("C0p  agg × Pareto", fontsize=9, color="#0a4")
        ax_c2.set_title("C2  LOB × uniform", fontsize=9, color="#a40")
        ax_c3.set_title("C3  LOB × Pareto", fontsize=9, color="#a40")
        ax_c1.set_title("C1  LOB null (FCN only)", fontsize=9, color="#888")

        # 各 metric block の左端に大きい label
        ax_c0u.text(-0.35, 1.20, metric["label"], transform=ax_c0u.transAxes,
                    fontsize=12, fontweight="bold", color="#222",
                    ha="left", va="bottom")

    fig.suptitle(
        "YH006 Phase 1 Lite — 2×2 (world × wealth) + null (C1)\n"
        "agg = aggregate-demand (YH005-style)   /   LOB = PAMS limit-order book   /   N=100, T=50000, seed=777",
        fontsize=12, y=0.995,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_metrics


# ---------------------------------------------------------------------------
# Figure 2: 5 列横並び (Option B)
# ---------------------------------------------------------------------------

def render_5col(loaded: Dict, out_path: Path) -> Dict[str, Dict]:
    order = ["c0u", "c0p", "c1", "c2", "c3"]
    fig, axes = plt.subplots(len(METRICS), len(order), figsize=(20, 22))
    out_metrics: Dict[str, Dict] = {name: {} for name in CONDITIONS}

    for mi, metric in enumerate(METRICS):
        for ci, name in enumerate(order):
            ax = axes[mi, ci]
            kind, data = loaded[name]
            try:
                m = metric["fn"](ax, kind, data)
            except Exception as e:
                _missing(ax, f"err: {e}")
                m = {"error": str(e)}
            if m is not None:
                out_metrics[name][metric["label"]] = m
            if mi == 0:
                color = ("#0a4" if CONDITIONS[name]["world"] == "agg"
                        else "#888" if CONDITIONS[name]["kind"] == "null"
                        else "#a40")
                ax.set_title(CONDITIONS[name]["label"], fontsize=10, color=color)
            if ci == 0:
                ax.set_ylabel(metric["label"] + "\n" + (ax.get_ylabel() or ""),
                              fontsize=9)

    fig.suptitle(
        "YH006 Phase 1 Lite — 5 conditions × 5 metrics (5col layout)\n"
        "[agg×uni, agg×Par, LOB null, LOB×uni, LOB×Par]   N=100, T=50000, seed=777",
        fontsize=12,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_metrics


# ---------------------------------------------------------------------------
# Figure 3: N scaling appendix (旧 N=1000 C0 ref vs N=100 C0u, both uniform)
# ---------------------------------------------------------------------------

def render_appendix_n_scaling(loaded: Dict, out_path: Path) -> Dict[str, Dict]:
    """N=1000 C0 ref (uniform) vs N=100 C0u (uniform) を 5 metric 並列比較.

    SPEC: appendix figure として本論 2×2 から分離。N effect を isolate する
    ため両方 uniform で揃える (Pareto を入れると N と wealth が交絡)。
    """
    order = ["c0_ref_1000", "c0u"]
    fig, axes = plt.subplots(len(METRICS), len(order), figsize=(10, 22))
    out_metrics: Dict[str, Dict] = {name: {} for name in CONDITIONS}

    for mi, metric in enumerate(METRICS):
        for ci, name in enumerate(order):
            ax = axes[mi, ci]
            kind, data = loaded[name]
            try:
                m = metric["fn"](ax, kind, data)
            except Exception as e:
                _missing(ax, f"err: {e}")
                m = {"error": str(e)}
            if m is not None:
                out_metrics[name][metric["label"]] = m
            if mi == 0:
                title = ("旧 C0 ref (N=1000, agg × uniform)" if name == "c0_ref_1000"
                         else "C0u (N=100, agg × uniform)")
                ax.set_title(title, fontsize=10)
            if ci == 0:
                ax.set_ylabel(metric["label"] + "\n" + (ax.get_ylabel() or ""),
                              fontsize=9)

    fig.suptitle(
        "YH006 Appendix — N scaling reference (旧 C0 N=1000 vs C0u N=100, 同 uniform init)\n"
        "本論 2×2 から分離。hold ratio は N 不変、α_hill は N 依存大。",
        fontsize=11,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_metrics


# ---------------------------------------------------------------------------
# JSON util & entry
# ---------------------------------------------------------------------------

def _clean_json(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _clean_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean_json(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        v = float(o)
        return v if np.isfinite(v) else None
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def main() -> None:
    outputs_dir = HERE / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    loaded = _load_all(outputs_dir)

    print("[compare] loaded:")
    for name, (kind, data) in loaded.items():
        status = "MISSING" if data is None else str(kind)
        print(f"   {name:14s}: {status}")

    out_2x2 = outputs_dir / "yh006_comparison_2x2.png"
    out_5col = outputs_dir / "yh006_comparison_5col.png"
    out_app = outputs_dir / "yh006_appendix_N_scaling.png"

    m_2x2 = render_2x2(loaded, out_2x2)
    print(f"[compare] saved: {out_2x2}")
    m_5col = render_5col(loaded, out_5col)
    print(f"[compare] saved: {out_5col}")
    m_app = render_appendix_n_scaling(loaded, out_app)
    print(f"[compare] saved: {out_app}")

    # 統合 metrics JSON (3 figure 由来の集合体、name → metric → values)
    out_json = outputs_dir / "yh006_metrics.json"
    aggregated = {
        "render_2x2": m_2x2,
        "render_5col": m_5col,
        "render_appendix_N_scaling": m_app,
    }
    with open(out_json, "w") as f:
        json.dump(_clean_json(aggregated), f, indent=2, default=str)
    print(f"[compare] saved: {out_json}")


if __name__ == "__main__":
    main()
