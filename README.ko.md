# mockup-canvas

AI 에이전트와 화면을 기획할 때 쓰는 Claude Code, Codex 스킬 세 개입니다. 에이전트가 로컬의 Figma 같은 캔버스에 HTML 목업을 그리고 리뷰합니다. 그다음 승인한 화면을 앱에 구현하고 목업과 비교합니다.

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

[![Tests](https://github.com/chrisjo-dev/mockup-canvas/actions/workflows/test.yml/badge.svg)](https://github.com/chrisjo-dev/mockup-canvas/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Claude Code, Codex 지원](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex-6b4fbb.svg)](#빠른-시작-claude-code-플러그인-또는-codex-스킬-설치)
[![pip 의존성 없음: Python 표준 라이브러리, PNG 렌더링에만 Chrome](https://img.shields.io/badge/no%20pip%20deps-Python%20stdlib%20%2B%20Chrome-brightgreen.svg)](#faq)

mockup-canvas는 Claude Code와 OpenAI Codex용 무료 오픈소스(MIT) 스킬 세 개입니다. AI 에이전트가 화면을 HTML 목업으로 로컬 캔버스에 그리고, 리뷰하고, 승인한 화면을 구현한 뒤 목업과 비교합니다. 에이전트가 앱 코드를 쓰기 전에 화면을 하나씩 직접 보고 승인할 수 있습니다.

`mockup-canvas`는 화면마다 평범한 HTML 파일을 그리고 Figma 같은 캔버스에 펼쳐 놓습니다. 캔버스에서 이동하고 확대하고, 화면을 흐름 화살표로 잇고, 승인하거나 반려합니다. `mockup-review`는 그 화면들을 리뷰하고 지적 사항을 해당 아트보드에 코멘트로 남깁니다. `mockup-to-code`는 승인된 화면을 앱에 구현하고, 실행 중인 각 경로를 목업과 픽셀 단위로 비교해 의도한 차이만 남을 때까지 고칩니다.

목업은 호스팅 도구가 아니라 내 저장소에 파일로 남습니다. 캔버스는 계정 없이 `127.0.0.1`에서 돌고, 승인, 코멘트, 구현 기록은 `canvas.json`에 저장됩니다. Python 3.8 이상만 있으면 됩니다(표준 라이브러리만 쓰고 pip 패키지는 없습니다). Google Chrome, Chromium, Edge는 PNG를 렌더링하고 캡처할 때만 씁니다.

AI 어시스턴트가 읽을 텍스트 요약은 [llms.txt](llms.txt)에 있습니다.

**라이브 데모:** [chrisjo-dev.github.io/mockup-canvas](https://chrisjo-dev.github.io/mockup-canvas/)에서 화면 6개짜리 TrailMate 예제를 캔버스로 볼 수 있습니다. 읽기 전용입니다. 이동과 확대/축소는 되지만 보드를 옮기거나 상태를 바꿀 수는 없습니다.

![다크 모드의 mockup-canvas 대시보드: 프로젝트 3개의 아이디어 카드 7개에 보드 썸네일, 상태 막대, 코멘트와 built와 new 배지가 있고, 왼쪽에 프로젝트와 상태 필터 목록이 있음](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/dashboard.png)

![아이디어 캔버스: 휴대폰 아트보드 3개가 이름 붙은 흐름 화살표로 이어져 있고, 승인 표시, 보라색 built 배지, 코멘트 수가 붙어 있음](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/canvas.png)

![데모: 대시보드에서 코멘트가 있는 아이디어만 거르고, /로 명령 팔레트를 열어 trail을 검색한 뒤 trailmate 아이디어를 캔버스로 열고, 이동과 확대로 승인된 보드와 반려된 보드를 살펴본 다음 한 보드의 리뷰 코멘트를 여는 장면](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/demo.gif)

## 세 가지 스킬

**그리기 → 리뷰 → 승인 → 구현 → 비교**

| 스킬 | 언제 쓰나 | 하는 일 | 요청 예시 |
| --- | --- | --- | --- |
| `mockup-canvas` | 기획 단계, 앱 코드 이전 | 화면마다 HTML 아트보드를 그리고, 흐름을 연결하고, 사용자의 승인을 캔버스에 기록합니다. | `습관 관리 앱 목업 그려줘. 홈, 습관 추가, 주간 통계 화면.` |
| `mockup-review` | 화면을 다 그렸고 다른 눈으로 점검받고 싶을 때 | 모든 보드와 흐름을 기획서와 체크리스트에 비춰 점검하고, `[must]`, `[should]`, `[could]` 코멘트를 보드에 남기고, `review.md`를 쓰고, 승인, 수정, 반려를 권고합니다. 보드를 고치거나 상태를 바꾸지는 않습니다. | `design/habits 목업 리뷰해서 빠진 거 알려줘.` |
| `mockup-to-code` | 승인된 보드가 있을 때 | 승인된 보드를 사용자 앱의 프레임워크로 구현하고, 실행 중인 각 경로를 `canvas compare`로 보드와 비교하고, 경로와 파일을 `canvas impl`로 기록합니다. | `승인된 습관 관리 화면들 우리 앱에 구현해줘.` |

승인은 사용자가 합니다. 승인한 보드(`canvas status ... approved`로 기록)만 구현합니다. 세 스킬 모두 같은 `canvas.py` CLI를 씁니다.

## AI 에이전트로 목업부터 그리는 이유

UI를 글로 설명하면 모호합니다. "상단에 히어로 배너, 아래에 카드 목록이 있는 홈" 같은 문장은 직접 보기 전까지 나와 에이전트가 서로 다르게 이해합니다. 에이전트와 제품을 기획할 때는 화면에 합의하기 전에 화면부터 봐야 합니다. mockup-canvas는 AI와 서비스를 기획하고 만들면서 나온 도구입니다. 필요한 것을 먼저 눈에 보이게 하고, 거기서부터 작업을 이어 갑니다.

에이전트가 화면마다 작은 HTML 파일을 그리면 캔버스가 나란히 보여 줍니다. 이 화면은 승인하고, 저 화면은 반려하고, 다른 안을 요청하면 에이전트가 작업하는 동안 보드가 바로 바뀝니다. 앱 코드는 화면이 승인된 다음에 시작합니다. 그 뒤로는 승인된 목업이 화면 기준이 되고, 만든 화면을 목업과 비교합니다. 목업은 계정 없이 어떤 브라우저에서도 열리는 독립 HTML 파일로 저장소에 남습니다.

## 주요 기능

**캔버스** (`viewer.html`, 로컬에서 제공)

- 디자인 툴처럼 드래그로 이동하고 확대, 축소합니다. 배율이 바뀔 때마다 다시 그리므로 늘어난 비트맵처럼 흐려지지 않습니다.
- 아트보드를 드래그해 옮기면 위치가 `canvas.json`에 저장됩니다. 이동은 실행 취소와 다시 실행이 됩니다.
- 화면 사이에 흐름 화살표를 그리고, 그 화면으로 넘어가는 버튼이나 동작 이름을 붙입니다.
- 승인, 반려 배지가 붙습니다. 메모는 아트보드 제목에 마우스를 올리면 보입니다.
- 구현이 기록된 보드에는 보라색 `built` 배지(마우스를 올리면 경로 표시)가, 리뷰 코멘트가 있는 보드에는 코멘트 수가 붙습니다. 코멘트 수를 누르면 패널에서 내용을 읽을 수 있습니다.
- 아트보드를 접고 펼 수 있는 그룹으로 묶습니다. 예: `current`, `old drafts`.
- 보드가 많아도 부드럽게 움직입니다. 화면 근처의 보드만 실제 페이지를 띄웁니다. 배율 약 30~40% 미만으로 축소하면 캐시된 PNG 썸네일을 보여 줍니다(서버로 열었을 때). 한 번 본 보드는 다시 불러오는 동안 빈 카드 대신 썸네일이 보입니다. 화면 갱신은 애니메이션 프레임마다 한 번으로 묶고, 썸네일은 낮은 우선순위로 뒤에서 만듭니다. 아트보드 71개짜리 캔버스(1440x900, Apple M4, headless Chrome)에서 이동과 확대/축소는 약 59~60 FPS, p95 프레임 시간 약 20 ms이고 50 ms를 넘는 프레임은 없습니다. 처음 열 때와 썸네일이 캐시된 뒤 모두 그렇습니다. `python3 tests/perf_check.py <아이디어 폴더>`로 다시 측정할 수 있습니다.
- 실시간으로 갱신됩니다. 서버가 1초마다 파일 변경을 확인하므로, 아트보드나 `canvas.json`을 고치면 열린 캔버스가 1초 안팎으로 바뀝니다.
- 서버를 열면 등록된 모든 프로젝트의 대시보드가 나옵니다. 최근 보드 썸네일, 상태 수, 코멘트, built 보드를 보여 주는 아이디어 카드가 있고, 결정이 필요한 것만 거르는 필터, 검색과 명령 팔레트(`/` 또는 `Cmd K`), 프로젝트 추가와 디자인 폴더 찾기, 사라진 폴더 경고, 라이트와 다크 테마, 휴대폰 레이아웃이 있습니다. [대시보드](#대시보드)를 보세요.
- 휴대폰에서도 볼 수 있습니다. 같은 네트워크에서 실시간으로 보는 공유 모드와, 어디든 올릴 수 있는 정적 내보내기가 있습니다.

**에이전트 스킬** (`skills/<skill>/SKILL.md`)

- `mockup-canvas`는 Claude Code나 Codex가 목업을 그리고, 등록하고, 연결하고, 점검하고, 보여 주는 순서를 단계별로 알려 줍니다. 이전 버전을 지우지 않고 남기며, 사용자의 승인을 기록으로 삼습니다.
- `mockup-review`는 상태 화면, 흐름, 토큰 일관성, 기본 접근성, 엄지 닿는 범위, 기획서 일치를 점검하고, 지적 사항을 심각도 태그와 함께 해당 보드에 남깁니다.
- `mockup-to-code`는 목업 토큰을 앱의 토큰 체계로 옮기고, 공통 셸을 먼저 만든 뒤, 승인된 보드를 하나씩 구현해 보드와 비교합니다.
- 각 스킬은 첫 작업이 끝나면 짧은 회고로 스킬 자체의 개선안을 제안합니다.

**CLI** (`skills/mockup-canvas/scripts/canvas.py`)

- 약 4,600줄짜리 Python 3 파일 하나입니다. 표준 라이브러리만 쓰고(Python 3.8 이상) pip 의존성은 없습니다. 명령은 18개입니다: `serve`, `roots`, `new`, `add`, `group`, `render`, `check`, `overview`, `export`, `link`, `status`, `artifact`, `snap`, `compare`, `impl`, `comment`, `trash`, `restore`.
- Chrome(또는 Chromium, Edge)은 보드를 렌더링하거나 앱 화면을 PNG로 캡처할 때만 씁니다.

## 대시보드

`canvas serve`를 띄우면 `http://localhost:4400/`에 등록된 모든 프로젝트를 모은 대시보드가 열립니다. 캔버스를 열기 전에 지금 봐야 할 것이 무엇인지 보여 줍니다.

- **아이디어 카드**에는 최근 보드 썸네일, 상태 막대(승인은 초록, 미결정은 회색, 반려는 빨강), 열린 코멘트 수, 구현된 보드 수, 그리고 그 아이디어를 마지막으로 연 뒤 바뀐 보드를 세는 `N new` 배지가 붙습니다.
- **왼쪽 목록**에는 프로젝트와 상태 필터 4개(Needs decision, Has comments, Approved, not built, Built)가 있습니다.
- **검색과 명령 팔레트.** 검색 상자, `/`, `Cmd+K`(`Ctrl+K`)로 모든 프로젝트의 아이디어와 보드를 찾고, 프로젝트 추가 같은 동작도 실행합니다. 보드 결과를 열면 그 보드에 맞춰진 캔버스가 열립니다.
- **보기.** Large와 Compact 카드, 최근 수정순, 이름순, 보드 수 정렬, 그리고 프로젝트마다 상태 필터가 있는 전체 보드 페이지가 있습니다.
- **프로젝트 관리.** Add project로 디자인 폴더를 등록하고, Find in folders로 폴더 안의 디자인 폴더를 찾습니다. 프로젝트마다 이름을 바꾸거나 목록에서 뺄 수 있습니다(파일은 지우지 않습니다).
- **묶음(Collections)** 은 여러 프로젝트에 흩어진 아이디어를 폴더를 옮기지 않고 왼쪽 목록의 이름 하나로 모아 보여 줍니다. 아이디어 카드 메뉴의 Move to collection으로 넣거나, 프로젝트 메뉴의 Add to collection으로 프로젝트 전체(나중에 생기는 아이디어 포함)를 넣습니다. 아이디어 하나는 묶음 하나에만 들어가고, 마지막 아이디어를 빼면 묶음도 사라지며, 묶음은 `roots.json`에 저장됩니다.
- **삭제와 되돌리기.** 아이디어 카드 메뉴의 Delete idea, 묶음 메뉴의 Delete collection으로 지웁니다. 아이디어 폴더는 `design/.trash/`로 옮겨지고, 8초 동안 뜨는 알림의 Undo로 되돌릴 수 있습니다. 묶음을 지워도 안의 아이디어는 그대로 남습니다. 공유 페이지와 읽기 전용 서버에는 삭제가 없습니다.
- **사라진 폴더 경고.** 등록된 프로젝트의 폴더가 옮겨지거나 지워지면 경고와 함께 다시 찾는 버튼을 보여 줍니다.
- **라이트와 다크 테마**(해와 달 버튼 또는 `Shift+T`), 그리고 프로젝트 탭과 상태 메뉴가 있는 휴대폰 레이아웃을 지원합니다.

![라이트 모드의 대시보드: 같은 프로젝트와 아이디어](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/dashboard-light.png)

![대시보드 위에 열린 명령 팔레트: 검색어에 맞는 아이디어와 보드가 상태와 함께 나오고, 필터 동작이 있음](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/palette.png)

![폭 390 px 휴대폰의 대시보드: 프로젝트 탭, 상태 메뉴, 세로로 쌓인 아이디어 카드](https://raw.githubusercontent.com/chrisjo-dev/mockup-canvas/main/docs/images/dashboard-phone.png)

## 빠른 시작: Claude Code 플러그인 또는 Codex 스킬 설치

Claude Code에서 아래 `/plugin` 명령 두 개를 실행합니다. 첫 번째는 `chrisjo-dev/mockup-canvas` 마켓플레이스를 추가하고, 두 번째는 스킬 세 개가 모두 든 플러그인을 설치합니다. 따로 설치할 pip 패키지는 없고, Chrome은 PNG 렌더링에만 씁니다.

### Claude Code 플러그인

```text
/plugin marketplace add chrisjo-dev/mockup-canvas
/plugin install mockup-canvas@mockup-canvas
```

그다음 평소 말투로 요청하면 됩니다.

```text
습관 관리 앱 목업 그려줘. 홈, 습관 추가, 주간 통계 화면.
```

에이전트가 아이디어 폴더를 만들고, 화면을 그리고, 캔버스 서버를 띄운 뒤 `http://localhost:4400/<project>/<idea>/` 같은 주소를 알려 줍니다.

### 수동 설치 (Claude Code, Codex)

```bash
git clone https://github.com/chrisjo-dev/mockup-canvas.git
cd mockup-canvas
./install.sh            # ~/.claude/skills와 ~/.codex/skills에 모든 스킬을 링크
```

- 한쪽만 설치하려면 `./install.sh --claude` 또는 `./install.sh --codex`.
- `./install.sh --dry-run`은 아무것도 바꾸지 않고 할 일만 출력합니다.
- mockup-canvas만이 아니라 `skills/` 아래의 모든 스킬 폴더(mockup-canvas, mockup-review, mockup-to-code)를 링크합니다. 같은 이름의 스킬이나 다른 파일이 대상 위치에 이미 있으면 먼저 `~/.mockup-canvas/backup/<timestamp>/`로 옮기고 링크로 바꿉니다. 여러 번 실행해도 안전합니다.

Codex에서는 스킬 이름으로 부릅니다. 예: `Use $mockup-canvas to draw the sign-up flow.`, `Use $mockup-review to review the sign-up mockups.`, `Use $mockup-to-code to build the approved sign-up screens.`

### 에이전트 없이 예제 열어 보기

```bash
python3 skills/mockup-canvas/scripts/canvas.py serve examples
```

`http://127.0.0.1:4400/trailmate/`를 열면 [`examples/trailmate`](https://github.com/chrisjo-dev/mockup-canvas/blob/main/examples/trailmate/canvas.json)의 화면 6개짜리 예제를 볼 수 있습니다.

## 서버 실행하기

목업을 그릴 때는 에이전트가 서버를 띄우고 주소를 알려 줍니다. 직접 띄우려면 스킬 폴더(`<skill-dir>`)의 `canvas.py`를 실행합니다.

| 설치 방식 | `<skill-dir>` |
| --- | --- |
| Claude Code 플러그인 | 에이전트 명령에서는 `${CLAUDE_PLUGIN_ROOT}/skills/mockup-canvas`, 내 터미널에서는 플러그인 캐시로 보통 `~/.claude/plugins/cache/mockup-canvas/mockup-canvas/<version>/skills/mockup-canvas` |
| 수동 설치 (`install.sh`) | `~/.claude/skills/mockup-canvas` (또는 `~/.codex/skills/mockup-canvas`) |
| 이 저장소를 클론한 경우 | `skills/mockup-canvas` |

팁: `~/.zshrc`나 `~/.bashrc`에 `canvas` 셸 함수를 정의해 두면 아래 명령이 짧아집니다.

```bash
canvas() { python3 ~/.claude/skills/mockup-canvas/scripts/canvas.py "$@"; }
```

### 등록된 모든 프로젝트

```bash
python3 <skill-dir>/scripts/canvas.py serve
```

| 주소 | 보이는 것 |
| --- | --- |
| `http://localhost:4400/` | 등록된 모든 프로젝트의 대시보드 |
| `http://localhost:4400/<project>/<idea>/` | 아이디어 하나의 캔버스 |
| `http://localhost:4400/<project>/<idea>/#<board>` | 보드 하나에 맞춘 같은 캔버스, 예: `#T01-Home` |

서버는 `127.0.0.1`에서만 받습니다. 같은 프로젝트를 보여 주는 서버가 이미 그 포트에 떠 있으면 `serve`는 그 주소만 출력하고 끝납니다. 다른 캔버스 서버가 포트를 쓰고 있으면 다음 빈 포트로 옮겨 그 주소를 출력합니다.

### 디자인 폴더 하나

```bash
python3 <skill-dir>/scripts/canvas.py serve path/to/design
```

이때 `http://localhost:4400/`에는 그 폴더의 아이디어가 나오고, 캔버스는 `http://localhost:4400/<idea>/`에 있습니다.

### 다른 포트

```bash
python3 <skill-dir>/scripts/canvas.py serve --port 4500
```

`--port`는 두 모드 모두에서 씁니다.

### 같은 Wi-Fi의 휴대폰에서 보기

```bash
python3 <skill-dir>/scripts/canvas.py serve --share --minutes 30
python3 <skill-dir>/scripts/canvas.py serve --share --project NAME
python3 <skill-dir>/scripts/canvas.py serve path/to/design --share
```

`--share`는 컴퓨터의 LAN 주소와 무작위 토큰이 붙은 주소(`http://<lan ip>:4400/?t=...`)를 출력합니다. 이 주소를 휴대폰에서 엽니다. 페이지는 읽기 전용이고, 토큰 없는 요청은 거절되며, 서버는 `--minutes`(1에서 240, 기본 30)가 지나면 스스로 멈춥니다. `--project NAME`은 전체 대신 등록된 프로젝트 하나만 공유합니다. 통신은 암호화되지 않은 HTTP이므로 믿을 수 있는 네트워크에서만 공유하세요. [보안 모델](#보안-모델)을 참고하세요.

### 백그라운드로 띄우고 멈추기

```bash
nohup python3 <skill-dir>/scripts/canvas.py serve > /tmp/mockup-canvas.log 2>&1 &
```

로그 파일에 주소와 오류가 남습니다. 터미널 앞에서 띄운 서버는 `Ctrl+C`로 멈춥니다. 백그라운드 서버는 그 포트에서 대기 중인 프로세스를 멈춥니다.

```bash
lsof -ti tcp:4400 -sTCP:LISTEN | xargs kill
```

이 명령은 그 포트의 서버만 멈춥니다. `pkill -f canvas.py`는 다른 세션이나 에이전트가 띄운 서버까지 멈추므로 쓰지 마세요.

## mockup-canvas 동작 방식

각 스킬은 자기 `SKILL.md`의 작업 순서를 따릅니다. 단계별 명령, 규칙, 커스터마이즈 방법은 [docs/skill.ko.md](docs/skill.ko.md)에 정리했습니다.

### 그리기 (mockup-canvas)

1. **아이디어 찾기 또는 만들기.** `design/<idea>/`가 이미 있으면 이어서 작업합니다. 없으면 `canvas new <design dir> <idea>`를 실행하고, 이때 디자인 폴더가 캔버스 서버에 자동 등록됩니다.
2. **토큰 먼저.** 화면을 그리기 전에 색, 글꼴, 간격, 모서리 반경을 `shared/tokens.css`에 정합니다. 아트보드는 `var(--...)`만 씁니다.
3. **아트보드 그리기.** 화면 하나가 `boards/` 안의 HTML 파일 하나이고, 이름은 `W01-Home.html` 형식입니다. 파일만 단독으로 열어도 똑같이 보여야 합니다. 상대 경로만 쓰고, 외부 스크립트는 넣지 않으며, 외부 리소스는 Google Fonts만 허용합니다.
4. **등록.** `canvas add <idea dir> boards/W01-Home.html --group current --size mobile`로 캔버스에 올립니다. 내용이 잘리면 새 `--size`로 `add`를 다시 실행해 보드 크기를 바꿉니다.
5. **흐름 연결.** `canvas link <idea dir> W01-Home.html W02-Detail.html --label "열기"`로 화살표를 그립니다. 빈 화면, 오류, 로딩, 권한 없음 같은 상태 화면도 함께 그립니다. 화면 수를 정해 줬다면 그리지 않고 보고에서 제안만 합니다.
6. **점검, 렌더링, 전체 보기.** `canvas check` 결과는 문제 0개여야 합니다. 사용자에게 보여 주기 전에 에이전트가 `canvas render`(스크롤 아래 내용은 `--full-page`), `canvas overview`로 만든 PNG를 직접 확인합니다.
7. **서버 띄우고 주소 전달.** `canvas serve`(레지스트리 모드, 포트 4400)는 서버 하나로 모든 프로젝트를 보여 줍니다. 에이전트는 서버를 켜 둔 채 주소를 알려 줍니다.
8. **휴대폰으로 보기.** `canvas export`로 만든 정적 번들을 비공개 호스팅 페이지에 올리거나, 같은 네트워크에서 `canvas serve <design dir> --share`로 실시간으로 봅니다.
9. **이전 버전 보존.** 에이전트는 스스로 지우지 않습니다. 이전 화면은 `old drafts` 그룹으로 옮기고 `rejected`로 표시합니다. 사용자가 삭제를 요청하면 `canvas trash`로 아이디어나 보드를 `design/.trash/`로 옮기고, `canvas restore`로 되돌립니다.
10. **승인이 곧 기록.** 사용자가 화면을 승인하면 에이전트가 `canvas status ... approved --note "..."`를 실행합니다. 단순한 칭찬은 승인이 아닙니다.
11. **첫 초안 회고.** 첫 초안이 끝나면 에이전트가 디자인이 아니라 작업 과정을 돌아보고, 스킬 개선안을 최대 3개 제안합니다. 사용자가 승인하기 전에는 스킬을 고치지 않습니다.

### 리뷰 (mockup-review)

1. **맥락 읽기:** 화면의 근거가 된 기획서, `tokens.css`, `canvas.json`, 이전 `review.md`가 있으면 그것까지 읽습니다.
2. **기계 점검:** `canvas check`와 `canvas overview`. `check`가 찾은 문제는 모두 지적 사항이 됩니다.
3. **보드별, 흐름 점검:** 현재 보드를 하나씩 렌더링하고(`--full-page`도), HTML을 읽고, 체크리스트를 따라 봅니다. 시작 화면부터 링크를 따라가며 막다른 화면과 닿지 않는 보드를 찾습니다.
4. **보드에 코멘트:** 지적 사항 하나에 `canvas comment` 하나, 앞에 `[must]`, `[should]`, `[could]`를 붙입니다.
5. **보고:** `design/<idea>/review.md`를 쓰고 보드마다 승인, 수정, 반려를 권고합니다. 상태를 바꾸는 결정은 사용자에게 남깁니다.

리뷰어는 아트보드, 토큰, `canvas.json`을 고치지 않습니다. 화면을 그린 에이전트나 세션이 아닌 다른 쪽에서 돌릴 때 가장 잘 동작합니다.

### 구현 (mockup-to-code)

1. **범위:** `canvas impl <idea dir>`로 승인된 보드를 봅니다. 그 보드만 구현하고, 승인된 보드가 없으면 먼저 물어봅니다.
2. **프로젝트 파악:** 프레임워크, 라우팅, 스타일 방식, 기존 컴포넌트와 토큰, 데이터 계약, 테스트, 린트, 개발 서버 명령을 확인합니다.
3. **토큰은 한 번, 셸 먼저:** 보드 토큰을 앱의 토큰 체계 한 곳에 옮긴 뒤 공통 레이아웃, 헤더, 내비게이션을 만듭니다.
4. **화면 하나씩:** 승인된 보드 하나를 경로 하나에 구현합니다. 빈 상태, 로딩, 오류는 실제 상태로 만들고 실제 데이터에 연결합니다(임시 스텁은 표시하고 보고합니다).
5. **비교:** `canvas compare <idea dir> W01-Home.html --url http://localhost:5173/`가 `side.png`, `diff.png`, 불일치 비율이 담긴 `report.json`을 씁니다. 에이전트가 이미지를 직접 보고 고친 뒤, 남은 차이가 모두 의도한 것이고 이름을 붙일 수 있을 때까지 다시 비교합니다.
6. **기록과 점검:** `canvas impl <idea dir> W01-Home.html --route / --file src/pages/Home.tsx`로 기록하고, 프로젝트의 테스트, 린트, 타입 검사를 돌린 뒤 모든 화면을 한 번에 다듬습니다.

### 대화 예시

줄인 예시입니다. 요청이 캔버스 위 화면이 되고, 한 화면은 승인되고 다른 화면은 수정되며, 첫 초안은 스킬 개선 제안으로 끝납니다.

> **사용자:** 주말 등산객용 트레일 앱 목업 그려줘. 화면 4개.
>
> **에이전트:** `design/trailmate/`를 만들고 토큰부터 정했습니다. T01-Home, T02-TrailDetail, T03-Invite, T04-Plan을 그려 순서대로 연결했고 `check` 결과 문제 0개입니다. `http://localhost:4400/myapp/trailmate/`에서 보시면 됩니다. 화면 4개로 정해 주셔서 그리지는 않았지만, 홈의 빈 상태와 초대 화면의 오류 상태도 있으면 좋겠습니다.
>
> **사용자:** 홈은 좋아. 상세 화면 지도를 더 크게 해줘.
>
> **에이전트:** T01-Home을 "홈 피드 구성" 메모와 함께 승인 처리했습니다. 기존 T02는 "old drafts"로 옮겨 반려 표시했고, 지도를 가로 전체로 넓힌 T02-TrailDetail-v2를 추가했습니다. 캔버스는 이미 갱신됐습니다.
>
> 스킬 개선 제안: 1. 요청에 지도 크기가 없어 다시 그림, 한 번 더 왕복, 지도나 차트가 중심인 화면은 핵심 요소 크기를 먼저 물어보기.

## CLI 명령

먼저 스킬 위치에 맞춰 셸 함수를 정의합니다.

```bash
canvas() { python3 ~/.claude/skills/mockup-canvas/scripts/canvas.py "$@"; }
```

각 명령의 사용법은 `canvas <command> -h`로 볼 수 있습니다.

| 명령 | 하는 일 | 예시 |
| --- | --- | --- |
| `serve` | 캔버스 서버를 띄웁니다. 폴더를 주지 않으면 등록된 모든 프로젝트의 대시보드를 보여 주는 레지스트리 모드, 폴더를 주면 그 디자인 폴더만 보여 줍니다. `--port N`으로 포트를 고릅니다(기본 4400). `--share`는 토큰을 붙여 로컬 네트워크에 열고, `--minutes N`은 멈출 시간을 정합니다. 레지스트리 모드에서 `--share --project NAME`은 프로젝트 하나만 공유합니다. [서버 실행하기](#서버-실행하기)를 보세요. | `canvas serve`<br>`canvas serve design --share --minutes 30` |
| `roots list` | 등록된 디자인 폴더 목록을 봅니다. | `canvas roots list` |
| `roots add` | 디자인 폴더를 등록합니다. 이름을 지정할 수 있습니다. | `canvas roots add ~/work/app/design --name app` |
| `roots remove` | 이름으로 등록을 해제합니다. 파일은 건드리지 않습니다. | `canvas roots remove app` |
| `roots scan` | 지정한 폴더 아래에서 디자인 폴더를 찾아 등록합니다. | `canvas roots scan ~/work ~/projects` |
| `new` | 아이디어 폴더(`boards/`, `shared/tokens.css`, `canvas.json` 등)를 만들고 디자인 폴더를 등록합니다. | `canvas new design wallet` |
| `add` | 아트보드를 캔버스에 등록합니다. 필요하면 `boards/`로 복사합니다. 크기: `mobile` 390x844, `tablet` 768x1024, `desktop` 1440x900, 또는 `WxH`. 등록된 보드는 새 `--size`로 다시 실행하면 크기가 바뀝니다. | `canvas add design/wallet boards/W01-Home.html --group current --size mobile` |
| `group` | 아트보드를 그룹으로 옮깁니다. | `canvas group design/wallet W01-Home.html "old drafts"` |
| `link` | 두 아트보드 사이에 흐름 화살표를 추가합니다. | `canvas link design/wallet W01-Home.html W02-Send.html --label "송금"` |
| `status` | `draft`, `approved`, `rejected`를 지정하고 메모를 붙입니다. | `canvas status design/wallet W01-Home.html approved --note "레이아웃 확정"` |
| `artifact` | 아이디어의 호스팅 페이지 주소를 저장합니다. 주소 없이 실행하면 저장된 주소를 출력합니다. | `canvas artifact design/wallet https://example.com/page` |
| `render` | headless Chrome으로 아트보드를 등록된 크기 그대로 `render/`에 PNG로 저장합니다. 파일을 지정하지 않으면 전부 렌더링합니다. `--full-page`는 스크롤 높이 전체를 캡처하고, `--wait MS`(기본 1000)는 페이지 load 이벤트 뒤에 기다리는 시간입니다. | `canvas render design/wallet W01-Home.html --full-page` |
| `overview` | 화살표와 그룹을 포함한 캔버스 전체를 `render/_overview.png`로 저장합니다. | `canvas overview design/wallet` |
| `check` | 없는 파일, 깨진 참조, 미등록 아트보드, 겹침, 끊긴 링크, 금지 문자, 존재하지 않는 구현 파일을 찾아 알려 줍니다. 승인 수와 코멘트 수도 출력합니다. | `canvas check design/wallet` |
| `export` | 읽기 전용 정적 캔버스 번들을 만듭니다. `index.html`에 boards, shared, assets가 함께 들어갑니다. 출력 폴더는 아이디어 폴더 자신, 그 안쪽, 그 바깥 상위 폴더일 수 없고, 아이디어 폴더 밖을 가리키는 심볼릭 링크는 건너뜁니다. | `canvas export design/wallet ./wallet-export` |
| `snap` | 실행 중인 앱 페이지(http, https)를 headless Chrome으로 지정한 크기(기본 `mobile`) 그대로 캡처합니다. `--wait MS`(기본 3000)는 페이지 load 이벤트 뒤 실제로 기다리는 시간이고, `--full-page`는 스크롤 높이 전체를 캡처합니다. | `canvas snap http://localhost:5173/ --size mobile --out home.png` |
| `compare` | 보드를 등록된 크기로 렌더링하고, 앱을 같은 크기로 캡처(`--url`)하거나 PNG(`--png`)를 받아 `board.png`, `app.png`, `diff.png`(다른 픽셀은 마젠타), `side.png`(보드, 앱, diff를 나란히), `report.json`(`mismatch_percent` 포함)을 `<idea>/compare/<board id>/`나 `--out DIR`에 씁니다. `--threshold N`(0~255, 기본 24)은 색 채널이 이만큼 넘게 달라야 다른 픽셀로 세는 기준이고, `--ignore-top N`, `--ignore-bottom N`은 위아래 띠를 계산에서 빼며, `--align-top N`은 보드가 그린 가짜 상태 표시줄 아래로 앱을 N px 내려 놓습니다. `--wait MS`(기본 3000). | `canvas compare design/wallet W01-Home.html --url http://localhost:5173/ --align-top 47` |
| `impl` | 보드를 주면 그 보드를 구현한 경로와 소스 파일(프로젝트 루트 기준)을 기록하고, `--clear`로 기록을 지웁니다. 보드를 주지 않으면 승인된 보드와 구현 여부를 보여 주고, `--strict`는 구현 안 된 보드가 있으면 1로 종료합니다. | `canvas impl design/wallet W01-Home.html --route / --file src/pages/Home.tsx`<br>`canvas impl design/wallet --strict` |
| `comment` | 보드에 리뷰 코멘트를 추가하고(`--by NAME`으로 작성자 지정), 텍스트 없이 실행하면 목록을 보여 주고, `--clear`로 지웁니다. | `canvas comment design/wallet W02-Send.html "[must] 오류 상태 없음" --by reviewer` |
| `trash` | 아이디어나 그 안의 보드 하나를 `<design dir>/.trash/`로 옮깁니다. 보드는 canvas.json 항목(위치, 그룹, 상태, 코멘트)과 흐름 화살표를 복원용 파일에 함께 남깁니다. `--list`로 들어 있는 것을 봅니다. 완전히 지우지는 않으니, 비우려면 폴더를 직접 지웁니다. | `canvas trash design/wallet W02-Send.html`<br>`canvas trash --list design` |
| `restore` | `trash --list`에 나온 id로 되돌립니다. 같은 이름이 이미 있으면 되돌리지 않습니다. | `canvas restore design wallet/W02-Send-20261029T101034Z` |

## 캔버스 단축키

| 입력 | 동작 |
| --- | --- |
| 빈 곳 드래그 | 화면 이동 |
| 마우스 휠, 트랙패드 스크롤이나 핀치 | 포인터 위치 기준 확대, 축소 |
| 한 손가락 드래그, 두 손가락 핀치 (터치) | 이동, 확대, 축소 |
| `F` | 모든 아트보드가 보이게 맞춤 |
| `L` | 흐름 화살표 보이기, 숨기기 |
| 아트보드 제목 클릭 | ID 복사 (예: `W01-Home`) |
| 아트보드 제목 더블클릭 | 새 탭에서 그 아트보드만 열기 |
| 아트보드 제목 드래그 | 위치 이동 후 저장 |
| `Cmd+Z` / `Ctrl+Z` | 마지막 이동 취소 |
| `Cmd+Shift+Z` / `Ctrl+Shift+Z`, 또는 `Cmd+Y` / `Ctrl+Y` | 다시 실행 |
| 그룹 머리글 클릭 | 그룹 접기, 펴기 |
| 아트보드 제목에 마우스 올리기 | 메모 보기 |
| 코멘트 수 클릭 | 보드 코멘트 열기, `Esc`로 닫기 |
| 아트보드 제목의 `...`, 또는 제목 오른쪽 클릭 | 보드 메뉴: 새 탭에서 열기, 파일 이름 복사, 보드 삭제(`design/.trash/`로 옮겨지고, 알림의 Undo로 되돌림) |
| `.../<idea>/#<board>` 열기, 예: `#T01-Home` | 그 보드 하나를 화면에 맞추기 (대시보드의 보드 결과가 이 주소로 연결됨) |

정적 내보내기에서는 아트보드를 옮길 수 없습니다. 공유 모드에서는 서버를 `--share-edit`로 띄웠을 때만 이동이 저장됩니다.

## 폴더 구조

아이디어는 프로젝트 안에 둡니다. 프로젝트가 없으면 `~/design/`을 씁니다.

```text
<project>/design/<idea>/
  canvas.json         배치, 그룹, 흐름 화살표(links), 상태와 메모, 구현 기록, 코멘트, artifact_url
  boards/*.html       아트보드. 파일 하나가 화면 하나 (예: W01-Home.html)
  shared/tokens.css   색, 글꼴, 간격, 모서리 반경. 모든 아트보드가 링크함
  assets/             이미지, 폰트
  render/             점검용으로 생성한 PNG, 낮은 배율용 캔버스 썸네일은 render/.thumbs/
  compare/            보드별 비교 결과: board, app, diff, side PNG와 report.json
  review.md           mockup-review 보고서 (리뷰를 돌렸을 때)
```

`render/`와 `compare/`는 생성물이라 아이디어 폴더의 `.gitignore`로 git에서 제외합니다.

사용자 데이터는 `~/.mockup-canvas/`에 있습니다. `MOCKUP_CANVAS_HOME`으로 위치를 바꿀 수 있습니다.

```text
~/.mockup-canvas/
  roots.json    등록된 디자인 폴더 (레지스트리 모드에서 사용)
  config.json   옵션. 예: {"forbidden_chars": ["—"]}
  backup/       install.sh가 옮겨 둔 기존 파일
```

`forbidden_chars`는 아트보드에 들어 있으면 `canvas check`가 알려 주는 문자 목록입니다. 에이전트는 문서와 답변에서도 이 문자를 쓰지 않습니다. 기본값은 없음입니다.

## 보안 모델

mockup-canvas는 로컬에서 쓰는 도구이고, 그 범위를 벗어나지 않게 만들었습니다. 자세한 내용은 [SECURITY.md](SECURITY.md)를 보세요.

- **기본은 localhost 전용.** `canvas serve`는 `127.0.0.1`에만 바인딩합니다.
- **공유 모드는 직접 켤 때만.** `--share`는 로컬 네트워크에 열리고, 모든 요청에 무작위 토큰이 필요합니다. 첫 방문 뒤에는 토큰이 `HttpOnly; SameSite=Strict` 쿠키로 옮겨집니다. `--share-edit`를 주지 않으면 읽기 전용이고, 프로젝트 등록 변경은 항상 막히며, `--minutes`(1~240, 기본 30분)가 지나면 저절로 멈춥니다. 레지스트리 공유는 시작 시점에 등록된 프로젝트(`--project NAME`이면 그 하나)만 보여 주고, 폴더 경로와 관리 화면은 숨깁니다. 통신은 평문 HTTP이니 믿을 수 있는 네트워크에서만 쓰세요.
- **Host 검사.** 모든 요청의 `Host` 헤더가 이 서버(`127.0.0.1`, `localhost`, `[::1]`과 포트, 공유 모드에서는 LAN 주소도)여야 합니다. 다르면 `421`로 거절해 DNS 리바인딩을 막습니다.
- **경로 제한.** 등록된 디자인 폴더 안의 파일만 제공합니다. `../`, 인코딩된 상위 경로, 절대 경로, 바깥을 가리키는 심볼릭 링크는 거부합니다.
- **최소한의 쓰기.** 아이디어에 대한 쓰기는 `canvas.json`에 있는 아트보드의 `x`, `y` 변경 하나뿐이고, 원자적으로 저장하며 본문은 64 KiB로 제한합니다.
- **CSRF 검사.** 배치 저장과 프로젝트 추가, 제거에는 같은 출처의 `Origin`이나 `Referer` 헤더와 정확히 `application/json`인 Content-Type이 필요합니다.
- **아트보드 격리.** `boards/`, `assets/`, `shared/` 아래 모든 파일을 `Content-Security-Policy: sandbox`로 제공하고 아트보드를 sandbox iframe 안에서 보여 주므로, 아트보드 스크립트가 캔버스 API를 부를 수 없습니다. 로컬 글꼴의 CORS는 sandbox 아트보드에만 허용합니다. 공유 모드에서 아트보드의 리소스 링크는 그 아트보드가 속한 아이디어만 엽니다.
- **페이지 CSP.** 대시보드와 캔버스 페이지에는 엄격한 `Content-Security-Policy`가 붙습니다. 페이지 자신의 인라인 스크립트만 SHA-256 해시로 허용해 실행하고(`unsafe-eval` 없음), 요청과 iframe은 이 서버로만 향하며, 다른 사이트는 이 페이지를 iframe에 넣을 수 없습니다.
- **렌더 보호.** 아트보드 렌더와 썸네일은 아이디어 바깥의 로컬 파일을 읽거나 localhost, 사설 네트워크 주소에 접속할 수 없습니다. WebSocket을 포함한 모든 연결이 보호 프록시를 거치고, 프록시는 이름을 한 번만 조회해 확인한 주소로만 연결하므로 DNS 리바인딩으로 우회할 수 없습니다. headless Chrome은 DevTools 포트 없이 파이프로 제어하고, 캔버스 프로세스가 끝나면 함께 종료됩니다.
- **시간 제한.** 연결마다 15초 제한이 있고(실시간 갱신 스트림은 예외), 동시에 64개 연결까지만 받습니다.
- **외부 요청 없음.** 도구 자체는 인터넷에 접속하지 않습니다. 아트보드가 불러오는 Google Fonts가 스킬이 허용하는 유일한 외부 리소스입니다. `snap`과 `compare --url`은 사용자가 준 http, https 주소만 열고, localhost가 아니면 경고합니다.

취약점은 공개 이슈가 아니라 GitHub Security Advisories로 비공개 제보해 주세요.

## FAQ

### Claude Code가 코드를 쓰기 전에 UI 목업부터 그리게 하려면 어떻게 하나요?

`/plugin marketplace add chrisjo-dev/mockup-canvas`와 `/plugin install mockup-canvas@mockup-canvas`로 플러그인을 설치합니다. 그다음 "습관 기록 앱 목업 그려줘: 홈, 습관 추가, 주간 통계"처럼 평소 말로 요청하면 됩니다. 에이전트가 `design/<idea>/`를 만들고, 화면마다 HTML 아트보드를 그려 점검과 렌더링까지 마친 뒤 캔버스의 로컬 URL을 알려 줍니다. 그 캔버스에서 화면마다 승인하거나 반려하고, `mockup-to-code` 스킬은 승인한 화면만 구현합니다.

### AI가 만든 목업을 리뷰할 로컬 오픈소스 Figma 대안이 있나요?

mockup-canvas가 그중 하나입니다. MIT 라이선스이고, 캔버스 서버는 공유 모드를 켜지 않는 한 `127.0.0.1`에만 열리며, 도구 자체는 외부로 요청을 보내지 않습니다. 목업은 저장소 안의 HTML 파일이라 계정 없이 diff로 비교하고 PR에서 리뷰할 수 있습니다. 벡터 디자인 편집기는 아닙니다. HTML은 에이전트(또는 사용자)가 쓰고, 캔버스에서는 화면을 배치하고, 잇고, 리뷰하고, 코멘트를 달고, 승인합니다.

### AI가 만든 UI 코드가 승인한 목업과 같은지 어떻게 확인하나요?

`canvas compare <아이디어 폴더> <보드> --url <실행 중인 경로>`를 실행합니다. 보드를 렌더링하고 앱을 같은 크기로 캡처한 뒤 차이 이미지, 나란히 놓은 이미지, 불일치 비율이 담긴 `report.json`을 만듭니다. `mockup-to-code` 스킬은 승인된 모든 보드에 대해 이 비교를 하고, 차이를 고친 뒤 다시 비교합니다. `canvas impl <아이디어 폴더> --strict`는 구현 기록이 없는 승인된 보드가 있으면 오류로 끝납니다.

### 왜 Figma가 아니라 HTML인가요?

AI 에이전트는 HTML과 CSS를 잘 쓰고, 결과물은 저장소 안의 실제 파일로 남습니다. diff로 비교하고 PR에서 리뷰할 수 있고, 계정 없이 어떤 브라우저에서도 열립니다. 실제 개발을 시작할 때도 같은 마크업과 토큰에서 바로 이어 갈 수 있습니다.

### 목업을 코드로 만들 수 있나요?

네, `mockup-to-code` 스킬이 그 일을 합니다. 보드를 승인하면 에이전트가 앱의 프레임워크와 컴포넌트로 구현합니다. 값을 그대로 복사하지 않고 목업 토큰을 앱의 토큰 체계로 옮깁니다. 화면마다 실행 중인 경로에 `canvas compare`를 돌려 `side.png`와 `diff.png`를 보고, 고치고, 의도한 차이(샘플 문구 대신 실제 데이터, 폰트 렌더링, 플랫폼 기본 컨트롤)만 남을 때까지 다시 비교합니다. 보드마다 경로와 파일을 `canvas impl`로 기록하므로 캔버스에 `built` 배지가 붙고, `canvas impl <idea dir> --strict`로 아직 구현되지 않은 승인 보드를 알 수 있습니다. 최종 보고는 직접 확인한 것과 확인하지 못한 것을 나눠 적습니다.

### compare는 얼마나 정확한가요?

`compare`는 판단이 아니라 픽셀 비교입니다. 색 채널 중 하나라도 기준값(기본 255 중 24, `--threshold`로 지정)보다 크게 다르면 다른 픽셀로 세고, `mismatch_percent`는 비교한 행에서 다른 픽셀의 비율입니다. 대략 2% 미만은 보통 폰트 렌더링과 안티앨리어싱, 2%~10%는 간격, 줄 높이, 빠진 요소, 10% 초과는 레이아웃이 밀린 경우가 많습니다. 목업은 실제 앱에 없는 가짜 휴대폰 상태 표시줄이나 홈 인디케이터를 그리는 일이 많습니다. `--align-top N`으로 앱을 상태 표시줄 아래에 놓거나 `--ignore-top N`, `--ignore-bottom N`으로 그 띠를 빼세요. 비율은 참고값으로 보고 `side.png`와 `diff.png`를 꼭 직접 보세요. 스킬도 숫자만으로 화면이 일치한다고 말하지 않습니다.

### 인터넷이 필요한가요?

아니요. 서버, 캔버스, CLI 모두 오프라인에서 동작합니다. Google Fonts를 쓰는 아트보드만 폰트를 받을 때 연결이 필요합니다. 플러그인을 설치할 때는 GitHub에 접속할 수 있어야 합니다.

### Windows나 Linux에서도 되나요?

Linux에서는 동작할 것으로 보고, Windows는 테스트하지 않았습니다. 서버와 캔버스는 Python 표준 라이브러리만 씁니다. PNG 렌더링과 캡처(`render`, `overview`, `snap`, `compare`, 캔버스 썸네일)에는 Chrome, Chromium, Edge 중 하나가 필요하고, CLI는 다음 순서로 브라우저를 찾습니다.

1. `MOCKUP_CANVAS_CHROME` 환경 변수
2. `/Applications`에 있는 macOS용 Google Chrome, Chromium, Microsoft Edge 앱 경로
3. `PATH`의 `google-chrome`, `google-chrome-stable`, `chromium`, `chromium-browser`, `msedge`, `chrome`

다른 위치에 있다면 직접 지정하세요.

```bash
export MOCKUP_CANVAS_CHROME=/path/to/chrome
```

`install.sh`는 POSIX 셸(bash)이 필요하므로 Windows에서는 Claude Code 플러그인으로 설치하세요.

### mockup-canvas는 어떤 AI 에이전트를 지원하나요?

mockup-canvas는 Claude Code 플러그인으로, 그리고 Claude Code와 OpenAI Codex용 스킬로 제공됩니다(Codex에서는 `$mockup-canvas`, `$mockup-review`, `$mockup-to-code`로 부릅니다). 스킬은 `canvas.py` CLI를 실행할 뿐이라, 셸 명령을 실행할 수 있는 에이전트라면 같은 단계를 따를 수 있습니다.

### mockup-canvas는 Figma, v0, Claude Artifacts와 무엇이 다른가요?

mockup-canvas는 호스팅형 디자인 도구나 앱 생성기가 아닙니다. 기획, 리뷰, 구현을 다루고, 모든 것이 내 파일로 남습니다. 목업은 저장소 안의 로컬 HTML 파일이고, 캔버스는 `127.0.0.1`에서 열리며, 도구는 외부로 요청을 보내지 않습니다. 승인과 메모, 리뷰 코멘트, 구현 기록이 `canvas.json`에 남으므로 무엇을 승인하고 반려하고 만들었는지 이력이 남습니다. 만든 화면은 승인된 목업과 비교해 확인합니다. CLI를 실행할 수 있는 에이전트라면 무엇이든 함께 쓸 수 있습니다.

### AI 에이전트 없이도 쓸 수 있나요?

네. HTML 파일을 직접 쓰고 `canvas new`, `canvas add`, `canvas link`, `canvas serve` 같은 CLI를 쓰면 되고, 직접 구현한 화면도 `canvas compare`, `canvas impl`로 확인할 수 있습니다. 스킬은 이 명령들을 대신 실행해 줄 뿐입니다.

## 기여하기

이슈와 PR 모두 환영합니다. PR을 올리기 전에 테스트(260개)를 돌려 주세요.

```bash
cd tests && python3 -m unittest discover .
```

Chrome을 찾지 못하면 렌더링 테스트는 건너뜁니다. `python3 tests/perf_check.py`는 headless Chrome에서 캔버스의 프레임 시간, 긴 작업, 전체 맞춤 화면이 뜨기까지의 시간을 잽니다. 단위 테스트에는 들어가지 않습니다.

개발 환경, end-to-end 테스트, 성능 측정, 커밋 형식, 캔버스에 먼저 그려서 UI 변경을 제안하는 방법은 [CONTRIBUTING.md](CONTRIBUTING.md)에 있습니다. 릴리스별 변경 사항은 [CHANGELOG.md](CHANGELOG.md)에 있습니다.

## 라이선스

mockup-canvas는 [MIT 라이선스](LICENSE)로 배포됩니다. Copyright (c) 2026 chrisjo-dev.
