# mockup-canvas 스킬

[English](skill.md) | [한국어](skill.ko.md) | [简体中文](skill.zh-CN.md) | [日本語](skill.ja.md)

mockup-canvas 스킬은 Claude Code나 Codex가 화면 목업을 HTML 아트보드로 그려 로컬 캔버스에 보여 주도록 안내하는 지침 모음입니다. 내용은 [`skills/mockup-canvas/SKILL.md`](../skills/mockup-canvas/SKILL.md)에 있습니다. 이 문서는 에이전트가 단계마다 무엇을 하고 어떤 명령을 실행하는지, 그리고 사용자가 무엇을 조정할 수 있는지 설명합니다.

핵심은 이것입니다. **HTML 파일 하나가 화면(아트보드) 하나, 아이디어 하나가 캔버스 하나이고, 원본은 언제나 HTML입니다.** 캔버스는 그것을 보여 주기만 합니다.

## 언제 동작하나

에이전트는 이런 요청에서 스킬을 불러옵니다.

- "...목업 그려줘"
- "...화면 시안 몇 개 만들어줘"
- "캔버스에 올려줘"
- "폰으로 보여줘"

기존 화면 묶음 수정, 흐름 화살표 추가, 승인 표시, 휴대폰 공유도 여기에 포함됩니다. 실제 앱 코드를 구현하는 용도는 **아닙니다**.

- **Claude Code**는 스킬 설명을 보고 알아서 고르며, 이름을 직접 말해도 됩니다.
- **Codex**는 `$mockup-canvas`라고 쓰면 사용합니다. 예: `Use $mockup-canvas to draw screen mockups for this idea.`

## 에이전트가 CLI를 실행하는 방식

스킬은 `python3 <skill-dir>/scripts/canvas.py <command>`를 호출합니다. `<skill-dir>`는 설치 방법에 따라 다릅니다.

| 설치 방법 | 스킬 폴더 |
| --- | --- |
| Claude Code 플러그인 | `${CLAUDE_PLUGIN_ROOT}/skills/mockup-canvas` |
| 수동 설치, Claude Code | `~/.claude/skills/mockup-canvas` |
| 수동 설치, Codex | `~/.codex/skills/mockup-canvas` |

에이전트는 먼저 짧은 셸 함수를 정의하고, 이 문서의 예시도 그 함수를 씁니다.

```bash
canvas() { python3 <skill-dir>/scripts/canvas.py "$@"; }
```

## 작업 순서

### 1. 아이디어 찾기

`design/` 아래에 같은 아이디어가 있으면 이어서 작업합니다. 그리기 전에 기획 문서, 기존 화면, 사용자가 좋아했거나 반려한 방향을 먼저 확인합니다. 새 아이디어라면 다음을 실행합니다.

```bash
canvas new design wallet
```

`design/wallet/` 아래에 `boards/`, `assets/`, `render/`, `shared/tokens.css`(기본 토큰 파일), `canvas.json`, 그리고 `render/`를 제외하는 `.gitignore`가 생깁니다. `design/` 폴더도 캔버스 서버에 등록되므로 `roots add`를 따로 할 필요가 없습니다. 프로젝트가 없으면 `~/design/<idea>/`를 씁니다.

### 2. 토큰 먼저

화면을 그리기 전에 `shared/tokens.css`에 색, 글꼴, 간격, 모서리 반경을 정합니다. 아트보드는 `var(--...)`만 쓰고 새 색상 값을 임의로 만들지 않습니다. 그래서 모든 화면이 일관되고, 색을 바꿀 때도 파일 하나만 고치면 됩니다.

### 3. 그리기

아트보드는 브라우저에서 단독으로 열어도 똑같이 보이는 독립된 HTML 파일이어야 합니다.

- 상대 경로만 씁니다: `../shared/tokens.css`, `../assets/x.png`.
- 외부 리소스는 Google Fonts만 허용합니다.
- 커스텀 태그와 외부 스크립트는 쓰지 않습니다.

파일 이름은 `<ID>-<EnglishName>.html` 형식입니다(예: `F06-Letter.html`). ID는 아이디어 이름의 첫 글자를 대문자로 쓰고 두 자리 숫자를 붙입니다(`W01`, `W02`, ...). 프로젝트에 이미 화면 ID 체계가 있으면 그걸 따릅니다.

### 4. 등록

파일을 먼저 `boards/`에 쓰고 등록합니다.

```bash
canvas add design/wallet boards/W01-Home.html --group current --size mobile
```

관련 화면은 흐름 순서대로 왼쪽에서 오른쪽으로 한 줄에 놓습니다. 크기 프리셋은 `mobile`(390x844), `tablet`(768x1024), `desktop`(1440x900)이고, `1280x800`처럼 `WxH`로 직접 지정할 수도 있습니다. `--size`를 생략하면 파일 앞부분의 `width: ...px; height: ...px` 스타일에서 크기를 읽고, 없으면 390x844를 씁니다.

### 5. 흐름 연결

```bash
canvas link design/wallet W01-Home.html W02-Send.html --label "송금"
```

화살표 하나가 한 화면에서 다른 화면으로 넘어가는 길을 보여 줍니다. 사용자가 화면 수를 정해 줬다면 딱 그만큼만 그리고, 빠진 상태 화면(빈 화면, 오류, 로딩, 권한 없음)은 보고에서 제안만 합니다. 정해 주지 않았다면 상태 화면까지 흐름에 넣습니다.

### 6. 점검

```bash
canvas check design/wallet
canvas render design/wallet W01-Home.html
canvas overview design/wallet
```

- `check` 결과는 문제 0개여야 합니다. 없는 파일, 깨진 `src`, `href`, `url()` 참조, `canvas.json`에 등록되지 않은 아트보드, 겹친 아트보드, 등록되지 않은 보드를 가리키는 링크, 금지 문자를 잡아냅니다.
- 에이전트는 바꾼 아트보드마다 `render`로 만든 PNG를 직접 엽니다. 여러 개를 바꿨다면 흐름 화살표와 그룹까지 담긴 `overview` PNG도 봅니다.
- 오류 문구나 깨진 이미지가 보이면 사용자에게 보여 주기 전에 고칩니다.

### 7. 보여 주기

```bash
canvas serve
```

레지스트리 모드는 등록된 모든 프로젝트를 포트 4400의 서버 하나로 보여 줍니다. 주소는 `http://localhost:4400/<project>/<idea>/`입니다. 에이전트는 출력된 주소를 그대로 전달하고 서버는 켜 둡니다. 기존 프로젝트를 한 번에 등록하려면 다음을 실행합니다.

```bash
canvas roots scan ~/work ~/projects
```

디자인 폴더 하나만 보려면 `canvas serve design`을 쓰고, 주소는 `http://127.0.0.1:4400/<idea>/`입니다. 프로젝트 추가와 제거는 브라우저의 목록 페이지에서도 할 수 있습니다.

### 8. 휴대폰으로 보기

- **호스팅 페이지(쓸 수 있으면 기본).** Claude artifact처럼 비공개 호스팅 페이지를 쓸 수 있는 환경이면 에이전트가 정적 번들을 만들어 올립니다. `index.html`이 페이지이고 나머지는 함께 올리는 파일입니다.

  ```bash
  canvas export design/wallet ./wallet-export
  canvas artifact design/wallet <url>
  ```

  올리기 전에 아이디어마다 한 번 묻습니다. 계속 올려 두라고 하면 이후에는 묻지 않고 변경할 때마다 같은 주소에 다시 올립니다. `canvas artifact`는 주소를 `canvas.json`에 저장해서 다른 세션도 같은 페이지를 갱신하게 합니다. 내보낼 폴더는 아이디어 폴더 바깥이어야 하고 아이디어 폴더를 품어서도 안 됩니다. 아이디어 폴더 밖을 가리키는 심볼릭 링크는 빠집니다.

- **같은 네트워크에서 실시간으로.**

  ```bash
  canvas serve design --share --minutes 30
  ```

  에이전트가 토큰이 붙은 주소를 알려 줍니다. 휴대폰에서는 보기만 가능하고, 시간이 지나면 닫힙니다(`--minutes`는 1~240). 레지스트리 서버에서 등록된 프로젝트 하나만 공유하려면 `canvas serve --share --project NAME`을 씁니다. 레지스트리 공유는 시작할 때 등록된 프로젝트만 보여 주고 폴더 경로는 숨깁니다.

- **간단한 대안.** `overview` PNG를 보내 줄 수도 있습니다.

### 9. 이전 버전 보존

이전 버전은 절대 지우지 않습니다. 옮기고 표시만 합니다.

```bash
canvas group design/wallet W02-Send.html "old drafts"
canvas status design/wallet W02-Send.html rejected
```

반려된 아트보드는 회색 배지와 취소선 제목으로 표시되어, 무엇을 반려했는지가 현재 버전 옆에 그대로 남습니다.

### 10. 승인이 곧 기록

사용자가 화면을 승인하면 에이전트가 기록합니다.

```bash
canvas status design/wallet W01-Home.html approved --note "홈 레이아웃과 카드 목록"
```

초록 배지와 메모가 승인 기록입니다. "괜찮네" 같은 단순한 칭찬은 승인이 아닙니다. `canvas check`는 승인된 아트보드 수도 함께 출력합니다(예: `Approved boards: 2/6`).

## 에이전트가 지키는 규칙

- **사용자의 언어로 답합니다.** 사용자가 쓴 언어로 답합니다.
- **`canvas.json`을 손으로 고치지 않습니다.** `canvas add`, `link`, `status`, `group`으로만 바꿉니다. 직접 고치면 병렬로 그리는 서브에이전트나 사용자가 드래그한 변경처럼 동시에 일어난 변경을 덮어쓸 수 있습니다.
- **자기가 띄운 서버만 끕니다.** 사용자가 쓰는 다른 포트는 건드리지 않습니다. 점검용으로만 띄운 서버는 PID나 `lsof -ti:<자기 포트>`로 끄고, 사용자의 서버까지 끄게 되는 `pkill -f canvas.py`는 쓰지 않습니다. 사용자를 위해 띄운 `serve`는 켜 둡니다.
- **`forbidden_chars`를 지킵니다.** `config.json`에 문자가 지정돼 있으면 아트보드, 문서, 보고 어디에도 쓰지 않습니다.
- **병렬로 그리기.** 화면이 많으면 화면 묶음별로 서브에이전트에 나눠 맡길 수 있습니다. 이때 `tokens.css`는 메인 에이전트가 먼저 정합니다.

## 첫 초안 회고

요청한 화면을 모두 그리고 `check`를 통과하면 첫 초안이 끝납니다. 에이전트는 보고 끝에 **스킬 개선 제안**을 붙입니다. 디자인 점검은 6단계에서 끝났으므로, 여기서는 일한 방식만 돌아봅니다.

- **보는 것**(이번 작업에서 실제로 일어난 일만): 사용자가 반복하거나 바로잡아야 했던 것과 그 뒤에 있는 규칙의 빈틈, 재작업, `canvas` 명령이 없어서 손으로 우회해야 했던 곳, 오류, 느리거나 불필요했던 단계, 따르기 어렵거나 서로 충돌한 규칙.
- **형식**: 최대 3개, 각각 "무슨 일이 있었나, 영향, 바꿀 규칙이나 명령" 한 줄. 없으면 "이번에는 없음".
- **반영**: 제안만 합니다. 사용자가 승인한 제안만 스킬에 반영하고, `references/lessons.md`에 한 줄을 추가합니다.

예시:

```text
스킬 개선 제안
1. 요청에 지도 크기가 없어 T02를 다시 그림, 한 번 더 왕복, 지도나 차트가 중심인 화면은 핵심 요소 크기를 먼저 물어보기.
2. 이전 시안을 파일 하나씩 옮김, 화면 6개라 느림, `canvas group`이 여러 파일을 받도록 하기.
```

## 커스터마이즈

### 금지 문자

`~/.mockup-canvas/config.json`(또는 `$MOCKUP_CANVAS_HOME/config.json`)을 만듭니다.

```json
{"forbidden_chars": ["—"]}
```

그러면 `canvas check`가 해당 문자가 들어 있는 아트보드를 코드 포인트와 함께 알려 줍니다.

```text
Error: forbidden character (U+2014) found: W01-Home.html
```

### 아트보드 크기

등록할 때 프리셋이나 정확한 크기를 넘깁니다.

```bash
canvas add design/wallet boards/W10-Dashboard.html --size desktop
canvas add design/wallet boards/W11-Kiosk.html --size 1080x1920
```

또는 아트보드 자체에 `<body style="width:768px;height:1024px">`처럼 크기를 적고 `--size`를 생략해도 됩니다.

### 데이터 폴더

`roots.json`과 `config.json`을 `~/.mockup-canvas/`가 아닌 곳에 두려면 `MOCKUP_CANVAS_HOME`을 지정합니다.

```bash
export MOCKUP_CANVAS_HOME=~/dotfiles/mockup-canvas
```

### 스킬 자체

`SKILL.md`는 평범한 Markdown입니다. 승인된 변경은 `skills/mockup-canvas/references/lessons.md`에 한 줄씩 남으므로, 각 규칙이 왜 생겼는지 확인할 수 있습니다.
