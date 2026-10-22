# mockup-canvas

**AI エージェントと画面を企画し、レビューし、作る。ローカルの Figma のようなキャンバスに HTML モックアップを描き、レビューし、承認した画面を実際のアプリのコードにして、モックアップと見た目で比較する、Claude Code と Codex のための 3 つのスキルです。**

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Claude Code と Codex に対応](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex-6b4fbb.svg)](#クイックスタート-claude-code-プラグインまたは-codex-スキルをインストール)
[![pip 依存なし: Python 標準ライブラリ、Chrome は PNG レンダリング用](https://img.shields.io/badge/no%20pip%20deps-Python%20stdlib%20%2B%20Chrome-brightgreen.svg)](#faq)

**mockup-canvas とは？** mockup-canvas は chrisjo-dev による無料のオープンソース（MIT）Claude Code プラグインで、OpenAI Codex からも使えます。企画、レビュー、実装を受け持つ 3 つのスキルでできています。**mockup-canvas** は、AI エージェントに画面モックアップをプレーンな HTML ファイルとして描かせ、それをローカルの Figma のようなキャンバスに並べて、パン、ズーム、配置、フロー矢印での接続、承認ができるようにします。**mockup-review** は、エージェントがそれらの画面をレビューし、指摘を該当するアートボードにコメントとして直接残します。**mockup-to-code** は、承認された画面をあなたのアプリの実際のコードにし、動いている各ルートをキャプチャしてモックアップとピクセル単位で比較し、意図した差だけが残るまで直します。Python 標準ライブラリだけで動き pip の依存はなく、Google Chrome（または Chromium、Edge）は PNG のレンダリングとキャプチャにだけ使います。

AI アシスタント向けの要約は [llms.txt](llms.txt) にあります。

![デモ: AI エージェントがモバイルアプリの画面を描くと、mockup-canvas のボードにすぐ表示される様子](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/demo.gif)

![サンプルのアイデア TrailMate の全体図: キャンバス上の 6 枚の HTML アートボードがフロー矢印でつながり、2 枚に承認マークが付いている](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/_overview.png)

## 3 つのスキル

**描く → レビュー → 承認 → 実装 → 比較**

| スキル | 使うとき | すること | 依頼の例 |
| --- | --- | --- | --- |
| `mockup-canvas` | 企画段階、アプリのコードより前 | 画面ごとに HTML アートボードを描き、フローをつなぎ、あなたの承認をキャンバスに記録します。 | `習慣トラッカーアプリのモックアップを描いて。ホーム、習慣の追加、週間統計の画面。` |
| `mockup-review` | 画面を描き終え、別の目で確認したいとき | すべてのボードとフローを仕様とチェックリストに照らして確認し、`[must]`、`[should]`、`[could]` のコメントをボードに残し、`review.md` を書き、承認、修正、却下を推奨します。ボードの編集や状態の設定はしません。 | `design/habits のモックアップをレビューして、足りないものを教えて。` |
| `mockup-to-code` | 承認済みのボードがあるとき | 承認されたボードをあなたのアプリのフレームワークで実装し、動いている各ルートを `canvas compare` でボードと比較し、ルートとファイルを `canvas impl` で記録します。 | `承認済みの習慣トラッカーの画面をアプリに実装して。` |

承認するのはいつもあなたです。あなたが承認したボード（`canvas status ... approved` で記録）だけが実装されます。3 つのスキルはどれも同じ `canvas.py` CLI を使います。

## AI エージェントでまずモックアップを描く理由

mockup-canvas が存在するのは、UI を文章で説明するとあいまいになるからです。AI エージェントとプロダクトを企画するときは、画面に合意する前にまず画面を見る必要があります。AI とサービスを企画し作っていく中で、必要なものを先に目に見える形にし、そこから作業を進めるための企画ツールとして作りました。「上にヒーローバナー、その下にカード一覧があるホーム」という一文は、実際に見るまではあなたとエージェントで違う意味になりがちです。mockup-canvas はこの工程を一番最初に持ってきます。エージェントが画面ごとに小さな HTML ファイルを描き、キャンバスがそれを横に並べ、あなたは見たものから判断します。この画面は承認、あの画面は却下、別案もほしい、と伝えれば、エージェントの作業中にボードが更新されていきます。アプリのコードは画面が承認されてから書き始め、その後も承認されたモックアップが見た目の仕様として残ります。作った画面をモックアップと比較するので、承認したとおりのものができあがります。すべてのモックアップはアカウントなしでどのブラウザでも開ける独立した HTML ファイルとしてリポジトリに残ります。

## 主な機能

**キャンバス**（`viewer.html`、ローカルで配信）

- キャンバスでは、デザインツールのようにパンとズームができます。どの倍率でも引き伸ばしたビットマップではなく、くっきり描き直します。
- キャンバスは、アートボードをドラッグして並べた位置を `canvas.json` に保存します。移動は元に戻す、やり直すが可能です。
- キャンバスは画面間にフロー矢印を描き、その画面へ進むボタンや操作の名前を矢印に付けます。
- キャンバスは承認、却下のバッジを表示し、メモはアートボードのタイトルにカーソルを合わせると表示します。
- キャンバスは、実装が記録されたボードに青い `built` バッジ（カーソルを合わせるとルートを表示）を、レビューコメントのあるボードにコメント数を表示します。コメント数をクリックするとパネルで読めます。
- キャンバスはアートボードを折りたためるグループにまとめます。例: `current`、`old drafts`。
- キャンバスはボードが多くても滑らかに動きます。表示範囲の近くのボードだけが実際のページを保持し、縮小時（倍率おおむね 30〜40% 未満）はキャッシュした PNG サムネイルを表示し（サーバーで開いたとき）、一度表示したボードは再読み込み中も白い空のカードではなくサムネイルを表示し、画面の更新はアニメーションフレームごとに 1 回にまとめます。サムネイルはバックグラウンドで低い優先度で作ります。71 枚のアートボードがあるキャンバス（1440x900、Apple M4、headless Chrome）で測ると、初回表示でもサムネイルのキャッシュ後でも、パンとズームは約 59〜60 FPS、p95 のフレーム時間は約 20 ms で、50 ms を超えるフレームはありません。`python3 tests/perf_check.py <アイデアフォルダ>` で再測定できます。
- キャンバスはライブリロードに対応しています。サーバーが 1 秒ごとにファイルの変更を確認するので、アートボードや `canvas.json` を編集すると、開いているキャンバスが 1 秒ほどで更新されます。
- 1 つのキャンバスサーバーが、登録済みのすべてのプロジェクトとアイデアを一覧ページに表示します。
- キャンバスはスマートフォンでも確認できます。同じネットワーク内でリアルタイムに見る共有モードと、どこにでも置ける静的エクスポートがあります。

**エージェントスキル**（`skills/<skill>/SKILL.md`）

- `mockup-canvas` は、Claude Code や Codex に、モックアップを描く、登録する、つなぐ、チェックする、見せる手順を順番に伝えます。古いバージョンを削除せずに残し、あなたの承認を正式な記録として扱います。
- `mockup-review` は、状態画面の網羅、フロー、トークンの一貫性、基本的なアクセシビリティ、親指の届く範囲、仕様との一致を確認し、指摘を重要度タグ付きで該当ボードに残します。
- `mockup-to-code` は、モックアップのトークンをアプリに移し、共通のシェルを先に作ってから、承認されたボードを 1 枚ずつ実装してボードと比較します。
- 各スキルは最初の作業が終わると、スキル自体の改善案を短いふりかえりとして提案します。

**CLI**（`skills/mockup-canvas/scripts/canvas.py`）

- CLI は pip の依存がない約 3,300 行の Python 3 ファイル 1 つ（標準ライブラリのみ、Python 3.8 以上）で、コマンドは 16 個です: `serve`、`roots`、`new`、`add`、`group`、`render`、`check`、`overview`、`export`、`link`、`status`、`artifact`、`snap`、`compare`、`impl`、`comment`。
- CLI は Chrome（または Chromium、Edge）を、ボードのレンダリングとアプリ画面の PNG キャプチャにだけ使います。

## クイックスタート: Claude Code プラグインまたは Codex スキルをインストール

Claude Code に mockup-canvas をインストールするには、下の `/plugin` コマンドを 2 つ実行します。1 つ目で `chrisjo-dev/mockup-canvas` のマーケットプレイスを追加し、2 つ目で 3 つのスキルすべてを含むプラグインをインストールします。pip パッケージは不要で、Chrome は PNG のレンダリングにだけ使います。

### Claude Code プラグイン

```text
/plugin marketplace add chrisjo-dev/mockup-canvas
/plugin install mockup-canvas@mockup-canvas
```

あとは普段の言葉で頼むだけです。

```text
習慣トラッカーアプリのモックアップを描いて。ホーム、習慣の追加、週間統計の画面。
```

エージェントがアイデアのフォルダを作り、画面を描き、キャンバスサーバーを起動して、`http://localhost:4400/<project>/<idea>/` のような URL を教えてくれます。

### 手動インストール（Claude Code、Codex）

```bash
git clone https://github.com/chrisjo-dev/mockup-canvas.git
cd mockup-canvas
./install.sh            # ~/.claude/skills と ~/.codex/skills にすべてのスキルをリンク
```

- 片方だけなら `./install.sh --claude` または `./install.sh --codex`。
- `./install.sh --dry-run` は何も変更せず、実行内容だけを表示します。
- mockup-canvas だけでなく、`skills/` 以下のすべてのスキルフォルダ（mockup-canvas、mockup-review、mockup-to-code）をリンクします。同じ名前のスキルなど既存のものがインストール先にあれば、先に `~/.mockup-canvas/backup/<timestamp>/` へ移動してからリンクに置き換えます。何度実行しても安全です。

Codex ではスキル名で呼び出します。例: `Use $mockup-canvas to draw the sign-up flow.`、`Use $mockup-review to review the sign-up mockups.`、`Use $mockup-to-code to build the approved sign-up screens.`

### エージェントなしでサンプルを開く

```bash
python3 skills/mockup-canvas/scripts/canvas.py serve examples
```

`http://127.0.0.1:4400/trailmate/` を開くと、[`examples/trailmate`](https://github.com/chrisjo-dev/mockup-canvas/blob/main/examples/trailmate/canvas.json) の 6 画面のサンプルが見られます。

## mockup-canvas の仕組み

各スキルはそれぞれの `SKILL.md` の手順に従います。各ステップのコマンド、ルール、カスタマイズ方法は [docs/skill.ja.md](docs/skill.ja.md) にまとめています。

### 描く（mockup-canvas）

1. **アイデアを探す、または作る。** `design/<idea>/` がすでにあれば続きから作業します。なければ `canvas new <design dir> <idea>` を実行し、このときデザインフォルダがキャンバスサーバーに自動登録されます。
2. **トークンが先。** 画面を描く前に、色、文字、余白、角丸を `shared/tokens.css` に決めます。アートボードは `var(--...)` だけを使います。
3. **アートボードを描く。** 1 画面が `boards/` 内の 1 つの HTML ファイルで、名前は `W01-Home.html` の形式です。単体で開いても同じ見た目でなければなりません。相対パスのみ、外部スクリプトなし、外部リソースは Google Fonts だけです。
4. **登録する。** `canvas add <idea dir> boards/W01-Home.html --group current --size mobile` でキャンバスに載せます。内容が切れる場合は、新しい `--size` で `add` を再実行してボードのサイズを変えます。
5. **フローをつなぐ。** `canvas link <idea dir> W01-Home.html W02-Detail.html --label "開く"` で矢印を描きます。空、エラー、読み込み中、権限なしといった状態画面も描きます。画面数が指定されている場合は描かずに、報告で提案だけします。
6. **チェック、レンダリング、全体図。** `canvas check` の結果は問題 0 件でなければなりません。見せる前に、エージェントが `canvas render`（スクロールの下の内容は `--full-page`）と `canvas overview` の PNG を自分で確認します。
7. **サーバーを起動して URL を伝える。** `canvas serve`（レジストリモード、ポート 4400）は 1 つのサーバーですべてのプロジェクトを表示します。エージェントはサーバーを動かしたまま URL を伝えます。
8. **スマートフォンで見る。** `canvas export` で作った静的バンドルを非公開のホスティングページにアップロードするか、同じネットワーク内で `canvas serve <design dir> --share` を使ってリアルタイムに見ます。
9. **古いバージョンを残す。** 何も削除しません。古い画面は `old drafts` グループへ移し、`rejected` にします。
10. **承認が記録になる。** あなたが画面を承認すると、エージェントが `canvas status ... approved --note "..."` を実行します。ただ褒めただけでは承認になりません。
11. **最初のドラフトのふりかえり。** 最初のドラフトが終わると、エージェントはデザインではなく作業の進め方をふりかえり、スキルの改善案を最大 3 つ挙げます。あなたが承認しない限り、スキルは変更しません。

### レビュー（mockup-review）

1. **文脈を読む:** 画面のもとになった仕様、`tokens.css`、`canvas.json`、以前の `review.md` があればそれも読みます。
2. **機械的なチェック:** `canvas check` と `canvas overview`。`check` が報告した問題はすべて指摘になります。
3. **ボードごととフロー:** 現在のボードを 1 枚ずつレンダリングし（`--full-page` も）、HTML を読み、チェックリストに沿って確認します。入口の画面からリンクをたどり、行き止まりや到達できないボードを探します。
4. **ボードにコメント:** 指摘 1 つにつき `canvas comment` 1 つで、先頭に `[must]`、`[should]`、`[could]` を付けます。
5. **報告:** `design/<idea>/review.md` を書き、ボードごとに承認、修正、却下を推奨します。状態の設定はあなたの判断に残します。

レビュアーはアートボード、トークン、`canvas.json` を編集しません。画面を描いたエージェントやセッションとは別のところで動かすと最もよく機能します。

### 実装（mockup-to-code）

1. **範囲:** `canvas impl <idea dir>` で承認済みのボードを一覧します。実装するのはそれだけで、承認済みのボードがなければ先に確認します。
2. **プロジェクトを調べる:** フレームワーク、ルーティング、スタイルの方式、既存のコンポーネントとトークン、データの契約、テスト、lint、開発サーバーのコマンドを確認します。
3. **トークンは一度だけ、シェルが先:** ボードのトークンをアプリのトークン体系の 1 か所に移し、共通のレイアウト、ヘッダー、ナビゲーションを作ります。
4. **画面を 1 つずつ:** 承認されたボード 1 枚を 1 つのルートに実装します。空、読み込み中、エラーは実際の状態として作り、実際のデータにつなぎます（仮のスタブは印を付けて報告します）。
5. **比較:** `canvas compare <idea dir> W01-Home.html --url http://localhost:5173/` が `side.png`、`diff.png`、不一致率を含む `report.json` を書き出します。エージェントは画像を自分で見て直し、残る差がすべて意図したもので名前を挙げられるまで比較を繰り返します。
6. **記録とチェック:** `canvas impl <idea dir> W01-Home.html --route / --file src/pages/Home.tsx` で記録し、プロジェクトのテスト、lint、型チェックを実行してから、すべての画面をまとめて 1 回仕上げます。

### 会話の例

依頼がキャンバス上の画面になり、承認と修正がやり取りされ、最初の下書きがスキル改善の提案で終わるまでを短くまとめた会話です。

> **あなた:** 週末ハイカー向けのトレイルアプリのモックアップを描いて。4 画面で。
>
> **エージェント:** `design/trailmate/` を作り、先にトークンを決めました。T01-Home、T02-TrailDetail、T03-Invite、T04-Plan を描いて順につなぎ、`check` は問題 0 件です。`http://localhost:4400/myapp/trailmate/` で確認できます。4 画面と指定いただいたので描いていませんが、ホームの空状態と招待画面のエラー状態もあるとよさそうです。
>
> **あなた:** ホームはいいね。詳細画面の地図をもっと大きくして。
>
> **エージェント:** T01-Home を「ホームフィードの構成」というメモ付きで承認にしました。元の T02 は "old drafts" に移して却下にし、地図を横幅いっぱいにした T02-TrailDetail-v2 を追加しました。キャンバスはもう更新されています。
>
> スキル改善の提案: 1. 依頼に地図のサイズがなく描き直した、往復が 1 回増えた、地図やグラフが主役の画面では主要要素のサイズを先に確認する。

## CLI リファレンス

まず、スキルの場所に合わせてシェル関数を定義します。

```bash
canvas() { python3 ~/.claude/skills/mockup-canvas/scripts/canvas.py "$@"; }
```

各コマンドの使い方は `canvas <command> -h` で確認できます。

| コマンド | 内容 | 例 |
| --- | --- | --- |
| `serve` | キャンバスサーバーを起動します。フォルダを指定しなければ登録済みの全プロジェクトを表示するレジストリモード、指定すればそのデザインフォルダだけを表示します。`--share` はトークン付きでローカルネットワークに公開します。レジストリモードの `--share --project NAME` はプロジェクトを 1 つだけ共有します。 | `canvas serve`<br>`canvas serve design --share --minutes 30` |
| `roots list` | 登録済みのデザインフォルダを一覧表示します。 | `canvas roots list` |
| `roots add` | デザインフォルダを登録します。名前も指定できます。 | `canvas roots add ~/work/app/design --name app` |
| `roots remove` | 名前を指定して登録を解除します。ファイルには触れません。 | `canvas roots remove app` |
| `roots scan` | 指定したディレクトリの下からデザインフォルダを探して登録します。 | `canvas roots scan ~/work ~/projects` |
| `new` | アイデアのフォルダ（`boards/`、`shared/tokens.css`、`canvas.json` など）を作り、デザインフォルダを登録します。 | `canvas new design wallet` |
| `add` | アートボードをキャンバスに登録します。必要なら `boards/` にコピーします。サイズ: `mobile` 390x844、`tablet` 768x1024、`desktop` 1440x900、または `WxH`。登録済みのボードは新しい `--size` で再実行するとサイズが変わります。 | `canvas add design/wallet boards/W01-Home.html --group current --size mobile` |
| `group` | アートボードをグループに移します。 | `canvas group design/wallet W01-Home.html "old drafts"` |
| `link` | 2 つのアートボードの間にフロー矢印を追加します。 | `canvas link design/wallet W01-Home.html W02-Send.html --label "送金"` |
| `status` | `draft`、`approved`、`rejected` を設定し、メモを付けられます。 | `canvas status design/wallet W01-Home.html approved --note "レイアウト確定"` |
| `artifact` | アイデアのホスティングページの URL を保存します。URL なしで実行すると保存済みの URL を表示します。 | `canvas artifact design/wallet https://example.com/page` |
| `render` | headless Chrome でアートボードを登録サイズのまま PNG にし、`render/` に保存します。ファイル指定がなければすべてをレンダリングします。`--full-page` はスクロールの高さ全体をキャプチャし、`--wait MS`（既定 1000）はページの load イベント後に待つ時間です。 | `canvas render design/wallet W01-Home.html --full-page` |
| `overview` | 矢印とグループを含むキャンバス全体を `render/_overview.png` に書き出します。 | `canvas overview design/wallet` |
| `check` | ファイルの欠落、壊れた参照、未登録のアートボード、重なり、つながり先のないリンク、禁止文字、存在しない実装ファイルを報告します。承認数とコメント数も表示します。 | `canvas check design/wallet` |
| `export` | 読み取り専用の静的キャンバスバンドルを作ります。`index.html` に boards、shared、assets が付きます。出力フォルダはアイデアフォルダ自身、その内側、それを含む上位フォルダにはできず、アイデアフォルダの外を指すシンボリックリンクはスキップします。 | `canvas export design/wallet ./wallet-export` |
| `snap` | 動いているアプリのページ（http または https）を headless Chrome で指定サイズ（既定 `mobile`）ちょうどにキャプチャします。`--wait MS`（既定 3000）はページの load イベント後に実際に待つ時間で、`--full-page` はスクロールの高さ全体をキャプチャします。 | `canvas snap http://localhost:5173/ --size mobile --out home.png` |
| `compare` | ボードを登録サイズでレンダリングし、アプリを同じサイズでキャプチャ（`--url`）するか PNG（`--png`）を受け取って、`board.png`、`app.png`、`diff.png`（不一致はマゼンタ）、`side.png`（ボード、アプリ、差分を横に並べたもの）、`report.json`（`mismatch_percent` を含む）を `<idea>/compare/<board id>/` または `--out DIR` に書き出します。`--threshold N`（0 から 255、既定 24）は色チャンネルがどれだけ違えば不一致ピクセルとみなすかの基準、`--ignore-top N` と `--ignore-bottom N` は上下の帯を集計から外し、`--align-top N` はボードが描いた偽のステータスバーの下にアプリを N px 下げて置きます。`--wait MS`（既定 3000）。 | `canvas compare design/wallet W01-Home.html --url http://localhost:5173/ --align-top 47` |
| `impl` | ボードを指定すると、それを実装したルートとソースファイル（プロジェクトルートからの相対パス）を記録し、`--clear` で記録を消します。ボードを指定しないと、承認済みのボードと実装の有無を一覧し、`--strict` は未実装のボードがあれば 1 で終了します。 | `canvas impl design/wallet W01-Home.html --route / --file src/pages/Home.tsx`<br>`canvas impl design/wallet --strict` |
| `comment` | ボードにレビューコメントを追加し（`--by NAME` で書き手を指定）、テキストなしで実行すると一覧を表示し、`--clear` で削除します。 | `canvas comment design/wallet W02-Send.html "[must] エラー状態がない" --by reviewer` |

## キャンバスのショートカット

| 入力 | 動作 |
| --- | --- |
| 空いている場所をドラッグ | パン |
| マウスホイール、トラックパッドのスクロールやピンチ | ポインター位置を中心にズーム |
| 1 本指ドラッグ、2 本指ピンチ（タッチ） | パン、ズーム |
| `F` | すべてのアートボードが収まるように表示 |
| `L` | フロー矢印の表示、非表示 |
| アートボードのタイトルをクリック | ID をコピー（例: `W01-Home`） |
| アートボードのタイトルをダブルクリック | そのアートボードだけを新しいタブで開く |
| アートボードのタイトルをドラッグ | 移動して位置を保存 |
| `Cmd+Z` / `Ctrl+Z` | 直前の移動を元に戻す |
| `Cmd+Shift+Z` / `Ctrl+Shift+Z`、または `Cmd+Y` / `Ctrl+Y` | やり直す |
| グループの見出しをクリック | グループを折りたたむ、展開する |
| アートボードのタイトルにカーソルを合わせる | メモを表示 |
| コメント数をクリック | ボードのコメントを開く、`Esc` で閉じる |

静的エクスポートではアートボードを移動できません。共有モードでは、サーバーを `--share-edit` 付きで起動したときだけ移動が保存されます。

## フォルダ構成

アイデアはプロジェクトの中に置きます。プロジェクトがなければ `~/design/` を使います。

```text
<project>/design/<idea>/
  canvas.json         配置、グループ、フロー矢印（links）、状態とメモ、実装の記録、コメント、artifact_url
  boards/*.html       アートボード。1 ファイル 1 画面（例: W01-Home.html）
  shared/tokens.css   色、文字、余白、角丸。すべてのアートボードがリンクする
  assets/             画像、フォント
  render/             チェック用に生成する PNG と、低倍率のキャンバス用の render/.thumbs/
  compare/            ボードごとの比較結果: board、app、diff、side の PNG と report.json
  review.md           mockup-review のレポート（レビューを実行したとき）
```

`render/` と `compare/` は生成物で、アイデアフォルダの `.gitignore` で git の対象外にしています。

ユーザーデータは `~/.mockup-canvas/` にあります。`MOCKUP_CANVAS_HOME` で場所を変えられます。

```text
~/.mockup-canvas/
  roots.json    登録済みのデザインフォルダ（レジストリモードで使用）
  config.json   オプション。例: {"forbidden_chars": ["—"]}
  backup/       install.sh が退避した既存ファイル
```

`forbidden_chars` は、アートボードに含まれていると `canvas check` が報告する文字のリストです。エージェントはドキュメントや返答でもこれらの文字を使いません。既定値はなしです。

## セキュリティモデル

mockup-canvas はローカルのツールで、ローカルにとどまるように作られています。詳細は [SECURITY.md](SECURITY.md) を参照してください。

- **既定は localhost のみ。** `canvas serve` は `127.0.0.1` にだけバインドします。
- **共有モードは明示的に有効化。** `--share` はローカルネットワークにバインドし、すべてのリクエストにランダムなトークンを要求します（初回アクセス後は `HttpOnly; SameSite=Strict` の Cookie に移ります）。`--share-edit` を付けない限り読み取り専用で、プロジェクト登録の変更は常に禁止、`--minutes`（1 から 240、既定 30 分）が過ぎると自動で停止します。レジストリの共有は起動時に登録済みのプロジェクト（`--project NAME` ならその 1 つ）だけを表示し、フォルダのパスと管理画面は隠します。通信は平文の HTTP なので、信頼できるネットワークでだけ使ってください。
- **Host の確認。** すべてのリクエストの `Host` ヘッダーはこのサーバー（`127.0.0.1`、`localhost`、`[::1]` とポート、共有モードでは LAN アドレスも）でなければならず、それ以外は `421` で拒否して DNS リバインディングを防ぎます。
- **パスの封じ込め。** 登録済みデザインフォルダ内のファイルだけを配信します。`../`、エンコードされたトラバーサル、絶対パス、外を指すシンボリックリンクは拒否します。
- **最小限の書き込み。** アイデアへの書き込みは、`canvas.json` にある既存アートボードの `x` と `y` の変更だけです。アトミックに保存し、本文は 64 KiB までです。
- **CSRF チェック。** 配置の保存とプロジェクトの追加、削除には、同一オリジンの `Origin` または `Referer` ヘッダーと、正確に `application/json` の Content-Type が必要です。
- **アートボードの隔離。** アートボード（と `assets/`、`shared/` の HTML、SVG）は `Content-Security-Policy: sandbox` 付きで配信し、sandbox の iframe に表示するため、アートボードのスクリプトはキャンバスの API を呼べません。
- **タイムアウト。** 接続ごとに 15 秒のタイムアウトがあり（ライブ更新のストリームは除く）、同時接続は 64 までです。
- **外部へのリクエストなし。** ツール自体はインターネットに接続しません。アートボードが読み込む Google Fonts が、スキルで許可された唯一の外部リソースです。`snap` と `compare --url` は、あなたが指定した http または https のアドレスだけを開き、localhost でなければ警告します。

脆弱性は公開の Issue ではなく、GitHub Security Advisories で非公開で報告してください。

## FAQ

### なぜ Figma ではなく HTML なのですか？

mockup-canvas が Figma ではなく HTML を使うのは、AI エージェントが HTML と CSS を得意としており、成果物はリポジトリ内の実ファイルとして残ります。diff で比較でき、プルリクエストでレビューでき、アカウントなしでどのブラウザでも開けます。実装を始めるときも、同じマークアップとトークンから実際の UI へすぐに進めます。

### モックアップをコードにできますか？

はい、`mockup-to-code` スキルが担当します。あなたがボードを承認すると、エージェントはアプリ自身のフレームワークとコンポーネントで実装し、値をそのまま写さずにモックアップのトークンをアプリのトークン体系に移します。画面ごとに動いているルートに対して `canvas compare` を実行し、`side.png` と `diff.png` を見て直し、意図した差（サンプル文言の代わりの実データ、フォントのレンダリング、プラットフォームの標準コントロール）だけが残るまで比較を繰り返します。ボードごとのルートとファイルを `canvas impl` で記録するので、キャンバスに `built` バッジが付き、`canvas impl <idea dir> --strict` でまだ実装されていない承認済みボードがわかります。最終報告では、自分で確認したことと確認できなかったことを分けて書きます。

### compare はどのくらい正確ですか？

`compare` は判断ではなくピクセルの比較です。どれか 1 つの色チャンネルがしきい値（既定は 255 のうち 24、`--threshold` で指定）より大きく違えばそのピクセルを不一致とし、`mismatch_percent` は比較した行のうち不一致ピクセルが占める割合です。目安として、約 2% 未満はたいていフォントのレンダリングとアンチエイリアス、2% から 10% は余白、行の高さ、要素の欠落、10% を超えるとレイアウトのずれであることが多いです。モックアップには実際のアプリが描かない偽のステータスバーやホームインジケーターがよくあるので、`--align-top N` でアプリをバーの下に置くか、`--ignore-top N` と `--ignore-bottom N` でその帯を外してください。割合は目安として扱い、必ず `side.png` と `diff.png` を自分の目で見てください。スキルも数字だけで画面が一致したとは言いません。

### インターネット接続は必要ですか？

いいえ。サーバー、キャンバス、CLI はオフラインで動きます。Google Fonts を使うアートボードだけ、フォントの読み込みに接続が必要です。プラグインのインストールには GitHub へのアクセスが必要です。

### Windows や Linux でも使えますか？

Linux では動作する見込みですが、Windows は未検証です。サーバーとキャンバスは Python 標準ライブラリだけを使います。PNG のレンダリングとキャプチャ（`render`、`overview`、`snap`、`compare`、キャンバスのサムネイル）には Chrome、Chromium、Edge のいずれかが必要で、CLI は次の順にブラウザを探します。

1. 環境変数 `MOCKUP_CANVAS_CHROME`
2. `/Applications` にある macOS 版 Google Chrome、Chromium、Microsoft Edge のアプリのパス
3. `PATH` 上の `google-chrome`、`google-chrome-stable`、`chromium`、`chromium-browser`、`msedge`、`chrome`

別の場所にある場合は指定してください。

```bash
export MOCKUP_CANVAS_CHROME=/path/to/chrome
```

`install.sh` は POSIX シェル（bash）が必要なので、Windows では Claude Code プラグインとしてインストールしてください。

### mockup-canvas はどの AI エージェントに対応していますか？

mockup-canvas は Claude Code プラグインとして、また Claude Code と OpenAI Codex 向けのスキルとして提供されます（Codex では `$mockup-canvas`、`$mockup-review`、`$mockup-to-code` で呼び出します）。スキルは `canvas.py` CLI を実行するだけなので、シェルコマンドを実行できるエージェントなら同じ手順をたどれます。

### mockup-canvas は Figma、v0、Claude Artifacts と何が違いますか？

mockup-canvas はホスト型のデザインツールやアプリ生成ツールではありません。あなたが持つファイルを中心に、企画、レビュー、実装を扱います。モックアップはすべてリポジトリ内のローカル HTML ファイルで、キャンバスは `127.0.0.1` から配信され、ツール自体は外部へリクエストを送りません。承認とメモ、レビューコメント、実装の記録は `canvas.json` に残るので、何を承認し、却下し、作ったかの履歴が残り、作った画面は承認済みのモックアップと比較して確かめます。CLI を実行できるエージェントなら何とでも使えます。

### AI エージェントなしでも使えますか？

はい。HTML ファイルを自分で書き、`canvas new`、`canvas add`、`canvas link`、`canvas serve` などの CLI を使えば十分です。自分で実装した画面も `canvas compare` と `canvas impl` で確認できます。スキルは同じコマンドを代わりに実行しているだけです。

## コントリビュート

Issue もプルリクエストも歓迎します。プルリクエストを出す前にテスト（170 件）を実行してください。

```bash
cd tests && python3 -m unittest discover .
```

Chrome が見つからない場合、レンダリングのテストはスキップされます。`python3 tests/perf_check.py` は headless Chrome でキャンバスのフレーム時間、長いタスク、全体表示までの時間を測ります。単体テストには含まれません。

## ライセンス

mockup-canvas は [MIT ライセンス](LICENSE)で公開されています。Copyright (c) 2026 chrisjo-dev.
