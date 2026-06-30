"""i18n — Japanese labels + one-line mechanism summaries.

User-facing output (gap-mine CLI, dashboard tables) shows the cryptic
English keys (`franke_westerhoff`, `absence-of-autocorr`) which carry
no meaning unless you already know the literature. This module attaches
a Japanese display name and a 1-line mechanism gloss to each.

Code identifiers stay English (registry keys, model_name in DB, etc.);
only the rendered text changes.
"""
from __future__ import annotations


# ----- ABM family English key → (Japanese label, 1-line gloss) ------------

ABM_FAMILY_JA: dict[str, tuple[str, str]] = {
    "minority_game": (
        "Minority Game(少数派ゲーム)",
        "N人が±1を選び、少数派が勝つ。記憶m個の戦略から最良過去成績のものを選ぶ。",
    ),
    "lux_marchesi": (
        "Lux–Marchesi(チャーチスト/ファンダメンタリスト)",
        "楽観/悲観チャーチスト/ファンダメンタリストの3集団が連続時間で行き来し、収益と意見伝染で構成比が変化。",
    ),
    "chiarella_iori": (
        "Chiarella–Iori(LOB対応3型)",
        "チャーチスト/ファンダメンタリスト/ノイズの3型を連続ダブルオークションLOB上で実装。",
    ),
    "cont_bouchaud": (
        "Cont–Bouchaud(浸透型ハーディング)",
        "エージェントがランダムにクラスタを作り、各クラスタが1単位として取引。ヘビーテールはクラスタサイズ分布から生成。",
    ),
    "franke_westerhoff": (
        "Franke–Westerhoff(離散選択スイッチ)",
        "チャーチスト⇔ファンダメンタリストの離散選択を直近利益+群集圧力で切替。",
    ),
    "gcmg": (
        "Grand-Canonical MG(大正準少数派ゲーム)",
        "Minority Game に参加/退出ダイナミクスを追加。儲かれば入る・損すれば出る。",
    ),
    "speculation_game": (
        "Speculation Game(投機ゲーム / SG)",
        "3層認知ABM:(1)市場認知 →(2)往復取引 →(3)富動的退出参入。ルールベースで5/6スタイル化事実を再現。",
    ),
    "zero_intelligence": (
        "Zero Intelligence(ゼロ知能)",
        "戦略なし。予算制約下のランダム注文のみ。戦略の null hypothesis として導入された。",
    ),
    "alfarano_lux_wagner": (
        "Alfarano–Lux–Wagner(解析的ハーディング)",
        "ペア相互作用+自発切替のセンチメント過程に価格写像を載せたモデル。高次モーメントが解析解で出る。",
    ),
}


# ----- stylized-fact slug → glossary English key (single source of truth) --

# Stylized-fact labels + glosses come from glossary.py to avoid drift.
# This module owns only the mapping between gap_finder's hyphenated slug
# and the glossary's English key — proper nouns (ABM families) and
# gap-finder-internal terms (views) stay local.
_FACT_TO_GLOSSARY_EN: dict[str, str] = {
    "fat-tails": "fat tails",
    "vol-clustering": "volatility clustering",
    "leverage": "leverage effect",
    "long-memory": "long memory",
    "regime-switching": "regime",  # glossary stores it under 'regime'
    "aggregational-gaussianity": "aggregational gaussianity",
    "absence-of-autocorr": "absence of autocorrelation",
    "herding": "herding",
    # 'other' has no glossary entry — fall back to a static label below.
}

_FACT_FALLBACK: dict[str, tuple[str, str]] = {
    "other": ("その他", ""),
}


# ----- view name English → Japanese -----------------------------------------

VIEW_JA: dict[str, tuple[str, str]] = {
    "A": ("分野 × スタイル化事実",
          "コーパス内の論文数。dense な行で空セル = 『この分野はこの事実をターゲットにしていない』"),
    "B": ("ABM家系 × スタイル化事実",
          "家系の中央値と実市場中央値の距離(σ単位)。大きい = 『この家系はこの事実を再現できていない』"),
    "C": ("実装手法 × 分野",
          "手法の参考論文と分野の関連論文の重複数。0 で両端が popular = 『誰も交叉していない』"),
}


# ----- helpers -------------------------------------------------------------

def family_label(key: str) -> str:
    """Return the Japanese display label for an ABM family key.
    Falls back to the raw key if no translation exists."""
    info = ABM_FAMILY_JA.get(key)
    return info[0] if info else key


def family_gloss(key: str) -> str:
    info = ABM_FAMILY_JA.get(key)
    return info[1] if info else ""


def _glossary_entry(slug: str) -> dict | None:
    en = _FACT_TO_GLOSSARY_EN.get(slug)
    if not en:
        return None
    try:
        from .glossary import lookup
        return lookup(en)
    except ImportError:
        return None


def fact_label(key: str) -> str:
    """Japanese display label for a stylized-fact slug.

    Single source of truth = glossary.py. The label is the glossary
    primary; we append a short English subtitle in parens when the
    glossary primary is pure katakana, to help the reader bridge to
    the literature jargon (e.g. 'ヘビーテール (fat tails)').
    """
    e = _glossary_entry(key)
    if e:
        ja = e["ja_primary"]
        # Add the English cue parenthetically when the JA is pure katakana
        # and the glossary entry has an `en` we can echo.
        if all(0x30A0 <= ord(c) <= 0x30FF or c in " ・"
                for c in ja.replace("(", "")
                          .replace(")", "")) and e.get("en"):
            return f"{ja} ({e['en']})"
        return ja
    return _FACT_FALLBACK.get(key, (key, ""))[0]


def fact_gloss(key: str) -> str:
    e = _glossary_entry(key)
    if e and e.get("notes"):
        return e["notes"]
    return _FACT_FALLBACK.get(key, (key, ""))[1]


def view_label(name: str) -> str:
    info = VIEW_JA.get(name)
    return info[0] if info else name


def view_gloss(name: str) -> str:
    info = VIEW_JA.get(name)
    return info[1] if info else ""


def translate_gap_row_col(view: str, row: str, col: str) -> tuple[str, str]:
    """Apply the right translation to (row, col) given the view's axes.
    Returns (row_ja, col_ja)."""
    if view == "A":   # subfield × stylized_fact
        return row, fact_label(col)   # subfields already have Japanese-ish names
    if view == "B":   # abm_family × stylized_fact
        return family_label(row), fact_label(col)
    if view == "C":   # technique × subfield
        return row, col  # techniques + subfields already have human names
    return row, col
