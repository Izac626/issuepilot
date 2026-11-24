# eval_set.csv 컬럼 설명

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | int | 고유 번호. 테스트 저장소 이슈 번호와 일치시킬 것 |
| split | train / test | 개발용 / 검증용 |
| source | manual / fastapi / streamlit | 출처 |
| title | str | 이슈 제목 |
| body | str | 이슈 본문 (줄바꿈은 `\n`) |
| gold_type | bug / feature / question / docs | 정답 유형 |
| gold_labels | str | 정답 영역 라벨, `;`로 구분. 없으면 빈칸 |
| gold_priority | P0 / P1 / P2 | 정답 우선순위 |
| gold_duplicate_of | int | 중복인 경우 원본 이슈 id. 아니면 빈칸 |
| gold_missing_info | str | bug일 때 누락 항목, `;`로 구분 (repro_steps, environment, expected_behavior, actual_behavior) |
| gold_affected_path | str | 영향 영역 폴더. 모호하면 빈칸 |
| gold_assignee | str | 기대 담당자 로그인 (manual만). 테스트 저장소 커밋 이력과 맞출 것 |
| note | str | 설계 의도 메모 (평가에 사용 안 함) |

## 테스트 저장소 전제

- 폴더: `src/auth`, `src/api`, `src/db`, `web`, `docs`, `infra`
- 라벨: bug, feature, question, docs, backend, frontend, auth, db, infra, P0, P1, P2
- 가상 기여자: `kim-dev`(src/auth, src/api 주로), `lee-fe`(web), `park-ops`(infra, src/db)
  → 커밋 author를 바꿔 넣어 이력을 만든다 (`git commit --author="kim-dev <kim@example.com>"`)
