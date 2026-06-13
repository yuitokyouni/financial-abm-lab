"""YH005: K=5 quinary history encoder + price-change quantization.

履歴 h(t) ∈ {-2, -1, 0, +1, +2} (論文1 Eq. 6) を過去 M 期分、底 5 の整数 μ ∈ [0, 5^M)
で表現する。shift_in は big-endian (古い方が最上位):

    μ = d_{t-M} · 5^(M-1) + d_{t-M+1} · 5^(M-2) + ... + d_{t-1} · 5^0
    d_k = h_k + 2 ∈ {0..4}
    shift:  μ' = (μ * 5) % (5^M) + d_new

量子化規則 (論文1 Eq. 6、不等号境界は論文通り):
    h(t) = +2  if Δp > C
           +1  if 0 < Δp ≤ C
            0  if Δp == 0
           -1  if -C ≤ Δp < 0
           -2  if Δp < -C
"""

from __future__ import annotations


def mu_capacity(M: int) -> int:
    return 5 ** M


def quantize_price_change(dp: float, C: float) -> int:
    """Δp を h ∈ {-2, -1, 0, +1, +2} に量子化。"""
    if dp > C:
        return 2
    if dp > 0:
        return 1
    if dp == 0:
        return 0
    if dp >= -C:
        return -1
    return -2


def shift_in(mu: int, h_code: int, M: int) -> int:
    """μ に新しい履歴 h_code ∈ {0..4} を右端 push、最古を drop。"""
    return (mu * 5) % (5 ** M) + h_code


def decode(mu: int, M: int) -> list[int]:
    """μ を h の列に復元 (古い順、デバッグ用)。"""
    out: list[int] = []
    for k in range(M):
        power = 5 ** (M - 1 - k)
        d = (mu // power) % 5
        out.append(d - 2)
    return out
