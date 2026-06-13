"""SC-005 (clearing 層): uniform-price clearing を engine と独立に単体テスト（D5c）。"""
from microstructure.book import Order, Side, clear_uniform


def _bid(p, s):
    return Order(Side.BUY, p, s, "b", 0)


def _ask(p, s):
    return Order(Side.SELL, p, s, "a", 0)


def test_clearing_handcalc():
    # demand: >=100 は 5+3=8、>=101 は 5。supply: <=100 は 4+2=6、<=99 は 4。
    # matched: p=99→4, p=100→6, p=101→5 → 最大 6 @ 100。
    bids = [_bid(101, 5), _bid(100, 3)]
    asks = [_ask(99, 4), _ask(100, 2)]
    price, vol = clear_uniform(bids, asks)
    assert price == 100
    assert vol == 6


def test_no_cross_returns_none():
    bids = [_bid(99, 5)]
    asks = [_ask(100, 5)]
    price, vol = clear_uniform(bids, asks)
    assert price is None and vol == 0.0


def test_empty_side():
    assert clear_uniform([], [_ask(100, 1)]) == (None, 0.0)
