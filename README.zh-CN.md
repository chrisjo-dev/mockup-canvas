# mockup-canvas

**和 AI 智能体一起规划、评审、实现界面：三个 Claude Code 和 Codex 技能，在本地类 Figma 画布上绘制 HTML 原型、评审原型，并把已批准的界面变成真正的应用代码，再与原型做可视化对比。**

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![支持 Claude Code 和 Codex](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex-6b4fbb.svg)](#快速开始-安装-claude-code-插件或-codex-技能)
[![无需 pip 依赖：Python 标准库，Chrome 仅用于渲染 PNG](https://img.shields.io/badge/no%20pip%20deps-Python%20stdlib%20%2B%20Chrome-brightgreen.svg)](#常见问题)

**mockup-canvas 是什么？** mockup-canvas 是 chrisjo-dev 开发的免费开源（MIT）Claude Code 插件，也可以在 OpenAI Codex 中使用，由覆盖规划、评审和实现的三个技能（skill）组成。**mockup-canvas** 让 AI 智能体把界面原型画成普通的 HTML 文件，并把这些界面铺在一块本地的类 Figma 画布上，供你平移、缩放、排列、用流程箭头连线和批准。**mockup-review** 让智能体评审这些界面，并把发现的问题作为评论直接留在对应的画板上。**mockup-to-code** 把已批准的界面实现为你应用中的真实代码，然后截取每个运行中的路由，与原型逐像素对比，直到只剩下有意为之的差异。它只依赖 Python 标准库，无需任何 pip 依赖，Google Chrome（或 Chromium、Edge）只用于渲染和截取 PNG。

给 AI 助手：项目摘要见 [llms.txt](llms.txt)。

![演示：AI 智能体绘制移动应用界面，界面实时出现在 mockup-canvas 画布上](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/demo.gif)

![示例创意 TrailMate 的全景图：画布上有六个 HTML 画板，由流程箭头相连，其中两个标记为已批准](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/_overview.png)

## 三个技能

**绘制 → 评审 → 批准 → 实现 → 对比**

| 技能 | 何时使用 | 做什么 | 请求示例 |
| --- | --- | --- | --- |
| `mockup-canvas` | 规划阶段，写应用代码之前 | 把每个界面画成 HTML 画板，连接流程，并在画布上记录你的批准。 | `画一个习惯打卡应用的原型：首页、添加习惯、每周统计。` |
| `mockup-review` | 界面已画好，想听听另一种意见 | 对照需求文档和检查清单检查每个画板和整个流程，在画板上留下 `[must]`、`[should]`、`[could]` 评论，写出 `review.md`，并建议批准、修改或否决。它从不修改画板，也不设置状态。 | `评审一下 design/habits 的原型，告诉我缺了什么。` |
| `mockup-to-code` | 已有批准的画板 | 用你应用自己的框架实现已批准的画板，用 `canvas compare` 把每个运行中的路由与画板对比，并用 `canvas impl` 记录路由和文件。 | `把已批准的习惯打卡界面实现到我们的应用里。` |

批准始终由你决定：只有你批准的画板（用 `canvas status ... approved` 记录）才会被实现。三个技能都使用同一个 `canvas.py` 命令行工具。

## 为什么先让 AI 智能体画原型

mockup-canvas 之所以存在，是因为用文字描述 UI 容易产生歧义：和 AI 智能体一起规划产品时，你需要先看到界面，再就界面达成一致。它诞生于用 AI 规划和开发服务的过程中，是一个规划工具，先把需要的东西变得可见，再从那里推进。"首页顶部是横幅，下面是卡片列表"这样一句话，在真正看到之前，你和智能体的理解往往并不一样。mockup-canvas 把这一步放到最前面：智能体把每个界面画成一个小小的 HTML 文件，画布把它们并排展示，你根据看到的内容做决定。批准这个，否决那个，再要一个变体，智能体工作的同时画布就会更新。界面获得批准之后才开始写应用代码，之后已批准的原型仍然是视觉规范：实现出来的界面要与它们对比，所以你批准的就是最终做出来的。每个原型都会作为独立的 HTML 文件留在你的代码仓库里，无需账号，任何浏览器都能打开。

## 功能一览

**画布**（`viewer.html`，在本地提供）

- 画布让你像设计工具一样平移和缩放，每个缩放级别都会清晰重绘，而不是拉伸位图。
- 画布会在你拖动画板排列后把位置保存到 `canvas.json`，移动操作支持撤销和重做。
- 画布在界面之间绘制流程箭头，并标注通往下一个界面的按钮或操作。
- 画布显示批准、否决徽章，鼠标悬停在画板标题上即可看到备注。
- 已记录实现的画板会显示蓝色的 `built` 徽章（悬停可看到路由），有评审评论的画板会显示评论数；点击评论数即可在面板中阅读评论。
- 画布用可折叠的分组整理画板，例如 `current` 和 `old drafts`。
- 画板很多时画布依然流畅：只有视图附近的画板保持实时页面，缩放低于 35% 时显示缓存的 PNG 缩略图（通过服务器打开时），界面更新按每个动画帧合并一次。缩略图在后台以低优先级渲染。在一个有 71 个画板的画布上（1440x900，Apple M4，headless Chrome）实测：无论首次打开还是缩略图已缓存，平移和缩放都保持在约 59 到 60 FPS，p95 帧时间约 20 ms，没有超过 50 ms 的帧。可用 `python3 tests/perf_check.py <创意文件夹>` 复现。
- 画布支持实时刷新：服务器每秒检查一次文件变化，修改画板或 `canvas.json` 后，打开的画布大约一秒内更新。
- 一个画布服务器就能在索引页列出所有已注册的项目及其创意。
- 画布也能在手机上查看：同一网络内实时查看（共享模式），或导出为可托管在任何地方的静态包。

**智能体技能**（`skills/<skill>/SKILL.md`）

- `mockup-canvas` 一步步告诉 Claude Code 或 Codex 如何绘制、注册、连线、检查和展示原型。它保留旧版本而不是删除，并以你的批准作为正式记录。
- `mockup-review` 检查状态界面覆盖、流程、令牌一致性、基础无障碍、拇指可达范围以及与需求的一致性，并把带严重程度标签的问题留在对应画板上。
- `mockup-to-code` 把原型令牌映射到你的应用中，先搭建共享外壳，再逐个实现已批准的画板并与画板对比。
- 每个技能在第一次完成后都会附上一段简短回顾，提出对技能本身的改进建议。

**命令行工具**（`skills/mockup-canvas/scripts/canvas.py`）

- 命令行工具是单个约 3,300 行的 Python 3 文件，无需 pip 依赖（只用标准库，Python 3.8 及以上），共 16 个命令：`serve`、`roots`、`new`、`add`、`group`、`render`、`check`、`overview`、`export`、`link`、`status`、`artifact`、`snap`、`compare`、`impl`、`comment`。
- 命令行工具只在渲染画板和把应用页面截取为 PNG 时使用 Chrome（或 Chromium、Edge）。

## 快速开始: 安装 Claude Code 插件或 Codex 技能

要在 Claude Code 中安装 mockup-canvas，运行下面两条 `/plugin` 命令即可：第一条添加 `chrisjo-dev/mockup-canvas` 插件市场，第二条安装包含全部三个技能的插件。不需要任何 pip 包，Chrome 只用于渲染 PNG。

### Claude Code 插件

```text
/plugin marketplace add chrisjo-dev/mockup-canvas
/plugin install mockup-canvas@mockup-canvas
```

然后直接用自然语言提出需求：

```text
画一个习惯打卡应用的原型：首页、添加习惯、每周统计。
```

智能体会创建创意文件夹、绘制界面、启动画布服务器，并给你一个类似 `http://localhost:4400/<project>/<idea>/` 的地址。

### 手动安装（Claude Code 和 Codex）

```bash
git clone https://github.com/chrisjo-dev/mockup-canvas.git
cd mockup-canvas
./install.sh            # 把所有技能链接到 ~/.claude/skills 和 ~/.codex/skills
```

- 只为其中一个工具安装：`./install.sh --claude` 或 `./install.sh --codex`。
- `./install.sh --dry-run` 只打印将要执行的操作，不做任何修改。
- 它会链接 `skills/` 下的所有技能文件夹（mockup-canvas、mockup-review、mockup-to-code），而不只是 mockup-canvas。目标位置已有同名技能或其他内容时，会先移到 `~/.mockup-canvas/backup/<timestamp>/`，再换成链接。重复运行是安全的。

在 Codex 中用技能名调用，例如：`Use $mockup-canvas to draw the sign-up flow.`、`Use $mockup-review to review the sign-up mockups.`、`Use $mockup-to-code to build the approved sign-up screens.`

### 不用智能体，先看看示例

```bash
python3 skills/mockup-canvas/scripts/canvas.py serve examples
```

打开 `http://127.0.0.1:4400/trailmate/`，即可看到 [`examples/trailmate`](https://github.com/chrisjo-dev/mockup-canvas/blob/main/examples/trailmate/canvas.json) 中包含六个界面的示例。

## mockup-canvas 如何工作

每个技能都按照各自 `SKILL.md` 中的流程工作。每一步对应的命令、规则以及自定义方法，见 [docs/skill.zh-CN.md](docs/skill.zh-CN.md)。

### 绘制（mockup-canvas）

1. **找到或创建创意。** 如果 `design/<idea>/` 已存在，就接着做。否则运行 `canvas new <design dir> <idea>`，这一步同时会把设计文件夹注册到画布服务器。
2. **先定设计令牌。** 画任何界面之前，先在 `shared/tokens.css` 中定好颜色、字体、间距和圆角。画板只使用 `var(--...)`。
3. **绘制画板。** 每个界面是 `boards/` 中的一个 HTML 文件，命名如 `W01-Home.html`。单独打开时效果必须一致：只用相对路径，不引用外部脚本，外部资源只允许 Google Fonts。
4. **注册。** `canvas add <idea dir> boards/W01-Home.html --group current --size mobile` 把它放到画布上。内容被截断时，用新的 `--size` 再次运行 `add` 即可调整画板尺寸。
5. **连接流程。** `canvas link <idea dir> W01-Home.html W02-Detail.html --label "打开"` 画出箭头。空状态、错误、加载中、无权限等状态界面也会一并绘制；如果你限定了界面数量，则只在报告中建议。
6. **检查、渲染、全景图。** `canvas check` 必须报告 0 个问题。在给你看之前，智能体会亲自查看 `canvas render`（首屏以下的内容加 `--full-page`）和 `canvas overview` 生成的 PNG。
7. **启动服务并给出地址。** `canvas serve`（注册表模式，端口 4400）用一个服务器展示所有项目。智能体让它保持运行，并把地址交给你。
8. **在手机上查看。** 用 `canvas export` 生成静态包，由智能体上传到私密托管页面；或在同一网络内用 `canvas serve <design dir> --share` 实时查看。
9. **保留旧版本。** 什么都不删。旧界面移到 `old drafts` 分组并标记为 `rejected`。
10. **批准即记录。** 你批准某个界面时，智能体会运行 `canvas status ... approved --note "..."`。单纯的夸奖不算批准。
11. **首版回顾。** 首版完成后，智能体回顾的是工作过程而不是设计，并列出最多三条技能改进建议。未经你同意，它不会修改技能。

### 评审（mockup-review）

1. **读取上下文：** 界面所依据的需求文档、`tokens.css`、`canvas.json`，以及之前的 `review.md`（如果有）。
2. **机器检查：** `canvas check` 和 `canvas overview`。`check` 报告的每个问题都会成为一条发现。
3. **逐个画板和流程：** 渲染每个当前画板（也用 `--full-page`），阅读其 HTML，按检查清单逐项检查，并从入口界面沿连线走一遍，找出死胡同和无法到达的画板。
4. **在画板上评论：** 每条发现一条 `canvas comment`，以 `[must]`、`[should]` 或 `[could]` 开头。
5. **报告：** 写出 `design/<idea>/review.md`，并对每个画板建议批准、修改或否决。设置状态仍由你决定。

评审者从不修改画板、令牌或 `canvas.json`。由不同于绘制界面的智能体或会话来运行时效果最好。

### 实现（mockup-to-code）

1. **范围：** `canvas impl <idea dir>` 列出已批准的画板。只实现这些；如果一个都没有批准，智能体会先询问。
2. **了解项目：** 框架、路由、样式方案、现有组件和令牌、数据契约，以及测试、lint 和开发服务器命令。
3. **令牌只映射一次，先做外壳：** 把画板令牌集中映射到应用的令牌体系中，然后搭建共享的布局、页头和导航。
4. **逐个界面：** 一个已批准的画板对应一个路由，空状态、加载中和错误作为真实状态实现，并接入真实数据（临时桩代码会标注并在报告中列出）。
5. **对比：** `canvas compare <idea dir> W01-Home.html --url http://localhost:5173/` 写出 `side.png`、`diff.png` 和带不一致比例的 `report.json`。智能体亲自查看图片、修正，再次对比，直到剩下的每处差异都是有意为之且能说出原因。
6. **记录与检查：** 用 `canvas impl <idea dir> W01-Home.html --route / --file src/pages/Home.tsx` 记录，然后运行项目的测试、lint 和类型检查，并对所有界面统一打磨一遍。

### 对话示例

下面是一段精简的对话，展示请求如何变成画布上的界面、批准和修改如何进行，以及第一版草稿如何以技能改进建议收尾。

> **你：** 给周末徒步爱好者画一个步道应用的原型，四个界面。
>
> **智能体：** 已创建 `design/trailmate/` 并先设定了令牌。绘制了 T01-Home、T02-TrailDetail、T03-Invite、T04-Plan，并按顺序连线，`check` 报告 0 个问题。请打开 `http://localhost:4400/myapp/trailmate/` 查看。因为你限定了四个界面，以下没有画，但建议补上：首页的空状态和邀请页的错误状态。
>
> **你：** 首页可以。详情页的地图再大一些。
>
> **智能体：** 已将 T01-Home 标记为批准，备注"首页信息流布局"。旧的 T02 已移到 "old drafts" 并标记为否决，另新增了地图通栏显示的 T02-TrailDetail-v2。画布已自动刷新。
>
> 技能改进建议：1. 需求里没有地图尺寸导致重画，多了一轮往返，以地图或图表为主的界面应先询问关键元素的尺寸。

## 命令参考

先按技能所在位置定义一个 shell 函数：

```bash
canvas() { python3 ~/.claude/skills/mockup-canvas/scripts/canvas.py "$@"; }
```

任何命令都可以用 `canvas <command> -h` 查看用法。

| 命令 | 作用 | 示例 |
| --- | --- | --- |
| `serve` | 启动画布服务器。不指定文件夹时为注册表模式，展示所有已注册项目；指定文件夹时只展示该设计文件夹。`--share` 带令牌向局域网开放；注册表模式下 `--share --project NAME` 只共享一个项目。 | `canvas serve`<br>`canvas serve design --share --minutes 30` |
| `roots list` | 列出已注册的设计文件夹。 | `canvas roots list` |
| `roots add` | 注册一个设计文件夹，可指定名称。 | `canvas roots add ~/work/app/design --name app` |
| `roots remove` | 按名称取消注册，不会改动文件。 | `canvas roots remove app` |
| `roots scan` | 在指定目录下查找设计文件夹并注册。 | `canvas roots scan ~/work ~/projects` |
| `new` | 创建创意文件夹（`boards/`、`shared/tokens.css`、`canvas.json` 等）并注册其设计文件夹。 | `canvas new design wallet` |
| `add` | 把画板注册到画布上，必要时复制到 `boards/`。尺寸：`mobile` 390x844、`tablet` 768x1024、`desktop` 1440x900，或 `WxH`。对已注册的画板用新的 `--size` 再次运行即可调整尺寸。 | `canvas add design/wallet boards/W01-Home.html --group current --size mobile` |
| `group` | 把画板移到某个分组。 | `canvas group design/wallet W01-Home.html "old drafts"` |
| `link` | 在两个画板之间添加流程箭头。 | `canvas link design/wallet W01-Home.html W02-Send.html --label "转账"` |
| `status` | 设置 `draft`、`approved` 或 `rejected`，可附备注。 | `canvas status design/wallet W01-Home.html approved --note "布局确定"` |
| `artifact` | 保存创意的托管页面地址；不带地址时打印已保存的地址。 | `canvas artifact design/wallet https://example.com/page` |
| `render` | 用无头 Chrome 按注册尺寸把画板渲染为 PNG，保存到 `render/`。不指定文件时渲染全部。`--full-page` 截取整个滚动高度；`--wait MS`（默认 1000）为页面 load 事件之后的等待时间。 | `canvas render design/wallet W01-Home.html --full-page` |
| `overview` | 把整个画布（含箭头和分组）渲染为 `render/_overview.png`。 | `canvas overview design/wallet` |
| `check` | 报告缺失文件、失效引用、未注册画板、重叠、悬空连线、禁用字符，以及不存在的实现文件。同时打印批准数和评论数。 | `canvas check design/wallet` |
| `export` | 生成只读的静态画布包：`index.html` 加上 boards、shared 和 assets。输出文件夹不能是创意文件夹本身、其内部或包含它的上级文件夹；指向创意文件夹外部的符号链接会被跳过。 | `canvas export design/wallet ./wallet-export` |
| `snap` | 用无头 Chrome 按指定尺寸（默认 `mobile`）精确截取运行中的应用页面（http 或 https）。`--wait MS`（默认 3000）是页面 load 事件之后的实际等待时间；`--full-page` 截取整个滚动高度。 | `canvas snap http://localhost:5173/ --size mobile --out home.png` |
| `compare` | 按注册尺寸渲染画板，以相同尺寸截取应用（`--url`）或使用一张 PNG（`--png`），并把 `board.png`、`app.png`、`diff.png`（不一致处为品红色）、`side.png`（画板、应用、差异并排）和 `report.json`（含 `mismatch_percent`）写到 `<idea>/compare/<board id>/` 或 `--out DIR`。`--threshold N`（0 到 255，默认 24）是颜色通道差异超过多少才算不同像素；`--ignore-top N` 和 `--ignore-bottom N` 把上下条带排除在外；`--align-top N` 把应用下移 N px，放在画板所画的假状态栏下方；`--wait MS`（默认 3000）。 | `canvas compare design/wallet W01-Home.html --url http://localhost:5173/ --align-top 47` |
| `impl` | 指定画板时：记录实现它的路由和源文件（相对于项目根目录），或用 `--clear` 清除记录。不指定画板时：列出已批准的画板及其是否已实现；`--strict` 在有未实现的画板时以 1 退出。 | `canvas impl design/wallet W01-Home.html --route / --file src/pages/Home.tsx`<br>`canvas impl design/wallet --strict` |
| `comment` | 给画板添加评审评论（`--by NAME` 指定作者），不带文字时列出评论，`--clear` 删除评论。 | `canvas comment design/wallet W02-Send.html "[must] 缺少错误状态" --by reviewer` |

## 画布快捷键

| 操作 | 效果 |
| --- | --- |
| 拖动空白处 | 平移 |
| 鼠标滚轮、触控板滚动或双指缩放 | 以指针为中心缩放 |
| 单指拖动、双指捏合（触屏） | 平移、缩放 |
| `F` | 让所有画板适配视图 |
| `L` | 显示或隐藏流程箭头 |
| 单击画板标题 | 复制其 ID，例如 `W01-Home` |
| 双击画板标题 | 在新标签页中单独打开该画板 |
| 拖动画板标题 | 移动并保存位置 |
| `Cmd+Z` / `Ctrl+Z` | 撤销上一次移动 |
| `Cmd+Shift+Z` / `Ctrl+Shift+Z`，或 `Cmd+Y` / `Ctrl+Y` | 重做 |
| 单击分组标题 | 折叠或展开分组 |
| 鼠标悬停在画板标题上 | 显示备注 |
| 单击评论数 | 打开该画板的评论，按 `Esc` 关闭 |

静态导出中无法移动画板。共享模式下，只有用 `--share-edit` 启动服务器时移动才会被保存。

## 文件夹结构

创意放在你的项目里；没有项目时放在 `~/design/`：

```text
<project>/design/<idea>/
  canvas.json         布局、分组、流程箭头（links）、状态和备注、实现记录、评论、artifact_url
  boards/*.html       画板，一个文件一个界面，例如 W01-Home.html
  shared/tokens.css   颜色、字体、间距、圆角；所有画板都引用它
  assets/             图片、字体
  render/             用于检查的 PNG，以及低缩放时画布使用的 render/.thumbs/
  compare/            每个画板的对比结果：board、app、diff、side PNG 和 report.json
  review.md           mockup-review 的报告（运行过评审时）
```

`render/` 和 `compare/` 是自动生成的，已通过创意文件夹的 `.gitignore` 排除在 git 之外。

用户数据位于 `~/.mockup-canvas/`，也可以用 `MOCKUP_CANVAS_HOME` 指定其他位置：

```text
~/.mockup-canvas/
  roots.json    已注册的设计文件夹（注册表模式使用）
  config.json   选项，例如 {"forbidden_chars": ["—"]}
  backup/       install.sh 移走的原有文件
```

`forbidden_chars` 是一个字符列表，画板中出现这些字符时 `canvas check` 会报告。智能体在文档和回复中也会避开它们。默认为空。

## 安全模型

mockup-canvas 是本地工具，设计上也只在本地运行。完整说明见 [SECURITY.md](SECURITY.md)。

- **默认仅限 localhost。** `canvas serve` 只绑定 `127.0.0.1`。
- **共享模式需主动开启。** `--share` 绑定到局域网，每个请求都需要随机令牌（首次访问后转存为 `HttpOnly; SameSite=Strict` Cookie）。除非传入 `--share-edit`，否则为只读；始终不允许修改项目注册；超过 `--minutes`（1 到 240，默认 30 分钟）后自动停止。注册表共享只展示启动时已注册的项目（用 `--project NAME` 时只有那一个），并隐藏文件夹路径和管理界面。传输使用明文 HTTP，请只在可信网络中使用。
- **Host 检查。** 每个请求的 `Host` 请求头必须是本服务器（`127.0.0.1`、`localhost`、`[::1]` 加端口，共享模式下还包括局域网地址），否则返回 `421`，以阻止 DNS 重绑定。
- **路径限制。** 只提供已注册设计文件夹内的文件。`../`、编码后的路径穿越、绝对路径以及指向外部的符号链接都会被拒绝。
- **极小的写入面。** 对创意的唯一写操作是修改 `canvas.json` 中已有画板的 `x` 和 `y`，原子写入，请求体上限 64 KiB。
- **CSRF 检查。** 保存布局以及添加或移除项目，需要同源的 `Origin` 或 `Referer` 请求头，且 Content-Type 必须正好是 `application/json`。
- **画板隔离。** 画板（以及 `assets/`、`shared/` 下的 HTML、SVG）带 `Content-Security-Policy: sandbox` 提供，并显示在沙盒 iframe 中，画板脚本无法调用画布 API。
- **超时。** 每个连接 15 秒超时（实时刷新流除外），同时最多处理 64 个连接。
- **不发起外部请求。** 工具本身不访问互联网。画板可以加载 Google Fonts，这是技能唯一允许的外部资源。`snap` 和 `compare --url` 只打开你给出的 http 或 https 地址，不在 localhost 上时会发出警告。

如发现漏洞，请通过 GitHub Security Advisories 私下报告，不要公开提 issue。

## 常见问题

### 为什么用 HTML 而不是 Figma？

mockup-canvas 用 HTML 而不是 Figma，是因为 AI 智能体写 HTML 和 CSS 得心应手，产物是仓库里的真实文件：可以 diff，可以在 PR 中审阅，任何浏览器都能打开，无需账号。真正开发时，同样的标记和令牌离正式 UI 只有一步之遥。

### 能把原型变成代码吗？

可以，由 `mockup-to-code` 技能负责。你批准画板后，智能体用你应用自己的框架和组件实现它们，并把原型令牌映射到你的令牌体系，而不是照抄原始数值。对每个界面，它针对运行中的路由执行 `canvas compare`，查看 `side.png` 和 `diff.png`，修正差异后再次对比，直到只剩下有意为之的差异（用真实数据代替示例文字、字体渲染、平台原生控件）。它用 `canvas impl` 记录每个画板的路由和文件，因此画布会显示 `built` 徽章，`canvas impl <idea dir> --strict` 会告诉你哪些已批准的画板还没有实现。最终报告会区分它亲自验证过的内容和无法验证的内容。

### compare 有多准确？

`compare` 是像素比较，而不是判断。只要任一颜色通道的差异超过阈值（默认 255 中的 24，用 `--threshold` 设置），该像素就算不同，`mismatch_percent` 是参与比较的行中不同像素所占的比例。粗略来说，约 2% 以下通常是字体渲染和抗锯齿，2% 到 10% 通常是间距、行高或缺少元素，超过 10% 通常是布局发生了偏移。原型常常画出真实应用并不渲染的假手机状态栏或 Home 指示条：用 `--align-top N` 把应用放到状态栏下方，或用 `--ignore-top N` 和 `--ignore-bottom N` 把这些条带排除在外。把百分比当作参考，一定要亲自查看 `side.png` 和 `diff.png`；技能也从不只凭数字就声称界面一致。

### 需要联网吗？

不需要。服务器、画布和命令行工具都能离线运行。只有使用 Google Fonts 的画板在加载字体时需要联网。安装插件时需要能访问 GitHub。

### 能在 Windows 或 Linux 上用吗？

Linux 应该可以使用；Windows 尚未测试。服务器和画布只依赖 Python 标准库。渲染和截取 PNG（`render`、`overview`、`snap`、`compare` 以及画布缩略图）需要 Chrome、Chromium 或 Edge，命令行工具按以下顺序查找浏览器：

1. `MOCKUP_CANVAS_CHROME` 环境变量。
2. `/Applications` 中 macOS 版 Google Chrome、Chromium、Microsoft Edge 的应用路径。
3. `PATH` 中的 `google-chrome`、`google-chrome-stable`、`chromium`、`chromium-browser`、`msedge`、`chrome`。

如果浏览器在其他位置，可以手动指定：

```bash
export MOCKUP_CANVAS_CHROME=/path/to/chrome
```

`install.sh` 需要 POSIX shell（bash），所以在 Windows 上请通过 Claude Code 插件安装。

### mockup-canvas 支持哪些 AI 智能体？

mockup-canvas 以 Claude Code 插件的形式提供，也作为 Claude Code 和 OpenAI Codex 的技能提供（在 Codex 中用 `$mockup-canvas`、`$mockup-review` 或 `$mockup-to-code` 调用）。技能只是运行 `canvas.py` 命令行工具，所以任何能执行 shell 命令的智能体都能按同样的步骤使用。

### mockup-canvas 和 Figma、v0、Claude Artifacts 有什么不同？

mockup-canvas 不是托管式的设计工具或应用生成器。它围绕你自己拥有的文件覆盖规划、评审和实现：每个原型都是你仓库里的本地 HTML 文件，画布从 `127.0.0.1` 提供，工具本身不发出任何外部请求。批准和备注、评审评论、实现记录都保存在 `canvas.json` 中，因此哪些界面被批准、否决和实现都有据可查，实现出来的界面也会与已批准的原型对比核实。任何能运行命令行工具的智能体都能使用它。

### 不用 AI 智能体也能用吗？

可以。自己编写 HTML 文件，再使用 `canvas new`、`canvas add`、`canvas link`、`canvas serve` 等命令即可；自己实现的界面也可以用 `canvas compare` 和 `canvas impl` 检查。技能只是替你执行这些命令。

## 参与贡献

欢迎提交 issue 和 PR。提交 PR 前请运行测试（共 143 个）：

```bash
cd tests && python3 -m unittest discover .
```

找不到 Chrome 时会跳过渲染测试。`python3 tests/perf_check.py` 在无头 Chrome 中测量画布的帧时间、长任务以及显示适配视图所需的时间，它不属于单元测试。

## 许可证

mockup-canvas 以 [MIT 许可证](LICENSE)发布。Copyright (c) 2026 chrisjo-dev.
