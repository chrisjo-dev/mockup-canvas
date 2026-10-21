# mockup-canvas スキル

[English](skill.md) | [한국어](skill.ko.md) | [简体中文](skill.zh-CN.md) | [日本語](skill.ja.md)

mockup-canvas スキルは、Claude Code や Codex に画面モックアップを HTML アートボードとして描かせ、ローカルのキャンバスに表示させるための指示のまとまりです。中身は [`skills/mockup-canvas/SKILL.md`](../skills/mockup-canvas/SKILL.md) にあります。このページでは、エージェントが各ステップで何をし、どのコマンドを実行するのか、そしてあなたが何を調整できるのかを説明します。

基本の考え方: **HTML ファイル 1 つが 1 画面（アートボード）、アイデア 1 つがキャンバス 1 枚で、正本は常に HTML です。** キャンバスはそれを表示するだけです。

## いつ動くか

次のような依頼で、エージェントはこのスキルを読み込みます。

- 「…のモックアップを描いて」
- 「…の画面デザインをいくつか作って」
- 「キャンバスに載せて」
- 「スマホで見せて」

既存の画面セットの修正、フロー矢印の追加、承認マーク、スマートフォンへの共有も対象です。実際のアプリのコードを実装する用途では**ありません**。

- **Claude Code** はスキルの説明から自動で選びます。名前を指定してもかまいません。
- **Codex** では `$mockup-canvas` と書くと使われます。例: `Use $mockup-canvas to draw screen mockups for this idea.`

## エージェントによる CLI の実行

スキルは `python3 <skill-dir>/scripts/canvas.py <command>` を呼び出します。`<skill-dir>` はインストール方法によって変わります。

| インストール方法 | スキルのフォルダ |
| --- | --- |
| Claude Code プラグイン | `${CLAUDE_PLUGIN_ROOT}/skills/mockup-canvas` |
| 手動、Claude Code | `~/.claude/skills/mockup-canvas` |
| 手動、Codex | `~/.codex/skills/mockup-canvas` |

エージェントはまず短いシェル関数を定義し、このページの例もそれを使います。

```bash
canvas() { python3 <skill-dir>/scripts/canvas.py "$@"; }
```

## 作業の流れ

### 1. アイデアを探す

`design/` の下に同じアイデアがあれば、続きから作業します。描く前に、仕様、既存の画面、あなたが気に入った方向や却下した方向を確認します。新しいアイデアなら次を実行します。

```bash
canvas new design wallet
```

`design/wallet/` の下に `boards/`、`assets/`、`render/`、`shared/tokens.css`（初期トークンファイル）、`canvas.json`、そして `render/` を除外する `.gitignore` が作られます。`design/` もキャンバスサーバーに登録されるので、別途 `roots add` する必要はありません。プロジェクトがない場合は `~/design/<idea>/` を使います。

### 2. トークンが先

画面を描く前に、`shared/tokens.css` で色、文字、余白、角丸を決めます。アートボードは `var(--...)` だけを使い、新しい色の値を勝手に作りません。そのため全画面の見た目がそろい、配色の変更もファイル 1 つの編集で済みます。

### 3. 描く

各アートボードは、ブラウザで単体で開いても同じ見た目になる独立した HTML ファイルです。

- 相対パスのみ: `../shared/tokens.css`、`../assets/x.png`。
- 外部リソースは Google Fonts だけ。
- カスタムタグも外部スクリプトも使いません。

ファイル名は `<ID>-<EnglishName>.html` の形式です（例: `F06-Letter.html`）。ID はアイデア名の頭文字を大文字にして 2 桁の数字を付けたものです（`W01`、`W02`、…）。プロジェクトにすでに画面 ID の体系があれば、それに従います。

### 4. 登録する

先にファイルを `boards/` に書き、それから登録します。

```bash
canvas add design/wallet boards/W01-Home.html --group current --size mobile
```

関連する画面は、フローの順に左から右へ 1 行に並べます。サイズのプリセットは `mobile`（390x844）、`tablet`（768x1024）、`desktop`（1440x900）で、`1280x800` のように `WxH` でも指定できます。`--size` を省くと、ファイル冒頭の `width: ...px; height: ...px` のスタイルからサイズを読み取り、見つからなければ 390x844 になります。

### 5. フローをつなぐ

```bash
canvas link design/wallet W01-Home.html W02-Send.html --label "送金"
```

矢印 1 本が、ある画面から別の画面への進み方を表します。画面数が指定されていれば、エージェントはその数だけ描き、足りない状態画面（空、エラー、読み込み中、権限なし）は報告で提案するだけにします。指定がなければ、状態画面もフローに含めます。

### 6. チェックする

```bash
canvas check design/wallet
canvas render design/wallet W01-Home.html
canvas overview design/wallet
```

- `check` の結果は問題 0 件でなければなりません。ファイルの欠落、壊れた `src`、`href`、`url()` の参照、`canvas.json` に未登録のアートボード、重なったアートボード、未登録のボードを指すリンク、禁止文字を検出します。
- エージェントは変更したアートボードごとに `render` の PNG を自分で開きます。複数を変更した場合は、フロー矢印とグループも写った `overview` の PNG も確認します。
- エラーの文言や壊れた画像が見つかれば、見せる前に直します。

### 7. 見せる

```bash
canvas serve
```

レジストリモードは、登録済みのすべてのプロジェクトをポート 4400 の 1 つのサーバーで表示します。URL は `http://localhost:4400/<project>/<idea>/` です。エージェントは表示された URL をそのまま伝え、サーバーは起動したままにします。既存のプロジェクトをまとめて登録するには次を実行します。

```bash
canvas roots scan ~/work ~/projects
```

デザインフォルダ 1 つだけを見るなら `canvas serve design` を使い、URL は `http://127.0.0.1:4400/<idea>/` です。プロジェクトの追加と削除は、ブラウザの一覧ページからもできます。

### 8. スマートフォンで見る

- **ホスティングページ（使える場合の既定）。** Claude artifact のような非公開のホスティングページが使える環境なら、エージェントは静的バンドルを作ってアップロードします。`index.html` がページで、残りは付属ファイルです。

  ```bash
  canvas export design/wallet ./wallet-export
  canvas artifact design/wallet <url>
  ```

  アップロード前に、アイデアごとに 1 回だけ確認します。置いたままでよいと言われれば、以後は確認せず、変更のたびに同じ URL へアップロードし直します。`canvas artifact` は URL を `canvas.json` に保存するので、別のセッションも同じページを更新します。書き出し先はアイデアフォルダの外で、アイデアフォルダを含まない場所にします。アイデアフォルダの外を指すシンボリックリンクは含めません。

- **同じネットワークでリアルタイムに。**

  ```bash
  canvas serve design --share --minutes 30
  ```

  エージェントがトークン付きの URL を伝えます。スマートフォンでは閲覧のみで、時間が来ると閉じます（`--minutes` は 1 から 240）。レジストリサーバーから登録済みプロジェクトを 1 つだけ共有するには `canvas serve --share --project NAME` を使います。レジストリの共有は起動時に登録済みのプロジェクトだけを表示し、フォルダのパスは隠します。

- **手軽な代替。** `overview` の PNG を送ることもできます。

### 9. 古いバージョンを残す

古いバージョンは決して削除しません。移動して印を付けるだけです。

```bash
canvas group design/wallet W02-Send.html "old drafts"
canvas status design/wallet W02-Send.html rejected
```

却下されたアートボードは灰色のバッジと取り消し線のタイトルで表示されるので、何を却下したかが現行バージョンの隣に残ります。

### 10. 承認が記録になる

あなたが画面を承認すると、エージェントがそれを記録します。

```bash
canvas status design/wallet W01-Home.html approved --note "ホームのレイアウトとカード一覧"
```

緑のバッジとメモが承認の記録です。「いい感じ」のような褒め言葉は承認ではありません。`canvas check` は承認済みのアートボード数も表示します（例: `Approved boards: 2/6`）。

## エージェントが守るルール

- **あなたの言語で返答する。** あなたが書いた言語で答えます。
- **`canvas.json` を手で編集しない。** 変更は `canvas add`、`link`、`status`、`group` だけで行います。直接編集すると、並行して描いているサブエージェントやあなたのドラッグ操作など、同時に起きた変更を上書きしかねません。
- **自分で起動したサーバーだけを止める。** あなたが使っている他のポートには触れません。チェックのためだけに起動したサーバーは PID か `lsof -ti:<自分のポート>` で止め、あなたのサーバーまで止めてしまう `pkill -f canvas.py` は使いません。あなたのために起動した `serve` は動かしたままにします。
- **`forbidden_chars` を守る。** `config.json` に文字が指定されていれば、アートボード、ドキュメント、報告のどこにも使いません。
- **並行して描く。** 画面が多いときは、画面のまとまりごとにサブエージェントへ分担できます。その場合、`tokens.css` はメインのエージェントが先に決めます。

## 最初のドラフトのふりかえり

依頼された画面がすべて描かれ、`check` が通れば最初のドラフトは完了です。エージェントは報告の最後に **スキル改善の提案** を付けます。デザインのチェックはステップ 6 で終わっているので、ここでは作業の進め方だけをふりかえります。

- **見るもの**（今回実際に起きたことだけ）: あなたが繰り返したり訂正したりする必要があったことと、その裏にあるルールの抜け、手戻り、`canvas` コマンドがなく手作業で回避した箇所、エラー、遅かったり不要だったりした手順、従いにくかったり矛盾したりしたルール。
- **形式**: 最大 3 つ、それぞれ「何が起きたか、影響、変えるべきルールやコマンド」を 1 行で。なければ「今回はなし」。
- **反映**: 提案だけを行います。あなたが承認した提案だけをスキルに反映し、`references/lessons.md` に 1 行追加します。

例:

```text
スキル改善の提案
1. 依頼に地図のサイズがなく T02 を描き直した、往復が 1 回増えた、地図やグラフが主役の画面では主要要素のサイズを先に確認する。
2. 古い案を 1 ファイルずつ移動した、6 画面あって時間がかかった、`canvas group` で複数ファイルを受け付ける。
```

## カスタマイズ

### 禁止文字

`~/.mockup-canvas/config.json`（または `$MOCKUP_CANVAS_HOME/config.json`）を作ります。

```json
{"forbidden_chars": ["—"]}
```

すると `canvas check` が、その文字を含むアートボードをコードポイント付きで報告します。

```text
Error: forbidden character (U+2014) found: W01-Home.html
```

### アートボードのサイズ

登録時にプリセットか正確なサイズを渡します。

```bash
canvas add design/wallet boards/W10-Dashboard.html --size desktop
canvas add design/wallet boards/W11-Kiosk.html --size 1080x1920
```

または、アートボード自体に `<body style="width:768px;height:1024px">` のようにサイズを書いて、`--size` を省略してもかまいません。

### データフォルダ

`roots.json` と `config.json` を `~/.mockup-canvas/` 以外に置くには、`MOCKUP_CANVAS_HOME` を設定します。

```bash
export MOCKUP_CANVAS_HOME=~/dotfiles/mockup-canvas
```

### スキルそのもの

`SKILL.md` はプレーンな Markdown です。承認された変更は `skills/mockup-canvas/references/lessons.md` に 1 行ずつ記録されるので、各ルールがなぜあるのかを確認できます。
