# mockup-canvas 스킬

[English](skill.md) | [한국어](skill.ko.md) | [简体中文](skill.zh-CN.md) | [日本語](skill.ja.md)

mockup-canvas에는 CLI 하나를 함께 쓰는 스킬 세 개가 들어 있습니다.

| 스킬 | 지침 | 하는 일 |
| --- | --- | --- |
| mockup-canvas | [`skills/mockup-canvas/SKILL.md`](../skills/mockup-canvas/SKILL.md) | 화면 목업을 HTML 아트보드로 그려 로컬 캔버스에 보여 줍니다. |
| mockup-review | [`skills/mockup-review/SKILL.md`](../skills/mockup-review/SKILL.md) | 그려 둔 화면을 리뷰하고 지적 사항을 보드에 코멘트로 남깁니다. |
| mockup-to-code | [`skills/mockup-to-code/SKILL.md`](../skills/mockup-to-code/SKILL.md) | 승인된 보드를 앱에 구현하고 화면마다 보드와 비교합니다. |

이 문서는 에이전트가 단계마다 무엇을 하고 어떤 명령을 실행하는지, 그리고 사용자가 무엇을 조정할 수 있는지 설명합니다. [mockup-review](#mockup-review-스킬)와 [mockup-to-code](#mockup-to-code-스킬) 설명은 mockup-canvas 작업 순서 뒤에 있습니다.

핵심은 이것입니다. **HTML 파일 하나가 화면(아트보드) 하나, 아이디어 하나가 캔버스 하나이고, 원본은 언제나 HTML입니다.** 캔버스는 그것을 보여 주기만 합니다.

## 언제 동작하나

에이전트는 이런 요청에서 스킬을 불러옵니다.

- "...목업 그려줘"
- "...화면 시안 몇 개 만들어줘"
- "캔버스에 올려줘"
- "폰으로 보여줘"

기존 화면 묶음 수정, 흐름 화살표 추가, 승인 표시, 휴대폰 공유도 여기에 포함됩니다. 다 그린 화면을 비평하는 일(mockup-review)이나 실제 앱 코드를 구현하는 일(mockup-to-code)에는 쓰지 **않습니다**.

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

`design/wallet/` 아래에 `boards/`, `assets/`, `render/`, `shared/tokens.css`(기본 토큰 파일), `canvas.json`, 그리고 `render/`와 `compare/`를 제외하는 `.gitignore`가 생깁니다. `design/` 폴더도 캔버스 서버에 등록되므로 `roots add`를 따로 할 필요가 없습니다. 프로젝트가 없으면 `~/design/<idea>/`를 씁니다.

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

관련 화면은 흐름 순서대로 왼쪽에서 오른쪽으로 한 줄에 놓습니다. 크기 프리셋은 `mobile`(390x844), `tablet`(768x1024), `desktop`(1440x900)이고, `1280x800`처럼 `WxH`로 직접 지정할 수도 있습니다. `--size`를 생략하면 파일 앞부분의 `width: ...px; height: ...px` 스타일에서 크기를 읽고, 없으면 390x844를 씁니다. 보드 내용이 잘리면 에이전트는 내용을 줄이지 않고 새 `--size`로 `add`를 다시 실행합니다.

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
- 에이전트는 바꾼 아트보드마다 `render`로 만든 PNG를 직접 엽니다. 렌더링은 보드 크기 그대로이고, 스크롤 아래 내용은 `render --full-page`로 담습니다. 여러 개를 바꿨다면 흐름 화살표와 그룹까지 담긴 `overview` PNG도 봅니다.
- 오류 문구나 깨진 이미지가 보이면 사용자에게 보여 주기 전에 고칩니다.

### 7. 보여 주기

```bash
canvas serve
```

레지스트리 모드는 등록된 모든 프로젝트를 포트 4400의 서버 하나로 보여 줍니다. `http://localhost:4400/`은 모든 프로젝트와 아이디어를 모은 대시보드이고, `http://localhost:4400/<project>/<idea>/`는 아이디어 하나의 캔버스입니다. 에이전트는 출력된 주소를 그대로 전달하고 서버는 켜 둡니다. 기존 프로젝트를 한 번에 등록하려면 다음을 실행합니다.

```bash
canvas roots scan ~/work ~/projects
```

디자인 폴더 하나만 보려면 `canvas serve design`을 쓰고, 주소는 `http://127.0.0.1:4400/<idea>/`입니다. 프로젝트 추가, 이름 변경, 제거는 브라우저의 대시보드에서도 할 수 있습니다. 포트, 휴대폰 공유, 백그라운드 실행은 [서버 실행하기](../README.ko.md#서버-실행하기)를 보세요.

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
- **`canvas.json`을 손으로 고치지 않습니다.** `canvas add`, `link`, `status`, `group`, `impl`, `comment`로만 바꿉니다. 직접 고치면 병렬로 그리는 서브에이전트나 사용자가 드래그한 변경처럼 동시에 일어난 변경을 덮어쓸 수 있습니다.
- **자기가 띄운 서버만 끕니다.** 사용자가 쓰는 다른 포트는 건드리지 않습니다. 점검용으로만 띄운 서버는 PID나 `lsof -ti:<자기 포트>`로 끄고, 사용자의 서버까지 끄게 되는 `pkill -f canvas.py`는 쓰지 않습니다. 사용자를 위해 띄운 `serve`는 켜 둡니다.
- **`forbidden_chars`를 지킵니다.** `config.json`에 문자가 지정돼 있으면 아트보드, 문서, 보고 어디에도 쓰지 않습니다.
- **병렬로 그리기.** 화면이 많으면 화면 묶음별로 서브에이전트에 나눠 맡길 수 있습니다. 이때 `tokens.css`는 메인 에이전트가 먼저 정합니다.
- **별 안내는 한 번만.** 이 컴퓨터에서 첫 작업이 끝나면 세 스킬 중 하나가 GitHub 별이 다른 사람이 mockup-canvas를 찾는 데 도움이 된다는 한 줄을 답 끝에 붙이고, `${MOCKUP_CANVAS_HOME:-~/.mockup-canvas}/.star-hint-shown` 파일을 만든 뒤 다시는 말하지 않습니다(이 파일을 직접 만들어 두면 꺼집니다).

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

## mockup-review 스킬

mockup-review는 두 번째 디자이너처럼 아이디어를 리뷰합니다. 아트보드 하나하나와 화면 사이의 흐름을 점검하고, 지적 사항은 해당 보드에 남기고, 요약을 하나 씁니다. **리뷰어는 보고만 하고 고치지 않습니다.** 화면을 그린 에이전트나 세션이 아닌 다른 쪽에서 돌릴 때 가장 잘 동작합니다. 새 맥락은 작성자의 가정을 공유하지 않기 때문입니다. 같은 세션에서 화면을 그렸다면 보고서에 그렇게 적습니다.

### 언제 동작하나

- "목업 리뷰해줘"
- "화면 점검해줘"
- "이 디자인 비평해줘"
- "빠진 거 없어?"

`design/<idea>/` 아래 이미 그려 둔 화면에 씁니다. Codex에서는 `$mockup-review`로 부릅니다. 형제 스킬인 mockup-canvas의 `canvas.py`(자기 폴더 기준 `../mockup-canvas/scripts/canvas.py`)를 쓰며, 그 스킬이 설치돼 있지 않으면 멈춥니다.

### 순서

1. **맥락 읽기.** 아이디어 폴더를 찾고, 화면의 근거가 된 기획 문서, `shared/tokens.css`, `canvas.json`(그룹, 링크, 상태, 메모), 기존 `review.md`를 읽습니다. 기획 문서가 없으면 화면만 보고 리뷰하고 그 사실을 적습니다.
2. **기계 점검.** `canvas check`가 알려 준 문제는 모두 지적 사항이 됩니다. `canvas overview` PNG에서 화살표, 그룹, 혼자 떨어진 화면도 봅니다.
3. **보드별 점검.** `current` 그룹의 보드마다(반려된 보드와 "old drafts"는 요청이 없으면 건너뜀) 렌더링해 PNG를 보고, HTML을 읽고, `references/checklist.md`를 따라 상태 화면, 흐름, 토큰 일관성, 기본 접근성, 모바일 엄지 닿는 범위, 문구, 기획 일치를 확인합니다. 판단하기 전에 `--full-page`로 스크롤 아래 내용까지 봅니다.

   ```bash
   canvas render design/wallet W02-Send.html --full-page
   ```

4. **흐름.** 시작 화면부터 링크를 따라갑니다. 보드의 버튼이나 링크는 모두 캔버스의 다른 보드로 이어지거나 흐름의 끝이라고 명시돼 있어야 합니다. 막다른 화면, 닿지 않는 보드, 없는 보드를 가리키는 링크는 지적 사항입니다.
5. **기획 일치.** 필수 기능인데 화면이 없거나, 기획과 어긋나는 화면은 지적 사항입니다.
6. **보드에 코멘트.** 지적 사항 하나에 코멘트 하나를 해당 보드에 남기고, 앞에 심각도 태그를 붙입니다.

   ```bash
   canvas comment design/wallet W02-Send.html "[must] 송금 실패 시 오류 상태가 없음. 기획 3.2는 재시도를 요구" --by reviewer
   ```

   | 태그 | 뜻 |
   | --- | --- |
   | `[must]` | 승인을 막음: 끊긴 흐름, 빠진 필수 상태, 기획과 어긋남, 읽을 수 없는 글자, `check` 문제. |
   | `[should]` | 구현 전에 고칠 만한 분명한 문제. |
   | `[could]` | 선택적 개선. |

   추가하기 전에 `canvas comment <idea dir> <file>`로 기존 코멘트를 보고 같은 내용을 반복하지 않습니다. 그러면 캔버스의 보드에 코멘트 수가 표시되고, 누르면 코멘트 패널이 열립니다.

7. **요약 보고서.** `references/review-template.md`를 바탕으로 `design/<idea>/review.md`를 씁니다. 이미 있으면 덮어쓰지 않고 맨 위에 날짜가 붙은 새 구역을 추가합니다.
8. **상태는 권고만.** 보고서에 보드마다 `approve`, `revise`, `reject` 권고와 한 줄 이유를 적습니다. 승인은 사용자가 결정합니다.

사용자에게는 심각도별 지적 수, 보드 ID가 붙은 상위 `[must]` 세 개, 상태 권고, `review.md` 경로, 그리고 확인한 것과 확인하지 못한 것(예: 움직임, 그리지 않은 화면 크기)을 나눠 답합니다.

### 규칙

- **고치지 않습니다.** 아트보드, `tokens.css`, 에셋, `canvas.json`은 오탈자 하나도 건드리지 않고 보고만 합니다.
- **승인하지 않습니다.** 사용자 대신 보드를 승인하거나 반려하지 않습니다.
- **취향이 아니라 근거.** 지적 사항마다 체크리스트 규칙, 기획 문서, 토큰, 구체적인 사용자 문제 같은 근거가 있어야 합니다.
- **코멘트 지우기.** `canvas comment ... --clear`는 이번 세션에서 자기가 쓴 코멘트에만, 사용자가 요청할 때만 씁니다.
- **언어.** 답은 사용자의 언어로, 코멘트와 `review.md`는 기획 문서의 언어로(없으면 사용자의 언어로) 씁니다. `forbidden_chars`는 코멘트와 보고서에도 쓰지 않습니다.
- **서버.** 사용자가 띄운 서버는 켜거나 끄거나 재사용하지 않습니다. 점검용으로만 띄운 서버는 PID나 `lsof -ti:<포트>`로 끕니다.

### 첫 리뷰 회고

현재 보드를 모두 점검하고, 지적 사항을 보드에 남기고, `review.md`를 쓰면 첫 리뷰가 끝납니다. 보고 끝에는 [첫 초안 회고](#첫-초안-회고)와 같은 형식의 **스킬 개선 제안**을 붙입니다. 디자인이 아니라 일한 방식에 대한 한 줄짜리 항목 최대 3개입니다. 승인된 변경은 `skills/mockup-review/references/lessons.md`에 남습니다.

## mockup-to-code 스킬

mockup-to-code는 승인된 보드를 사용자 앱의 실제 화면으로 구현하고, 실행 중인 각 경로를 보드와 비교해 의도한 차이만 남을 때까지 고칩니다. **승인된 보드가 화면 기준이고, 앱의 프레임워크, 컴포넌트, 데이터가 재료입니다.**

### 언제 동작하나

- "승인된 목업 구현해줘"
- "승인된 화면 만들어줘"
- "목업을 코드로 옮겨줘"
- "앱을 캔버스랑 똑같이 맞춰줘"

Codex에서는 `$mockup-to-code`로 부릅니다. mockup-review처럼 형제 스킬 mockup-canvas의 `canvas.py`를 씁니다. `snap`과 `compare`는 `render`처럼 Chrome이 필요합니다.

### 순서

1. **범위는 승인된 보드만.** 에이전트가 목록을 봅니다.

   ```bash
   canvas impl design/wallet
   ```

   `canvas status`로 `approved` 표시된 보드만 범위에 들어갑니다. 칭찬은 승인이 아니며, 승인된 보드가 없으면 에이전트가 멈추고 어떤 보드를 승인할지 묻습니다. 보드마다 상태 메모와 코멘트도 읽습니다.
2. **코드 쓰기 전에 프로젝트 파악.** 프레임워크와 버전, 라우팅, 스타일 방식(CSS 변수, Tailwind, CSS 모듈, UI 키트), 기존 컴포넌트와 토큰, 데이터 계층과 API 계약, 테스트, 린트, 타입 검사, 개발 서버 명령, 그리고 프로젝트 자체 지침(README, AGENTS.md, CLAUDE.md)을 확인합니다.
3. **토큰은 한 번만 옮기기.** `shared/tokens.css`를 앱의 토큰 체계 한 곳으로 옮깁니다(스택별 요령은 `references/stack-notes.md`). 컴포넌트는 토큰만 쓰고, 아트보드의 hex 색, 픽셀 글자 크기, 모서리 반경을 복사하지 않습니다.
4. **공통 셸 먼저.** 레이아웃 틀, 헤더, 내비게이션, 탭 바, 페이지 폭, 브레이크포인트를 개별 화면보다 먼저 만듭니다.
5. **화면 하나씩.** 승인된 보드 하나를 그 경로에 구현합니다. 두 번째 보드에도 나오는 부분은 컴포넌트로 뽑습니다. 빈 상태, 로딩, 오류는 별도 페이지가 아니라 화면의 실제 상태로 만듭니다.
6. **실제 동작, 실제 데이터.** 기존 데이터 계약에 연결합니다. 백엔드가 준비되지 않은 곳은 분명히 표시한 스텁(`TODO(mockup-to-code)`)을 쓰고 보고에 적습니다. 기존 동작, 검증, 라우팅, 분석, 접근성은 그대로 지킵니다.
7. **화면마다 비교.** 앱 개발 서버를 빈 포트에 띄운 뒤 실행합니다.

   ```bash
   canvas compare design/wallet W01-Home.html --url http://localhost:5173/
   ```

   `design/wallet/compare/W01-Home/`에 `board.png`, `app.png`, `diff.png`, `side.png`, `report.json`(`mismatch_percent` 포함)이 생깁니다. 에이전트가 `side.png`와 `diff.png`를 직접 보고 레이아웃, 간격, 글꼴, 색, 빠진 요소를 고친 뒤 다시 비교합니다. 남은 차이가 모두 의도한 것(실제 데이터, 폰트 렌더링, 안티앨리어싱, 플랫폼 기본 컨트롤)이고 하나하나 이름을 댈 수 있으면 멈춥니다.

   | 상황 | 할 일 |
   | --- | --- |
   | 보드에 실제 앱에는 없는 가짜 상태 표시줄이 있음 | `--align-top N`(N은 표시줄 높이, 보통 44~54 px). 앱에 가짜 표시줄을 넣지 않음 |
   | 앱은 맨 위부터 시작하지만 띠 하나가 다름 | `--ignore-top N`, 그려 둔 홈 인디케이터는 `--ignore-bottom N` |
   | 앱이 데이터를 받아 오거나 애니메이션으로 나타남 | `--wait MS`(기본 3000)를 늘림 |
   | 보드가 없는 크기나 상태를 더 보고 싶음 | `canvas snap <url> --size mobile --out FILE.png` |

   대략 2% 미만은 보통 폰트 렌더링과 안티앨리어싱, 2%~10%는 간격, 줄 높이, 빠진 요소, 10% 초과는 레이아웃이 밀린 경우가 많습니다. 비율은 참고값이지 목표가 아닙니다.
8. **구현 기록.**

   ```bash
   canvas impl design/wallet W01-Home.html --route / --file src/pages/Home.tsx --file src/components/TabBar.tsx
   canvas impl design/wallet --strict
   ```

   그러면 캔버스의 보드에 `built` 배지가 붙습니다. `--strict`는 구현이 없는 승인 보드가 남아 있으면 1로 종료하고, `--clear`는 잘못된 기록을 지웁니다.
9. **프로젝트 점검.** 테스트, 린트, 타입 검사를 돌립니다. 빌드가 통과해도 화면이 보드와 같다는 증거가 아니고, 스크린샷이 같아도 동작한다는 증거가 아니므로 보고에 둘 다 적습니다.
10. **한 번의 다듬기.** 범위 안 화면을 모두 마친 뒤 정렬, 간격 리듬, 글꼴 단계, 상태, 포커스와 호버, 반응형을 모든 화면에 걸쳐 한 번에 다듬고, 바뀐 화면은 다시 `compare`합니다. 일반 규칙이 승인된 보드에서 사용자가 고른 것을 덮어쓰지 않습니다.
11. **자기가 띄운 서버 끄기.** PID나 `lsof -ti:<포트>`로 끄고, 사용자의 서버는 건드리지 않습니다.

최종 보고(`references/final-reply.md`)에는 구현한 보드와 경로, 바꾼 파일, 보드별 비교 결과와 `side.png`, `diff.png` 경로, 남은 차이와 각각 괜찮은 이유, 스텁과 빈틈, 프로젝트 점검 결과, 확인한 것과 확인하지 못한 것(예: 실제 백엔드, 다른 브라우저, 보드가 없는 크기)을 적습니다.

### 규칙

- **승인은 사용자의 몫.** 보드를 승인 처리하지 않고, 사용자의 결정 없이 승인되지 않은 보드를 구현하지 않습니다.
- **보드는 읽기 전용.** 아트보드, `tokens.css`, `canvas.json`을 손으로 고치지 않습니다. 보드가 틀렸거나 그대로 만들 수 없으면 보고하고 `canvas comment`를 제안합니다.
- **기준은 승인된 보드.** 반려된 보드나 예전 UI를 기준으로 삼지 않습니다.
- **숫자만으로 일치를 주장하지 않기.** 화면이 같다고 말하기 전에 이미지를 직접 봅니다.
- **Git.** 프로젝트의 git 규칙을 따르고, 요청이 없으면 커밋, 푸시, 배포하지 않습니다.
- **서브에이전트.** 일을 나눌 때는 각 서브에이전트에 승인된 보드 경로와 메모, 토큰 매핑, 셸 컴포넌트, 맡을 경로와 파일, 비교 명령을 줍니다. 토큰 매핑과 셸은 메인 에이전트가 맡습니다.

### 첫 구현 회고

범위 안 보드를 모두 구현하고, 비교하고, `impl`로 기록하고, 프로젝트 점검까지 돌리면 첫 구현이 끝납니다. 보고 끝에는 [첫 초안 회고](#첫-초안-회고)와 같은 형식으로, 코드가 아니라 일한 방식을 돌아보는 **스킬 개선 제안**을 붙입니다. 승인된 변경은 `skills/mockup-to-code/references/lessons.md`에 남습니다.

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
