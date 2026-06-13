# 仮説と検証計画

## 仮説 1: Chartist 比率の相転移

Chartist 比率 n_c が閾値を超えると、リターン分布の裾が厚くなり
ボラティリティクラスタリングが強化される。

**検証**: experiments/03_mixed_sweep で n_c を 0.1→0.9 でスイープし、
tail exponent α と GARCH(1,1) の持続性パラメータを測定。

## 仮説 2: 情報構造と Stylized Facts の関係

Type C (過去価格パターン依存) と Type V (外部バリューシグナル依存) の
情報構造の違いが、異なる Stylized Facts プロファイルを生む。

**検証**:
- experiments/01 で Type C 単独の Stylized Facts を確認（Katahira-Chen 再現）
- experiments/02 で Type V 単独の Stylized Facts を測定
- 比較により情報構造 → 市場統計量のマッピングを得る

## 仮説 3: 内生的スイッチングによる regime 変化

Brock-Hommes スイッチングを入れると、n_c(t) の変動に応じて
市場が「効率的 regime」と「投機的 regime」を内生的に行き来する。

**検証**: experiments/05 で switching=True の長期シミュレーションを実行し、
n_c(t) の時系列と同期間の Stylized Facts の変化を測定。
