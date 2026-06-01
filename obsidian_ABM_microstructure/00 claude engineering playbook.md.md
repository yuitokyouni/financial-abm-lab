
# Claude Engineering Playbook — 永久保存版

> 思想 = ファイル。記憶頼みをやめ、置いた瞬間に自動ロードされる場所に置く。 この文書自体が、お前に渡した single source of truth の原則を自分に適用したもの。

---

## ⚡ This is all you have to do

**毎回やるのはこの3つだけ:**

1. **spec を書く / 更新する**（`/speckit.specify` → `/speckit.plan` → `/speckit.tasks`、または Plan Mode で起動）
2. **spec / plan をレビューして OK を出す**（直すならここ。一番安い checkpoint）
3. **`/speckit.implement` → 出てきた diff・図・Semgrep 結果を見る**

これ以外は設定が勝手にやる。大きな決定をしたら ADR を1枚（`/adr`）、context が 60–70% になったら `/compact focus on …`。

**一度だけのセットアップ（以後は保存される）:**

- [ ] `uv` を入れる（prereq）
- [ ] Obsidian vault を作り、この文書を `00_…` として置く
- [ ] `~/.claude/CLAUDE.md` を設置（別ファイルで同梱／§3a）
- [ ] global skills を `~/.claude/skills/` に置く（§3b）
- [ ] Semgrep plugin を入れる：`/plugin marketplace add semgrep/mcp-marketplace`
- [ ] Spec Kit を入れる：`uv tool install specify-cli --from git+https://github.com/github/spec-kit.git` → `specify check`
- [ ] 図抽出器を入れる：`pip install pylint pydeps`（JS/TS なら `npm i -g madge`）

**勝手に効いてるもの（もう触らなくていい）:** session 開始時の「何を読んでるか」自己申告 ／ ファイル編集ごとの Semgrep スキャン ／ commit ごとの構造図再生成 ／ spec を一次ソースとして毎ターン読み直す挙動。

---

## 0. どこに置くか・なぜ忘れないか

「忘れずに毎度参照する」の答えは **「自分で参照しない設計にする」**。Claude Code は毎セッション、決まったパスのファイルを自動で読む。だから _操作に効く部分_ は正規パスに置けば、お前の記憶に依存しない。人間が読む解説（この文書）は Obsidian vault に固定して、索引/encyclopedia の起点にする。

**ロードの流れ（毎セッション、お前が何もしなくても起きる）:**

```
session 起動
  └─ ~/.claude/CLAUDE.md          ← 全リポ共通の事実・cardinal rules（自動）
  └─ ./CLAUDE.md（+ 上位階層）     ← そのリポの標準事実（自動・cwd から遡って読む）
  └─ skills の description           ← 名前と説明だけ常駐、本体は必要時にロード
  └─ spec / ontology / 図           ← ファイルとして読む（Plan Mode / 指示時）
ファイル編集のたび  → Semgrep hook が変更コードを自動スキャン
commit のたび       → 構造図を再生成して docs/architecture.md に出力
```

**置き場の早見表:**

|文書|役割|置き場|誰が読む|手動参照？|
|---|---|---|---|---|
|この playbook|なぜ・手順・チートカード|Obsidian vault `00_…md`|お前|セットアップ時に1回。以後はチートカードだけ|
|global CLAUDE.md|付き合い方＋cardinal rules|`~/.claude/CLAUDE.md`|全 CC セッション|**不要（自動）**|
|skills|再利用する手順|`~/.claude/skills/<name>/SKILL.md`|CC（コマンド or 自動）|**不要（自動）**|
|project CLAUDE.md|そのリポの事実|リポ直下 `CLAUDE.md`|CC＋お前|**不要（自動）**|
|ontology / spec / ADR / 図|用語・意図・決定・構造|リポ内 `ontology.md` `specs/` `docs/`|CC＋お前|**不要（自動）**|

vault はリポの `docs/` を取り込む（vault フォルダにリポを置く or `docs/` を symlink）と、`docs/architecture.md` の Mermaid も同じ画面で描画される。**索引・spec置き場・図ビューアが1面に畳まれる** ── これが一番レバレッジの効く一手。

---

## 1. セットアップ（1回やれば保存される）

### A. Global（全プロジェクト共通・1回だけ）

順番に意味がある。下ほど上に依存する。

**0) `uv` を入れる** — 目的：Spec Kit と Semgrep CLI の前提。無ければ `curl -LsSf https://astral.sh/uv/install.sh | sh`。

**1) Obsidian vault を作る → この文書を `00_OPERATING_MANUAL.md` として置く** — 目的：索引/encyclopedia の起点。以後ここに ontology・ADR・図が集まる。

**2) `~/.claude/CLAUDE.md` を設置**（§3a の中身、または同梱ファイル `claude-global-CLAUDE.md` をコピー） — 目的：**毎回の初期設定を永久に消す**。付き合い方と cardinal rules を一度だけ固定。lean に保つ（手順はここに書かない）。

**3) global skills を `~/.claude/skills/` に置く**（§3b） — 目的：再ペースト地獄の解消。手順は skill 化すると必要時だけロードされる。

**4) Semgrep plugin を入れる** — 目的：脆弱性の常駐化（IDE 不要）。

```
/plugin marketplace add semgrep/mcp-marketplace
```

→ marketplace から semgrep plugin を有効化。MCP＋hook＋skill が一括で入り、**生成ファイルごとに自動スキャン、findings が出たら clean になるまで再生成を促す**（SAST＋依存＋secrets、Trail of Bits / OWASP ルール、要 Python 3.10+）。

**5) Spec Kit を入れる** — 目的：SDD の型。意図をファイルに固定して drift を前倒し検出。

```
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
specify check          # 導入確認
specify version
```

⚠ **PyPI の `specify-cli` は別物（非公式）。必ず上の git ソースから入れる。** `init` は per-project（§1B）。

**6) 図抽出器を入れる** — 目的：構造図を _LLM に描かせず_ 決定論的に抽出（LLM はエッジを幻覚する）。

```
pip install pylint pydeps      # pyreverse(クラス/パッケージ図) + pydeps(import依存)
# JS/TS なら：npm i -g madge dependency-cruiser
```

### B. Per-project（新しいリポごとに1回）

**1) `specify init`** — 目的：SDD のディレクトリ構造と `/speckit.*` コマンドを注入。

```
cd <repo>
specify init . --integration claude        # flag名はバージョン差あり → specify init --help で確認
```

**2) constitution を固める**（`.specify/memory/constitution.md`） — 目的：プロジェクトの mission / stack / 方針を不変の一次ソースに。最初に1回書く。

**3) project `CLAUDE.md` を書く**（§3c テンプレ） — 目的：そのリポの **標準事実だけ**。手順・lint規則・コードスニペットは書かない。

**4) `ontology.md` を書く**（§3d テンプレ） — 目的：ジャーゴンを固定。agent はここを一次解釈に使う。**Type C/V は J-REIT 固有で SG とは無関係**、のような混同注意も最初に明記。

**5) 構造図スクリプト＋配線**（§3e） — 目的：常に最新の図を Obsidian で見れる状態に。per-edit ではなく **commit ごと**に回す（thrash 回避）。

---

## 2. 毎回のループ（per-task）

自動化が大半を吸収したので、**お前の手動は実質3アクション**。

|ステップ|何を|目的|自動 / 手動|
|---|---|---|---|
|A|`/speckit.specify`→`plan`→`tasks`（or Plan Mode 起動）|意図をファイル化。「全然ちゃう」を spec 段階に前倒し|**手動**|
|–|session kickoff の「何を読んでるか」要約|「どこまで分かってるか」確認|自動（CLAUDE.md が指示）|
|B|spec / plan をレビューして承認|一番安い checkpoint|**手動**|
|C|`/speckit.implement`|実装|半自動（Plan→承認後に走る）|
|–|ファイル編集ごとの Semgrep|脆弱性ブロック|自動（plugin hook）|
|D|diff・`docs/architecture.md`・Semgrep 結果を確認|監査|**手動（見るだけ）**|
|–|commit|構造図再生成|自動（pre-commit）|
|E|非自明な決定をしたら `/adr`|provenance（決定の系譜）|手動・任意|
|–|context 60–70% で `/compact focus on …`|context 管理|手動・任意|

**「壁うち」したくなったら**：chat に prose を吐いて伝書鳩するのではなく、`/speckit.specify`（or `spec-new` skill）で spec に落とす。思考の出力が揮発せず、お前と CC が同じファイルを見る。これで伝書鳩が消える。

---

## 3. Claude への指示集（中身）

### 3a. `~/.claude/CLAUDE.md`（global・lean）

> 同梱の `claude-global-CLAUDE.md` をそのまま `~/.claude/CLAUDE.md` にコピーすればよい。中身は以下と同一。

```markdown
# ~/.claude/CLAUDE.md — Yuito / global operating instructions
<!-- 全プロジェクトに効く。標準事実と cardinal rules のみ。手順は skill、強制は hook へ。 -->

## How to work with me
- 忖度なし・ガチ。弱い前提や間違いは遠慮なく潰し、俺が言語化してない blind spot を先回りで指摘する。reassurance は不要、判断は中身で。
- 初心者向けに薄めるな。常にプロ前提の 120%。分からなければ俺が訊く。
- casual JP / romaji、簡潔に。over-format（過剰な見出し・箇条書き・太字）は避ける。
- 状況やタイミングではなく、アイデアの中身で評価する。

## Cardinal rules（全リポ共通）
1. Single source of truth = files。リポ内に書いてあることは読め、俺に訊き返すな。会話で受けた意図は、まずファイルに落としてから実装する。
2. Spec first。コードは spec の build 出力。spec / constitution に無いものを勝手に作らない。噛み合わなければ実装を止めて spec に戻る。`specs/` と `.specify/memory/` が一次ソース。
3. Plan before act。デフォルトでまず計画を出し、承認後に書き込む。「何を作るか」を俺がレビューできる状態にしてから進む。
4. Respect the layers。標準事実→CLAUDE.md ／ 手順→skill ／ 強制→hook ／ 隔離+永続記憶→subagent。混同しない。lint/format 規則やコードスニペットを CLAUDE.md に書かない（hook と file:line 参照を使う）。
5. Read the ontology。プロジェクト固有語は `ontology.md` を読んで解釈する。一般的な意味で勝手に解釈しない。

## Session kickoff（最初の実タスクの前に1回だけ）
- いま読み込んでいるもの（このファイル / project CLAUDE.md / 該当 spec / ontology）を1〜2行で要約して提示する。
- context が不確かなら `/memory` での確認を促す。
→ 毎回「どこまで分かっているか」を明示する。
```

### 3b. Skills

**`~/.claude/skills/spec-new/SKILL.md`**

```markdown
---
name: spec-new
description: 新機能/タスクの着手時に spec を共著する。Yuito が「壁うち」したくなったら prose で返さず spec ファイルに落とす。Spec Kit 導入リポなら /speckit.specify に繋ぐ。
---

# spec-new — 意図をファイルに固定する

新しい機能/タスクを始めると言われたら、いきなりコードを書かない。まず spec を共著する。

1. 不足している場合のみ、最大3問だけ訊く。対象は outcomes / scope 境界 / constraints / 既存の決定 / 検証基準 のうち曖昧な点。憶測で埋めない。
2. spec を書く。EARS 風に「WHEN <条件> THE SYSTEM SHALL <振る舞い>」で検証可能にする。outcomes・scope 外（明示）・constraints・前提・タスク分解・受け入れ条件を含める。
3. Spec Kit 導入リポなら /speckit.specify → /speckit.plan → /speckit.tasks に乗せ、各成果物を該当ディレクトリへ書く。未導入なら specs/NNN-<name>.md に書く。
4. 要件の完全性・明確性・一貫性を検証する checklist（"英語の unit test"）を添える。
5. そこで止めてレビューを求める。承認前に実装へ入らない。
```

**`~/.claude/skills/adr/SKILL.md`**

```markdown
---
name: adr
description: 非自明な設計上の意思決定を記録する。アーキテクチャ/トレードオフのある選択をしたら、決定の系譜（provenance）を残す。
---

# adr — Architectural Decision Record

非自明な設計判断（技術選定・構造変更・トレードオフのある選択）をした/する直前に、docs/adr/NNNN-<title>.md を1枚書く。

- Context: なぜこの判断が必要か
- Decision: 何を選んだか（断定形）
- Consequences: 良い面 / 悪い面 / 後で効く制約
- Alternatives considered: 却下した選択肢と理由

archive されても理由が残る形で書く。後の変更提案がこれを参照できるようにする。
```

> kickoff（session 開始時の自己申告）は手順ではなく「常に効く事実」なので skill ではなく CLAUDE.md 側に置いた（§3a）。

### 3c. project `CLAUDE.md` テンプレ（リポ直下）

```markdown
# CLAUDE.md — <project> / 標準事実のみ

## What this is
<1–2行：このリポの目的>

## Stack / entrypoints
- 言語/FW:
- 主要エントリ: `path/to/main`（file:line で指す。スニペットは貼らない）
- 主要パッケージ/モジュール:

## Conventions
- <このリポ固有の規約のみ。一般論は書かない>

## Where the truth lives
- spec: `specs/` および `.specify/memory/constitution.md`
- 用語: `ontology.md`
- 構造図: `docs/architecture.md`
- 決定: `docs/adr/`

<!-- 手順は skill、強制は hook、隔離は subagent。ここには「動かない事実」だけ。 -->
```

### 3d. `ontology.md` テンプレ（リポ内）

```markdown
# ontology.md — <project> / 用語定義
<!-- ここの定義を agent は一次解釈に使う。曖昧語はここで固定する。 -->

## 用語
- **<term>**: <定義>。<文脈 / 単位 / 由来>。

## 混同しやすい語（注意）
- 例) **Type C / V** は J-REIT モデリング固有の概念であり、Speculation Game とは無関係。
  SG は homogeneous エージェント（Type C/V の区別なし）。混同しない。
```

### 3e. 構造図スクリプト＋配線

**`scripts/generate_diagrams.sh`** — 決定論的に図を生成し、Obsidian が描画できる markdown に書く。

```bash
#!/usr/bin/env bash
# 前提: pip install pylint pydeps （pyreverse は pylint 同梱）
set -euo pipefail

PKG="${1:-your_package}"        # 対象パッケージのパス
OUT="docs/architecture.md"
mkdir -p docs .diagrams

# クラス図 + パッケージ図 を mermaid で出力
# ※ pylint が古く -o mmd 非対応なら -o dot/plantuml に切替
pyreverse -o mmd -p "$PKG" "$PKG" -d .diagrams >/dev/null

{
  echo "# Architecture (auto-generated $(date +%F))"
  echo
  echo '## Packages'; echo '```mermaid'; cat ".diagrams/packages_${PKG}.mmd"; echo '```'
  echo
  echo '## Classes';  echo '```mermaid'; cat ".diagrams/classes_${PKG}.mmd";  echo '```'
} > "$OUT"

echo "wrote $OUT"
```

**`.git/hooks/pre-commit`**（`chmod +x` する）— commit ごとに最新化。

```bash
#!/usr/bin/env bash
bash scripts/generate_diagrams.sh your_package
git add docs/architecture.md
```

Obsidian は `docs/architecture.md` 内の ` ```mermaid ` を直接描画する。 （CC のターンごとに回したい場合だけ、settings の Stop hook に同スクリプトを足す。ただし per-edit はやめる＝重い。）

---

## 4. Honest notes

- **コスト**：SDD は agent が spec/plan/tasks を毎ターン読み直すので、素の prompt より概ね **+20–40% トークン**。その代わり「作り直し」サイクルが激減して相殺。試作は vibe、本番は spec、で使い分けろ。
- **可視化は監査ツールであって、壊れたパイプラインの修理ツールではない。** §1–§2（spec ＋ files-as-truth）を先に入れること。図と Semgrep は _出力を点検_ するもので、_誤りを生む handoff_ は直さない。
- **subagent は stateless worker**。別 Claude / 別セッションで作ったものは状態が伝わらない。ハーネスは「コピー」ではなく「同じファイルを読ませる」で共有する。
- **preview 機能はコマンドが変わり得る**（Agent View＝`claude agents` は research preview、Spec Kit の flag 名もバージョン差あり）。迷ったら一次ソースで確認。

### 一次ソース

- Claude Code memory / imports：https://docs.anthropic.com/en/docs/claude-code/memory
- Claude Code session 管理（plan mode / compact / rewind）：https://claude.com/blog/using-claude-code-session-management-and-1m-context
- Semgrep plugin：https://claude.com/plugins/semgrep ／ https://semgrep.dev/docs/mcp
- GitHub Spec Kit：https://github.com/github/spec-kit ／ https://github.github.io/spec-kit/installation.html
- OpenSpec（ADR 同梱の代替）：https://intent-driven.dev/knowledge/openspec/

---

_v1 — 必要に応じて ontology / project CLAUDE.md を各リポで育てていく。この文書は vault の `00_` に固定。_