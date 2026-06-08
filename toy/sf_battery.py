"""sf_battery — Stylized Facts SF1-SF6 測定(spec §4)。

留保2(v0.2 解決): **SF1-4 = calibration target**、SF5/6 = post-equivalence 独立検証量。
calibration の距離は SF1-4(4 次元)上で測る(§5.1, §6.1)。

- SF1: return autocorrelation の不在     — ACF(r, lag 1-10) の sum-of-squares
- SF2: |r| autocorrelation の slow decay  — |r| ACF を lag 1-50 で power law fit、decay 指数
- SF3: heavy tails                        — excess kurtosis(+ Hill estimator、top 5% tail)
- SF4: volatility clustering              — GARCH(1,1) の α+β(persistence)
- SF5: leverage effect                    — corr(r_t, σ²_{t+k}) の負号(post-equivalence)
- SF6: gain-loss asymmetry                — inverse statistics(scaffold、post-equivalence)
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

# calibration target(留保2)。SF classifier 入力 = この 4 次元(§6.1)。
CALIBRATION_SF: tuple[str, ...] = ("SF1", "SF2", "SF3", "SF4")
SF_IDS: tuple[str, ...] = ("SF1", "SF2", "SF3", "SF4", "SF5", "SF6")

Returns = npt.NDArray[np.float64]


def _acf(x: Returns, lag: int) -> float:
    if x.size <= lag or x.std() == 0.0:
        return 0.0
    return float(np.corrcoef(x[:-lag], x[lag:])[0, 1])


def sf1_return_acf(r: Returns) -> float:
    """ACF(r, lag 1-10) の sum-of-squares(小さいほど無相関 = stylized)。"""
    return float(sum(_acf(r, k) ** 2 for k in range(1, 11)))


def sf2_absret_decay(r: Returns) -> float:
    """|r| の ACF を lag 1-50 で power law fit、decay 指数(slow decay ほど小さい)。"""
    absr = np.abs(r)
    lags = np.arange(1, 51)
    acfs = np.array([_acf(absr, int(k)) for k in lags], dtype=np.float64)
    mask = acfs > 1e-6  # 正の ACF のみ log fit
    if mask.sum() < 5:
        return 0.0
    slope = np.polyfit(np.log(lags[mask]), np.log(acfs[mask]), 1)[0]
    return float(-slope)  # decay rate(正、小さい=slow decay)


def sf3_excess_kurtosis(r: Returns) -> float:
    """excess kurtosis(heavy tails、正で fat tail)。"""
    sd = r.std()
    if sd == 0.0:
        return 0.0
    return float(((r - r.mean()) ** 4).mean() / sd**4 - 3.0)


def sf3_hill(r: Returns, tail_frac: float = 0.05) -> float:
    """Hill estimator(top tail_frac の tail index、小さいほど heavy tail)。"""
    absr = np.sort(np.abs(r))[::-1]
    k = max(int(tail_frac * absr.size), 2)
    top = absr[:k]
    thresh = absr[k]
    if thresh <= 0.0 or np.any(top <= 0.0):
        return 0.0
    return float(np.mean(np.log(top) - np.log(thresh)))


def sf4_garch_persistence(r: Returns) -> float:
    """GARCH(1,1) の α+β(volatility clustering の persistence)。"""
    if r.std() == 0.0 or r.size < 100:
        return 0.0
    from arch import arch_model

    scaled = (r - r.mean()) * 100.0  # arch は O(1) scale を想定
    try:
        res = arch_model(scaled, vol="GARCH", p=1, q=1, mean="Zero").fit(disp="off")
        return float(res.params.get("alpha[1]", 0.0) + res.params.get("beta[1]", 0.0))
    except Exception:
        return 0.0


def sf5_leverage(r: Returns, kmax: int = 10) -> float:
    """leverage effect: corr(r_t, σ²_{t+k}) の k=1..kmax 平均(負が leverage)。"""
    if r.size <= kmax + 1 or r.std() == 0.0:
        return 0.0
    vol2 = r**2
    cs = [
        float(np.corrcoef(r[:-k], vol2[k:])[0, 1])
        for k in range(1, kmax + 1)
        if r[:-k].std() > 0 and vol2[k:].std() > 0
    ]
    return float(np.mean(cs)) if cs else 0.0


def measure_sf_battery(returns: Returns, *, include_post: bool = True) -> dict[str, float]:
    """return 系列から SF battery を測る。SF1-4 は calibration target、SF5(/6)は post-equiv。"""
    r = np.asarray(returns, dtype=np.float64)
    out: dict[str, float] = {
        "SF1": sf1_return_acf(r),
        "SF2": sf2_absret_decay(r),
        "SF3": sf3_excess_kurtosis(r),
        "SF3_hill": sf3_hill(r),
        "SF4": sf4_garch_persistence(r),
    }
    if include_post:
        out["SF5"] = sf5_leverage(r)
    return out


def sf6_gain_loss_asymmetry(returns: Returns) -> float:
    """SF6: inverse statistics による gain-loss asymmetry(Donangelo 流、post-equivalence)。"""
    raise NotImplementedError("SF6: inverse statistics 未実装(post-equivalence 検証量、後続)")
