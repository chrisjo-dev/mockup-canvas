# mockup-canvas

**만들기 전에 화면부터 봅니다. AI 에이전트가 HTML 목업을 그리고 사용자는 로컬의 Figma 같은 캔버스에서 확인하는 Claude Code, Codex 스킬입니다.**

[English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Claude Code, Codex 지원](https://img.shields.io/badge/works%20with-Claude%20Code%20%7C%20Codex-6b4fbb.svg)](#빠른-시작-claude-code-플러그인-또는-codex-스킬-설치)
[![pip 의존성 없음: Python 표준 라이브러리, PNG 렌더링에만 Chrome](https://img.shields.io/badge/no%20pip%20deps-Python%20stdlib%20%2B%20Chrome-brightgreen.svg)](#faq)

**mockup-canvas란?** mockup-canvas는 chrisjo-dev가 만든 무료 오픈소스(MIT) Claude Code 플러그인이자 스킬로, OpenAI Codex에서도 쓸 수 있습니다. AI 에이전트가 화면 목업을 평범한 HTML 파일로 그리게 하고, 그 화면들을 로컬의 Figma 같은 캔버스에 펼쳐 이동, 확대, 배치, 흐름 화살표 연결, 승인을 할 수 있게 해 줍니다. Python 표준 라이브러리만으로 동작해 pip 의존성이 없고, Google Chrome(또는 Chromium, Edge)은 PNG를 렌더링할 때만 씁니다.

AI 어시스턴트용 요약은 [llms.txt](llms.txt)에 있습니다.

![데모: AI 에이전트가 모바일 앱 화면을 그리면 mockup-canvas 보드에 바로 나타나는 모습](docs/images/demo.gif)

![예제 아이디어 TrailMate 전체 보기: 캔버스 위 HTML 아트보드 6개가 흐름 화살표로 이어져 있고 2개는 승인 표시가 붙어 있음](docs/images/_overview.png)

## AI 에이전트로 목업부터 그리는 이유

mockup-canvas를 만든 이유는 UI를 글로 설명하면 모호하기 때문입니다. AI 에이전트와 제품을 기획할 때는 화면에 합의하기 전에 먼저 화면을 봐야 합니다. AI와 함께 서비스를 기획하고 만들면서, 필요한 것을 먼저 눈에 보이게 만들고 거기서부터 작업을 이어 가려고 만든 기획 도구입니다. "상단에 히어로 배너, 아래에 카드 목록이 있는 홈" 같은 문장은 직접 보기 전까지 나와 에이전트가 서로 다르게 이해합니다. mockup-canvas는 이 단계를 맨 앞으로 끌어옵니다. 에이전트가 화면마다 작은 HTML 파일을 그리면 캔버스가 그것들을 나란히 보여 주고, 사용자는 눈으로 보고 결정합니다. 이 화면은 승인하고, 저 화면은 반려하고, 다른 안을 요청하면 에이전트가 작업하는 동안 보드가 바로 갱신됩니다. 앱 코드는 화면이 승인된 다음에야 시작하고, 모든 목업은 계정 없이 어떤 브라우저에서도 열리는 독립 HTML 파일로 저장소에 남습니다.

## 주요 기능

**캔버스** (`viewer.html`, 로컬에서 제공)

- 디자인 툴처럼 드래그로 이동하고 확대, 축소합니다. 확대 배율이 바뀌어도 늘어난 비트맵이 아니라 선명하게 다시 그립니다.
- 아트보드를 드래그해 배치하면 위치가 `canvas.json`에 저장됩니다. 이동은 실행 취소, 다시 실행이 됩니다.
- 화면 사이 흐름 화살표에 그 화면으로 넘어가는 버튼이나 동작 이름을 붙일 수 있습니다.
- 승인, 반려 배지와 메모. 메모는 아트보드 제목에 마우스를 올리면 보입니다.
- 접고 펼 수 있는 그룹. 예: `current`, `old drafts`.
- 실시간 갱신. 아트보드나 `canvas.json`을 고치면 열려 있는 캔버스가 1초 안팎으로 바뀝니다.
- 여러 프로젝트 목록. 서버 하나로 등록된 모든 프로젝트와 아이디어를 봅니다.
- 휴대폰으로 보기. 같은 네트워크에서 실시간으로 보는 공유 모드와, 어디든 올릴 수 있는 정적 내보내기를 지원합니다.

**에이전트 스킬** (`skills/mockup-canvas/SKILL.md`)

- Claude Code나 Codex가 목업을 그리고, 등록하고, 연결하고, 점검하고, 보여 주는 순서를 단계별로 알려 줍니다.
- 이전 버전은 지우지 않고 남기며, 사용자의 승인을 기록으로 삼습니다.
- 첫 초안이 끝나면 짧은 회고로 스킬 자체의 개선안을 제안합니다.

**CLI** (`skills/mockup-canvas/scripts/canvas.py`)

- pip 의존성 없는 Python 3 파일 하나(표준 라이브러리만, Python 3.8 이상)이며 명령은 12개입니다: `serve`, `roots`, `new`, `add`, `group`, `render`, `check`, `overview`, `export`, `link`, `status`, `artifact`.
- Chrome(또는 Chromium, Edge)은 PNG를 렌더링할 때만 필요합니다.

## 빠른 시작: Claude Code 플러그인 또는 Codex 스킬 설치

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
./install.sh            # ~/.claude/skills와 ~/.codex/skills에 스킬을 링크
```

- 한쪽만 설치하려면 `./install.sh --claude` 또는 `./install.sh --codex`.
- `./install.sh --dry-run`은 아무것도 바꾸지 않고 할 일만 출력합니다.
- 대상 위치에 이미 다른 것이 있으면 먼저 `~/.mockup-canvas/backup/<timestamp>/`로 옮깁니다. 여러 번 실행해도 안전합니다.

Codex에서는 `$mockup-canvas`로 부릅니다. 예: `Use $mockup-canvas to draw the sign-up flow.`

### 에이전트 없이 예제 열어 보기

```bash
python3 skills/mockup-canvas/scripts/canvas.py serve examples
```

`http://127.0.0.1:4400/trailmate/`를 열면 [`examples/trailmate`](examples/trailmate)의 화면 6개짜리 예제를 볼 수 있습니다.

## mockup-canvas 동작 방식

에이전트는 `SKILL.md`의 작업 순서를 따릅니다.

1. **아이디어 찾기 또는 만들기.** `design/<idea>/`가 이미 있으면 이어서 작업합니다. 없으면 `canvas new <design dir> <idea>`를 실행하고, 이때 디자인 폴더가 캔버스 서버에 자동 등록됩니다.
2. **토큰 먼저.** 화면을 그리기 전에 색, 글꼴, 간격, 모서리 반경을 `shared/tokens.css`에 정합니다. 아트보드는 `var(--...)`만 씁니다.
3. **아트보드 그리기.** 화면 하나가 `boards/` 안의 HTML 파일 하나이고, 이름은 `W01-Home.html` 형식입니다. 파일만 단독으로 열어도 똑같이 보여야 합니다. 상대 경로만 쓰고, 외부 스크립트는 넣지 않으며, 외부 리소스는 Google Fonts만 허용합니다.
4. **등록.** `canvas add <idea dir> boards/W01-Home.html --group current --size mobile`로 캔버스에 올립니다.
5. **흐름 연결.** `canvas link <idea dir> W01-Home.html W02-Detail.html --label "열기"`로 화살표를 그립니다. 빈 화면, 오류, 로딩, 권한 없음 같은 상태 화면도 함께 그립니다. 화면 수를 정해 줬다면 그리지 않고 보고에서 제안만 합니다.
6. **점검, 렌더링, 전체 보기.** `canvas check` 결과는 문제 0개여야 합니다. 사용자에게 보여 주기 전에 에이전트가 `canvas render`, `canvas overview`로 만든 PNG를 직접 확인합니다.
7. **서버 띄우고 주소 전달.** `canvas serve`(레지스트리 모드, 포트 4400)는 서버 하나로 모든 프로젝트를 보여 줍니다. 에이전트는 서버를 켜 둔 채 주소를 알려 줍니다.
8. **휴대폰으로 보기.** `canvas export`로 만든 정적 번들을 비공개 호스팅 페이지에 올리거나, 같은 네트워크에서 `canvas serve <design dir> --share`로 실시간으로 봅니다.
9. **이전 버전 보존.** 아무것도 지우지 않습니다. 이전 화면은 `old drafts` 그룹으로 옮기고 `rejected`로 표시합니다.
10. **승인이 곧 기록.** 사용자가 화면을 승인하면 에이전트가 `canvas status ... approved --note "..."`를 실행합니다. 단순한 칭찬은 승인이 아닙니다.
11. **첫 초안 회고.** 첫 초안이 끝나면 에이전트가 디자인이 아니라 작업 과정을 돌아보고, 스킬 개선안을 최대 3개 제안합니다. 사용자가 승인하기 전에는 스킬을 고치지 않습니다.

단계별 명령, 규칙, 커스터마이즈 방법은 [docs/skill.ko.md](docs/skill.ko.md)에 정리했습니다.

### 대화 예시

요청이 캔버스 위 화면이 되고, 승인과 수정이 오가고, 첫 초안이 스킬 개선 제안으로 끝나는 과정을 줄여서 보여 주는 대화입니다.

> **사용자:** 주말 등산객용 트레일 앱 목업 그려줘. 화면 4개.
>
> **에이전트:** `design/trailmate/`를 만들고 토큰부터 정했습니다. T01-Home, T02-TrailDetail, T03-Invite, T04-Plan을 그려 순서대로 연결했고 `check` 결과 문제 0개입니다. http://localhost:4400/myapp/trailmate/ 에서 보시면 됩니다. 화면 4개로 정해 주셔서 그리지는 않았지만, 홈의 빈 상태와 초대 화면의 오류 상태도 있으면 좋겠습니다.
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
| `serve` | 캔버스 서버를 띄웁니다. 폴더를 주지 않으면 등록된 모든 프로젝트를 보여 주는 레지스트리 모드, 폴더를 주면 그 디자인 폴더만 보여 줍니다. `--share`는 토큰을 붙여 로컬 네트워크에 엽니다. 레지스트리 모드에서 `--share --project NAME`은 프로젝트 하나만 공유합니다. | `canvas serve`<br>`canvas serve design --share --minutes 30` |
| `roots list` | 등록된 디자인 폴더 목록을 봅니다. | `canvas roots list` |
| `roots add` | 디자인 폴더를 등록합니다. 이름을 지정할 수 있습니다. | `canvas roots add ~/work/app/design --name app` |
| `roots remove` | 이름으로 등록을 해제합니다. 파일은 건드리지 않습니다. | `canvas roots remove app` |
| `roots scan` | 지정한 폴더 아래에서 디자인 폴더를 찾아 등록합니다. | `canvas roots scan ~/work ~/projects` |
| `new` | 아이디어 폴더(`boards/`, `shared/tokens.css`, `canvas.json` 등)를 만들고 디자인 폴더를 등록합니다. | `canvas new design wallet` |
| `add` | 아트보드를 캔버스에 등록합니다. 필요하면 `boards/`로 복사합니다. 크기: `mobile` 390x844, `tablet` 768x1024, `desktop` 1440x900, 또는 `WxH`. | `canvas add design/wallet boards/W01-Home.html --group current --size mobile` |
| `group` | 아트보드를 그룹으로 옮깁니다. | `canvas group design/wallet W01-Home.html "old drafts"` |
| `link` | 두 아트보드 사이에 흐름 화살표를 추가합니다. | `canvas link design/wallet W01-Home.html W02-Send.html --label "송금"` |
| `status` | `draft`, `approved`, `rejected`를 지정하고 메모를 붙입니다. | `canvas status design/wallet W01-Home.html approved --note "레이아웃 확정"` |
| `artifact` | 아이디어의 호스팅 페이지 주소를 저장합니다. 주소 없이 실행하면 저장된 주소를 출력합니다. | `canvas artifact design/wallet https://example.com/page` |
| `render` | headless Chrome으로 아트보드를 `render/`에 PNG로 저장합니다. 파일을 지정하지 않으면 전부 렌더링합니다. | `canvas render design/wallet W01-Home.html` |
| `overview` | 화살표와 그룹을 포함한 캔버스 전체를 `render/_overview.png`로 저장합니다. | `canvas overview design/wallet` |
| `check` | 없는 파일, 깨진 참조, 미등록 아트보드, 겹침, 끊긴 링크, 금지 문자를 찾아 알려 줍니다. | `canvas check design/wallet` |
| `export` | 읽기 전용 정적 캔버스 번들을 만듭니다. `index.html`에 boards, shared, assets가 함께 들어갑니다. 출력 폴더는 아이디어 폴더 자신, 그 안쪽, 그 바깥 상위 폴더일 수 없고, 아이디어 폴더 밖을 가리키는 심볼릭 링크는 건너뜁니다. | `canvas export design/wallet ./wallet-export` |

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

정적 내보내기에서는 아트보드를 옮길 수 없습니다. 공유 모드에서는 서버를 `--share-edit`로 띄웠을 때만 이동이 저장됩니다.

## 폴더 구조

아이디어는 프로젝트 안에 둡니다. 프로젝트가 없으면 `~/design/`을 씁니다.

```text
<project>/design/<idea>/
  canvas.json         배치, 그룹, 흐름 화살표(links), 상태와 메모, artifact_url
  boards/*.html       아트보드. 파일 하나가 화면 하나 (예: W01-Home.html)
  shared/tokens.css   색, 글꼴, 간격, 모서리 반경. 모든 아트보드가 링크함
  assets/             이미지, 폰트
  render/             점검용으로 생성한 PNG (.gitignore로 git에서 제외)
```

사용자 데이터는 `~/.mockup-canvas/`에 있습니다. `MOCKUP_CANVAS_HOME`으로 위치를 바꿀 수 있습니다.

```text
~/.mockup-canvas/
  roots.json    등록된 디자인 폴더 (레지스트리 모드에서 사용)
  config.json   옵션. 예: {"forbidden_chars": ["—"]}
  backup/       install.sh가 옮겨 둔 기존 파일
```

`forbidden_chars`는 아트보드에 들어 있으면 `canvas check`가 알려 주는 문자 목록입니다. 에이전트는 문서와 답변에서도 이 문자를 쓰지 않습니다. 기본값은 없음입니다.

## 보안 모델

mockup-canvas는 로컬 도구이고, 그렇게 머물도록 만들었습니다. 자세한 내용은 [SECURITY.md](SECURITY.md)를 보세요.

- **기본은 localhost 전용.** `canvas serve`는 `127.0.0.1`에만 바인딩합니다.
- **공유 모드는 직접 켤 때만.** `--share`는 로컬 네트워크에 열리고, 모든 요청에 무작위 토큰이 필요합니다. 첫 방문 뒤에는 토큰이 `HttpOnly; SameSite=Strict` 쿠키로 옮겨집니다. `--share-edit`를 주지 않으면 읽기 전용이고, 프로젝트 등록 변경은 항상 막히며, `--minutes`(1~240, 기본 30분)가 지나면 저절로 멈춥니다. 레지스트리 공유는 시작 시점에 등록된 프로젝트(`--project NAME`이면 그 하나)만 보여 주고, 폴더 경로와 관리 화면은 숨깁니다. 통신은 평문 HTTP이니 믿을 수 있는 네트워크에서만 쓰세요.
- **Host 검사.** 모든 요청의 `Host` 헤더가 이 서버(`127.0.0.1`, `localhost`, `[::1]`과 포트, 공유 모드에서는 LAN 주소도)여야 합니다. 다르면 `421`로 거절해 DNS 리바인딩을 막습니다.
- **경로 제한.** 등록된 디자인 폴더 안의 파일만 제공합니다. `../`, 인코딩된 상위 경로, 절대 경로, 바깥을 가리키는 심볼릭 링크는 거부합니다.
- **최소한의 쓰기.** 아이디어에 대한 쓰기는 `canvas.json`에 있는 아트보드의 `x`, `y` 변경 하나뿐이고, 원자적으로 저장하며 본문은 64 KiB로 제한합니다.
- **CSRF 검사.** 배치 저장과 프로젝트 추가, 제거에는 같은 출처의 `Origin`이나 `Referer` 헤더와 정확히 `application/json`인 Content-Type이 필요합니다.
- **아트보드 격리.** 아트보드(그리고 `assets/`, `shared/` 아래 HTML, SVG)는 `Content-Security-Policy: sandbox`로 제공하고 sandbox iframe 안에서 보여 주므로, 아트보드 스크립트가 캔버스 API를 부를 수 없습니다.
- **시간 제한.** 연결마다 15초 제한이 있고(실시간 갱신 스트림은 예외), 동시에 64개 연결까지만 받습니다.
- **외부 요청 없음.** 도구 자체는 인터넷에 접속하지 않습니다. 아트보드가 불러오는 Google Fonts가 스킬이 허용하는 유일한 외부 리소스입니다.

취약점은 공개 이슈가 아니라 GitHub Security Advisories로 비공개 제보해 주세요.

## FAQ

### 왜 Figma가 아니라 HTML인가요?

mockup-canvas가 Figma 대신 HTML을 쓰는 이유는 AI 에이전트가 HTML과 CSS를 능숙하게 다루고, 결과물이 저장소 안의 실제 파일로 남습니다. diff로 비교하고 PR에서 리뷰할 수 있으며, 계정 없이 어떤 브라우저에서도 열립니다. 실제 개발을 시작할 때도 같은 마크업과 토큰에서 바로 이어 갈 수 있습니다.

### 인터넷이 필요한가요?

아니요. 서버, 캔버스, CLI 모두 오프라인에서 동작합니다. Google Fonts를 쓰는 아트보드만 폰트를 받을 때 연결이 필요합니다. 플러그인을 설치할 때는 GitHub에 접속할 수 있어야 합니다.

### Windows나 Linux에서도 되나요?

Linux에서는 동작할 것으로 보고, Windows는 테스트하지 않았습니다. 서버와 캔버스는 Python 표준 라이브러리만 씁니다. PNG 렌더링(`render`, `overview`)에는 Chrome, Chromium, Edge 중 하나가 필요하고, CLI는 다음 순서로 브라우저를 찾습니다.

1. `MOCKUP_CANVAS_CHROME` 환경 변수
2. `/Applications`에 있는 macOS용 Google Chrome, Chromium, Microsoft Edge 앱 경로
3. `PATH`의 `google-chrome`, `google-chrome-stable`, `chromium`, `chromium-browser`, `msedge`, `chrome`

다른 위치에 있다면 직접 지정하세요.

```bash
export MOCKUP_CANVAS_CHROME=/path/to/chrome
```

`install.sh`는 POSIX 셸(bash)이 필요하므로 Windows에서는 Claude Code 플러그인으로 설치하세요.

### mockup-canvas는 어떤 AI 에이전트를 지원하나요?

mockup-canvas는 Claude Code 플러그인으로, 그리고 Claude Code와 OpenAI Codex용 스킬로 제공됩니다(Codex에서는 `$mockup-canvas`로 부릅니다). 스킬은 `canvas.py` CLI를 실행할 뿐이라, 셸 명령을 실행할 수 있는 에이전트라면 같은 단계를 따를 수 있습니다.

### mockup-canvas는 Figma, v0, Claude Artifacts와 무엇이 다른가요?

mockup-canvas는 호스팅형 디자인 도구나 앱 생성기가 아니라 앱 코드 이전의 기획 단계를 위한 도구입니다. 모든 목업은 저장소 안의 로컬 HTML 파일이고, 캔버스는 `127.0.0.1`에서 열리며, 도구는 외부로 요청을 보내지 않습니다. CLI를 실행할 수 있는 에이전트라면 무엇이든 함께 쓸 수 있고, 승인과 메모가 `canvas.json`에 기록되어 무엇을 승인하고 반려했는지 이력이 남습니다.

### AI 에이전트 없이도 쓸 수 있나요?

네. HTML 파일을 직접 쓰고 `canvas new`, `canvas add`, `canvas link`, `canvas serve` 같은 CLI를 쓰면 됩니다. 스킬은 이 명령들을 대신 실행해 줄 뿐입니다.

## 기여하기

이슈와 PR 모두 환영합니다. PR을 올리기 전에 테스트(92개)를 돌려 주세요.

```bash
python3 -m unittest discover tests
```

Chrome을 찾지 못하면 렌더링 테스트는 건너뜁니다.

## 라이선스

mockup-canvas는 [MIT 라이선스](LICENSE)로 배포됩니다. Copyright (c) 2026 chrisjo-dev.
