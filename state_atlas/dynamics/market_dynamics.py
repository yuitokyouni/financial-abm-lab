"""
market_dynamics.py
==================
非平衡系（ランジュバン / McKean-Vlasov 平均場）に基づく市場力学リサーチエンジン。

設計思想（2軸構成）:
  (b) 生成側  : N体アンダーダンプ平均場ランジュバンを BAOAB 法で積分し、
                創発する密度 rho(x,t) をヒートマップとして可視化する。
  (a) 逆問題側 : 観測された1本の系列から V(x), D(x) を Kramers-Moyal 係数で
                逆推定する（= 市場と繋がる唯一の現実的キャリブレーション層）。

加えて: クリティカル・スローダウン（分岐前の分散・自己相関の上昇）を
        手元で「信じる前に検証する」ための診断器を同梱する。

すべて自前実装。ブラックボックスなし。numpy / scipy / matplotlib のみ。
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Callable
import matplotlib.pyplot as plt
from scipy.stats import kendalltau


# =============================================================================
# 1. ポテンシャル場（レジーム構造）
# =============================================================================
# ダブルウェル: V(x) = x^4/4 - c*x^2/2 - h*x
#   c > 0 : 二谷（強気/弱気の2レジーム）。谷は x = ±sqrt(c)、障壁高 = c^2/4
#   h     : 傾き（外場）。h を動かすと一方の谷が浅くなり、fold 分岐で他方へ転移
#           → 「クリティカル・スローダウン → レジームシフト」の教科書シナリオ

def potential(x: np.ndarray, c: float, h: float = 0.0) -> np.ndarray:
    return 0.25 * x**4 - 0.5 * c * x**2 - h * x


def grad_potential(x: np.ndarray, c: float, h: float = 0.0) -> np.ndarray:
    """V'(x) = x^3 - c*x - h"""
    return x**3 - c * x - h


# =============================================================================
# 2. 生成側 (b): N体アンダーダンプ平均場ランジュバン（BAOAB 積分）
# =============================================================================
# 連立SDE（単位質量・per-mass 表記）:
#   dx = v dt
#   dv = [ -V'(x) + kappa*(xbar - x) ] dt - gamma*v dt + sigma dW
#   xbar = (1/N) Σ x_j  （平均場 = ハーディング/群集心理）
#
# 注意: アンダーダンプ系に素朴な Euler-Maruyama は弱安定でバイアスが乗る。
#       Leimkuhler-Matthews の BAOAB スプリッティングを使う（MDの定番、有限dtで高精度）。
#       O ステップは Ornstein-Uhlenbeck の厳密解。有効温度 T = sigma^2/(2 gamma)。

@dataclass
class MeanFieldLangevin:
    N: int = 200            # 粒子数（市場参加者 / 価格クラスタ）
    gamma: float = 1.0      # 摩擦 = モメンタムの減衰率（小さいほど慣性が効く）
    sigma: float = 0.45     # ノイズ強度（ボラティリティ）
    kappa: float = 0.5      # ハーディング強度（同調圧力）
    dt: float = 0.01
    seed: int | None = 0

    def simulate(
        self,
        steps: int,
        c_fn: Callable[[float], float] | float = 1.0,
        h_fn: Callable[[float], float] | float = 0.0,
        x0: np.ndarray | None = None,
        v0: np.ndarray | None = None,
    ) -> dict:
        """
        c_fn, h_fn は定数でも t->値 の関数でもよい（時間依存でレジーム変形を駆動）。
        戻り値: X (steps+1, N), Vel (steps+1, N), t (steps+1,)
        """
        rng = np.random.default_rng(self.seed)
        cfun = c_fn if callable(c_fn) else (lambda t, _c=c_fn: _c)
        hfun = h_fn if callable(h_fn) else (lambda t, _h=h_fn: _h)

        x = (rng.standard_normal(self.N) if x0 is None else np.array(x0, float)).copy()
        v = (np.zeros(self.N) if v0 is None else np.array(v0, float)).copy()

        X = np.empty((steps + 1, self.N))
        Vel = np.empty((steps + 1, self.N))
        X[0], Vel[0] = x, v

        dt, g, s = self.dt, self.gamma, self.sigma
        c_o = np.exp(-g * dt)                       # OU 減衰係数
        c_n = np.sqrt((s**2 / (2 * g)) * (1 - c_o**2))  # OU ゆらぎ係数

        def force(xx, t):
            xbar = xx.mean()
            return -grad_potential(xx, cfun(t), hfun(t)) + self.kappa * (xbar - xx)

        t = 0.0
        for k in range(steps):
            f = force(x, t)
            v = v + 0.5 * dt * f          # B
            x = x + 0.5 * dt * v          # A
            v = c_o * v + c_n * rng.standard_normal(self.N)  # O (厳密)
            x = x + 0.5 * dt * v          # A
            t += dt
            f = force(x, t)
            v = v + 0.5 * dt * f          # B
            X[k + 1], Vel[k + 1] = x, v

        return {"X": X, "V": Vel, "t": np.arange(steps + 1) * dt}


def emergent_density(X: np.ndarray, bins: int = 120, x_range=(-3, 3)) -> dict:
    """各時刻で粒子位置をヒストグラム化 → 創発密度 rho(x,t)（McKean-Vlasov の経験版）。"""
    edges = np.linspace(*x_range, bins + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    rho = np.empty((X.shape[0], bins))
    for k in range(X.shape[0]):
        rho[k], _ = np.histogram(X[k], bins=edges, density=True)
    return {"rho": rho, "x": centers}


# =============================================================================
# 3. 逆問題側 (a): Kramers-Moyal によるドリフト/拡散の逆推定
# =============================================================================
# 観測系列 x_t（過減衰仮定）から条件付きモーメントで推定:
#   D1(x) = <(x_{t+1}-x_t)> / dt           | x_t=x   … ドリフト
#   D2(x) = <(x_{t+1}-x_t)^2> / (2 dt)      | x_t=x   … 拡散
# 過減衰 dx = -V'(x)dt + sqrt(2 D2) dW なら V'(x) = -D1(x)。
# → 実効ポテンシャル V(x) = -∫ D1 dx で「市場のポテンシャル地形」を復元。
#
# 重大な但し書き（実データ適用前に必ず読むこと）:
#   * 単一価格系列は非定常。τ→0 の極限は離散データでは存在しない（有限dtバイアス）。
#   * 過減衰仮定はモメンタムの強い相場で破綻する（本来はアンダーダンプ）。
#   * よってこれは「真の力学の推定」ではなく「定常近似下の実効地形」。過信禁物。

def estimate_drift_diffusion(series: np.ndarray, dt: float, bins: int = 40,
                             min_count: int = 20) -> dict:
    x = np.asarray(series, float)
    dx = np.diff(x)
    xc = x[:-1]
    edges = np.linspace(xc.min(), xc.max(), bins + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    idx = np.clip(np.digitize(xc, edges) - 1, 0, bins - 1)

    D1 = np.full(bins, np.nan)
    D2 = np.full(bins, np.nan)
    cnt = np.zeros(bins, int)
    for b in range(bins):
        m = idx == b
        cnt[b] = m.sum()
        if cnt[b] >= min_count:
            D1[b] = dx[m].mean() / dt
            D2[b] = 0.5 * (dx[m] ** 2).mean() / dt
    return {"x": centers, "D1": D1, "D2": D2, "count": cnt}


def reconstruct_potential(km: dict) -> dict:
    """V'(x) = -D1(x) を台形積分して実効ポテンシャル V(x) を復元。"""
    x, D1 = km["x"], km["D1"]
    valid = ~np.isnan(D1)
    xv, fv = x[valid], -D1[valid]   # V'(x) = -D1
    V = np.concatenate([[0.0], np.cumsum(0.5 * (fv[1:] + fv[:-1]) * np.diff(xv))])
    V -= V.min()
    return {"x": xv, "V": V}


# =============================================================================
# 4. クリティカル・スローダウン診断（先行サインを「信じる前に検証」する道具）
# =============================================================================
# 分岐に近づくと復元力が弱まり、揺らぎからの回復が遅くなる:
#   * 移動分散      が上昇
#   * lag-1 自己相関 (AR1) が 1 に近づく
# Kendall の tau でトレンドの有意性を見る。
# 注意: クリーンな合成系では効くが、実市場ではS/Nが悪く誤検知だらけ。これは「検証器」。

def rolling_ar1(series: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(series, float)
    out = np.full(len(x), np.nan)
    for i in range(window, len(x)):
        w = x[i - window:i]
        a, b = w[:-1] - w[:-1].mean(), w[1:] - w[1:].mean()
        denom = np.sqrt((a**2).sum() * (b**2).sum())
        if denom > 0:
            out[i] = (a * b).sum() / denom
    return out


def early_warning(series: np.ndarray, window: int = 250) -> dict:
    x = np.asarray(series, float)
    var = np.full(len(x), np.nan)
    for i in range(window, len(x)):
        var[i] = x[i - window:i].var()
    ar1 = rolling_ar1(x, window)
    t = np.arange(len(x))
    out = {"var": var, "ar1": ar1}
    for k in ("var", "ar1"):
        v = out[k]; m = ~np.isnan(v)
        tau, p = kendalltau(t[m], v[m]) if m.sum() > 3 else (np.nan, np.nan)
        out[f"{k}_tau"], out[f"{k}_p"] = tau, p
    return out


# =============================================================================
# 5. IBKR デモ接続フック（スタブ。本格実装は別ファイルに切り出す前提）
# =============================================================================
def ibkr_demo_signal(potential_state: dict) -> dict:
    """
    プレースホルダ: 復元ポテンシャル / 現在状態から建玉方向を返すだけの骨組み。
    実接続は ib_async (旧 ib_insync) を別モジュールで。ここは「形」だけ。
    例: 現在価格が左谷なら mean-reversion ロング、AR1 急騰なら手仕舞い、など。
    """
    raise NotImplementedError("デモ取引ロジックは次の反復で実装する（スタブ）。")


# =============================================================================
# 6. デモ実行: 図を生成して動作確認
# =============================================================================
def _demo(outdir: str = "."):
    import os
    rng = np.random.default_rng(42)

    # --- (A) 生成側: 二谷でのレジーム分極 + ノイズによる谷間遷移 ---
    model = MeanFieldLangevin(N=300, gamma=1.0, sigma=0.55, kappa=0.4, dt=0.01, seed=1)
    sim = model.simulate(steps=4000, c_fn=1.2)
    dens = emergent_density(sim["X"], bins=120)

    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    for i in range(0, model.N, 6):
        ax[0].plot(sim["t"], sim["X"][:, i], lw=0.3, alpha=0.3, color="steelblue")
    ax[0].plot(sim["t"], sim["X"].mean(1), color="crimson", lw=2, label="mean field (consensus)")
    ax[0].set(title="(b) N-body underdamped trajectories", xlabel="time", ylabel="state x")
    ax[0].legend()
    im = ax[1].imshow(dens["rho"].T, aspect="auto", origin="lower",
                      extent=[sim["t"][0], sim["t"][-1], dens["x"][0], dens["x"][-1]],
                      cmap="magma")
    ax[1].set(title="emergent density rho(x,t)", xlabel="time", ylabel="state x")
    fig.colorbar(im, ax=ax[1], label="density")
    fig.tight_layout(); fig.savefig(os.path.join(outdir, "fig1_generative.png"), dpi=130)

    # --- (B) 逆問題側: 既知ポテンシャルから合成 → KM で復元できるか検証 ---
    c_true = 1.5
    n = 200_000; dt = 0.01; D2_true = 0.5
    xs = np.empty(n); xs[0] = -np.sqrt(c_true)
    for k in range(n - 1):
        xs[k+1] = xs[k] - grad_potential(xs[k], c_true) * dt + np.sqrt(2*D2_true*dt) * rng.standard_normal()
    km = estimate_drift_diffusion(xs, dt, bins=50)
    rec = reconstruct_potential(km)
    grid = np.linspace(rec["x"][0], rec["x"][-1], 300)
    Vtrue = potential(grid, c_true); Vtrue -= Vtrue.min()

    fig2, ax2 = plt.subplots(1, 2, figsize=(14, 5))
    ax2[0].plot(km["x"], km["D1"], "o", ms=3, label="estimated drift D1(x)")
    ax2[0].plot(grid, -grad_potential(grid, c_true), color="crimson", label="true -V'(x)")
    ax2[0].set(title="(a) Kramers-Moyal drift recovery", xlabel="x", ylabel="D1(x)"); ax2[0].legend()
    ax2[1].plot(rec["x"], rec["V"], lw=2, label="reconstructed V(x)")
    ax2[1].plot(grid, Vtrue, "--", color="crimson", label="true V(x)")
    ax2[1].set(title="effective potential recovery", xlabel="x", ylabel="V(x)"); ax2[1].legend()
    fig2.tight_layout(); fig2.savefig(os.path.join(outdir, "fig2_calibration.png"), dpi=130)

    # --- (C) クリティカル・スローダウン: 傾き h を漸増 → fold 転移の手前で先行サイン ---
    n2 = 30_000; dt2 = 0.01; c2 = 1.0; D2c = 0.04
    h = np.linspace(0, 1.2, n2)   # 左谷を徐々に不安定化
    xc = np.empty(n2); xc[0] = -1.0
    transition = None
    for k in range(n2 - 1):
        xc[k+1] = xc[k] - grad_potential(xc[k], c2, h[k]) * dt2 + np.sqrt(2*D2c*dt2)*rng.standard_normal()
        if transition is None and xc[k+1] > 0.5:
            transition = k+1
    ew = early_warning(xc, window=1500)

    # 正しい EWS は「転移より手前」だけでトレンド検定する（転移後の収束に汚染されないため）
    pre = slice(0, transition)
    def _tau(v):
        m = ~np.isnan(v); m[transition:] = False
        return kendalltau(np.arange(len(v))[m], v[m])
    var_tau_pre, var_p_pre = _tau(ew["var"])
    ar1_tau_pre, ar1_p_pre = _tau(ew["ar1"])

    fig3, ax3 = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
    ax3[0].plot(xc, color="black", lw=0.5)
    if transition: ax3[0].axvline(transition, color="crimson", ls="--", label="regime shift")
    ax3[0].set(title="(C) state with slowly ramping tilt h(t)", ylabel="x"); ax3[0].legend()
    ax3[1].plot(ew["var"], color="darkorange")
    ax3[1].set(ylabel="rolling var",
               title=f"variance  [pre-shift trend] tau={var_tau_pre:.2f}, p={var_p_pre:.1e}  "
                     f"(full-series tau={ew['var_tau']:.2f} <- misleading)")
    ax3[2].plot(ew["ar1"], color="seagreen")
    ax3[2].set(ylabel="lag-1 AC", xlabel="step",
               title=f"AR1  [pre-shift trend] tau={ar1_tau_pre:.2f}, p={ar1_p_pre:.1e}  "
                     f"(full-series tau={ew['ar1_tau']:.2f} <- misleading)")
    for a in ax3[1:]:
        if transition: a.axvline(transition, color="crimson", ls="--")
    fig3.tight_layout(); fig3.savefig(os.path.join(outdir, "fig3_early_warning.png"), dpi=130)

    print("transition step:", transition)
    print(f"variance pre-shift trend: tau={var_tau_pre:.3f} p={var_p_pre:.2e}  (full={ew['var_tau']:.3f})")
    print(f"AR1 pre-shift trend:      tau={ar1_tau_pre:.3f} p={ar1_p_pre:.2e}  (full={ew['ar1_tau']:.3f})")
    print("figures saved.")


if __name__ == "__main__":
    _demo(outdir=".")
