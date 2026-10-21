# mockup-canvas 技能

[English](skill.md) | [한국어](skill.ko.md) | [简体中文](skill.zh-CN.md) | [日本語](skill.ja.md)

mockup-canvas 技能是一组指令，告诉 Claude Code 或 Codex 如何把界面原型画成 HTML 画板并展示在本地画布上，内容位于 [`skills/mockup-canvas/SKILL.md`](../skills/mockup-canvas/SKILL.md)。本文说明智能体在每一步做什么、运行哪些命令，以及你可以如何调整它。

核心理念：**一个 HTML 文件就是一个界面（画板），一个创意就是一块画布，HTML 始终是唯一的事实来源。** 画布只负责展示。

## 何时触发

遇到以下请求时，智能体会加载这个技能：

- "画一个……的原型"
- "做几个……的界面设计"
- "放到画布上"
- "让我在手机上看看"

修改已有的界面组、添加流程箭头、标记批准和手机分享也都在范围内。它**不**用于实现真正的应用代码。

- **Claude Code** 会根据技能描述自动选用，你也可以直接点名。
- **Codex** 在你写 `$mockup-canvas` 时使用，例如 `Use $mockup-canvas to draw screen mockups for this idea.`

## 智能体如何运行命令行工具

技能调用 `python3 <skill-dir>/scripts/canvas.py <command>`，其中 `<skill-dir>` 取决于安装方式：

| 安装方式 | 技能文件夹 |
| --- | --- |
| Claude Code 插件 | `${CLAUDE_PLUGIN_ROOT}/skills/mockup-canvas` |
| 手动安装，Claude Code | `~/.claude/skills/mockup-canvas` |
| 手动安装，Codex | `~/.codex/skills/mockup-canvas` |

智能体会先定义一个简短的 shell 函数，本文后面的示例也都使用它：

```bash
canvas() { python3 <skill-dir>/scripts/canvas.py "$@"; }
```

## 工作流程

### 1. 找到创意

如果 `design/` 下已有同一个创意，智能体就接着做。动笔之前，它会先看需求文档、现有界面，以及你喜欢或否决过的方向。如果是新创意：

```bash
canvas new design wallet
```

这会在 `design/wallet/` 下创建 `boards/`、`assets/`、`render/`、`shared/tokens.css`（初始令牌文件）、`canvas.json`，以及一个忽略 `render/` 的 `.gitignore`。同时会把 `design/` 注册到画布服务器，因此无需再单独执行 `roots add`。没有项目时，使用 `~/design/<idea>/`。

### 2. 先定令牌

画任何界面之前，先在 `shared/tokens.css` 中设定颜色、字体、间距和圆角。画板只使用 `var(--...)`，不会自行发明新的颜色值。这样所有界面风格一致，改配色也只需改一个文件。

### 3. 绘制

每个画板都是独立的 HTML 文件，直接在浏览器中打开时效果必须一致：

- 只用相对路径：`../shared/tokens.css`、`../assets/x.png`。
- 外部资源只允许 Google Fonts。
- 不使用自定义标签，不引用外部脚本。

文件名格式为 `<ID>-<EnglishName>.html`，例如 `F06-Letter.html`。ID 是创意名称首字母的大写加两位数字（`W01`、`W02`……）。如果项目已有界面编号，智能体会沿用。

### 4. 注册

先把文件写入 `boards/`，再注册：

```bash
canvas add design/wallet boards/W01-Home.html --group current --size mobile
```

相关界面按流程顺序从左到右排成一行。尺寸预设有 `mobile`（390x844）、`tablet`（768x1024）、`desktop`（1440x900），也可以用 `WxH` 指定，例如 `1280x800`。省略 `--size` 时，会从文件开头的 `width: ...px; height: ...px` 样式读取尺寸，读不到则默认 390x844。

### 5. 连接流程

```bash
canvas link design/wallet W01-Home.html W02-Send.html --label "转账"
```

每个箭头表示从一个界面如何进入另一个界面。如果你限定了界面数量，智能体只画这么多，缺少的状态界面（空状态、错误、加载中、无权限）只在报告中建议；如果没有限定，就把这些状态界面也纳入流程。

### 6. 检查

```bash
canvas check design/wallet
canvas render design/wallet W01-Home.html
canvas overview design/wallet
```

- `check` 必须报告 0 个问题。它能发现缺失的文件、失效的 `src`、`href` 和 `url()` 引用、未在 `canvas.json` 中注册的画板、相互重叠的画板、指向未知画板的连线，以及禁用字符。
- 每个改动过的画板，智能体都会亲自打开 `render` 生成的 PNG。改动多个时，还会查看包含流程箭头和分组的 `overview` PNG。
- 看到错误文字或损坏的图片，会在给你看之前修好。

### 7. 展示

```bash
canvas serve
```

注册表模式用端口 4400 上的一个服务器展示所有已注册项目，地址为 `http://localhost:4400/<project>/<idea>/`。智能体把打印出的地址原样交给你，并让服务器保持运行。要一次性注册已有项目：

```bash
canvas roots scan ~/work ~/projects
```

如果只想看一个设计文件夹，用 `canvas serve design`，地址为 `http://127.0.0.1:4400/<idea>/`。也可以在浏览器的索引页中添加或移除项目。

### 8. 在手机上查看

- **托管页面（可用时为默认方式）。** 如果环境提供私密托管页面（例如 Claude artifact），智能体会生成静态包并上传。`index.html` 是页面，其余是配套文件。

  ```bash
  canvas export design/wallet ./wallet-export
  canvas artifact design/wallet <url>
  ```

  每个创意在上传前只询问一次。如果你说一直保留，之后每次修改都会重新上传到同一地址，不再询问。`canvas artifact` 把地址保存到 `canvas.json`，其他会话也会更新同一个页面。导出文件夹必须在创意文件夹之外，且不能包含创意文件夹；指向创意文件夹外部的符号链接不会被导出。

- **同一网络内实时查看。**

  ```bash
  canvas serve design --share --minutes 30
  ```

  智能体会给你带令牌的地址。手机上只能查看，时间到后自动关闭（`--minutes` 取 1 到 240）。如需从注册表服务器只共享一个已注册项目，用 `canvas serve --share --project NAME`；注册表共享只展示启动时已注册的项目，并隐藏文件夹路径。

- **快捷替代方案。** 智能体也可以直接发送 `overview` PNG。

### 9. 保留旧版本

旧版本从不删除，只移动并标记：

```bash
canvas group design/wallet W02-Send.html "old drafts"
canvas status design/wallet W02-Send.html rejected
```

被否决的画板显示灰色徽章和删除线标题，你否决过什么，会一直留在当前版本旁边。

### 10. 批准即记录

你批准某个界面时，智能体会记录下来：

```bash
canvas status design/wallet W01-Home.html approved --note "首页布局和卡片列表"
```

绿色徽章和备注就是批准记录。"看起来不错"这样的夸奖不算批准。`canvas check` 也会输出已批准的画板数量，例如 `Approved boards: 2/6`。

## 智能体遵守的规则

- **用你的语言回复。** 你用什么语言提问，它就用什么语言回答。
- **从不手动编辑 `canvas.json`。** 只通过 `canvas add`、`link`、`status`、`group` 修改。直接编辑可能覆盖同时发生的改动，例如并行绘制的子智能体或你拖动画板产生的改动。
- **只停止自己启动的服务器。** 不碰你在用的其他端口。仅用于检查的服务器，通过 PID 或 `lsof -ti:<自己的端口>` 停止，绝不用会连你的服务器一起停掉的 `pkill -f canvas.py`。为你启动的 `serve` 保持运行。
- **遵守 `forbidden_chars`。** 如果 `config.json` 列出了字符，智能体在画板、文档和报告中都不会使用。
- **并行绘制。** 界面很多时，可以按界面组拆分给子智能体。此时由主智能体先定好 `tokens.css`。

## 首版回顾

所有要求的界面都画完且 `check` 通过，首版即告完成。智能体会在报告末尾附上 **技能改进建议**，回顾的是工作方式，而不是设计（设计检查在第 6 步已经结束）。

- **关注什么**（仅限本次实际发生的情况）：你不得不重复或纠正的地方及其背后的规则漏洞、返工、缺少 `canvas` 命令而只能手动绕过的地方、错误、缓慢或多余的步骤、难以遵守或相互冲突的规则。
- **格式**：最多三条，每条一行："发生了什么，影响，要改的规则或命令"。没有就写"本次无"。
- **采纳方式**：只提建议。只有你批准的建议才会改进技能，并在 `references/lessons.md` 中追加一行。

示例：

```text
技能改进建议
1. 需求里没有地图尺寸导致 T02 重画，多了一轮往返，以地图或图表为主的界面应先询问关键元素的尺寸。
2. 旧稿只能逐个文件移动，六个界面时很慢，让 `canvas group` 支持多个文件。
```

## 自定义

### 禁用字符

创建 `~/.mockup-canvas/config.json`（或 `$MOCKUP_CANVAS_HOME/config.json`）：

```json
{"forbidden_chars": ["—"]}
```

之后 `canvas check` 会按码位报告包含这些字符的画板：

```text
Error: forbidden character (U+2014) found: W01-Home.html
```

### 画板尺寸

注册时传入预设或精确尺寸：

```bash
canvas add design/wallet boards/W10-Dashboard.html --size desktop
canvas add design/wallet boards/W11-Kiosk.html --size 1080x1920
```

也可以把尺寸写在画板本身，例如 `<body style="width:768px;height:1024px">`，然后省略 `--size`。

### 数据文件夹

想把 `roots.json` 和 `config.json` 放在 `~/.mockup-canvas/` 以外的位置，设置 `MOCKUP_CANVAS_HOME`：

```bash
export MOCKUP_CANVAS_HOME=~/dotfiles/mockup-canvas
```

### 技能本身

`SKILL.md` 是普通的 Markdown。已批准的改动会逐行记录在 `skills/mockup-canvas/references/lessons.md` 中，方便你了解每条规则的由来。
