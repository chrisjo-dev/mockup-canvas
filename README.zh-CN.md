# mockup-canvas

**先看到界面，再动手开发：这是一个 Claude Code 和 Codex 技能，由 AI 智能体绘制 HTML 原型，你在本地类 Figma 画布上审阅。**

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![支持 Claude Code 和 Codex](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex-6b4fbb.svg)](#快速开始-安装-claude-code-插件或-codex-技能)
[![无需 pip 依赖：Python 标准库，Chrome 仅用于渲染 PNG](https://img.shields.io/badge/no%20pip%20deps-Python%20stdlib%20%2B%20Chrome-brightgreen.svg)](#常见问题)

**mockup-canvas 是什么？** mockup-canvas 是 chrisjo-dev 开发的免费开源（MIT）Claude Code 插件和技能（skill），也可以在 OpenAI Codex 中使用。它让 AI 智能体把界面原型画成普通的 HTML 文件，并把这些界面铺在一块本地的类 Figma 画布上，供你平移、缩放、排列、用流程箭头连线和批准。它只依赖 Python 标准库，无需任何 pip 依赖，Google Chrome（或 Chromium、Edge）只用于渲染 PNG。

给 AI 助手：项目摘要见 [llms.txt](llms.txt)。

![演示：AI 智能体绘制移动应用界面，界面实时出现在 mockup-canvas 画布上](docs/images/demo.gif)

![示例创意 TrailMate 的全景图：画布上有六个 HTML 画板，由流程箭头相连，其中两个标记为已批准](docs/images/_overview.png)

## 为什么先让 AI 智能体画原型

mockup-canvas 之所以存在，是因为用文字描述 UI 容易产生歧义：和 AI 智能体一起规划产品时，你需要先看到界面，再就界面达成一致。它诞生于用 AI 规划和开发服务的过程中，是一个规划工具，先把需要的东西变得可见，再从那里推进。"首页顶部是横幅，下面是卡片列表"这样一句话，在真正看到之前，你和智能体的理解往往并不一样。mockup-canvas 把这一步放到最前面：智能体把每个界面画成一个小小的 HTML 文件，画布把它们并排展示，你根据看到的内容做决定。批准这个，否决那个，再要一个变体，智能体工作的同时画布就会更新。界面获得批准之后才开始写应用代码，每个原型都会作为独立的 HTML 文件留在你的代码仓库里，无需账号，任何浏览器都能打开。

## 功能一览

**画布**（`viewer.html`，在本地提供）

- 像设计工具一样平移和缩放，每个缩放级别都会清晰重绘，而不是拉伸位图。
- 拖动画板进行排列，位置保存到 `canvas.json`。移动操作支持撤销和重做。
- 界面之间的流程箭头，可以标注通往下一个界面的按钮或操作。
- 批准、否决徽章和备注，鼠标悬停在画板标题上即可看到备注。
- 可折叠的分组，例如 `current` 和 `old drafts`。
- 实时刷新：修改画板或 `canvas.json` 后，打开的画布大约一秒内更新。
- 多项目索引：一个服务器列出所有已注册的项目及其创意。
- 在手机上查看：同一网络内实时查看（共享模式），或导出为可托管在任何地方的静态包。

**智能体技能**（`skills/mockup-canvas/SKILL.md`）

- 一步步告诉 Claude Code 或 Codex 如何绘制、注册、连线、检查和展示原型。
- 保留旧版本而不是删除，并以你的批准作为正式记录。
- 首版完成后附上一段简短回顾，提出对技能本身的改进建议。

**命令行工具**（`skills/mockup-canvas/scripts/canvas.py`）

- 单个 Python 3 文件，无需 pip 依赖（只用标准库，Python 3.8 及以上），共 12 个命令：`serve`、`roots`、`new`、`add`、`group`、`render`、`check`、`overview`、`export`、`link`、`status`、`artifact`。
- Chrome（或 Chromium、Edge）只在渲染 PNG 时需要。

## 快速开始: 安装 Claude Code 插件或 Codex 技能

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
./install.sh            # 把技能链接到 ~/.claude/skills 和 ~/.codex/skills
```

- 只为其中一个工具安装：`./install.sh --claude` 或 `./install.sh --codex`。
- `./install.sh --dry-run` 只打印将要执行的操作，不做任何修改。
- 目标位置已有内容时，会先移到 `~/.mockup-canvas/backup/<timestamp>/`。重复运行是安全的。

在 Codex 中用 `$mockup-canvas` 调用技能，例如：`Use $mockup-canvas to draw the sign-up flow.`

### 不用智能体，先看看示例

```bash
python3 skills/mockup-canvas/scripts/canvas.py serve examples
```

打开 `http://127.0.0.1:4400/trailmate/`，即可看到 [`examples/trailmate`](examples/trailmate) 中包含六个界面的示例。

## mockup-canvas 如何工作

智能体按照 `SKILL.md` 中的流程工作：

1. **找到或创建创意。** 如果 `design/<idea>/` 已存在，就接着做。否则运行 `canvas new <design dir> <idea>`，这一步同时会把设计文件夹注册到画布服务器。
2. **先定设计令牌。** 画任何界面之前，先在 `shared/tokens.css` 中定好颜色、字体、间距和圆角。画板只使用 `var(--...)`。
3. **绘制画板。** 每个界面是 `boards/` 中的一个 HTML 文件，命名如 `W01-Home.html`。单独打开时效果必须一致：只用相对路径，不引用外部脚本，外部资源只允许 Google Fonts。
4. **注册。** `canvas add <idea dir> boards/W01-Home.html --group current --size mobile` 把它放到画布上。
5. **连接流程。** `canvas link <idea dir> W01-Home.html W02-Detail.html --label "打开"` 画出箭头。空状态、错误、加载中、无权限等状态界面也会一并绘制；如果你限定了界面数量，则只在报告中建议。
6. **检查、渲染、全景图。** `canvas check` 必须报告 0 个问题。在给你看之前，智能体会亲自查看 `canvas render` 和 `canvas overview` 生成的 PNG。
7. **启动服务并给出地址。** `canvas serve`（注册表模式，端口 4400）用一个服务器展示所有项目。智能体让它保持运行，并把地址交给你。
8. **在手机上查看。** 用 `canvas export` 生成静态包，由智能体上传到私密托管页面；或在同一网络内用 `canvas serve <design dir> --share` 实时查看。
9. **保留旧版本。** 什么都不删。旧界面移到 `old drafts` 分组并标记为 `rejected`。
10. **批准即记录。** 你批准某个界面时，智能体会运行 `canvas status ... approved --note "..."`。单纯的夸奖不算批准。
11. **首版回顾。** 首版完成后，智能体回顾的是工作过程而不是设计，并列出最多三条技能改进建议。未经你同意，它不会修改技能。

每一步对应的命令、规则以及自定义方法，见 [docs/skill.zh-CN.md](docs/skill.zh-CN.md)。

### 对话示例

下面是一段精简的对话，展示请求如何变成画布上的界面、批准和修改如何进行，以及第一版草稿如何以技能改进建议收尾。

> **你：** 给周末徒步爱好者画一个步道应用的原型，四个界面。
>
> **智能体：** 已创建 `design/trailmate/` 并先设定了令牌。绘制了 T01-Home、T02-TrailDetail、T03-Invite、T04-Plan，并按顺序连线，`check` 报告 0 个问题。请打开 http://localhost:4400/myapp/trailmate/ 查看。因为你限定了四个界面，以下没有画，但建议补上：首页的空状态和邀请页的错误状态。
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
| `add` | 把画板注册到画布上，必要时复制到 `boards/`。尺寸：`mobile` 390x844、`tablet` 768x1024、`desktop` 1440x900，或 `WxH`。 | `canvas add design/wallet boards/W01-Home.html --group current --size mobile` |
| `group` | 把画板移到某个分组。 | `canvas group design/wallet W01-Home.html "old drafts"` |
| `link` | 在两个画板之间添加流程箭头。 | `canvas link design/wallet W01-Home.html W02-Send.html --label "转账"` |
| `status` | 设置 `draft`、`approved` 或 `rejected`，可附备注。 | `canvas status design/wallet W01-Home.html approved --note "布局确定"` |
| `artifact` | 保存创意的托管页面地址；不带地址时打印已保存的地址。 | `canvas artifact design/wallet https://example.com/page` |
| `render` | 用无头 Chrome 把画板渲染为 PNG，保存到 `render/`。不指定文件时渲染全部。 | `canvas render design/wallet W01-Home.html` |
| `overview` | 把整个画布（含箭头和分组）渲染为 `render/_overview.png`。 | `canvas overview design/wallet` |
| `check` | 报告缺失文件、失效引用、未注册画板、重叠、悬空连线和禁用字符。 | `canvas check design/wallet` |
| `export` | 生成只读的静态画布包：`index.html` 加上 boards、shared 和 assets。输出文件夹不能是创意文件夹本身、其内部或包含它的上级文件夹；指向创意文件夹外部的符号链接会被跳过。 | `canvas export design/wallet ./wallet-export` |

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

静态导出中无法移动画板。共享模式下，只有用 `--share-edit` 启动服务器时移动才会被保存。

## 文件夹结构

创意放在你的项目里；没有项目时放在 `~/design/`：

```text
<project>/design/<idea>/
  canvas.json         布局、分组、流程箭头（links）、状态和备注、artifact_url
  boards/*.html       画板，一个文件一个界面，例如 W01-Home.html
  shared/tokens.css   颜色、字体、间距、圆角；所有画板都引用它
  assets/             图片、字体
  render/             用于检查的 PNG（自动生成，已通过 .gitignore 排除）
```

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
- **不发起外部请求。** 工具本身不访问互联网。画板可以加载 Google Fonts，这是技能唯一允许的外部资源。

如发现漏洞，请通过 GitHub Security Advisories 私下报告，不要公开提 issue。

## 常见问题

### 为什么用 HTML 而不是 Figma？

mockup-canvas 用 HTML 而不是 Figma，是因为 AI 智能体写 HTML 和 CSS 得心应手，产物是仓库里的真实文件：可以 diff，可以在 PR 中审阅，任何浏览器都能打开，无需账号。真正开发时，同样的标记和令牌离正式 UI 只有一步之遥。

### 需要联网吗？

不需要。服务器、画布和命令行工具都能离线运行。只有使用 Google Fonts 的画板在加载字体时需要联网。安装插件时需要能访问 GitHub。

### 能在 Windows 或 Linux 上用吗？

Linux 应该可以使用；Windows 尚未测试。服务器和画布只依赖 Python 标准库。渲染 PNG（`render`、`overview`）需要 Chrome、Chromium 或 Edge，命令行工具按以下顺序查找浏览器：

1. `MOCKUP_CANVAS_CHROME` 环境变量。
2. `/Applications` 中 macOS 版 Google Chrome、Chromium、Microsoft Edge 的应用路径。
3. `PATH` 中的 `google-chrome`、`google-chrome-stable`、`chromium`、`chromium-browser`、`msedge`、`chrome`。

如果浏览器在其他位置，可以手动指定：

```bash
export MOCKUP_CANVAS_CHROME=/path/to/chrome
```

`install.sh` 需要 POSIX shell（bash），所以在 Windows 上请通过 Claude Code 插件安装。

### mockup-canvas 支持哪些 AI 智能体？

mockup-canvas 以 Claude Code 插件的形式提供，也作为 Claude Code 和 OpenAI Codex 的技能提供（在 Codex 中用 `$mockup-canvas` 调用）。技能只是运行 `canvas.py` 命令行工具，所以任何能执行 shell 命令的智能体都能按同样的步骤使用。

### mockup-canvas 和 Figma、v0、Claude Artifacts 有什么不同？

mockup-canvas 面向写应用代码之前的规划阶段，而不是托管式的设计工具或应用生成器。每个原型都是你仓库里的本地 HTML 文件，画布从 `127.0.0.1` 提供，工具本身不发出任何外部请求。任何能运行命令行工具的智能体都能使用它，批准状态和备注记录在 `canvas.json` 中，因此哪些界面被批准、哪些被否决都有据可查。

### 不用 AI 智能体也能用吗？

可以。自己编写 HTML 文件，再使用 `canvas new`、`canvas add`、`canvas link`、`canvas serve` 等命令即可。技能只是替你执行这些命令。

## 参与贡献

欢迎提交 issue 和 PR。提交 PR 前请运行测试（共 92 个）：

```bash
python3 -m unittest discover tests
```

找不到 Chrome 时会跳过渲染测试。

## 许可证

mockup-canvas 以 [MIT 许可证](LICENSE)发布。Copyright (c) 2026 chrisjo-dev.
