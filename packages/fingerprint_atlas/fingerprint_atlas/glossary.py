"""glossary — personal English↔Japanese terminology dictionary.

LLM-drafted Japanese for technical research text defaults to stilted
Meiji-era Sino-Japanese coinages (例: '富動学' for wealth dynamics,
'指紋' for fingerprint, '梃子効果' for leverage effect). This catalog
codifies (a) the renderings the user actually wants and (b) the ones
to refuse, with reasons attached so the LLM can apply the rule in
new contexts.

Each Entry carries:
  en          English term (the LLM's input cue)
  ja_primary  preferred Japanese rendering
  ja_also     acceptable alternatives (use when context demands)
  avoid       list of {bad, why} — translations to refuse + the reason
  notes       1-2 lines on meaning / typical context
  domain      financial-abm / ml / general / stats

The dict is curated by hand. Extend by editing this file or via the
`glossary add` CLI; LLM calls that set `generate_japanese=True` get
the relevant entries prepended to their system prompt automatically.
"""
from __future__ import annotations

from typing import TypedDict


class _Avoid(TypedDict):
    bad: str
    why: str


class Entry(TypedDict, total=False):
    en: str
    ja_primary: str
    ja_also: list[str]
    avoid: list[_Avoid]
    notes: str
    domain: str


GLOSSARY: list[Entry] = [
    # ----- core fingerprint-atlas terms -----
    {"en": "fingerprint",
     "ja_primary": "市場特徴量ベクトル",
     "ja_also": ["特徴量ベクトル", "統計署名"],
     "avoid": [{"bad": "指紋",
                 "why": "literal すぎて意味不明、専門家でも誰も使わない"}],
     "notes": "stylized facts (Hill α 等)を 6-9 次元ベクトル化したもの。市場/ABMの統計的シグネチャ。",
     "domain": "financial-abm"},
    {"en": "wealth dynamics",
     "ja_primary": "ウェルス・ダイナミクス",
     "ja_also": ["富のダイナミクス"],
     "avoid": [{"bad": "富動学", "why": "造語感が強く意味不明、誰も使わない"},
                {"bad": "動的富動", "why": "語順が変、意味不明"},
                {"bad": "資産動学", "why": "'動学' は使わない方針 — ダイナミクスで統一"}],
     "notes": "agent ひとりひとりが持つお金 + 保有株が、時間とともにどう増減していくかの過程。SG では layer 3 がこれを担う(損したら退場、儲かった人は残る)。",
     "domain": "financial-abm"},
    {"en": "canon",
     "ja_primary": "カノン",
     "ja_also": ["古典的論文群"],
     "avoid": [{"bad": "聖典",
                 "why": "宗教的すぎる、学術文脈では不適"}],
     "notes": "ある分野の foundational / 必読論文。'Lux-Marchesi はこの分野のカノン'のように使う。",
     "domain": "financial-abm"},
    {"en": "stylized facts",
     "ja_primary": "スタイル化事実",
     "ja_also": ["定型化事実"],
     "avoid": [{"bad": "様式化事実", "why": "古い、現代研究では使わない"}],
     "notes": "Cont 2001 が整理した金融時系列の普遍的特徴(ヘビーテール、ボラクラ等)。",
     "domain": "financial-abm"},
    {"en": "subfield",
     "ja_primary": "分野",
     "ja_also": ["サブ分野"],
     "avoid": [{"bad": "副分野", "why": "不自然、学術日本語として聞かない"}],
     "notes": "Minority Game / Leverage effect / LOB 等、ABM 研究の研究領域単位。",
     "domain": "general"},

    # ----- ABM core -----
    {"en": "agent-based model",
     "ja_primary": "エージェントベース・モデル",
     "ja_also": ["ABM", "マルチエージェントモデル"],
     "avoid": [{"bad": "行為者基盤模型", "why": "漢字盛り、誰も使わない造語"}],
     "notes": "個別エージェントの相互作用から集計的挙動を生む計算モデル。",
     "domain": "financial-abm"},
    {"en": "mechanism",
     "ja_primary": "機構",
     "ja_also": ["メカニズム"],
     "avoid": [{"bad": "仕組み",
                 "why": "口語的すぎ、学術論文では避ける(blog はOK)"}],
     "notes": "stylized fact を生成する内的構造。両方使うが、'機構' のほうが論文向き。",
     "domain": "general"},
    {"en": "agent",
     "ja_primary": "エージェント",
     "avoid": [{"bad": "行為者", "why": "古い社会学訳、ABM 文脈では使わない"}],
     "notes": "ABM の構成主体。学習エージェント・取引エージェント等の prefix で使う。",
     "domain": "financial-abm"},
    {"en": "regime",
     "ja_primary": "レジーム",
     "ja_also": ["局面"],
     "avoid": [{"bad": "体制", "why": "政治用語と衝突して文意がブレる"}],
     "notes": "市場の挙動が定性的に異なる状態(平常/危機/バブル)。",
     "domain": "financial-abm"},
    {"en": "intensity of choice",
     "ja_primary": "選択強度 (intensity of choice)",
     "notes": "Brock-Hommes の softmax 温度パラメータ β。",
     "domain": "financial-abm"},

    # ----- stylized facts (per-fact recommended translations) -----
    {"en": "fat tails",
     "ja_primary": "ヘビーテール",
     "ja_also": ["厚い裾", "ファットテール"],
     "notes": "リターン分布の裾が正規分布より厚いこと。",
     "domain": "financial-abm"},
    {"en": "volatility clustering",
     "ja_primary": "ボラティリティクラスタリング",
     "ja_also": ["ボラクラ"],
     "avoid": [{"bad": "変動率群集化",
                 "why": "直訳で意味不明"}],
     "notes": "大きな変動の後に大きな変動が続く現象。|r| の自己相関が長く残る。",
     "domain": "financial-abm"},
    {"en": "leverage effect",
     "ja_primary": "レバレッジ効果",
     "avoid": [{"bad": "梃子効果", "why": "literal すぎ、誰も使わない"}],
     "notes": "リターン低下後にボラティリティが上がる非対称性。corr(r_t, σ²_{t+k})<0。",
     "domain": "financial-abm"},
    {"en": "long memory",
     "ja_primary": "長期記憶",
     "notes": "|r| や σ² の自己相関が冪乗則で減衰する性質。fractional integration。",
     "domain": "financial-abm"},
    {"en": "absence of autocorrelation",
     "ja_primary": "自己相関の欠如",
     "ja_also": ["無相関リターン"],
     "notes": "リターン自体は lag-1 で ≈ 0。効率市場仮説の最 robust な経験的根拠。",
     "domain": "financial-abm"},
    {"en": "aggregational gaussianity",
     "ja_primary": "集計的ガウス性",
     "notes": "高頻度では非ガウス、低頻度に集計すると正規へ収束する性質。",
     "domain": "financial-abm"},
    {"en": "herding",
     "ja_primary": "群集行動",
     "ja_also": ["ハーディング"],
     "notes": "agents が互いを模倣することで意見・注文フローが偏る現象。",
     "domain": "financial-abm"},
    {"en": "gain-loss asymmetry",
     "ja_primary": "利得-損失非対称性",
     "notes": "上向き運動と下向き運動の statistics が非対称な性質。prospect theory の motivation の一つ。",
     "domain": "financial-abm"},

    # ----- decision-rule terms -----
    {"en": "chartist",
     "ja_primary": "チャーチスト",
     "ja_also": ["テクニカル派"],
     "avoid": [{"bad": "図表派", "why": "死語、現代日本語の経済学で使われない"}],
     "notes": "過去価格パターンから売買シグナルを引く agent type。",
     "domain": "financial-abm"},
    {"en": "fundamentalist",
     "ja_primary": "ファンダメンタリスト",
     "ja_also": ["ファンダ派"],
     "avoid": [{"bad": "原理主義者",
                 "why": "政治・宗教用語と衝突して文意が破綻"}],
     "notes": "ファンダメンタル価値からの乖離を mean-revert させる方向に取引する agent。",
     "domain": "financial-abm"},
    {"en": "noise trader",
     "ja_primary": "ノイズトレーダー",
     "notes": "情報を持たずランダムに取引する agent。ZI の典型形。",
     "domain": "financial-abm"},
    {"en": "bounded rationality",
     "ja_primary": "限定合理性",
     "notes": "完全合理性 (rational expectations) からの逸脱を許容する agent 設計原理。",
     "domain": "financial-abm"},
    {"en": "heterogeneous beliefs",
     "ja_primary": "不均質信念",
     "ja_also": ["異質信念"],
     "notes": "agents が異なる予測モデル(strategy)を持つ前提。Brock-Hommes の中核。",
     "domain": "financial-abm"},
    {"en": "loss aversion",
     "ja_primary": "損失回避",
     "ja_also": ["損失を嫌う傾向"],
     "notes": "「同じ額のプラスとマイナスを比べたとき、マイナスのほうがずっと嫌に感じる」という人間の性質。Tversky-Kahneman は実験から λ ≈ 2.25(損失の苦しみは同額の利得の喜びの 2.25 倍)と推定した。',回避' は ',できれば避けたい' の意。",
     "domain": "financial-abm"},
    {"en": "round-trip trade",
     "ja_primary": "往復取引",
     "notes": "建玉を持って (entry) → 反対売買で決済 (exit) する 1 サイクル。SG layer 2 の単位。",
     "domain": "financial-abm"},

    # ----- microstructure -----
    {"en": "limit order book",
     "ja_primary": "指値注文板",
     "ja_also": ["LOB", "リミットオーダーブック"],
     "avoid": [{"bad": "制限注文書", "why": "誤訳、'limit' は指値の意"}],
     "notes": "売買双方の指値注文を価格-時間優先で並べたデータ構造。PAMS / ABIDES の中核。",
     "domain": "financial-abm"},
    {"en": "bid-ask spread",
     "ja_primary": "ビッド・アスク・スプレッド",
     "ja_also": ["売気配と買気配の差"],
     "avoid": [{"bad": "売買気配差", "why": "古い、現代教科書では併用程度"}],
     "notes": "売気配と買気配の差。microstructure noise の主要源。",
     "domain": "financial-abm"},
    {"en": "matching engine",
     "ja_primary": "マッチングエンジン",
     "avoid": [{"bad": "約定機関", "why": "誤訳。'機関' は institution の訳語"}],
     "notes": "注文を突き合わせて約定を生むコンポーネント。event-driven 実装が標準。",
     "domain": "financial-abm"},
    {"en": "market microstructure",
     "ja_primary": "市場ミクロ構造",
     "notes": "取引制度・注文形態・約定機構など、価格形成の micro レベル研究分野。",
     "domain": "financial-abm"},
    {"en": "market impact",
     "ja_primary": "マーケットインパクト",
     "ja_also": ["価格インパクト"],
     "notes": "大口注文が価格に与える瞬間的・恒久的な影響。Almgren-Chriss が定式化。",
     "domain": "financial-abm"},
    {"en": "high-frequency trading",
     "ja_primary": "高頻度取引",
     "ja_also": ["HFT"],
     "notes": "μ秒~ms 単位で売買する戦略群。マーケットメイク / 裁定 / 注文フロー分析等。",
     "domain": "financial-abm"},

    # ----- ML / interpretability -----
    {"en": "reinforcement learning",
     "ja_primary": "強化学習",
     "ja_also": ["RL"],
     "notes": "報酬最大化で方策を学ぶ枠組み。",
     "domain": "ml"},
    {"en": "sparse autoencoder",
     "ja_primary": "スパースオートエンコーダ",
     "ja_also": ["SAE"],
     "avoid": [{"bad": "疎自己符号化器",
                 "why": "古典訳、現代の解釈可能性研究では使われない"}],
     "notes": "L1 penalty で活性をスパース化する自己符号化器。LLM 内部の monosemantic feature 抽出に使う。",
     "domain": "ml"},
    {"en": "mechanistic interpretability",
     "ja_primary": "機構的解釈可能性",
     "ja_also": ["メカニスティック解釈"],
     "notes": "学習モデル内部を機構レベルで解析する研究分野。Anthropic の中心テーマ。",
     "domain": "ml"},
    {"en": "linear probe",
     "ja_primary": "線形プローブ",
     "notes": "中間層の表現に線形分類器を fit し、表現に target 情報が含まれるかを定量化する診断。",
     "domain": "ml"},
    {"en": "ground truth",
     "ja_primary": "正解",
     "ja_also": ["グラウンドトゥルース", "正解ラベル"],
     "avoid": [{"bad": "地表真理", "why": "literal すぎて滑稽"}],
     "notes": "学習・評価の参照基準となる正しい値。",
     "domain": "ml"},
    {"en": "ablation study",
     "ja_primary": "アブレーション実験",
     "ja_also": ["削除実験", "成分除去実験"],
     "avoid": [{"bad": "切除研究", "why": "医学用語と混同される"}],
     "notes": "モデルの構成要素を順に除き、各要素の寄与を分離する実験設計。",
     "domain": "ml"},

    # ----- methodology / stats -----
    {"en": "Hill estimator",
     "ja_primary": "Hill 推定量",
     "notes": "ヘビーテール分布の裾指数 α を上位順序統計量から推定する method。",
     "domain": "stats"},
    {"en": "stationary bootstrap",
     "ja_primary": "定常ブートストラップ",
     "ja_also": ["Politis-Romano ブートストラップ"],
     "notes": "幾何分布長のブロック ブートストラップ。時系列の依存構造を保つ。",
     "domain": "stats"},
    {"en": "calibration",
     "ja_primary": "キャリブレーション",
     "ja_also": ["較正"],
     "notes": "ABM context: パラメータを実データに合わせる手続き。",
     "domain": "financial-abm"},
    {"en": "blind spot",
     "ja_primary": "盲点",
     "ja_also": ["ブラインドスポット"],
     "notes": "ある手法 / モデルが構造的に捉えられない領域。",
     "domain": "general"},
    {"en": "gap",
     "ja_primary": "研究空白",
     "ja_also": ["空隙", "ギャップ"],
     "avoid": [{"bad": "隙間", "why": "口語的すぎ、論文では使わない"}],
     "notes": "未探索の研究領域。gap-mine の中核概念。",
     "domain": "general"},
    {"en": "null hypothesis",
     "ja_primary": "帰無仮説",
     "ja_also": ["ヌル仮説"],
     "notes": "ZI の epistemic role がまさにこれ。'戦略の null'。",
     "domain": "stats"},
]


# ----- helpers ------------------------------------------------------------

def format_for_prompt(domain: str | None = None) -> str:
    """Render the glossary as a system-prompt-injectable block.

    Pass `domain` to scope (e.g. 'financial-abm' to skip 'ml' / 'stats').
    Returns an empty string if no entries match.
    """
    items = [e for e in GLOSSARY
              if (domain is None or e.get("domain", "general") == domain
                   or e.get("domain") == "general")]
    if not items:
        return ""
    lines: list[str] = [
        "## 日本語訳ガイド",
        "",
        "原則:",
        "1. この表の訳語を使う。reject 訳は絶対に生成しないこと。",
        "2. 学術文体で書くこと。LLM が default で出す Meiji-era の漢字直訳",
        "   (例: 富動学 / 指紋 / 梃子効果) は避け、現代日本語の研究文脈で",
        "   通用する語を選ぶこと。",
        "3. 「動学」は使わない。dynamics は「ダイナミクス」に統一すること",
        "   (例: 'wealth dynamics' は ウェルス・ダイナミクス、",
        "    × 富動学 / 資産動学)。",
        "4. 良い日本語訳がない概念は、無理に漢語訳を造らない。",
        "   カタカナ表記 + 直後の括弧内で『何のことか』を 1 文で説明する。",
        "   例: 「アブレーション実験(モデルの一部を消して効果を測る実験)」。",
        "",
        "用語表:",
    ]
    for e in items:
        line = f'- "{e["en"]}" → {e["ja_primary"]}'
        also = e.get("ja_also") or []
        if also:
            line += f"  (also: {', '.join(also)})"
        avoid = e.get("avoid") or []
        if avoid:
            bads = "; ".join(f"{a['bad']} ({a['why']})" for a in avoid)
            line += f"\n    reject: {bads}"
        notes = e.get("notes")
        if notes:
            line += f"\n    note: {notes.strip()}"
        lines.append(line)
    return "\n".join(lines)


def lookup(en: str) -> Entry | None:
    target = en.strip().lower()
    for e in GLOSSARY:
        if e["en"].lower() == target:
            return e
    return None


def search(query: str) -> list[Entry]:
    """Substring match against en / ja_primary / ja_also / notes."""
    q = query.lower()
    hits: list[Entry] = []
    for e in GLOSSARY:
        haystack = [e.get("en", ""), e.get("ja_primary", ""),
                     e.get("notes", "")] + list(e.get("ja_also") or [])
        if any(q in str(h).lower() for h in haystack):
            hits.append(e)
    return hits


def all_domains() -> list[str]:
    return sorted({e.get("domain", "general") for e in GLOSSARY})
