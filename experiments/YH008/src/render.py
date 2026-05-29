"""render.py -- state dict -> prompt string, per FCLAgent (Hashimoto et al.) Appendix A.

Two variants:
  - behavioral: faithful FCLAgent prompt (order_price/is_buy/order_volume/reason),
    asks for reason + emotion. Used ONLY for the behavioral-faithfulness check.
  - clean_probe: same Premise/Instruction/Information, but the answer format is the
    immediate-decision form constrained to is_buy only. The prompt is rendered through
    the chat template (add_generation_prompt=True) and the literal assistant prefix
    `{"0": {"is_buy": "` is appended; the decision token is read at the next position.
    NO autoregressive generation, NO reason/emotion (CoT-contamination-free; fixed
    research decision #3).

A `State` is a plain dataclass of the numeric fields the FCLAgent prompt exposes.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
import json


@dataclass(frozen=True)
class State:
    cash: float
    position: int            # holding volume (FCLAgent v); >0 long
    unrealized_gain: float   # position * (price - avg_cost)
    price: float             # current market price
    ath: float               # all time high price (>= price)
    atl: float               # all time low price (<= price)
    remaining_time: int
    total_time: int
    buy_price: float         # trading-history entry price (avg cost)
    buy_volume: int          # trading-history volume
    ofi: float               # order flow imbalance in [-1, 1]

    def round_for_prompt(self) -> "State":
        # FCLAgent prints prices to 1 decimal, gains to 1 decimal, ofi to 2.
        return State(
            cash=round(self.cash, 1), position=int(self.position),
            unrealized_gain=round(self.unrealized_gain, 1), price=round(self.price, 1),
            ath=round(self.ath, 1), atl=round(self.atl, 1),
            remaining_time=int(self.remaining_time), total_time=int(self.total_time),
            buy_price=round(self.buy_price, 1), buy_volume=int(self.buy_volume),
            ofi=round(self.ofi, 2),
        )


# ---- shared prompt blocks (verbatim-faithful to FCLAgent Appendix A) ----------

PREMISE = (
    "You are a participant of the simulation of stock markets. Behave as an investor. "
    "Answer your order decision after analysing the given information."
)

INSTRUCTION = (
    "Your current portfolio is provided as a following format. "
    "Unrealized gain refers to the increase in value of the investment that has not yet "
    "been sold. It represents the potential profit on your stock position. Negative "
    "unrealized gain means that the investment has decreased in value.\n"
    "[Your portfolio]cash: {}\n"
    "[Your portfolio]market id: {}, volume: {}, unrealized gain: {}, ...\n"
    "Each market condition is provided as a following format.\n"
    "[Market condition]market id: {}, current market price: {}, all time high price: {}, "
    "all time low price: {}, ...\n"
    "[Market condition]market id: {}, remaining time: {}, total time: {}\n"
    "Your trading history is provided as a following format. Negative volume means that "
    "you sold the stock.\n"
    "[Your trading history]market id: {}, price: {}, volume: {}, ...\n"
    "Order flow imbalance is provided as a following format. Order flow imbalance means "
    "the difference between the number of buy and sell orders submitted to the stock "
    "market. Order flow imbalance can range from -1 to 1. Negative order flow imbalance "
    "indicates that the number of sell orders exceed that of buy orders. If the order "
    "flow is positive (negative), the fundamental value tends to be high (low). Higher "
    "absolute value of order flow imbalance indicates that orders are imbalance to one "
    "side, and suggests stronger evidence about the fundamentals value of the stock.\n"
    "[Order flow imbalance]market id: {}, order flow imbalance: {}, ...\n"
)


def _information_block(s: State) -> str:
    s = s.round_for_prompt()
    cash_line = f"[Your portfolio]cash: {s.cash:g}"
    if s.cash < 0:
        cash_line += (" (Caution! Your cash amount is negative! To avoid this situation, "
                      "you have to sell the stocks.)")
    vol_line = (f"[Your portfolio]market id: 0, volume: {s.position}, "
                f"unrealized gain: {s.unrealized_gain:g}")
    if s.position < 0:
        vol_line += (" (Caution! Your holding stock volume is negative! To avoid this "
                     "situation, you have to buy this stock.)")
    return (
        "Here's the information.\n"
        f"{cash_line}\n"
        f"{vol_line}\n"
        f"[Market condition]market id: 0, current market price: {s.price:g}, "
        f"all time high price: {s.ath:g}, all time low price: {s.atl:g}\n"
        f"[Market condition]market id: 0, remaining time: {s.remaining_time}, "
        f"total time: {s.total_time}\n"
        f"[Your trading history]market id: 0, price: {s.buy_price:g}, "
        f"volume: {s.buy_volume}\n"
        f"[Order flow imbalance]market id: 0, order flow imbalance: {s.ofi:g}\n"
    )


# ---- behavioral variant (faithfulness only) -----------------------------------

BEHAVIORAL_ANSWER = (
    "Decide your investment in the following JSON format. Do not deviate from the format, "
    "and do not add any additional words to your response outside of the format. Make sure "
    "to enclose each property in double quotes. Order volume means the number of units you "
    "want to trade the stock. is_buy means whether to buy or sell the stock. is_buy must be "
    "True or False. Short selling is not allowed. If your holding stock volume in the "
    "portfolio is negative, buy them back immediately. Cash shortage is not allowed. If your "
    "cash amount in the portfolio is negative, sell your holding stocks immediately. Try to "
    "keep your order volume as non-zero and not-extreme as possible. Try to keep your "
    "portfolio balanced. Order price means the limit price at which you want to buy or sell "
    "the stock.\n"
    'Here are the answer format.\n'
    '{"0": {"order_price": "<order price>", "is_buy": "<True or False>", '
    '"order_volume": "<order volume>", "reason": "<reason>"}}\n'
    "Now, decide your order. Please explain the reason and your emotion in as much detail "
    "as possible."
)


def render_behavioral(s: State) -> str:
    return (PREMISE + "\n" + INSTRUCTION + _information_block(s) + BEHAVIORAL_ANSWER)


def build_behavioral_probe(tokenizer, s: State,
                           assistant_prefix: str = None) -> str:
    """Behavioral answer-format prompt, but read the is_buy decision via a single logit
    (no free generation). The behavioral JSON puts order_price BEFORE is_buy, so the
    assistant prefix pre-fills order_price (=current price; no market here) up to the
    is_buy slot. This isolates the effect of the *reason-requesting answer format* on the
    decision, comparable to clean-probe on the same state, without slow fp32 generation.
    NOTE: this still does not capture free CoT the model would emit before the JSON; for
    that, a few real generations are run separately (qualitative)."""
    s = s.round_for_prompt()
    if assistant_prefix is None:
        assistant_prefix = f'{{"0": {{"order_price": "{s.price:g}", "is_buy": "'
    user = PREMISE + "\n" + INSTRUCTION + _information_block(s) + BEHAVIORAL_ANSWER
    chat = tokenizer.apply_chat_template(
        [{"role": "user", "content": user}], tokenize=False, add_generation_prompt=True)
    return chat + assistant_prefix


# ---- clean-probe variant (probing / intervention) -----------------------------
# Answer format reduced to the immediate is_buy decision: no order_price / order_volume,
# no reason / emotion. The closing instruction pins the decision token to a True/False
# spelling so the structural slot after the literal prefix is well-defined.

CLEAN_ANSWER = (
    "Decide your order in the following JSON format. Do not deviate from the format, and "
    "do not add any additional words to your response outside of the format. Make sure to "
    "enclose each property in double quotes. is_buy means whether to buy or sell the stock. "
    'Here are the answer format.\n'
    '{"0": {"is_buy": "<True or False>"}}\n'
    "Now, decide your order. Answer JSON only. is_buy must be True or False."
)

# literal assistant prefix; decision token read at the slot right after this.
ASSISTANT_PREFIX = '{"0": {"is_buy": "'

# Neutral wording variants of the closing answer instruction, for the Stage 0.2
# prompt-sensitivity sweep. The FROZEN probe uses "sec1_faithful" (== CLEAN_ANSWER,
# matching section 1's stated minimal format). The others are alternative *neutral*
# phrasings (no buy/sell nudging beyond stating the True/False meaning) used ONLY to
# quantify how much P(sell) moves with phrasing -- a sensitivity diagnostic, not a
# selection step. (The first wording that gave P(sell)=0.466 is included as
# "embellished_v0" to document the original drift.)
CLEAN_ANSWER_VARIANTS = {
    "sec1_faithful": CLEAN_ANSWER,
    "minimal": (
        'Answer in JSON only, exactly: {"0": {"is_buy": "<True or False>"}}. '
        "is_buy must be True or False."
    ),
    "plain": (   # neutral, no orientation hint (P0.5 direction-robustness)
        "Now state your order as JSON and nothing else: "
        '{"0": {"is_buy": "<True or False>"}}. The value of is_buy is either True or False.'
    ),
    "orientation_explicit": (
        "Decide your order in the following JSON format. Do not add any words outside "
        'the format.\n{"0": {"is_buy": "<True or False>"}}\n'
        "is_buy must be True or False (True = buy, False = sell)."
    ),
    "embellished_v0": (   # the original drifted wording (gave P(sell)=0.466 on smoke_loss)
        "Decide your order. Answer in JSON only. Do not add any words outside the format. "
        'Use exactly this format: {"0": {"is_buy": "<True or False>"}}. '
        "is_buy must be True or False (True = buy more, False = sell). "
        "Short selling is not allowed; if your holding volume is negative, buy back. "
        "Cash shortage is not allowed; if your cash is negative, sell."
    ),
}


def build_clean_probe_variant(tokenizer, s: State, variant: str,
                              assistant_prefix: str = ASSISTANT_PREFIX) -> str:
    """Like build_clean_probe but with an alternative closing wording (sweep only)."""
    answer = CLEAN_ANSWER_VARIANTS[variant]
    user = PREMISE + "\n" + INSTRUCTION + _information_block(s) + answer
    chat = tokenizer.apply_chat_template(
        [{"role": "user", "content": user}], tokenize=False, add_generation_prompt=True)
    return chat + assistant_prefix


def render_clean_user(s: State) -> str:
    """The user-turn content for the clean-probe (everything before chat templating)."""
    return PREMISE + "\n" + INSTRUCTION + _information_block(s) + CLEAN_ANSWER


def build_clean_probe(tokenizer, s: State, assistant_prefix: str = ASSISTANT_PREFIX) -> str:
    """Full prompt string: chat-templated user turn + literal assistant prefix.
    Caller tokenizes with prepend_bos=False (template already includes BOS)."""
    user = render_clean_user(s)
    chat = tokenizer.apply_chat_template(
        [{"role": "user", "content": user}], tokenize=False, add_generation_prompt=True)
    return chat + assistant_prefix


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def template_hashes(tokenizer) -> dict:
    """Hashes of both prompt variants for a fixed reference state (reproducibility)."""
    ref = State(cash=30000, position=10, unrealized_gain=-63.0, price=293.7, ath=300.0,
                atl=287.5, remaining_time=70, total_time=100, buy_price=300.0,
                buy_volume=10, ofi=0.01)
    return {
        "behavioral": prompt_hash(render_behavioral(ref)),
        "clean_probe": prompt_hash(build_clean_probe(tokenizer, ref)),
        "clean_user_template": prompt_hash(PREMISE + INSTRUCTION + CLEAN_ANSWER),
        "behavioral_template": prompt_hash(PREMISE + INSTRUCTION + BEHAVIORAL_ANSWER),
    }


def state_to_dict(s: State) -> dict:
    return asdict(s)
