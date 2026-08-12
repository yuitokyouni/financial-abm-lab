# -*- coding: utf-8 -*-
"""sieve inspect レポートの日本語レビュー版を生成する。

本番(英語)レポートの全テキスト(reading guide / caveats / limitations)を
日本語に訳し、同じ figure SVG をインラインで並べる。訳文は bundle の実テキスト
(inspect_bundle.json) と 1:1 対応。英語版の記載内容チェック用であり、封印
bundle の一部ではない。

実行: uv run python experiments/sieve_export/build_ja_report.py <run_dir>
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

RUN = Path(sys.argv[1] if len(sys.argv) > 1
           else "experiments/sieve_export/sieve_runs/010bf1d5c448")
OUT = Path(__file__).parent / "REPORT_ja_review.html"

T_STATUS = {"OBSERVED": "OBSERVED(計算・描画済み — 「成立」の意味ではない)",
            "NOT_TESTED": "NOT_TESTED(この版では未実装)",
            "INSUFFICIENT": "INSUFFICIENT(データ不足)",
            "NOT_APPLICABLE": "NOT_APPLICABLE(対象外)"}

# figure_id -> (日本語タイトル, stylized fact 訳, reading guide 訳)
T_FIG = {
 "return_path": ("リターン経路 / ボラティリティの質感",
  "volatility clustering・間欠性",
  "大きな |r| が時間的に固まるエピソード(clustering / 間欠性)と、典型的リターン帯の"
  "ドリフトや水準シフトを見る。run 間で質感は細部こそ違えど種類は揃っているべき。"),
 "marginal_distribution": ("周辺分布 vs ガウス",
  "厚い裾",
  "線形パネルではシミュレーション密度とガウスの尖度差を、log-y パネルでは裾がガウスの"
  "上に乗るか(厚い裾)と、どこまで伸びるかを見る。"),
 "tail_ccdf": ("裾 CCDF + Hill 推定オーバーレイ",
  "厚い裾(裾指数)",
  "log-log 軸で上部領域がおおむね直線なら power-law 的な裾と整合的。破線はマークされた"
  " k 領域のみでの Hill フィット。左右の裾の非対称も比較する。"),
 "return_acf": ("リターンの自己相関",
  "リターン自己相関の不在",
  "リターンが系列無相関なら、表示された全ラグで値はほぼ帯の中に収まるはず。"
  "遅い減衰や系統的な符号パターンは、モデルが意図しない予測可能性を示す。"),
 "volatility_acf": ("|r| と r² の自己相関",
  "volatility clustering・ボラ自己相関の遅い減衰",
  "正でゆっくり減衰する ACF(|r|)(と ACF(r²))が volatility clustering の証拠。"
  "1 ラグでなく減衰形状を比較する。log-log 表示は遅い減衰の判定補助で、何もフィットしない。"),
 "aggregation_profile": ("集約プロファイル(尖度 vs ホライズン)",
  "集約に伴うガウス化",
  "集約ガウス性が成り立つなら、ホライズンを伸ばすほど超過尖度は 0 へ落ちる。"
  "右端ほど有効サンプルが減るので注意して読む。"),
 "leverage_kernel": ("レバレッジ・カーネル c(τ)",
  "レバレッジ効果",
  "株式的データでは τ>0 で c(τ)<0(悪いリターンが高ボラに先行)、τ<0 ではほぼ 0。"
  "対称なカーネルはレバレッジ型非対称が無いことを意味する。"),
 "drift_variance_diagnostic": ("ドリフトと分散比の診断",
  "ドリフト / リターン依存(較正の正気度)",
  "run ごとの drift はモデルの意図値(多くは ~0)近くに散るべき。全 q で VR(q)≈1 なら"
  "強い mean reversion(<1)もトレンド(>1)も無い。"),
 "volume_volatility": ("出来高–ボラティリティ関係",
  "出来高 / ボラ相関",
  "出来高ビンに沿った |r| の平均の上昇(と正の順位相関)が出来高–ボラ関係。"
  "生の散布図は低出来高の密集域に支配される。"),
 "conditional_tails": ("条件付き厚い裾(標準化残差)",
  "条件付き厚い裾",
  "計画中: 生リターンの裾と、条件付きボラで標準化した残差の裾を比較する。"
  "残差の裾が厚ければ、ボラ動学で説明できない裾が残っている。"),
 "timescale_asymmetry": ("粗視化–細粒ボラのリード・ラグ",
  "時間スケールの非対称性",
  "計画中: 粗視化ボラと細粒ボラの正負ラグでの相互相関。非対称なら情報が長い"
  "ホライズンから短いホライズンへ流れている。"),
 "gain_loss_asymmetry": ("利得/損失の初到達時間分布",
  "利得/損失の非対称性",
  "計画中: 各時点から +θ / −θ への初到達時間の分布。株価指数では同サイズなら"
  "損失の方が早く到達する傾向。"),
}

# caveat 原文(前方一致キー) -> 訳
T_CAVEAT = [
 ("min-max decimation", "ピクセル単位の min-max 間引き: 極値は保存されるが点密度は保存されない"),
 ("showing the first 4", "10 run 中、run_id 順で先頭 4 run を表示 — 固定の選択規則であり、恣意的な選抜ではない"),
 ("reference overlay 'Nikkei 225' is visual context only: no statistical comparison is made and no status depends on it; the reference VR",
  "reference オーバーレイ「Nikkei 225」は視覚的文脈のみ: 統計比較はしておらず、どの status もこれに依存しない。reference の VR 曲線は右パネルにだけ描かれる(左パネルは run ごとの drift)"),
 ("reference overlay 'Nikkei 225'",
  "reference オーバーレイ「Nikkei 225」は視覚的文脈のみ: 統計比較はしておらず、どの status もこれに依存しない"),
 ("standardized per run, then pooled across runs",
  "run ごとに標準化してからこの周辺分布ビューのためだけにプール。プールはここで開示され、時間添字つきの量には決して適用しない"),
 ("histogram shape depends on binning",
  "ヒストグラム形状はビン割りに依存する。裾の一次証拠は CCDF figure の方"),
 ("pooled histogram can hide run-to-run",
  "プールしたヒストグラムは run 間差を隠しうる。run ごとの裾指数は metric 表にある"),
 ("positive tail: Hill",
  "正の裾: Hill は上位 1248 個の順序統計量を使用 (frac=0.05)。推定は k に敏感(記録済み盲点: frac 2.5–10% で ~0.9 IQR 振れる)"),
 ("negative (|z|) tail: Hill",
  "負(|z|)の裾: Hill は上位 1251 個の順序統計量を使用 (frac=0.05)。推定は k に敏感(同上)"),
 ("runs are scaled by their own sd",
  "プール前に各 run を自身の sd でスケール(平均は引かない)。よって Hill オーバーレイは hill_left/right metric と同じ裾指数を推定する。プールはこの周辺ビュー限定で開示済み"),
 ("each panel shows the survival fraction",
  "各パネルは自分の裾の内側での生存率(符号で条件付け)を表示。y 軸ラベルどおり"),
 ("log-log straightness alone",
  "log-log の直線性だけでは power law は立証されない。Hill 線はマークした k 領域上の推定にすぎない"),
 ("the +/-1.96/sqrt(n) band",
  "±1.96/√n の帯は iid 系列を仮定しており、volatility clustering 下では不確実性を過小評価する"),
 ("read the decay shape",
  "単一ラグでなく、ラグ方向の減衰形状を読む"),
 ("vertical mark at lag 20", "lag 20 の縦線は acf_abs_20 metric のラグ位置"),
 ("no functional form is fitted",
  "関数形は何もフィットしていない: log-log で直線に見えることは power law の証拠ではない(フィット範囲と推定量の事前指定が必要)"),
 ("the effective sample size shrinks",
  "有効サンプル数はホライズンに反比例して縮む(n/dt 個)。右端の点が最もノイジー"),
 ("horizons shown only where",
  "全 run が集約後 200 観測以上を保つホライズンのみ表示"),
 ("kurtosis -> 0 with growing horizon",
  "ホライズン増加で尖度→0 は集約ガウス性と整合的だが、その検定ではない"),
 ("the scalar 'leverage' metric",
  "スカラー leverage metric は τ=1..5(網掛け領域)の c(τ) 平均 — この曲線と同一の τ 別計算で、テストで検証済み"),
 ("c(tau) for tau<0",
  "τ<0 の c(τ)(将来リターン vs 過去ボラ)は時間の矢の対比用。株式データは通常 τ>0 でのみ c(τ)<0"),
 ("recorded metric blind spot: the lag-count",
  "記録済み盲点: ラグ数ノブでスカラー値が ~0.94 IQR 動く"),
 ("drift here is per-run mean/sd",
  "ここの drift は run ごとの mean/sd(step 単位)。絶対基準ではなく、モデルの意図した drift と比較する"),
 ("VR(q) needs q*10",
  "VR(q) は 1 点あたり q×10 観測が必要。短い run では大きい q が NaN に落ちる"),
 ("pairs are matched within each run",
  "ペアは各 run 内で対応付け。プールはこの周辺散布図のためだけ(開示済み)"),
 ("display: stride thinning",
  "表示上は stride 間引き + 出来高を 99.5 パーセンタイルでクリップ。ビン平均と ρ は全点を使用"),
 ("Spearman rho is reported per run",
  "Spearman ρ は run ごとに算出(run 横断の中央値)。探索モードでは不確実性区間を付けない"),
 ("volume and |return| are divided",
  "出来高と |return| はプール前に run ごとの平均で割る。散布図とビン平均は run 内関係を示し、run 間の水準差は意図的に除去(残すと、どの run も持たない見かけの傾きを捏造する)"),
 ("standardizing by a fitted GARCH",
  "フィットした GARCH での標準化は推定依存を持ち込む。ボラモデルとそのパラメータの記録が必須"),
 ("confusing raw-tail and residual-tail", "生の裾と残差の裾の証拠の混同(に注意)"),
 ("lag sign conventions differ",
  "ラグ符号の規約は文献間で異なる。集約ホライズンとラグ規約は図と一緒に印字しなければならない"),
 ("first-passage times are right-censored",
  "初到達時間は系列末尾で右打ち切りされる。非到達の扱いを明示しなければならない"),
 ("passages must never cross a run boundary", "到達判定が run 境界をまたいではならない"),
]

T_LIMITS = [
 "探索モード: この run は確認的判定を一切しない。figure と記述統計は目視検査の支援のみ",
 "reference との統計比較は行っていない。ここにある何物も「シミュレーションが実市場に合う」とは言っていない",
 "OBSERVED は「十分なデータから計算・描画できた」の意味であり、stylized fact が『成立する』という意味ではない",
 "確認的な主張には、事前指定された推論を持つ reference suite への `sieve test` が必要",
 "figure には経験的 reference「Nikkei 225」(content sha256 49161191…, 2461 観測)を視覚的文脈としてのみ重ねている。統計比較は行っていない",
]


def t_caveat(c: str) -> str:
    for k, v in T_CAVEAT:
        if c.startswith(k.split("{")[0][:40]) or c.startswith(k):
            return v
    for k, v in T_CAVEAT:
        if c[:25] == k[:25]:
            return v
    return c  # 未訳はそのまま(レビューで気づけるように)


def main() -> None:
    b = json.loads((RUN / "inspect_bundle.json").read_text())
    parts = [
        "<!-- 日本語レビュー版: 本番(英語)レポートの内容確認用。封印 bundle の一部ではない -->",
        "<meta charset='utf-8'>",
        "<style>body{font-family:'Hiragino Sans','Noto Sans JP',sans-serif;"
        "max-width:1360px;margin:24px auto;padding:0 16px;color:#14181f;background:#fff}"
        ".fig{border:1px solid #e5eaef;border-radius:8px;margin:20px 0;padding:16px}"
        ".st{display:inline-block;border:1px solid #2a78d6;color:#2a78d6;border-radius:4px;"
        "padding:1px 8px;font-size:12px;font-weight:600}"
        ".guide{background:#f6f8fa;border-radius:6px;padding:10px 12px;margin:10px 0}"
        "ul{margin:6px 0}li{margin:3px 0;font-size:13.5px;color:#3a4454}"
        "h1{font-size:22px}h2{font-size:16px;margin:4px 0}"
        ".meta{font-size:13px;color:#5a6577}.fig>svg{max-width:100%;height:auto}"
        ".warn{background:#fff8e6;border:1px solid #e6d9a8;border-radius:6px;"
        "padding:10px 12px;font-size:13.5px}</style>",
        "<h1>sieve inspect 日本語レビュー版 — Self-Organized Book (ZI-only, 10 seeds) "
        "+ Nikkei 225 overlay</h1>",
        f"<p class='meta'>対応する本番 bundle: <code>{RUN.name}</code> / "
        "suite: financial-stylized-facts@0.1 / dataset: "
        f"<code>{b['dataset']['dataset_id']}</code> (burn-in 200 step/run, "
        "geometry: multi_run_ensemble, 10 runs × 5001 obs → 50000 obs)</p>",
        "<div class='warn'><b>この文書について</b>: 英語レポートの全テキスト"
        "(reading guide / caveats / limitations)の日本語訳 + 同一 SVG。"
        "内容チェック用の非公式版で、封印 bundle には含まれない。</div>",
        "<h2>レポート全体の限定事項 (limitations)</h2><ul>",
        *[f"<li>{html.escape(t)}</li>" for t in T_LIMITS],
        "</ul>",
    ]
    for f in b["figures"]:
        fid = f["figure_id"]
        title, fact, guide = T_FIG[fid]
        parts.append("<div class='fig'>")
        parts.append(f"<h2>{html.escape(title)} "
                     f"<span class='st'>{html.escape(T_STATUS[f['status']])}"
                     f"</span></h2>")
        parts.append(f"<p class='meta'>対象 stylized fact: {html.escape(fact)}"
                     f" / figure_id: <code>{fid}@{f['version']}</code></p>")
        svg_path = RUN / "figures" / f"{fid}.svg"
        if svg_path.exists():
            parts.append(svg_path.read_text())
        parts.append(f"<div class='guide'><b>読み方</b>: {html.escape(guide)}</div>")
        sv = f.get("summary_values") or {}
        if sv:
            parts.append("<p class='meta'>スカラー要約: " + " · ".join(
                f"<code>{k}</code> = {v:.6g}" for k, v in sv.items()) + "</p>")
        if f.get("note"):
            parts.append(f"<p class='meta'>note: この版では未実装として登録のみ"
                         f"(計画手法は references 参照)</p>")
        cavs = f.get("caveats") or []
        if cavs:
            parts.append("<b style='font-size:13.5px'>注意点 (caveats)</b><ul>")
            parts.extend(f"<li>{html.escape(t_caveat(c))}</li>" for c in cavs)
            parts.append("</ul>")
        parts.append("</div>")
    OUT.write_text("\n".join(parts))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
