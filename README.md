# IssuePilot

GitHub 저장소에 이슈가 올라오면 LLM이 유형·영역·우선순위를 분류하고, 중복 이슈를 찾고, 담당자를 추천하고, 빠진 정보를 요청해 결과를 라벨과 코멘트로 남기는 에이전트.

## 내 저장소에 설치하기

서버나 코드 복사 없이 워크플로 파일 하나로 설치합니다.

1. [console.anthropic.com](https://console.anthropic.com)에서 API 키를 발급받아 저장소 **Settings → Secrets and variables → Actions**에 `ANTHROPIC_API_KEY`라는 이름으로 등록합니다.
2. [examples/issue-pilot.yml](examples/issue-pilot.yml)을 내 저장소의 `.github/workflows/issue-pilot.yml`로 복사합니다. 핵심은 이 부분입니다.

   ```yaml
   - uses: Izac626/issuepilot@v1
     with:
       anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
   ```
3. 이슈를 올리면 1분 안에 라벨과 분석 코멘트가 달립니다.

알아 둘 점
- **라벨**: 저장소에 이미 있는 라벨만 붙입니다. 유형은 `bug`, `feature`, `question`, `docs`, 우선순위는 `P0`, `P1`, `P2`라는 이름의 라벨이 있으면 쓰고, 없으면 코멘트에만 적습니다. 그 밖의 라벨은 영역 라벨 후보로 봅니다.
- **비용**: 이슈 1건에 약 2센트(Claude Opus 5.5 기준)이며 설치한 사람의 API 키로 청구됩니다. `model` 입력으로 더 저렴한 모델을 고를 수 있습니다.
- **전송되는 정보**: Anthropic API에는 이슈 제목·본문, 라벨 이름, 폴더 이름만 보냅니다. 소스 코드는 보내지 않습니다. 중복 검색용 임베딩은 러너 안에서 계산합니다.
- **하지 않는 것**: 담당자 지정, 이슈 닫기. 추천과 표시만 합니다.
- 공개 저장소에서는 누구나 이슈를 올려 비용을 발생시킬 수 있습니다. [보안 설계](docs/06_보안.md)의 남은 위험을 참고하세요.

| 입력 | 기본값 | 설명 |
|---|---|---|
| `anthropic-api-key` | (필수) | Anthropic API 키 |
| `issue-number` | 이벤트의 이슈 | 다시 분석할 때 지정 |
| `model` | `claude-opus-5-5` | Claude 모델 ID |
| `effort` | `low` | `low` / `medium` / `high` |
| `github-token` | `github.token` | `issues: write` 권한 필요 |

## 개발 환경

```bash
make setup                 # 가상환경과 의존성
cp .env.example .env       # ANTHROPIC_API_KEY 입력
make test                  # 단위 테스트 (API 호출 없음)
make dry ISSUE=5           # 테스트 저장소 이슈를 게시 없이 분석
make eval                  # 평가셋 측정 (비용 발생)
```

## 구조

헥사고날(포트와 어댑터). 자세한 내용은 [docs/02_아키텍처_인터페이스.md](docs/02_아키텍처_인터페이스.md).

```
issuepilot/
  domain/        모델, 정규화 규칙, 담당자 순위 규칙, 코멘트 생성, 텍스트 정화 (외부 의존 없음)
  application/   포트 정의, TriageIssue 유스케이스, 유사 이슈 검색, 담당자 추천
  adapters/      inbound(cli) / outbound(GitHub, Claude, 로컬 임베딩, 로그)
  bootstrap.py   조립 지점
```

## 문서

| # | 문서 | 내용 |
|---|---|---|
| 1 | [요구사항 명세](docs/01_요구사항명세.md) | 기능, 비기능, 범위 밖 |
| 2 | [아키텍처](docs/02_아키텍처_인터페이스.md) | 계층, 포트, 의존 규칙 |
| 3 | [평가 계획](docs/03_평가계획.md) | 평가셋, 지표, 목표 |
| 4 | [개발 일정](docs/04_스프린트계획.md) | 일정, 완료 정의, 일일 기록 |
| 5 | [리스크](docs/05_리스크.md) | 리스크와 대응 |
| 6 | [보안 설계](docs/06_보안.md) | 위협 모델과 대응 |
| | [실험 로그](docs/experiment_log.md) | 변경마다 측정한 지표 |

## 개발 규칙

1. 변경은 하나씩, 매번 `make test`와 `make eval`
2. 결과는 `docs/experiment_log.md`에 기록
3. 계층 의존 규칙은 `tests/test_architecture.py`가 강제
