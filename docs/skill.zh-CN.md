# mockup-canvas 技能

[English](skill.md) | [한국어](skill.ko.md) | [简体中文](skill.zh-CN.md) | [日本語](skill.ja.md)

mockup-canvas 包含三个技能，共用同一个命令行工具：

| 技能 | 指令 | 职责 |
| --- | --- | --- |
| mockup-canvas | [`skills/mockup-canvas/SKILL.md`](../skills/mockup-canvas/SKILL.md) | 把界面原型画成 HTML 画板并展示在本地画布上。 |
| mockup-review | [`skills/mockup-review/SKILL.md`](../skills/mockup-review/SKILL.md) | 评审已画好的界面，把发现作为评论留在画板上。 |
| mockup-to-code | [`skills/mockup-to-code/SKILL.md`](../skills/mockup-to-code/SKILL.md) | 在你的应用中实现已批准的画板，并把每个界面与画板对比。 |

本文说明智能体在每一步做什么、运行哪些命令，以及你可以如何调整它。[mockup-review](#mockup-review-技能) 和 [mockup-to-code](#mockup-to-code-技能) 的说明位于 mockup-canvas 工作流程之后。

核心理念：**一个 HTML 文件就是一个界面（画板），一个创意就是一块画布，HTML 始终是唯一的事实来源。** 画布只负责展示。

## 何时触发

遇到以下请求时，智能体会加载这个技能：

- "画一个……的原型"
- "做几个……的界面设计"
- "放到画布上"
- "让我在手机上看看"

修改已有的界面组、添加流程箭头、标记批准和手机分享也都在范围内。它**不**用于点评已完成的界面（那是 mockup-review）或实现真正的应用代码（那是 mockup-to-code）。

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

这会在 `design/wallet/` 下创建 `boards/`、`assets/`、`render/`、`shared/tokens.css`（初始令牌文件）、`canvas.json`，以及一个忽略 `render/` 和 `compare/` 的 `.gitignore`。同时会把 `design/` 注册到画布服务器，因此无需再单独执行 `roots add`。没有项目时，使用 `~/design/<idea>/`。

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

相关界面按流程顺序从左到右排成一行。尺寸预设有 `mobile`（390x844）、`tablet`（768x1024）、`desktop`（1440x900），也可以用 `WxH` 指定，例如 `1280x800`。省略 `--size` 时，会从文件开头的 `width: ...px; height: ...px` 样式读取尺寸，读不到则默认 390x844。画板内容被截断时，智能体会用新的 `--size` 再次运行 `add`，而不是删减内容。

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
- 每个改动过的画板，智能体都会亲自打开 `render` 生成的 PNG。渲染结果与画板尺寸完全一致，首屏以下的内容用 `render --full-page` 截取。改动多个时，还会查看包含流程箭头和分组的 `overview` PNG。
- 看到错误文字或损坏的图片，会在给你看之前修好。

### 7. 展示

```bash
canvas serve
```

注册表模式用端口 4400 上的一个服务器展示所有已注册项目：`http://localhost:4400/` 是汇总所有项目和创意的仪表板，`http://localhost:4400/<project>/<idea>/` 是单个创意的画布。智能体把打印出的地址原样交给你，并让服务器保持运行。要一次性注册已有项目：

```bash
canvas roots scan ~/work ~/projects
```

如果只想看一个设计文件夹，用 `canvas serve design`，地址为 `http://127.0.0.1:4400/<idea>/`。也可以在浏览器的仪表板中添加、重命名或移除项目。端口、手机共享和后台运行见 [运行服务器](../README.zh-CN.md#运行服务器)。

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

智能体只在你要求时才删除。这时 `canvas trash` 把创意或画板移到 `design/.trash/`，`canvas restore` 再放回原处。仪表板（Delete idea）和画布（画板标题上的 `...`）也能做同样的删除，可用提示里的 Undo 撤销。

### 10. 批准即记录

你批准某个界面时，智能体会记录下来：

```bash
canvas status design/wallet W01-Home.html approved --note "首页布局和卡片列表"
```

绿色徽章和备注就是批准记录。"看起来不错"这样的夸奖不算批准。`canvas check` 也会输出已批准的画板数量，例如 `Approved boards: 2/6`。

## 智能体遵守的规则

- **用你的语言回复。** 你用什么语言提问，它就用什么语言回答。
- **从不手动编辑 `canvas.json`。** 只通过 `canvas add`、`link`、`status`、`group`、`impl`、`comment` 修改。直接编辑可能覆盖同时发生的改动，例如并行绘制的子智能体或你拖动画板产生的改动。
- **只停止自己启动的服务器。** 不碰你在用的其他端口。仅用于检查的服务器，通过 PID 或 `lsof -ti:<自己的端口>` 停止，绝不用会连你的服务器一起停掉的 `pkill -f canvas.py`。为你启动的 `serve` 保持运行。
- **遵守 `forbidden_chars`。** 如果 `config.json` 列出了字符，智能体在画板、文档和报告中都不会使用。
- **并行绘制。** 界面很多时，可以按界面组拆分给子智能体。此时由主智能体先定好 `tokens.css`。
- **只询问一次加星。** 在这台机器上完成第一个任务后，三个技能中的任意一个会在回复末尾询问是否要替你在 GitHub 上给 mockup-canvas 加星（加星能帮助其他人找到它）。只有你回答愿意时，才会用已登录的 `gh` 加星或给出链接，然后创建 `${MOCKUP_CANVAS_HOME:-~/.mockup-canvas}/.star-hint-shown`，之后不再提起（自己创建这个文件即可关闭它）。

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

## mockup-review 技能

mockup-review 像第二位设计师那样评审一个创意：检查每个画板以及画板之间的流程，把每条发现留在它所属的画板上，并写一份总结。**评审者只报告，不修改。** 由不同于绘制界面的智能体或会话来运行时效果最好，因为全新的上下文不会带着作者的预设。如果是同一个会话画的界面，报告中会写明。

### 何时触发

- "评审一下原型"
- "检查一下这些界面"
- "点评一下这个设计"
- "还缺什么吗？"

适用于 `design/<idea>/` 下已经画好的界面。在 Codex 中用 `$mockup-review` 调用。它使用同级 mockup-canvas 技能的 `canvas.py`（相对自身文件夹为 `../mockup-canvas/scripts/canvas.py`），如果没有安装该技能就会停止。

### 步骤

1. **读取上下文。** 智能体找到创意文件夹，阅读界面所依据的需求或规格文档、`shared/tokens.css`、`canvas.json`（分组、连线、状态、备注）以及已有的 `review.md`。没有规格文档时只对照界面本身评审，并写明这一点。
2. **机器检查。** `canvas check` 报告的每个问题都会成为一条发现。智能体还会查看 `canvas overview` 的 PNG，检查箭头、分组和孤立的界面。
3. **逐个画板。** 对 `current` 分组中的每个画板（除非你要求，否则跳过已否决的画板和 "old drafts"），渲染并查看 PNG，阅读 HTML，按 `references/checklist.md` 检查：状态界面覆盖、流程、令牌一致性、基础无障碍、移动端拇指可达范围、文案以及与规格的一致性。下结论之前，用 `--full-page` 查看首屏以下的内容。

   ```bash
   canvas render design/wallet W02-Send.html --full-page
   ```

4. **流程。** 从入口界面沿连线走一遍。画板上的每个按钮或链接都应通往画布上的某个画板，或明确标为流程终点。死胡同、无法到达的画板和指向不存在画板的连线都是发现。
5. **规格一致性。** 规格要求的功能没有对应界面，或界面与规格矛盾，都是发现。
6. **在画板上评论。** 每条发现一条评论，留在它所涉及的画板上，并以严重程度标签开头：

   ```bash
   canvas comment design/wallet W02-Send.html "[must] 转账失败时没有错误状态；规格 3.2 要求可以重试" --by reviewer
   ```

   | 标签 | 含义 |
   | --- | --- |
   | `[must]` | 阻止批准：流程中断、缺少必需状态、与规格矛盾、文字无法阅读、`check` 报告的问题。 |
   | `[should]` | 值得在实现前修正的明确问题。 |
   | `[could]` | 可选的改进。 |

   添加之前，先用 `canvas comment <idea dir> <file>` 列出已有评论，避免重复。之后画布上的画板会显示评论数，点击即可打开评论面板。

7. **总结报告。** 按 `references/review-template.md` 写出 `design/<idea>/review.md`。如果已存在，就在顶部新增一个带日期的小节，而不是覆盖。
8. **只建议状态，不设置状态。** 报告对每个画板给出 `approve`、`revise` 或 `reject` 的建议和一行理由。批准仍由你决定。

给你的回复会列出按严重程度统计的发现数量、带画板 ID 的前三条 `[must]`、状态建议、`review.md` 的路径，并区分已检查的内容和无法检查的内容（例如动效或没有画出的屏幕尺寸）。

### 规则

- **不修改。** 评审者从不改动画板、`tokens.css`、资源或 `canvas.json`，哪怕是一个错别字，而是报告出来。
- **不批准。** 从不替你把画板标记为批准或否决。
- **讲依据，不讲喜好。** 每条发现都要有依据：检查清单规则、规格、令牌或具体的用户问题。
- **清除评论。** `canvas comment ... --clear` 只用于本次会话中自己写的评论，而且只在你要求时使用。
- **语言。** 回复使用你的语言；评论和 `review.md` 使用规格文档的语言，没有规格时使用你的语言。`forbidden_chars` 也不会出现在评论和报告中。
- **服务器。** 不启动、停止或复用你正在运行的服务器。仅用于检查而启动的服务器，通过 PID 或 `lsof -ti:<端口>` 停止。

### 首次评审回顾

所有当前画板都检查过、发现都留在画板上、`review.md` 也已写好，首次评审即告完成。报告末尾会附上与[首版回顾](#首版回顾)格式相同的 **技能改进建议**：最多三条，每条一行，关注工作方式而不是设计。获批准的改动记录在 `skills/mockup-review/references/lessons.md` 中。

## mockup-to-code 技能

mockup-to-code 把已批准的画板实现为你应用中的真实界面，然后把每个运行中的路由与其画板对比，直到只剩下有意为之的差异。**已批准的画板是视觉规范，你应用的框架、组件和数据是材料。**

### 何时触发

- "把已批准的原型做出来"
- "实现已批准的界面"
- "把原型变成代码"
- "让应用和画布一致"

在 Codex 中用 `$mockup-to-code` 调用。和 mockup-review 一样，它使用同级 mockup-canvas 技能的 `canvas.py`。`snap` 和 `compare` 与 `render` 一样需要 Chrome。

### 步骤

1. **范围只限已批准的画板。** 智能体先列出它们：

   ```bash
   canvas impl design/wallet
   ```

   只有用 `canvas status` 标记为 `approved` 的画板才在范围内。夸奖不算批准；如果一个画板都没有批准，智能体会停下来问你要批准哪些。它还会阅读每个画板的状态备注和评论。
2. **写代码之前先了解项目。** 框架及版本、路由、样式方案（CSS 变量、Tailwind、CSS Modules、UI 组件库）、现有组件和令牌、数据层和 API 契约，以及测试、lint、类型检查和开发服务器命令，还有项目自身的说明（README、AGENTS.md、CLAUDE.md）。
3. **令牌只映射一次。** 把 `shared/tokens.css` 集中映射到应用的令牌体系中（各技术栈的要点见 `references/stack-notes.md`）。组件只使用令牌，不从画板复制十六进制颜色、像素字号或圆角。
4. **先做共享外壳。** 布局框架、页头、导航、标签栏、页面宽度和断点，先于任何单个界面完成。
5. **逐个界面。** 一次实现一个已批准的画板，放在它的路由上。在第二个画板上也出现的部分提取为组件。空状态、加载中和错误作为界面的真实状态实现，而不是单独的页面。
6. **真实行为，真实数据。** 界面接入现有的数据契约。后端尚未就绪的地方，使用明确标注的桩代码（`TODO(mockup-to-code)`）并在报告中列出。保留现有的行为、校验、路由、埋点和无障碍。
7. **逐个界面对比。** 在空闲端口上运行应用的开发服务器后：

   ```bash
   canvas compare design/wallet W01-Home.html --url http://localhost:5173/
   ```

   这会把 `board.png`、`app.png`、`diff.png`、`side.png` 和 `report.json`（含 `mismatch_percent`）写到 `design/wallet/compare/W01-Home/`。智能体亲自查看 `side.png` 和 `diff.png`，修正布局、间距、字体、颜色和缺失的元素，然后再次对比。当剩下的每处差异都是有意为之（真实数据、字体渲染、抗锯齿、平台原生控件）并且能逐一说明时就停止。

   | 情况 | 做法 |
   | --- | --- |
   | 画板画了真实应用没有的假状态栏 | `--align-top N`（N 为状态栏高度，通常 44 到 54 px）；绝不在应用里加假状态栏 |
   | 应用从顶部开始，但某一条带不同 | `--ignore-top N`，画出的 Home 指示条用 `--ignore-bottom N` |
   | 应用会拉取数据或有入场动画 | 调高 `--wait MS`（默认 3000） |
   | 想看没有画板的其他尺寸或状态 | `canvas snap <url> --size mobile --out FILE.png` |

   粗略来说，约 2% 以下通常是字体渲染和抗锯齿，2% 到 10% 通常是间距、行高或缺少元素，超过 10% 通常是布局偏移。百分比是参考，不是目标。
8. **记录实现。**

   ```bash
   canvas impl design/wallet W01-Home.html --route / --file src/pages/Home.tsx --file src/components/TabBar.tsx
   canvas impl design/wallet --strict
   ```

   之后画布上的画板会显示 `built` 徽章。只要还有已批准的画板没有实现，`--strict` 就以 1 退出；`--clear` 用于重置错误的记录。
9. **项目检查。** 运行测试、lint 和类型检查。构建通过不能证明界面与画板一致，截图一致也不能证明行为正确；报告会同时说明两者。
10. **统一打磨一次。** 范围内的界面全部完成后，对所有界面统一检查一遍对齐、间距节奏、字号层级、状态、焦点和悬停以及响应式表现，并对改动过的界面重新运行 `compare`。通用规则从不覆盖你在已批准画板上做出的选择。
11. **停止自己启动的服务器**，通过 PID 或 `lsof -ti:<端口>`，不碰你的服务器。

最终报告（`references/final-reply.md`）列出已实现的画板和路由、改动的文件、每个画板的对比结果及 `side.png` 和 `diff.png` 的路径、剩余差异及其可接受的理由、桩代码和缺口、项目检查结果，以及已验证和未验证的内容（例如真实后端、其他浏览器或没有画板的尺寸）。

### 规则

- **批准由你决定。** 从不把画板标记为批准，没有你的决定也不会实现未批准的画板。
- **画板只读。** 从不手动编辑画板、`tokens.css` 或 `canvas.json`。如果画板有误或无法照原样实现，会报告出来并建议一条 `canvas comment`。
- **以已批准的画板为准，** 而不是已否决的画板或旧界面。
- **不只凭数字声称一致。** 在说界面一致之前，会亲自查看图片。
- **Git。** 遵守项目的 git 规则，除非你要求，否则不提交、不推送、不部署。
- **子智能体。** 拆分工作时，每个子智能体会拿到已批准画板的路径和备注、令牌映射、外壳组件、它负责的路由和文件以及对比命令。令牌映射和外壳由主智能体负责。

### 首次实现回顾

范围内的画板全部实现、对比并用 `impl` 记录，且项目检查已运行，首次实现即告完成。报告末尾会附上与[首版回顾](#首版回顾)格式相同的 **技能改进建议**，回顾的是工作方式而不是代码。获批准的改动记录在 `skills/mockup-to-code/references/lessons.md` 中。

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
